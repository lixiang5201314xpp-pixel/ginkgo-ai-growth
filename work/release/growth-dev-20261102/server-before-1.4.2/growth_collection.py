"""Admin-enabled continuous public-page intake. No social sending or credentials."""
import hashlib
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from flask import g, jsonify, request

VERSION = 'growth-collection-1.4.1'

def post_title(value):
    """Ignore UI series labels/punctuation, retaining the actual request text."""
    value = re.split(r'[#。\n]', str(value), maxsplit=1)[0].strip()
    value = re.sub(r'^第\s*[0-9零一二三四五六七八九十百]+\s*[集期]\s*[:：|丨.\-]?\s*', '', value)
    return re.sub(r'[\W_]+', '', value)

def register(bp, admin_guard, engine, helpers, normalize):
    store = engine.store
    lock = threading.Lock()
    key = 'public_collection_config_v1'
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS growth_collection_receipts(
            id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
            created_at TEXT NOT NULL, actor TEXT NOT NULL)''')

    def config():
        with store.db() as c:
            r = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(r[0]) if r else {'enabled': False}

    @bp.get('/api/collection')
    @admin_guard
    def collection_state():
        with store.db() as c:
            receipts = [dict(r) for r in c.execute(
                'SELECT id,result,created_at FROM growth_collection_receipts ORDER BY created_at DESC LIMIT 12')]
        for r in receipts:
            r['result'] = json.loads(r['result'])
        return jsonify(version=VERSION, **config(), receipts=receipts,
                       automatic_platform_sending=False, requires_local_browser=True,
                       supported_platforms=['douyin', 'xiaohongshu', 'kuaishou'])

    @bp.put('/api/collection')
    @admin_guard
    def collection_config():
        d = request.get_json()
        if not isinstance(d, dict) or set(d) != {'enabled'} or type(d['enabled']) is not bool:
            raise ValueError('仅支持开启或停止公开页面自动采集')
        value = {'enabled': d['enabled'], 'updated_at': engine.now()}
        with store.db() as c:
            c.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                      (key, json.dumps(value)))
            store.audit(c, None, 'collection_settings',
                        '开启公开页面自动入库与AI准备' if value['enabled'] else '停止公开页面自动入库', g.growth_actor)
        return jsonify(**value, automatic_platform_sending=False)

    @bp.post('/api/collection/batches')
    @admin_guard
    def collection_batch():
        if not config()['enabled']:
            return jsonify(error='请先在工作台开启公开页面自动采集', code='collection_off'), 409
        d = request.get_json()
        if not isinstance(d, dict):
            raise ValueError('自动采集批次无效')
        ident = d.get('batch_id')
        if not isinstance(ident, str) or not re.fullmatch('[a-f0-9-]{24,64}', ident):
            raise ValueError('采集批次标识无效')
        raw = d.get('items')
        if not isinstance(raw, list) or not 1 <= len(raw) <= 20:
            raise ValueError('每批需要1至20条公开原文')
        proof = d.get('observation')
        if not isinstance(proof, dict) or proof.get('read_scope') != 'rendered_public_page':
            raise ValueError('缺少已渲染公开页面的采集凭据')
        page = str(proof.get('page_url') or '')
        captured = helpers['parse_time'](proof.get('observed_at'))
        if not captured or abs((datetime.now(timezone.utc) - captured).total_seconds()) > 900:
            raise ValueError('采集凭据已过期，请重新读取公开页面')
        # All validation precedes writes. Search pages are not original sources.
        rows = [normalize(x, helpers) for x in raw]
        for row in rows:
            if row['platform'] not in ('douyin', 'xiaohongshu', 'kuaishou'):
                raise ValueError('此平台尚未完成自动采集适配')
            page_valid = helpers['validate_source'](row['platform'], page)
            if (urlsplit(page_valid).hostname,urlsplit(page_valid).path) != (urlsplit(row['source_url']).hostname,urlsplit(row['source_url']).path):
                raise ValueError('原文链接与当前采集页面不一致')
            if urlsplit(page_valid).path.startswith(('/search', '/search_result')):
                raise ValueError('搜索结果不能代替原帖')
        fingerprint = hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with lock:
            with store.db() as c:
                prior = c.execute('SELECT * FROM growth_collection_receipts WHERE id=?', (ident,)).fetchone()
            if prior:
                if prior['fingerprint'] != fingerprint:
                    raise ValueError('批次标识已被其他内容使用')
                return jsonify(**json.loads(prior['result']), replayed=True)
            added = valid = pending = duplicates = skipped = 0
            ids = []
            for row in rows:
                assess = row['assessment']
                if assess['rejected'] or not assess['explicit_demand']:
                    skipped += 1
                    continue
                posted = helpers['parse_time'](row.get('posted_at'))
                if posted and posted < datetime.now(timezone.utc) - timedelta(days=30):
                    # Known stale content needs no manual qualification or AI call.
                    # A fresh comment retains its own timestamp, even on an old video.
                    skipped += 1
                    continue
                # Old manually transcribed post titles may include image text, while the
                # automatic adapter only sees the rendered title/description. Hold these
                # overlapping sources for review rather than generating another invitation.
                if row.get('source_kind') == 'post':
                    incoming_path=urlsplit(row['source_url']).path.rstrip('/')
                    title=post_title(row['excerpt'])
                    with store.db() as c:
                        old_rows=c.execute('SELECT source_url,excerpt FROM leads WHERE platform=?',(row['platform'],)).fetchall()
                    if len(title)>=6 and any(urlsplit(old['source_url']).path.rstrip('/')==incoming_path
                                             and post_title(old['excerpt']).startswith(title) for old in old_rows):
                        duplicates+=1;continue
                # Machine qualification uses explicit original-text evidence, never search keywords/IP.
                original_city = '成都' in row['excerpt']
                saved, fresh = store.add({**row, 'confirmed': bool(assess['eligible'] and original_city)}, g.growth_actor)
                duplicates += int(not fresh)
                if fresh:
                    added += 1
                    good = saved['stage'] == 'qualified'
                    valid += int(good)
                    pending += int(not good)
                    ids.append(saved['id'])
                    with store.db() as c:
                        store.audit(c, saved['id'], 'automatic_source',
                                    '来自已授权浏览器公开页面采集；证据不足保留待核实；未发送消息', g.growth_actor)
            job = None
            if valid:
                queued, _ = engine.create('respond', g.growth_actor)
                job = queued['id']
            result = dict(added=added, added_valid=valid, pending_review=pending,
                          duplicates=duplicates, skipped=skipped, lead_ids=ids,
                          job_id=job, sent=0, bookings=0)
            with store.db() as c:
                c.execute('INSERT INTO growth_collection_receipts VALUES(?,?,?,?,?)',
                          (ident, fingerprint, json.dumps(result), engine.now(), g.growth_actor))
            return jsonify(**result, replayed=False), 201
