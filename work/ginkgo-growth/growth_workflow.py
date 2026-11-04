"""Operational queue and publication receipts; no platform sending or business SQL."""
import csv
import io
import json
from datetime import datetime, timezone
from flask import g, jsonify, request, Response

VERSION = 'growth-workflow-1.2.0'


def register(bp, admin_guard, engine, app):
    store=engine.store

    def active_plans():
        with store.db() as c:
            return [dict(r) for r in c.execute('''SELECT p.*,COALESCE(a.status,'pending') AS status
                FROM growth_plans p LEFT JOIN growth_plan_actions a ON a.plan_id=p.id
                WHERE (p.subject_type='lead' AND EXISTS(SELECT 1 FROM leads l WHERE l.id=p.subject_id
                    AND l.stopped=0 AND l.stage NOT IN ('blocked','closed','archived','booked')))
                OR (p.subject_type='inquiry' AND EXISTS(SELECT 1 FROM inquiries i WHERE i.id=p.subject_id AND i.stage='new'))
                ORDER BY p.due_at,p.created_at LIMIT 200''')]

    def content_items():
        with store.db() as c:
            return [dict(r) for r in c.execute('''SELECT d.*,p.url AS published_url,p.recorded_at AS published_at
                FROM growth_content d LEFT JOIN growth_publications p ON p.content_id=d.id
                ORDER BY d.created_at DESC,d.id LIMIT 60''')]

    @bp.get('/workflow/health')
    def workflow_health():return jsonify(status='ok',version=VERSION)

    @bp.get('/api/workflow')
    @admin_guard
    def workflow_overview():
        plans=[x for x in active_plans() if x['status']=='pending']
        with store.db() as c:
            pending_sources=c.execute("SELECT COUNT(*) FROM growth_candidates WHERE status='needs_review'").fetchone()[0]
            new_inquiries=c.execute("SELECT COUNT(*) FROM inquiries WHERE stage='new'").fetchone()[0]
            booked=c.execute("SELECT COUNT(*) FROM leads WHERE stage='booked' AND booking_ref!=''").fetchone()[0]
            verified=c.execute("SELECT COUNT(*) FROM leads WHERE confirmed=1 AND stage NOT IN ('blocked','archived')").fetchone()[0]
            replied=c.execute("SELECT COUNT(*) FROM leads WHERE contact_count>0").fetchone()[0]
            content_counts={r['status']:r['n'] for r in c.execute('SELECT status,COUNT(*) AS n FROM growth_content GROUP BY status')}
        channels=app.extensions['ginkgo_growth'].get('channels')
        status=channels.status() if channels else {'items':[],'counts':[]}
        active=[x['name'] for x in status['items'] if x['automatic'] and x['verified_at']]
        human=sum(x['n'] for x in status['counts'] if x['state'] in ('human','uncertain'))
        return jsonify(version=VERSION,active_reception=active,customer_service_human=human,
            pending_sources=pending_sources,new_inquiries=new_inquiries,verified_needs=verified,
            contacted_needs=replied,bookings_with_receipt=booked,
            pending_plans=len(plans),due_plans=sum(bool(x['due_at'] and datetime.fromisoformat(x['due_at'])<=datetime.now(timezone.utc)) for x in plans),
            draft_content=content_counts.get('draft',0),published_content=content_counts.get('published',0),
            note='网页线索、确认需求、已联系和凭据报名分别统计；客服消息数量不等于人数或报名数。')

    @bp.patch('/api/candidates/<cid>')
    @admin_guard
    def workflow_candidate_action(cid):
        status=(request.get_json() or {}).get('status')
        if status not in ('ignored','needs_review'):raise ValueError('请选择保留待核实或忽略')
        with store.db() as c:
            if not c.execute('SELECT id FROM growth_candidates WHERE id=?',(cid,)).fetchone():raise LookupError('网页线索不存在')
            c.execute('UPDATE growth_candidates SET status=?,updated_at=? WHERE id=?',(status,engine.now(),cid))
            store.audit(c,None,'candidate_review','网页 '+cid+'：'+status,g.growth_actor)
        return jsonify(ok=True,status=status)

    @bp.get('/api/workflow/plans')
    @admin_guard
    def workflow_plans():return jsonify(items=active_plans())

    @bp.patch('/api/workflow/plans/<pid>')
    @admin_guard
    def workflow_plan_action(pid):
        status=(request.get_json() or {}).get('status')
        if status not in ('pending','done'):raise ValueError('跟进计划状态无效')
        if not any(x['id']==pid for x in active_plans()):raise LookupError('计划已结束或不存在')
        with store.db() as c:
            c.execute('INSERT INTO growth_plan_actions VALUES(?,?,?) ON CONFLICT(plan_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at',(pid,status,engine.now()))
            store.audit(c,None,'plan_action','计划 '+pid+'：'+status+'；未变更联系或报名记录',g.growth_actor)
        return jsonify(ok=True,sent=False,booking_created=False)

    @bp.get('/api/workflow/content')
    @admin_guard
    def workflow_content():return jsonify(items=content_items())

    @bp.post('/api/workflow/content/<cid>/published')
    @admin_guard
    def workflow_published(cid):
        with store.db() as c:row=c.execute('SELECT * FROM growth_content WHERE id=?',(cid,)).fetchone()
        if not row:raise LookupError('文案不存在')
        # A manual publication record requires the actual native-platform post URL.
        url=engine.h['validate_source'](row['platform'],(request.get_json() or {}).get('url'))
        with store.db() as c:
            c.execute('INSERT INTO growth_publications VALUES(?,?,?,?) ON CONFLICT(content_id) DO UPDATE SET url=excluded.url,actor=excluded.actor,recorded_at=excluded.recorded_at',(cid,url,g.growth_actor,engine.now()))
            c.execute("UPDATE growth_content SET status='published' WHERE id=?",(cid,))
            store.audit(c,None,'publication','人工登记本平台作品链接：'+cid,g.growth_actor)
        return jsonify(ok=True,status='published',automatically_verified=False)

    @bp.get('/api/workflow/content/export')
    @admin_guard
    def workflow_export():
        items=content_items();fmt=request.args.get('format','markdown')
        if fmt not in ('markdown','csv'):raise ValueError('导出格式无效')
        if fmt=='csv':
            out=io.StringIO(newline='');writer=csv.writer(out)
            writer.writerow(['平台','标题','正文','拍摄建议','小程序入口','状态','作品链接'])
            for x in items:
                dest=json.loads(x['destination'])
                values=[dest['platform'],x['title'],x['body'],x['shot_list'],dest['guide'],x['status'],x['published_url'] or '']
                writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=','+','-','@')) else str(v) for v in values])
            body='\ufeff'+out.getvalue();mime='text/csv';ext='csv'
        else:
            parts=['# 银杏乒乓 · 内容发布包','每条关联对应平台的「银杏奖牌」小程序；文案不等同已发布。比赛与课表以发布时实时页面为准。']
            for x in items:
                dest=json.loads(x['destination'])
                parts.append('\n## '+dest['platform']+' · '+x['title']+'\n\n'+x['body']+'\n\n拍摄建议：'+x['shot_list']+'\n\n入口：'+dest['guide']+'\n\n状态：'+('已登记作品链接' if x['status']=='published' else '待发布')+(('\n作品：'+x['published_url']) if x['published_url'] else ''))
            body='\n\n'.join(parts);mime='text/markdown';ext='md'
        return Response(body,mimetype=mime,headers={'Content-Disposition':'attachment; filename=ginkgo-content.'+ext})
