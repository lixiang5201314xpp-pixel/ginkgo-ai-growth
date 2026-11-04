"""External-platform intake: source evidence first; no platform login, crawling or sending."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit
import json
import re
import secrets
from flask import g, jsonify, request
from growth_ai import CST, redacted

VERSION='growth-external-1.3.0'
TOPICS=['成都 乒乓球 找教练','成都 乒乓球 比赛报名','成都 零基础 学乒乓球','成都 乒乓球 找球搭子']


def publication_time(raw,captured_at,explicit,parse_time):
    if explicit:
        try:return parse_time(str(explicit)).isoformat()
        except (ValueError,AttributeError,TypeError):raise ValueError('原文时间格式无效')
    raw=str(raw or '').strip()
    if not raw:return None
    if re.search(r'IP|属地|在线|播放|观看',raw,re.I):return None
    if raw in ('刚刚','刚才'):return captured_at.isoformat()
    m=re.fullmatch(r'(\d+)\s*(分钟|小时|天)前',raw)
    if m:
        n=int(m[1]);unit={'分钟':'minutes','小时':'hours','天':'days'}[m[2]]
        if n>10000:return None
        return (captured_at-timedelta(**{unit:n})).isoformat()
    m=re.fullmatch(r'(今天|昨天|前天)(?:\s+(\d{1,2}):(\d{2}))?',raw)
    if m:
        # A date-only label does not specify a time; preserve the day without inventing precision.
        day=(captured_at-timedelta(days={'今天':0,'昨天':1,'前天':2}[m[1]])).date()
        try:return datetime(day.year,day.month,day.day,int(m[2] or 0),int(m[3] or 0),tzinfo=CST).isoformat()
        except ValueError:return None
    if re.match(r'^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}',raw):
        normalized=re.sub(r'^(\d{4})[/.](\d{1,2})[/.](\d{1,2})',lambda m:f'{m[1]}-{int(m[2]):02}-{int(m[3]):02}',raw)
        try:return parse_time(normalized).isoformat()
        except (ValueError,AttributeError):return None
    m=re.fullmatch(r'(\d{1,2})[-/](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?',raw)
    if m:
        try:
            d=datetime(captured_at.year,int(m[1]),int(m[2]),int(m[3] or 0),int(m[4] or 0),tzinfo=CST)
            if d>captured_at+timedelta(days=1):d=d.replace(year=d.year-1)
            return d.isoformat()
        except ValueError:return None
    return None


def normalize_capture(data,helpers):
    if not isinstance(data,dict):raise ValueError('评论记录格式无效')
    platform=data.get('platform');url=helpers['validate_source'](platform,data.get('source_url'))
    location=urlsplit(url)
    if location.hostname.startswith(('miniapp.','open.','developer.','mp.weixin.')) or location.path.startswith(('/search','/search_result','/f/search/')):
        raise ValueError('请填写外部平台具体原文链接，不能用小程序后台或搜索列表代替原文')
    excerpt=redacted(str(data.get('excerpt') or '').strip())
    if not 6<=len(excerpt)<=800:raise ValueError('每条原文需为6至800字')
    context=redacted(str(data.get('source_context') or '').strip())[:500]
    geo=redacted(str(data.get('city_evidence') or '').strip())[:160]
    if not geo and '成都' in excerpt:geo='评论原文包含成都'
    if not geo and '成都' in context:geo='发布内容原文：'+context[:140]
    # Search keywords and IP labels never establish the comment author's service location.
    if re.search('IP属地|IP地址|搜索词|关键词',geo,re.I):geo=''
    captured=helpers['parse_time'](str(data.get('captured_at') or '')) or datetime.now(CST)
    if captured>datetime.now(timezone.utc)+timedelta(minutes=5):raise ValueError('采集时间不能是未来时间')
    posted=publication_time(data.get('posted_text'),captured,data.get('posted_at'),helpers['parse_time'])
    return {'platform':platform,'source_url':url,'excerpt':excerpt,'source_context':context,
            'city_evidence':geo,'posted_at':posted,'posted_text':str(data.get('posted_text') or '')[:60],
            'captured_at':captured.isoformat(),'alias':'','relation':'public_request',
            'assessment':helpers['classify'](excerpt,geo,posted)}


def register(bp,admin_guard,engine,app):
    from growth_acquisition import parse_time
    store=engine.store;h={**engine.h,'parse_time':parse_time}
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS growth_external_batches(
            id TEXT PRIMARY KEY,created_at TEXT NOT NULL,platform TEXT NOT NULL,
            imported INTEGER NOT NULL,duplicates INTEGER NOT NULL,actor TEXT NOT NULL)''')

    def records():
        d=request.get_json() or {}
        if not isinstance(d,dict):raise ValueError('请提交评论记录对象')
        items=d.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=20:raise ValueError('每批请选择1至20条原文')
        return d,[normalize_capture(x,h) for x in items]

    @bp.get('/external/health')
    def external_health():return jsonify(status='ok',version=VERSION)

    @bp.get('/api/external')
    @admin_guard
    def external_overview():
        with store.db() as c:
            counts={r['platform']:dict(r) for r in c.execute('''SELECT platform,COUNT(*) AS recorded,
                SUM(CASE WHEN stage='qualified' AND stopped=0 THEN 1 ELSE 0 END) AS ready,
                SUM(CASE WHEN contact_count>0 THEN 1 ELSE 0 END) AS contacted,
                SUM(CASE WHEN stage='booked' AND booking_ref!='' THEN 1 ELSE 0 END) AS booked
                FROM leads WHERE relation='public_request' GROUP BY platform''')}
            pending=c.execute("SELECT COUNT(*) FROM growth_candidates WHERE status='needs_review'").fetchone()[0]
            batches=[dict(r) for r in c.execute('SELECT * FROM growth_external_batches ORDER BY created_at DESC LIMIT 12')]
        platforms=[]
        for key,p in h['platforms'].items():
            platforms.append({'id':key,'name':p['name'],'mode':'手机搜索后复制原文' if key=='channels' else '站内搜索＋当前页评论助手',
                'searches':[{'query':q,'url':p['search'].format(q=quote(q)) if p['search'] else None} for q in TOPICS],
                'home':p['home'],'counts':counts.get(key,{'recorded':0,'ready':0,'contacted':0,'booked':0})})
        return jsonify(version=VERSION,platforms=platforms,public_index_candidates=pending,batches=batches,
            helper='/api/match-center/growth/assets/browser-helper.zip',
            notice='外部评论才是需求来源；银杏奖牌小程序用于报名。网页索引是补充线索，不能覆盖完整站内评论。',
            sending_connected=False,miniapp_reception_is_separate=True)

    @bp.post('/api/external/preview')
    @admin_guard
    def external_preview():
        _,items=records()
        return jsonify(items=items,imported=0,sent=0)

    @bp.post('/api/external/import')
    @admin_guard
    def external_import():
        d,items=records()
        if d.get('source_reviewed') is not True:raise ValueError('请先确认已查看并核对原平台的公开原文')
        if any(x['assessment']['rejected'] or not x['assessment']['explicit_demand'] for x in items):
            raise ValueError('请选择明确求助的原文，不导入拒绝联系、招生广告或普通夸赞')
        added=0;duplicates=0;out=[]
        # Validate the entire batch before making any writes.
        for item in items:
            row,new=store.add({**item,'confirmed':bool(item['assessment']['eligible'])},g.growth_actor)
            added+=int(new);duplicates+=int(not new);out.append({'id':row['id'],'stage':row['stage'],'assessment':row['assessment']})
        with store.db() as c:
            c.execute('INSERT INTO growth_external_batches VALUES(?,?,?,?,?,?)',
                      (secrets.token_hex(10),engine.now(),','.join(sorted(set(x['platform'] for x in items))),added,duplicates,g.growth_actor))
        job=None
        if d.get('prepare_replies') is True and added:
            value,_=engine.create('respond',g.growth_actor);job=engine.job(value['id'])
        return jsonify(added=added,duplicates=duplicates,items=out,job=job,sent=0,booking_created=False),201
