"""Durable, bounded acquisition jobs. Search is web-index discovery, not comment scraping."""
from __future__ import annotations
import hashlib
import json
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import growth_ai

from flask import g, jsonify, request, Response
from growth_ai import AIError, AIService, redacted, DESTINATIONS, CST

VERSION = 'growth-workflow-1.2.0'


class Automation:
    def __init__(self,store,catalog,helpers):
        self.store=store;self.catalog=catalog;self.h=helpers;self.ai=AIService(store)
        self.wakeup=threading.Event();self.stopping=threading.Event();self.thread=None
        self.process_lock=threading.Lock()
        with store.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS growth_jobs(
                id TEXT PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL,result TEXT NOT NULL DEFAULT '{}',error TEXT NOT NULL DEFAULT '',
                actor TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,cancelled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS growth_candidates(
                id TEXT PRIMARY KEY,url TEXT NOT NULL UNIQUE,platform TEXT NOT NULL,title TEXT NOT NULL,
                excerpt TEXT NOT NULL,date_hint TEXT NOT NULL DEFAULT '',query TEXT NOT NULL,
                ai_result TEXT,status TEXT NOT NULL DEFAULT 'needs_review',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS growth_plans(
                id TEXT PRIMARY KEY,subject_type TEXT NOT NULL,subject_id TEXT NOT NULL,body TEXT NOT NULL,
                next_action TEXT NOT NULL,due_at TEXT,provider TEXT NOT NULL,created_at TEXT NOT NULL,
                UNIQUE(subject_type,subject_id));
                CREATE TABLE IF NOT EXISTS growth_content(
                id TEXT PRIMARY KEY,platform TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,
                shot_list TEXT NOT NULL,destination TEXT NOT NULL,created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft');
                CREATE TABLE IF NOT EXISTS growth_chat_sessions(
                id TEXT PRIMARY KEY,campaign TEXT NOT NULL,history TEXT NOT NULL DEFAULT '[]',
                hour TEXT NOT NULL,calls INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS growth_checkpoints(
                kind TEXT NOT NULL,subject_id TEXT NOT NULL,fingerprint TEXT NOT NULL,updated_at TEXT NOT NULL,
                PRIMARY KEY(kind,subject_id));
                CREATE TABLE IF NOT EXISTS growth_search_runs(
                day TEXT NOT NULL,platform TEXT NOT NULL,intent TEXT NOT NULL,state TEXT NOT NULL,
                updated_at TEXT NOT NULL,PRIMARY KEY(day,platform,intent));
                CREATE TABLE IF NOT EXISTS growth_plan_actions(
                plan_id TEXT PRIMARY KEY,status TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS growth_publications(
                content_id TEXT PRIMARY KEY,url TEXT NOT NULL,actor TEXT NOT NULL,recorded_at TEXT NOT NULL);''')
        (store.root/'inbox').mkdir(exist_ok=True)

    def now(self):return datetime.now(timezone.utc).isoformat(timespec='seconds')

    def fingerprint(self,source):
        # Counters/timestamps change while a job runs; only relevant facts invalidate work.
        fields=('excerpt','city_evidence','posted_at','platform','confirmed','stage','contact_count','last_contact_at',
                'interest','district','availability','campaign_id')
        events=[{k:e.get(k) for k in ('id','title','starts_at','venue','payment_mode')}
                for e in self.catalog.current()['events']]
        # Overlay preflight loads this module from the installer, while AIService
        # and the unchanged playbook stay in the installed runtime directory.
        book=hashlib.sha256(Path(growth_ai.__file__).with_name('growth_playbook.json').read_bytes()).hexdigest()
        data=[VERSION,book,{k:source.get(k) for k in fields},events]
        return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def unchanged(self,kind,subject,source):
        with self.store.db() as c:
            row=c.execute('SELECT fingerprint FROM growth_checkpoints WHERE kind=? AND subject_id=?',(kind,subject)).fetchone()
        return bool(row and row[0]==self.fingerprint(source))

    def checkpoint(self,c,kind,subject,source):
        c.execute('INSERT INTO growth_checkpoints VALUES(?,?,?,?) ON CONFLICT(kind,subject_id) DO UPDATE SET fingerprint=excluded.fingerprint,updated_at=excluded.updated_at',
                  (kind,subject,self.fingerprint(source),self.now()))

    def create(self,kind,actor):
        if kind not in ('discover','respond','followup','all'):raise ValueError('不支持的执行任务')
        with self.store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            active=c.execute("SELECT * FROM growth_jobs WHERE status IN ('queued','running') ORDER BY created_at LIMIT 1").fetchone()
            if active:return dict(active),False
            ident=secrets.token_hex(10)
            c.execute('INSERT INTO growth_jobs(id,kind,status,message,actor,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                      (ident,kind,'queued','任务已排队，等待执行',actor,self.now(),self.now()))
            row=dict(c.execute('SELECT * FROM growth_jobs WHERE id=?',(ident,)).fetchone())
        self.wakeup.set();return row,True

    def job(self,ident):
        with self.store.db() as c:row=c.execute('SELECT * FROM growth_jobs WHERE id=?',(ident,)).fetchone()
        if not row:raise LookupError('任务不存在')
        value=dict(row);value['result']=json.loads(value['result']);return value

    def progress(self,ident,message,percent):
        with self.store.db() as c:
            row=c.execute('SELECT cancelled FROM growth_jobs WHERE id=?',(ident,)).fetchone()
            if row and row[0]:raise AIError('任务已取消；已完成的搜索或 API 调用不会撤销。','cancelled')
            c.execute('UPDATE growth_jobs SET message=?,progress=?,updated_at=? WHERE id=?',(message,percent,self.now(),ident))

    def sources(self):
        with self.store.db() as c:
            candidates=c.execute("SELECT COUNT(*) FROM growth_candidates WHERE status='needs_review'").fetchone()[0]
            leads=c.execute("SELECT COUNT(*) FROM leads WHERE stage NOT IN ('closed','blocked','archived','booked')").fetchone()[0]
            inquiries=c.execute("SELECT COUNT(*) FROM inquiries WHERE stage='new'").fetchone()[0]
        return {'web_candidates':candidates,'existing_leads':leads,'opt_in_inquiries':inquiries,
                'owned_export_files':len(list((self.store.root/'inbox').glob('*.json'))),
                'platform_comment_api_connected':False,'platform_send_connected':False,
                'web_search_connected':self.ai.config()['enabled'] and self.ai.config()['search_enabled']}

    def import_owned_files(self,actor):
        imported=0;errors=[]
        for path in sorted((self.store.root/'inbox').glob('*.json'))[:10]:
            if path.is_symlink() or path.stat().st_size>128000:continue
            try:
                d=json.loads(path.read_text('utf-8-sig'))
                if not isinstance(d,dict) or d.get('own_account_export') is not True:
                    errors.append(path.name+'：缺少自己账号导出确认');continue
                rows=d.get('rows')
                if not isinstance(rows,list) or len(rows)>50:raise ValueError('每个文件最多50条')
                for row in rows:
                    if not isinstance(row,dict):raise ValueError('咨询行格式错误')
                    self.h['validate_source'](row.get('platform'),row.get('source_url'))
                    if len(str(row.get('excerpt','')).strip())<6:raise ValueError('缺少需求原文')
                    self.h['classify'](row['excerpt'],row.get('city_evidence',''),row.get('posted_at'))
                for row in rows:
                    _,added=self.store.add({**row,'relation':'inbound'},actor)
                    imported+=int(added)
            except (ValueError,OSError,TypeError):errors.append(path.name+'：格式或原文无效，未继续导入该文件')
        return imported,errors

    def discover(self,ident,actor):
        self.progress(ident,'正在同步比赛与整理自己账号的咨询导出…',8)
        cat=self.catalog.sync();imported,errors=self.import_owned_files(actor)
        cfg=self.ai.config()
        result={'catalog_events':len(cat['events']),'catalog_error':cat.get('error',''),
                'owned_inquiries_imported':imported,'import_errors':errors,'queries_completed':0,
                'new_web_candidates':0,'candidate_ids':[], 'platform_comment_api_connected':False,
                'note':'搜索范围是公开网页索引，无法覆盖所有站内视频及评论；结果须核对原文，不等于客户。'}
        if not cfg['enabled'] or not cfg['search_enabled']:
            result['blocked_reason']='请在 AI 设置中启用 DeepSeek 和公开网页搜索。'
            return result
        self.ai.require_ready(True)
        after=(datetime.now(CST).date()-timedelta(days=30)).isoformat()
        specs=[('douyin','site:douyin.com'),('kuaishou','site:kuaishou.com'),
               ('xiaohongshu','site:xiaohongshu.com'),('channels','site:weixin.qq.com')]
        day=datetime.now(CST).date().isoformat();result['searches_skipped']=0
        for i,(platform,site) in enumerate(specs):
            self.progress(ident,'正在搜索公开成都乒乓需求：'+self.h['platforms'][platform]['name'],12+i*10)
            with self.store.db() as c:
                done={r['intent']:r for r in c.execute('SELECT * FROM growth_search_runs WHERE day=? AND platform=?',(day,platform))}
            intent=next((x for x in ('training','competition') if x not in done or
                         (done[x]['state'] in ('failed','running') and (datetime.now(timezone.utc)-datetime.fromisoformat(done[x]['updated_at'])).total_seconds()>=1800)),None)
            if not intent:result['searches_skipped']+=1;continue
            terms='(想学 OR 找教练 OR 求推荐)' if intent=='training' else '(比赛报名 OR 积分赛 OR 哪里有比赛)'
            query=f'成都 乒乓球 {terms} {site} after:{after}'
            with self.store.db() as c:
                c.execute('INSERT INTO growth_search_runs VALUES(?,?,?,?,?) ON CONFLICT(day,platform,intent) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at',
                          (day,platform,intent,'running',self.now()))
            try:items=self.ai.search(query)
            except AIError as error:
                with self.store.db() as c:c.execute("UPDATE growth_search_runs SET state='failed',updated_at=? WHERE day=? AND platform=? AND intent=?",(self.now(),day,platform,intent))
                result['error_code']=error.code
                if error.code=='daily_limit':result['note']='今日搜索额度已用完，咨询处理与内容准备继续在各自额度内运行。'
                else:result['blocked_reason']=str(error)
                break
            with self.store.db() as c:c.execute("UPDATE growth_search_runs SET state='completed',updated_at=? WHERE day=? AND platform=? AND intent=?",(self.now(),day,platform,intent))
            result['queries_completed']+=1
            for item in items:
                try:url=self.h['validate_source'](platform,item.get('url'))
                except ValueError:continue
                snippet=redacted(str(item.get('snippet') or item.get('summary') or ''))[:500]
                title=redacted(str(item.get('title') or '公开网页'))[:160]
                cid=hashlib.sha256(url.encode()).hexdigest()[:24]
                with self.store.db() as c:
                    exists=c.execute('SELECT id FROM growth_candidates WHERE url=?',(url,)).fetchone()
                    if not exists:
                        c.execute('INSERT INTO growth_candidates(id,url,platform,title,excerpt,date_hint,query,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                  (cid,url,platform,title,snippet,str(item.get('date') or '')[:80],query,self.now(),self.now()))
                        result['new_web_candidates']+=1
                    result['candidate_ids'].append(cid)
        # A small, cost-bounded first screening. No author identity or contact extraction.
        screened=0
        with self.store.db() as c:
            pending_ids=[r[0] for r in c.execute("SELECT id FROM growth_candidates WHERE status='needs_review' AND ai_result IS NULL ORDER BY created_at,id LIMIT 4")]
        for cid in pending_ids:
            self.progress(ident,'AI 正在初筛搜索摘要，保留需要核实的原文…',55+screened*3)
            with self.store.db() as c:row=dict(c.execute('SELECT * FROM growth_candidates WHERE id=?',(cid,)).fetchone())
            if row['ai_result'] or row['status']!='needs_review':continue
            source={'excerpt':row['title']+'\n'+row['excerpt'],'platform':row['platform'],'posted_at':''}
            try:
                analysis=self.ai.analyze(source,cat['events'],'screen_search_snippet')
                with self.store.db() as c:
                    c.execute('UPDATE growth_candidates SET ai_result=?,updated_at=? WHERE id=?',
                              (json.dumps(analysis,ensure_ascii=False),self.now(),cid))
                screened+=1
            except AIError as e:result['analysis_note']=str(e);break
        result['ai_screened']=screened
        return result

    def analyze_lead(self,lead,task='reply'):
        if lead['stopped'] or lead['stage'] in ('blocked','closed','archived','booked'):
            raise AIError('这条需求已停止跟进，不再调用 AI。','stopped')
        analysis=self.ai.analyze(lead,self.catalog.current()['events'],task)
        with self.store.db() as c:
            # Recheck after the external call so a concurrent stop is respected.
            live=c.execute('SELECT * FROM leads WHERE id=?',(lead['id'],)).fetchone()
            if not live or live['stopped'] or live['stage'] in ('blocked','closed','archived','booked'):
                raise AIError('需求在分析期间停止跟进，结果未采用。','stopped')
            c.execute('INSERT INTO ai_results(lead_id,result,provider,model,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(lead_id) DO UPDATE SET result=excluded.result,provider=excluded.provider,model=excluded.model,updated_at=excluded.updated_at',
                      (lead['id'],json.dumps(analysis,ensure_ascii=False),analysis['provider'],analysis['model'],self.now()))
            if not self.store.contact_guard(self.store.view(live)) and analysis['reply']:
                c.execute('UPDATE leads SET latest_reply=?,reply_version=reply_version+1,updated_at=? WHERE id=?',
                          (analysis['reply'],self.now(),lead['id']))
            self.store.audit(c,lead['id'],'ai_analysis','AI 完成需求分析和回复准备；未发送', 'AI 任务')
            self.checkpoint(c,'reply',lead['id'],lead)
        return analysis

    def respond(self,ident,actor):
        self.ai.require_ready()
        if not self.catalog.current()['events']:self.catalog.sync()
        with self.store.db() as c:
            rows=[self.store.view(r) for r in c.execute("SELECT * FROM leads WHERE stopped=0 AND stage IN ('new','qualified','replied') ORDER BY CASE stage WHEN 'replied' THEN 0 ELSE 1 END,created_at DESC")]
        result={'analyzed':0,'drafts_prepared':0,'needs_source_review':0,'errors':[], 'sent':0,
                'unchanged_skipped':0,
                'note':'AI 分析不会把待核实网页或未知时间自动确认为有效客户，也不等同发送消息。'}
        pending=[]
        for lead in rows:
            if self.unchanged('reply',lead['id'],lead):result['unchanged_skipped']+=1
            else:pending.append(lead)
        for i,lead in enumerate(pending[:10]):
            self.progress(ident,f'AI 正在准备第 {i+1}/{len(rows)} 条需求…',15+int(i/max(1,len(rows))*65))
            try:
                self.analyze_lead(lead)
                result['analyzed']+=1
                if not self.store.contact_guard(self.store.get(lead['id'])):result['drafts_prepared']+=1
                else:result['needs_source_review']+=1
            except AIError as error:
                result['errors'].append(str(error))
                if error.code in ('daily_limit','background_daily_limit','not_configured','invalid_key','balance','forbidden'):break
        if not rows:result['note']='当前没有已录入的有效咨询。请先搜索并核实原文，或导入自己账号收到的咨询。'
        return result

    def followup(self,ident,actor):
        self.ai.require_ready()
        with self.store.db() as c:
            leads=[self.store.view(r) for r in c.execute("SELECT * FROM leads WHERE stopped=0 AND stage IN ('qualified','replied','invited') ORDER BY updated_at DESC")]
            inquiries=[dict(r) for r in c.execute("SELECT * FROM inquiries WHERE stage='new' ORDER BY created_at")]
        subjects=[('inquiry',r) for r in inquiries]+[('lead',r) for r in leads]
        result={'plans_prepared':0,'waiting_for_reply':0,'errors':[], 'sent':0,'registrations_confirmed':0,
                'unchanged_skipped':0,
                'note':'邀请与内容已保存；发布或联系由经营者在对应平台执行，实际报名凭据另行登记。'}
        attempted=0
        for i,(kind,row) in enumerate(subjects):
            if attempted>=10:break
            if self.unchanged('followup-'+kind,row['id'],row):result['unchanged_skipped']+=1;continue
            self.progress(ident,'正在整理邀请和跟进计划…',15+int(i/max(1,len(subjects[:10]))*65))
            if kind=='lead':
                if row['contact_count'] and row['stage']!='replied':result['waiting_for_reply']+=1;continue
                source=row
            else:
                source={'excerpt':'用户主动咨询乒乓球'+self.h['intents'][row['interest']]+'；方便时间：'+redacted(row['availability']),
                        'city_evidence':'用户在成都俱乐部咨询页提交的区域：'+redacted(row['district']),
                        'posted_at':row['created_at'],'platform':row['campaign_id'].split('-')[0]}
            try:
                attempted+=1
                analysis=self.ai.analyze(source,self.catalog.current()['events'],'invitation_and_followup')
                due=(datetime.now(timezone.utc)+timedelta(hours=max(1,analysis['followup_hours']))).isoformat()
                with self.store.db() as c:
                    if kind=='lead':
                        fresh=c.execute('SELECT stopped,stage FROM leads WHERE id=?',(row['id'],)).fetchone()
                        if not fresh or fresh['stopped'] or fresh['stage'] in ('blocked','closed','archived','booked'):continue
                    else:
                        fresh=c.execute('SELECT stage FROM inquiries WHERE id=?',(row['id'],)).fetchone()
                        if not fresh or fresh['stage']!='new':continue
                    c.execute('INSERT INTO growth_plans(id,subject_type,subject_id,body,next_action,due_at,provider,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(subject_type,subject_id) DO UPDATE SET body=excluded.body,next_action=excluded.next_action,due_at=excluded.due_at,provider=excluded.provider,created_at=excluded.created_at',
                              (secrets.token_hex(10),kind,row['id'],analysis['reply'],analysis['next_action'],due,analysis['provider'],self.now()))
                    self.checkpoint(c,'followup-'+kind,row['id'],row)
                    c.execute('DELETE FROM growth_plan_actions WHERE plan_id IN (SELECT id FROM growth_plans WHERE subject_type=? AND subject_id=?)',(kind,row['id']))
                result['plans_prepared']+=1
            except AIError as e:
                result['errors'].append(str(e))
                if e.code in ('daily_limit','background_daily_limit','balance','invalid_key','forbidden'):break
        result['channel_drafts']=self.channel_content(ident)
        return result

    def channel_content(self,ident):
        """Own-channel inbound marketing, never impersonated customer comments."""
        result={'prepared':0,'published':0,'errors':[]}
        for platform,dest in DESTINATIONS.items():
            self.progress(ident,'正在准备'+dest['platform']+'同平台小程序引流内容…',85)
            # One draft per channel per CST date; scheduled reruns don't rewrite it repeatedly.
            from growth_ai import CST
            cid=datetime.now(CST).date().isoformat()+'-'+platform
            with self.store.db() as c:exists=c.execute('SELECT id FROM growth_content WHERE id=?',(cid,)).fetchone()
            if exists:continue
            try:
                topics=['儿童零基础如何选择课程，说明三种已确认课费方案','按自己的积分选择适合的成都比赛',
                        '第一次参加乒乓球比赛的报名步骤','成人1600分以下指定比赛前三名自动发放训练课程的条件',
                        '工作日晚上和周末如何找到适合自己的比赛','儿童25次课与月卡怎样根据出勤频率选择',
                        '新手打球前的热身和基础练习，邀请查看训练安排']
                topic=topics[datetime.now(CST).date().toordinal()%len(topics)]
                formats={'douyin':'短视频口播：开头一句直接回答问题，正文简短，拍摄建议分成3个镜头。',
                         'kuaishou':'用球馆工作人员自然讲解的口吻，重点说清参与方式，不能用邀请返奖、分享获益引流。',
                         'xiaohongshu':'实用笔记：标题有明确问题，正文分行，给出选择方法和到店体验步骤。',
                         'channels':'微信视频号短视频：亲切回答家长和球友的问题，结尾提示微信银杏奖牌。'}
                source={'platform':platform,'excerpt':'为成都银杏乒乓球俱乐部自己的'+dest['platform']+'账号准备一条实用内容。主题：'+topic+'。'+formats[platform]+'只用已核实比赛和已确认课程方案，不提供虚构价格和优惠。'}
                analysis=self.ai.analyze(source,self.catalog.current()['events'],'channel_content')
                body=analysis['reply']+'\n\n'+dest['guide']
                with self.store.db() as c:
                    c.execute('INSERT OR IGNORE INTO growth_content(id,platform,title,body,shot_list,destination,created_at) VALUES(?,?,?,?,?,?,?)',
                              (cid,platform,analysis['summary'][:60],body,analysis['next_action'],json.dumps(dest,ensure_ascii=False),self.now()))
                result['prepared']+=1
            except AIError as e:
                result['errors'].append(str(e))
                if e.code in ('daily_limit','background_daily_limit','balance','invalid_key','forbidden'):break
        return result

    def run(self,ident):
        if not self.process_lock.acquire(blocking=False):return
        try:
            with self.store.db() as c:
                c.execute('BEGIN IMMEDIATE')
                row=c.execute("SELECT * FROM growth_jobs WHERE id=? AND status='queued'",(ident,)).fetchone()
                if not row:return
                row=dict(row)
                c.execute("UPDATE growth_jobs SET status='running',message='正在执行',updated_at=? WHERE id=?",(self.now(),ident))
            # Actual inquiries and ready-to-use content come before optional web discovery.
            kinds=['followup','respond','discover'] if row['kind']=='all' else [row['kind']]
            result={};blocked=False
            for kind in kinds:
                part=getattr(self,kind)(ident,row['actor']);result[kind]=part
                if part.get('blocked_reason'):blocked=True
                with self.store.db() as c:c.execute('UPDATE growth_jobs SET result=? WHERE id=?',(json.dumps(result,ensure_ascii=False),ident))
            self.progress(ident,'正在保存执行结果…',95)
            status='needs_setup' if blocked else 'completed'
            message='已完成可执行部分；请查看所需接入或核实事项' if blocked else '任务完成，执行结果已保存'
            with self.store.db() as c:
                c.execute('UPDATE growth_jobs SET status=?,progress=100,message=?,result=?,updated_at=? WHERE id=?',
                          (status,message,json.dumps(result,ensure_ascii=False),self.now(),ident))
        except AIError as e:
            with self.store.db() as c:
                c.execute('UPDATE growth_jobs SET status=?,message=?,error=?,updated_at=? WHERE id=?',
                          ('cancelled' if e.code=='cancelled' else 'needs_setup' if e.code in ('not_configured','search_disabled','consent') else 'failed',str(e),e.code,self.now(),ident))
        except Exception as error:
            with self.store.db() as c:
                c.execute("UPDATE growth_jobs SET status='failed',message=?,error=?,updated_at=? WHERE id=?",
                          ('执行失败，已停止；请重试或查看任务记录',type(error).__name__,self.now(),ident))
        finally:self.process_lock.release()

    def budget_paused(self):
        state=self.ai.status();usage={x['kind']:x['n'] for x in state['usage']}
        background_limit=state['daily_ai_limit']-min(10,state['daily_ai_limit']//3)
        return usage.get('chat',0)>=background_limit

    def start(self):
        if self.thread and self.thread.is_alive():return
        self.thread=threading.Thread(target=self.loop,name='GinkgoGrowthAutomation',daemon=True);self.thread.start()

    def loop(self):
        while not self.stopping.is_set():
            try:
                with self.store.db() as c:
                    stale=(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()
                    c.execute("UPDATE growth_jobs SET status='interrupted',message='上次执行中断，请核对结果后重新运行' WHERE status='running' AND updated_at<?",(stale,))
                    row=c.execute("SELECT id FROM growth_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
                if row:self.run(row[0]);continue
                cfg=self.ai.config()
                if cfg['automatic'] and cfg['enabled'] and not self.budget_paused():
                    with self.store.db() as c:
                        latest=c.execute('SELECT created_at FROM growth_jobs ORDER BY created_at DESC LIMIT 1').fetchone()
                    due=not latest or (datetime.now(timezone.utc)-datetime.fromisoformat(latest[0])).total_seconds()>=cfg['interval_minutes']*60
                    if due:self.create('all','定时自动任务')
            except Exception:pass  # Optional automation never stops the existing match server.
            self.wakeup.wait(15);self.wakeup.clear()


def register(bp,admin_guard,store,catalog,helpers,app):
    engine=Automation(store,catalog,helpers)
    app.extensions['ginkgo_growth']['automation']=engine
    import growth_workflow
    growth_workflow.register(bp,admin_guard,engine,app)

    @bp.route('/api/ai/settings',methods=['GET','POST'])
    @admin_guard
    def ai_settings():
        if request.method=='POST':
            state=engine.ai.configure(request.get_json() or {})
            with store.db() as c:store.audit(c,None,'ai_config','更新 AI 配置（密钥不写入记录）',g.growth_actor)
            return jsonify(state)
        return jsonify(engine.ai.status())

    @bp.errorhandler(AIError)
    def ai_error(error):return jsonify(error=str(error),code=error.code),409

    @bp.post('/api/ai/test')
    @admin_guard
    def ai_test():return jsonify(engine.ai.test_connection())

    @bp.post('/api/ai/leads/<lid>/analyze')
    @admin_guard
    def ai_analyze(lid):return jsonify(result=engine.analyze_lead(store.get(lid)),sent=False)

    @bp.get('/api/automation')
    @admin_guard
    def automation_status():
        with store.db() as c:jobs=[dict(row) for row in c.execute('SELECT * FROM growth_jobs ORDER BY created_at DESC LIMIT 15')]
        for row in jobs:row['result']=json.loads(row['result'])
        return jsonify(jobs=jobs,sources=engine.sources(),ai=engine.ai.status(),worker_running=bool(engine.thread and engine.thread.is_alive()),paused_for_budget=engine.budget_paused())

    @bp.post('/api/automation/jobs')
    @admin_guard
    def create_job():
        data=request.get_json() or {}
        row,created=engine.create(data.get('kind'),g.growth_actor)
        return jsonify(job=engine.job(row['id']),created=created),202 if created else 200

    @bp.get('/api/automation/jobs/<ident>')
    @admin_guard
    def get_job(ident):return jsonify(job=engine.job(ident))

    @bp.post('/api/automation/jobs/<ident>/cancel')
    @admin_guard
    def cancel_job(ident):
        engine.job(ident)
        with store.db() as c:
            c.execute("UPDATE growth_jobs SET cancelled=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=?",(ident,))
        return jsonify(ok=True)

    @bp.get('/api/candidates')
    @admin_guard
    def candidates():
        with store.db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM growth_candidates ORDER BY created_at DESC LIMIT 100')]
        for row in rows:row['ai_result']=json.loads(row['ai_result']) if row['ai_result'] else None
        return jsonify(items=rows,notice='这些是搜索引擎公开摘要，不是已核实客户或完整站内评论。')

    @bp.get('/api/followup-plans')
    @admin_guard
    def plans():
        with store.db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM growth_plans ORDER BY created_at DESC LIMIT 100')]
        return jsonify(items=rows,sent=0,platform_send_connected=False)

    @bp.get('/api/ai/content')
    @admin_guard
    def channel_drafts():
        with store.db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM growth_content ORDER BY created_at DESC LIMIT 60')]
        return jsonify(items=rows,published=0,publication_connected=False)

    @bp.post('/public/chat')
    def public_chat():
        if not request.is_json:return jsonify(error='请使用咨询页提交'),415
        d=request.get_json() or {}
        if d.get('consent') is not True:return jsonify(error='请先同意由 DeepSeek 处理脱敏咨询文字'),400
        question=redacted(str(d.get('question') or '').strip())
        if not 2<=len(question)<=600:return jsonify(error='问题请填写2至600字，不要填写密码、验证码或证件资料'),400
        cid=str(d.get('campaign_id') or '');platform=cid.split('-')[0]
        with store.db() as c:campaign=c.execute('SELECT id FROM campaigns WHERE id=?',(cid,)).fetchone()
        if not campaign or platform not in DESTINATIONS:return jsonify(error='咨询入口不存在'),404
        token=str(d.get('conversation_token') or '')
        if token and not re.fullmatch('[a-f0-9]{48}',token):raise ValueError('会话无效，请刷新后重试')
        if not token:token=secrets.token_hex(24)
        session=hashlib.sha256(token.encode()).hexdigest();hour=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM growth_chat_sessions WHERE id=?',(session,)).fetchone()
            if row and row['campaign']!=cid:return jsonify(error='请从相应平台的咨询入口重新提问'),400
            if row and row['hour']==hour and row['calls']>=6:return jsonify(error='本次会话提问较多，请稍后再试，或提交人工咨询'),429
            history=json.loads(row['history']) if row else []
            c.execute('INSERT INTO growth_chat_sessions(id,campaign,hour,calls,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET calls=CASE WHEN hour=excluded.hour THEN calls+1 ELSE 1 END,hour=excluded.hour,updated_at=excluded.updated_at',
                      (session,cid,hour,1,engine.now()))
            c.execute('DELETE FROM growth_chat_sessions WHERE updated_at<?',((datetime.now(timezone.utc)-timedelta(days=7)).isoformat(),))
        if not catalog.current()['updated_at']:catalog.sync()
        context='\n'.join(x['role']+'：'+x['text'][:160] for x in history[-4:])
        source={'platform':platform,'excerpt':'当前咨询：'+question+'\n前文仅用于理解上下文：'+context[:450]}
        analysis=engine.ai.analyze(source,catalog.current()['events'],'inbound_question')
        reply=analysis['reply']
        if not reply:raise AIError('这个问题需要工作人员核实，请提交人工咨询。','human_needed')
        history=(history+[{'role':'用户','text':question},{'role':'AI接待','text':reply}])[-12:]
        with store.db() as c:c.execute('UPDATE growth_chat_sessions SET history=?,updated_at=? WHERE id=?',(json.dumps(history,ensure_ascii=False),engine.now(),session))
        return jsonify(reply=reply,conversation_token=token,destination=DESTINATIONS[platform],ai_generated=True,booking_created=False)

    if not app.testing:engine.start()
    return engine
