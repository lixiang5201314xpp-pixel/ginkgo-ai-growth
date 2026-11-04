"""Ginkgo acquisition workbench. No social-platform crawler or silent sender.

Mounted into the existing Flask server with its existing authenticated admin guard.
Its SQLite store is separate from accounts, events, payments and medals.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import ssl
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, Response, g, jsonify, request, send_from_directory

VERSION = 'ginkgo-growth-1.1.0'
PREFIX = '/api/match-center/growth'
BASE = Path(__file__).resolve().parent
CST = timezone(timedelta(hours=8))
BUSINESS = '银杏乒乓球俱乐部'
MINIAPP = '银杏奖牌'
API_ORIGIN = 'https://qiuchen.yinxingpingpang.com'

PLATFORMS = {
    'douyin': {'name': '抖音', 'color': '#292b36', 'hosts': ['douyin.com', 'iesdouyin.com'],
        'home': 'https://www.douyin.com/', 'console': 'https://e.douyin.com/',
        'search': 'https://www.douyin.com/search/{q}',
        'status': '辅助搜索', 'reason': '未接入评论接口。关键词视频能力需申请，且只允许审核通过的自有品牌关键词。',
        'docs': 'https://open.douyin.com/platform/resource/docs/ability/search-management/video/'},
    'kuaishou': {'name': '快手', 'color': '#ef7738', 'hosts': ['kuaishou.com', 'gifshow.com'],
        'home': 'https://www.kuaishou.com/', 'console': 'https://cp.kuaishou.com/',
        'search': 'https://www.kuaishou.com/search/{q}?source=NewReco',
        'status': '辅助搜索', 'reason': '未接入评论或私信接口。可导入自己账号的咨询导出，正式发送使用平台工作台。',
        'docs': 'https://open.kuaishou.com/platformDocs/newGuide/applicationManagementSpecifica'},
    'channels': {'name': '微信视频号', 'color': '#48a774', 'hosts': ['weixin.qq.com', 'weixinbridge.com'],
        'home': 'https://channels.weixin.qq.com/', 'console': 'https://channels.weixin.qq.com/',
        'search': '', 'status': '微信内搜索', 'reason': '在手机微信视频号搜索关键词；本工具没有全站评论采集或视频号私信权限。',
        'docs': 'https://channels.weixin.qq.com/'},
    'xiaohongshu': {'name': '小红书', 'color': '#e44d62', 'hosts': ['xiaohongshu.com', 'xhslink.com'],
        'home': 'https://www.xiaohongshu.com/', 'console': 'https://pro.xiaohongshu.com/',
        'search': 'https://www.xiaohongshu.com/search_result?keyword={q}&source=web_search_result_notes',
        'status': '辅助搜索', 'reason': '未接入私信获客接口。优先专业号咨询、站内小程序入口，勿在回复中放站外联系方式。',
        'docs': 'https://xue.xiaohongshu.com/pro/home'},
    'bilibili': {'name': '哔哩哔哩', 'color': '#5f9cb4', 'hosts': ['bilibili.com', 'b23.tv'],
        'home': 'https://www.bilibili.com/', 'console': 'https://member.bilibili.com/',
        'search': 'https://search.bilibili.com/all?keyword={q}', 'status': '辅助搜索',
        'reason': '补充成都球友和教学内容搜索；未接入消息接口。', 'docs': 'https://www.bilibili.com/'},
    'tieba': {'name': '百度贴吧', 'color': '#587bdd', 'hosts': ['tieba.baidu.com'],
        'home': 'https://tieba.baidu.com/', 'console': 'https://tieba.baidu.com/',
        'search': 'https://tieba.baidu.com/f/search/res?ie=utf-8&qw={q}', 'status': '辅助搜索',
        'reason': '仅针对明确求助的公开帖子，先查看吧规，再在原帖回应。', 'docs': 'https://tieba.baidu.com/'},
}
INTENTS = {'training': '训练咨询', 'competition': '比赛报名', 'practice': '找球搭子', 'unknown': '待核实'}
STAGES = {'new': '待核实', 'qualified': '可回应', 'contacted': '已人工联系', 'replied': '对方已回复',
          'invited': '已发报名指引', 'booked': '已核实报名', 'closed': '暂不需要', 'blocked': '不再联系', 'archived': '已归档'}
DISTRICTS = ['青羊', '金牛', '武侯', '锦江', '成华', '高新', '天府新区', '双流', '温江', '郫都', '龙泉驿', '新都']
DEMAND = [r'想.{0,8}(学|练|报名|参赛|打球)', r'求.{0,8}(推荐|教练|培训|比赛|球友|带)',
          r'(哪里|哪儿|有没有|请问|怎么).{0,12}(教练|培训|比赛|报名|学球|练球|打球)',
          r'找.{0,8}(教练|培训|比赛|球友|搭子|陪练)', r'(报名|参赛|培训|学球|教练|训练).{0,8}(怎么|哪|推荐|多少钱|费用|吗|么|？|\?)']
DEMAND.append(r'(有没有|哪里|哪儿).{0,12}(球友|球搭子|搭子)')
DEMAND.extend([r'有人.{0,8}一起.{0,8}(打|练).{0,6}(乒乓|单球|球)',
               r'来个.{0,12}(搭子|球友)'])
NEGATIVE = [r'不(想|需要|要|用).{0,4}(训练|教练|报名|比赛|推荐|学球|联系)', r'别.{0,4}(联系|推销|发广告)', r'勿扰', r'禁止.{0,5}(广告|推销)']
NO_CUSTOMER = [r'(招聘|招募|诚聘).{0,6}(教练|陪练)', r'(招收学员|招生中|招生啦|私教招生)',
               r'(我是|我们是|这里是|来自).{0,24}(俱乐部|球馆).{0,8}(工作人员|教练|客服|招生)',
               r'招(?:一[位名个]|全职|兼职|专业|助理|乒乓球?|男|女|\s){0,4}(教练|陪练)',
               r'(求职|应聘|求聘).{0,16}(乒乓|教练|陪练)',
               r'(教练|陪练).{0,16}(找工作|求职|工作机会|岗位|职位)',
               r'(找|求)[^，。！？;\n]{0,12}(教练|陪练)工作(?!经验|时间|态度|方式|安排)',
               r'(我|本人).{0,12}(教练|陪练).{0,20}(找学生|找学员|收学员|招生|收徒|接课)',
               r'(世界杯|奥运|世乒赛|乒超).{0,8}(门票|直播|观赛|票)', r'(门票|直播|观赛).{0,8}(世界杯|奥运|世乒赛|乒超)']


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def parse_time(value):
    if not value:
        return None
    try:
        value = str(value).strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=CST) if dt.tzinfo is None else dt
    except ValueError:
        raise ValueError('发布时间请填写有效日期时间')


def text(value, limit=800):
    return str(value or '').strip()[:limit]


def mask_contacts(value):
    # No extraction of private contact details from a public comment.
    value = re.sub(r'sk-[a-zA-Z0-9_-]+', '[密钥已隐藏]', str(value), flags=re.I)
    value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[邮箱已隐藏]', value)
    value = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[电话已隐藏]', value)
    return re.sub(r'(?i)(微信|微号|vx|wechat|qq)\s*[:：号]?\s*[a-zA-Z0-9_-]{5,}', r'\1[联系方式已隐藏]', value)


def validate_source(platform, url):
    if platform not in PLATFORMS:
        raise ValueError('请选择支持的平台')
    p = urllib.parse.urlsplit(text(url, 1600))
    host = (p.hostname or '').lower()
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('来源必须是该平台的 HTTPS 原文链接')
    if not any(host == d or host.endswith('.' + d) for d in PLATFORMS[platform]['hosts']):
        raise ValueError('来源链接与选择的平台不符')
    # Keep a verifiable original URL; no server-side URL fetching or redirect following.
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


def classify(excerpt, city_evidence='', posted_at=None):
    """Explainable need classification, not demographic or credit profiling."""
    s = text(excerpt)
    geo = text(city_evidence, 160)
    reasons, warnings = [], []
    unreliable_geo = bool(re.search(r'搜索词|搜索关键词|关键词为|IP属地|ip属地|IP地址', geo))
    local = '成都' in s or ('成都' in geo and not unreliable_geo)
    if re.search(r'不在成都|不是成都人|离开成都|搬离成都|成都以外', s):
        local = False
    sport = bool(re.search('乒乓|乒乒|学球|练球|球友|球搭子', s))
    demand = sport and any(re.search(p, s) for p in DEMAND)
    negative = any(re.search(p, s) for p in NEGATIVE)
    non_customer = any(re.search(p, s) for p in NO_CUSTOMER)
    training = bool(re.search('教练|学球|培训|陪练|私教|训练|零基础|学乒乓', s))
    competition = bool(re.search('报名|参赛|积分赛|比赛|团体赛|双打赛', s))
    intent = 'training' if training else 'competition' if competition else 'practice' if sport and demand else 'unknown'
    score = 0
    if local:
        reasons.append('原文或核对的来源上下文明示成都'); score += 30
    else:
        warnings.append('尚未确认成都；搜索词或IP属地不能证明所在地')
    if sport:
        reasons.append('明确涉及乒乓球'); score += 15
    if demand:
        reasons.append('有明确询问或寻求服务的语句'); score += 35
    else:
        warnings.append('未识别到明确服务需求，请勿仅凭点赞或兴趣推销')
    if intent != 'unknown':
        score += 10
    dt = parse_time(posted_at)
    fresh = False
    if dt:
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        if age < -1:
            raise ValueError('发布时间不能在未来')
        fresh = -1 <= age <= 30
        if age <= 7: score += 10
        elif fresh: score += 5
        else: warnings.append('需求已超过30天，不进入主动回应队列')
    else:
        warnings.append('缺少原文发布时间，请先核实')
    if negative:
        warnings.append('原文有拒绝联系或拒绝服务意向')
    if non_customer:
        warnings.append('可能为招聘、求职、招生或观赛内容，不作为客户需求')
    eligible = local and demand and fresh and not negative and not non_customer
    return {'intent': intent, 'score': max(0, min(score, 100)), 'reasons': reasons, 'warnings': warnings,
            'local': local, 'explicit_demand': demand, 'eligible': eligible,
            'rejected': negative or non_customer, 'district': next((x for x in DISTRICTS if x in s or x in geo), '')}


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'acquisition.sqlite3'
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS leads(
                id TEXT PRIMARY KEY, platform TEXT NOT NULL, source_url TEXT NOT NULL,
                excerpt TEXT NOT NULL, alias TEXT NOT NULL DEFAULT '', city_evidence TEXT NOT NULL DEFAULT '',
                posted_at TEXT, relation TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE,
                person_key TEXT NOT NULL, assessment TEXT NOT NULL, stage TEXT NOT NULL,
                confirmed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                follow_at TEXT, contact_count INTEGER NOT NULL DEFAULT 0, last_contact_at TEXT,
                latest_reply TEXT NOT NULL DEFAULT '', booking_ref TEXT NOT NULL DEFAULT '',
                stopped INTEGER NOT NULL DEFAULT 0, reply_version INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS activity(
                id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT, type TEXT NOT NULL,
                detail TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS suppressions(person_key TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS campaigns(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, platform TEXT NOT NULL,
                intent TEXT NOT NULL, created_at TEXT NOT NULL, visits INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS inquiries(
                id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, alias TEXT NOT NULL,
                interest TEXT NOT NULL, district TEXT NOT NULL, availability TEXT NOT NULL,
                contact TEXT NOT NULL, consent_at TEXT NOT NULL, consent_version TEXT NOT NULL,
                created_at TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'new');
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inbound_ids(id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS delivery_attempts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,lead_id TEXT NOT NULL REFERENCES leads(id),
                account TEXT NOT NULL,content TEXT NOT NULL,evidence_url TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','not_visible','failed','confirmed')),
                note TEXT NOT NULL DEFAULT '',actor TEXT NOT NULL,created_at TEXT NOT NULL,
                checked_at TEXT,request_id TEXT NOT NULL UNIQUE);
            CREATE INDEX IF NOT EXISTS delivery_lead_idx ON delivery_attempts(lead_id,id DESC);
            ''')
            for platform in list(PLATFORMS)[:4]:
                for intent in ('competition', 'training'):
                    cid = f'{platform}-{intent}'
                    c.execute('INSERT OR IGNORE INTO campaigns(id,name,platform,intent,created_at) VALUES(?,?,?,?,?)',
                              (cid, PLATFORMS[platform]['name'] + '·' + INTENTS[intent], platform, intent, stamp()))

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA busy_timeout=10000')
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()

    @staticmethod
    def audit(c, lid, kind, detail, actor):
        c.execute('INSERT INTO activity(lead_id,type,detail,actor,created_at) VALUES(?,?,?,?,?)',
                  (lid, kind, mask_contacts(text(detail, 1200)), text(actor, 50), stamp()))

    @staticmethod
    def view(row):
        d = dict(row)
        # Re-evaluate time-dependent eligibility at every read, never trust a saved score forever.
        d['assessment'] = classify(d['excerpt'], d['city_evidence'], d['posted_at'])
        return d

    def add(self, data, actor):
        platform = text(data.get('platform'), 30)
        url = validate_source(platform, data.get('source_url'))
        excerpt = mask_contacts(text(data.get('excerpt')))
        if len(excerpt) < 6:
            raise ValueError('请录入可核对的需求原文，至少6字')
        alias = mask_contacts(text(data.get('alias'), 60))
        geo = mask_contacts(text(data.get('city_evidence'), 160))
        relation = data.get('relation', 'public_request')
        if relation not in ('public_request', 'inbound'):
            raise ValueError('仅支持公开明确求助或自己账号收到的咨询')
        posted = parse_time(data.get('posted_at'))
        assessment = classify(excerpt, geo, posted.isoformat() if posted else None)
        # Public source identity must not change when a platform rotates tracking/signature parameters.
        identity_url = urllib.parse.urlsplit(url)
        identity_url = identity_url.scheme+'://'+identity_url.netloc+identity_url.path.rstrip('/')
        fp = hashlib.sha256((platform + '|' + identity_url + '|' + re.sub(r'\s+', '', excerpt)).encode()).hexdigest()
        # Deduplicate within a platform only. Never infer one person across multiple services.
        person = hashlib.sha256((platform + '|' + (alias.lower() if alias else url + '|' + excerpt)).encode()).hexdigest()
        lid, now = secrets.token_hex(10), stamp()
        confirmed = bool(data.get('confirmed') is True)
        stage = 'qualified' if assessment['eligible'] and confirmed else 'new'
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            previous = c.execute('SELECT * FROM leads WHERE fingerprint=?', (fp,)).fetchone()
            if not previous:
                # Compatibility with existing receipts created before stable source identities.
                for old in c.execute('SELECT * FROM leads WHERE platform=? AND excerpt=?', (platform,excerpt)):
                    prior=urllib.parse.urlsplit(old['source_url'])
                    if prior.scheme+'://'+prior.netloc+prior.path.rstrip('/') == identity_url:
                        previous=old;break
            if previous:
                return self.view(previous), False
            stopped = c.execute('SELECT 1 FROM suppressions WHERE person_key=?', (person,)).fetchone() is not None
            c.execute('''INSERT INTO leads(id,platform,source_url,excerpt,alias,city_evidence,posted_at,relation,
                fingerprint,person_key,assessment,stage,confirmed,created_at,updated_at,stopped)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (lid, platform, url, excerpt, alias, geo, posted.isoformat() if posted else None, relation,
                 fp, person, json.dumps(assessment, ensure_ascii=False), 'blocked' if stopped else stage,
                 int(confirmed), now, now, int(stopped)))
            self.audit(c, lid, 'created', '来源原文录入；尚未向平台发送消息', actor)
            return self.view(c.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone()), True

    def get(self, lid):
        with self.db() as c:
            row = c.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone()
        if not row: raise LookupError('线索不存在')
        return self.view(row)

    def contact_guard(self, lead, include_delivery=True):
        if lead['stopped'] or lead['stage'] in ('blocked', 'closed', 'archived', 'booked'):
            return '这条线索已停止联系或完成，请勿再发送邀请'
        if not lead['confirmed']:
            return '请先核对原文确为成都当前需求并确认'
        if not lead['assessment']['eligible']:
            return '请先补齐成都、原文发布时间和明确需求证据'
        if lead['contact_count'] >= 1 and lead['stage'] not in ('replied',):
            return '已经联系过，等待对方回复；不重复催促'
        if include_delivery:
            block=self.delivery_block(lead['id'])
            if block:return block
        if lead['last_contact_at']:
            last = parse_time(lead['last_contact_at'])
            if (datetime.now(timezone.utc) - last).total_seconds() < 60:
                return '刚完成联系，请稍后再操作'
        return ''

    def delivery_block(self,lid):
        with self.db() as c:
            attempt=c.execute('SELECT status FROM delivery_attempts WHERE lead_id=? ORDER BY id DESC LIMIT 1',(lid,)).fetchone()
        return '已有发送尝试尚未核实发布；请先查看发送核对记录，不自动重发' if attempt and attempt['status']!='confirmed' else ''

    def update(self, lid, data, actor):
        original = self.get(lid)
        allowed = {'confirmed', 'stage', 'follow_at', 'booking_ref', 'city_evidence', 'posted_at'}
        if set(data) - allowed: raise ValueError('不支持修改这些字段')
        merged = {**original, **data}
        if merged['stage'] not in STAGES: raise ValueError('跟进状态无效')
        confirmed = data.get('confirmed', bool(original['confirmed']))
        if not isinstance(confirmed, bool): raise ValueError('确认标记须为布尔值')
        posted = parse_time(merged['posted_at'])
        follow = parse_time(merged.get('follow_at'))
        assess = classify(original['excerpt'], merged['city_evidence'], merged['posted_at'])
        if merged['stage'] == 'qualified' and (not confirmed or not assess['eligible']):
            raise ValueError('可回应线索须核实当前成都服务需求')
        if merged['stage'] == 'contacted' and original['contact_count'] == 0:
            raise ValueError('请通过“登记实际联系”录入已发送内容和原文凭据')
        if merged['stage'] == 'booked' and not text(merged.get('booking_ref'), 100):
            raise ValueError('请填写已核实的报名记录编号；点击链接不算报名')
        if original['stopped'] and merged['stage'] != 'blocked':
            raise ValueError('已拒绝联系，不能通过改状态重新联系')
        if merged['stage'] in ('replied', 'invited') and original['contact_count'] == 0:
            raise ValueError('请先登记真实联系记录')
        with self.db() as c:
            c.execute('''UPDATE leads SET confirmed=?,stage=?,follow_at=?,booking_ref=?,city_evidence=?,
                posted_at=?,assessment=?,updated_at=? WHERE id=?''',
                (int(confirmed), merged['stage'], follow.isoformat() if follow else None,
                 text(merged.get('booking_ref'), 100), mask_contacts(text(merged['city_evidence'], 160)),
                 posted.isoformat() if posted else None, json.dumps(assess, ensure_ascii=False), stamp(), lid))
            self.audit(c, lid, 'updated', '更新核实/跟进状态：' + STAGES[merged['stage']], actor)
        return self.get(lid)


class Catalog:
    def __init__(self, fetcher=None):
        self.data = {'events': [], 'updated_at': None, 'error': '尚未同步', 'training': '训练时间及费用请在小程序「训练」查看，或咨询俱乐部。'}
        self.fetcher = fetcher
        self.lock = threading.Lock()

    def sync(self):
        if not self.lock.acquire(blocking=False): return self.data
        try:
            if self.fetcher:
                source = self.fetcher()
            else:
                ctx = ssl.create_default_context()
                # Windows trusted intermediates as well as root CAs; never disable certificate checks.
                if hasattr(ssl, 'enum_certificates'):
                    for store in ('ROOT', 'CA'):
                        for cert, encoding, trust in ssl.enum_certificates(store):
                            if encoding == 'x509_asn' and (trust is True or ssl.Purpose.SERVER_AUTH.oid in trust):
                                ctx.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(cert))
                    # OpenSSL may otherwise demand a self-signed root even when
                    # Windows explicitly trusts an intermediate CA. Hostname and
                    # certificate validation stay enabled; only installed trust is used.
                    ctx.verify_flags |= getattr(ssl, 'VERIFY_X509_PARTIAL_CHAIN', 0)
                url = API_ORIGIN + '/api/match-center/events?' + urllib.parse.urlencode({'city': '成都', 'page': 1})
                with urllib.request.urlopen(url, timeout=8, context=ctx) as response:
                    source = json.loads(response.read(2_000_000))
            items = source.get('items', [])
            events = []
            for item in items:
                if item.get('city') != '成都' or '银杏' not in str(item.get('venue', '')):
                    continue
                start, until = parse_time(item.get('starts_at')), parse_time(item.get('signup_until') or item.get('deadline'))
                now = datetime.now(timezone.utc)
                if item.get('status') != 'open' or item.get('signup_open') is not True or not start or start <= now or (until and until <= now):
                    continue
                eid = str(item.get('id', ''))
                if not re.fullmatch(r'[a-fA-F0-9-]{36}', eid): continue
                events.append({'id': eid, 'title': text(item.get('title'), 100), 'starts_at': start.isoformat(),
                    'time_text': start.astimezone(CST).strftime('%m月%d日 %H:%M'), 'venue': text(item.get('venue'), 80),
                    'payment_mode': item.get('payment_mode'), 'enrolled': item.get('enrolled'),
                    'miniapp_page': 'pages/match-center/detail?id=' + eid})
            self.data = {'events': sorted(events, key=lambda x: x['starts_at']), 'updated_at': stamp(),
                         'error': '', 'training': self.data['training']}
        except Exception as error:
            # Never keep stale events eligible for replies when a refresh fails.
            self.data = {**self.data, 'events': [], 'error': '公开赛事同步失败：' + type(error).__name__}
        finally:
            self.lock.release()
        return self.data

    def current(self):
        if not self.data['updated_at'] or (datetime.now(timezone.utc) - parse_time(self.data['updated_at'])).total_seconds() > 600:
            return {**self.data, 'events': [], 'error': self.data['error'] or '请先刷新赛事信息'}
        return {**self.data, 'events': [e for e in self.data['events'] if parse_time(e['starts_at']) > datetime.now(timezone.utc)]}


def make_reply(lead, catalog):
    if lead['assessment']['intent'] == 'training':
        body = '看到你在找乒乓球训练。你更想从基础动作开始，还是针对发球、接发球提升？可以按你的空闲时间再核对合适课程。'
        tail = '可在本平台的「银杏奖牌」小程序「训练」查看安排；具体费用、名额以课程页面为准。'
    elif lead['assessment']['intent'] == 'competition':
        events = catalog.get('events', [])
        if events:
            e = events[0]
            body = f'看到你在找成都乒乓球比赛。目前可查看 {e["time_text"]} 的「{e["title"]}」，在{e["venue"]}。'
        else:
            body = '看到你在找成都乒乓球比赛。可以先看看近期分组和参赛条件，选适合自己水平的一场。'
        tail = '可在本平台的「银杏奖牌」小程序「比赛」查看并报名，费用和报名状态以实时页面为准。'
    else:
        body = '看到你想在成都找球友。你一般哪天方便、平时打球是什么水平？可以先看看适合你的活动。'
        tail = '可在本平台的「银杏奖牌」小程序查看比赛、训练安排。'
    if lead['platform'] == 'channels':
        tail = tail.replace('本平台的', '微信')
    elif lead['platform'] in ('bilibili', 'tieba'):
        tail = '如果你需要，可以继续在这里问我时间和参与方式，我再根据你的需求说明。'
    return '你好，我是银杏乒乓球俱乐部的工作人员。' + body + tail


def register(app, require_login=None, is_admin=None, data_dir=None, catalog_fetcher=None, local_token=None):
    """No business database access. Existing admin sessions are checked by the host."""
    store = Store(data_dir or os.getenv('GINKGO_GROWTH_DATA') or BASE / 'growth-data')
    catalog = Catalog(catalog_fetcher)
    bp = Blueprint('ginkgo_growth', __name__)
    app.extensions['ginkgo_growth'] = {'store': store, 'catalog': catalog}
    rate = {}
    rate_lock = threading.Lock()

    def admin_guard(fn):
        @wraps(fn)
        def check(*args, **kwargs):
            if local_token:
                auth = request.headers.get('Authorization', '')
                if not secrets.compare_digest(auth, 'Bearer ' + local_token): return jsonify(error='请从本机桌面入口打开，或使用管理员登录'), 401
                g.growth_actor = '本机管理员'
            else:
                user = getattr(g, 'match_user', None)
                if not user or not is_admin(user): return jsonify(error='仅俱乐部管理员可使用获客工作台'), 403
                g.growth_actor = text(user.get('name') or user.get('id'), 50)
            if request.method != 'GET' and not request.is_json:
                return jsonify(error='请求须为 JSON'), 415
            return fn(*args, **kwargs)
        return require_login(check) if require_login else check

    @bp.before_request
    def preflight():
        if request.content_length and request.content_length > 128_000: return jsonify(error='一次最多导入50条，正文不超过128KB'), 413
        if local_token and request.host.split(':')[0] not in ('127.0.0.1', 'localhost', '[::1]'):
            return jsonify(error='本机版仅允许 localhost 访问'), 403

    @bp.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @bp.errorhandler(ValueError)
    def invalid(error): return jsonify(error=str(error)), 400

    @bp.errorhandler(LookupError)
    def missing(error): return jsonify(error=str(error)), 404

    @bp.get('/health')
    def health(): return jsonify(status='ok', version=VERSION, auto_send=False)

    @bp.get('/')
    def home(): return send_from_directory(BASE / 'growth-web', 'index.html')

    @bp.get('/assets/<path:name>')
    def assets(name): return send_from_directory(BASE / 'growth-web', name)

    @bp.get('/api/meta')
    @admin_guard
    def meta():
        return jsonify(version=VERSION, platforms=PLATFORMS, intents=INTENTS, stages=STAGES, actor=g.growth_actor,
                       mode='local' if local_token else 'server', auto_send=False, dispatch_connected=False,
                       ingestion='逐条核实录入／自己账号的咨询导出', name=BUSINESS,
                       public_origin=API_ORIGIN, districts=DISTRICTS)

    @bp.get('/api/overview')
    @admin_guard
    def overview():
        with store.db() as c:
            leads = [store.view(row) for row in c.execute("SELECT * FROM leads WHERE stage!='archived' ORDER BY created_at DESC LIMIT 2000")]
            stages = {stage: sum(x['stage'] == stage for x in leads) for stage in STAGES}
            platforms = {p: {'total': sum(x['platform'] == p for x in leads),
                             'booked': sum(x['platform'] == p and x['stage'] == 'booked' for x in leads)} for p in PLATFORMS}
            inquiries = c.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0]
        return jsonify(total=len(leads), qualified=sum(x['assessment']['eligible'] and x['confirmed'] and not store.contact_guard(x) for x in leads),
                       contacted=sum(x['contact_count'] > 0 for x in leads), booked=stages['booked'], stages=stages,
                       platforms=platforms, inquiries=inquiries,
                       due=sum(bool(x['follow_at'] and parse_time(x['follow_at']) <= datetime.now(timezone.utc) and x['stage'] not in ('blocked','closed','booked')) for x in leads),
                       actual_platform_sends=0, notice='联系与报名由人工凭据登记；本工具尚未接入自动发送与订单归因接口。')

    @bp.route('/api/leads', methods=['GET', 'POST'])
    @admin_guard
    def leads():
        if request.method == 'POST':
            lead, added = store.add(request.get_json() or {}, g.growth_actor)
            return jsonify(item=lead, added=added), 201 if added else 200
        with store.db() as c:
            rows = [store.view(row) for row in c.execute('SELECT * FROM leads ORDER BY created_at DESC LIMIT 2000')]
            delivery = {r['lead_id']:r['status'] for r in c.execute('''SELECT a.lead_id,a.status FROM delivery_attempts a
                WHERE a.id=(SELECT MAX(b.id) FROM delivery_attempts b WHERE b.lead_id=a.lead_id)''')}
        for row in rows:
            row['delivery_status'] = delivery.get(row['id'], 'confirmed' if row['contact_count'] else 'none')
        q, platform, stage = text(request.args.get('q'), 100), request.args.get('platform'), request.args.get('stage')
        rows = [x for x in rows if (not q or q in x['excerpt'] or q in x['alias']) and (not platform or x['platform'] == platform)
                and (x['stage'] == stage if stage else x['stage'] != 'archived')]
        rows.sort(key=lambda x: x['assessment']['score'], reverse=True)
        return jsonify(items=rows[:200], truncated=len(rows) > 200)

    @bp.get('/api/delivery-summary')
    @admin_guard
    def delivery_summary():
        with store.db() as c:
            counts={r['status']:r['n'] for r in c.execute('''SELECT a.status,COUNT(*) AS n FROM delivery_attempts a
                JOIN leads l ON l.id=a.lead_id WHERE a.id=(SELECT MAX(b.id) FROM delivery_attempts b WHERE b.lead_id=a.lead_id)
                AND l.stage NOT IN ('archived','blocked','closed','booked') GROUP BY a.status''')}
        return jsonify(counts={s:counts.get(s,0) for s in ('pending','not_visible','failed','confirmed')},
                       automatic_external_sending=False,recording_only=True)

    @bp.post('/api/classify')
    @admin_guard
    def classify_api():
        d = request.get_json() or {}
        return jsonify(classify(text(d.get('excerpt')), text(d.get('city_evidence')), d.get('posted_at')))

    @bp.post('/api/import')
    @admin_guard
    def imports():
        d = request.get_json() or {}
        if d.get('own_account_export') is not True:
            return jsonify(error='批量导入仅接收自己经营账号收到的咨询导出；公开第三方求助请逐条核实录入'), 400
        rows = d.get('rows')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 50: raise ValueError('一次导入1–50条')
        # Validate all rows before writes; malformed CSV does not leave a partial batch.
        for row in rows:
            if not isinstance(row, dict): raise ValueError('每行须为对象')
            validate_source(row.get('platform'), row.get('source_url'))
            if len(text(row.get('excerpt'))) < 6: raise ValueError('需求原文至少6字')
            classify(text(row.get('excerpt')), text(row.get('city_evidence')), row.get('posted_at'))
        added, duplicates = 0, 0
        for row in rows:
            _, fresh = store.add({**row, 'relation': 'inbound'}, g.growth_actor)
            added += int(fresh); duplicates += int(not fresh)
        return jsonify(added=added, duplicates=duplicates, sent=0)

    @bp.route('/api/leads/<lid>', methods=['GET', 'PATCH'])
    @admin_guard
    def detail(lid):
        if request.method == 'PATCH': return jsonify(item=store.update(lid, request.get_json() or {}, g.growth_actor))
        lead = store.get(lid)
        with store.db() as c:
            history = [dict(r) for r in c.execute('SELECT type,detail,actor,created_at FROM activity WHERE lead_id=? ORDER BY id DESC LIMIT 50', (lid,))]
            delivery = [dict(r) for r in c.execute('SELECT * FROM delivery_attempts WHERE lead_id=? ORDER BY id DESC LIMIT 10', (lid,))]
        return jsonify(item=lead, activity=history, delivery=delivery, contact_block=store.contact_guard(lead))

    @bp.post('/api/leads/<lid>/notes')
    @admin_guard
    def lead_note(lid):
        store.get(lid)
        d = request.get_json()
        if not isinstance(d, dict) or set(d) != {'note'} or not isinstance(d['note'], str) or not 2 <= len(d['note'].strip()) <= 1000:
            raise ValueError('请填写2至1000字的跟进备注')
        with store.db() as c:
            store.audit(c, lid, 'note', '跟进备注：' + d['note'].strip(), g.growth_actor)
        return jsonify(saved=True, sent=False)

    @bp.post('/api/leads/<lid>/delivery-attempts')
    @admin_guard
    def delivery_attempt(lid):
        d = request.get_json()
        allowed = {'account','content','evidence_url','status','note','submitted_in_platform','checked_in_platform','request_id'}
        if not isinstance(d, dict) or set(d) - allowed:
            raise ValueError('发送核对记录格式无效')
        if d.get('submitted_in_platform') is not True:
            raise ValueError('仅在已经在原平台点击发送后记录；本工具不会发送消息')
        account, content, note = (mask_contacts(text(d.get(k), n)) for k,n in [('account',60),('content',800),('note',1000)])
        status, request_id = d.get('status','pending'), d.get('request_id','')
        if status not in ('pending','not_visible','failed') or len(account)<2 or not content:
            raise ValueError('请填写实际账号、发送内容和有效核对状态')
        if not isinstance(request_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{12,80}',request_id):
            raise ValueError('发送核对请求编号无效，请重新打开表单')
        if status != 'pending' and (d.get('checked_in_platform') is not True or len(note)<2):
            raise ValueError('记录未显示或失败前，请核对原平台并填写结果说明')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM leads WHERE id=?',(lid,)).fetchone()
            if not row:raise LookupError('线索不存在')
            lead = store.view(row)
            evidence = validate_source(lead['platform'],d.get('evidence_url'))
            prior = c.execute('SELECT * FROM delivery_attempts WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if any(prior[k]!=v for k,v in [('lead_id',lid),('account',account),('content',content),('evidence_url',evidence)]):
                    return jsonify(error='请求编号已用于其他发送记录'),409
                return jsonify(item=dict(prior),recorded=False,contact_count=lead['contact_count'],sent=False)
            block=store.contact_guard(lead)
            if block:return jsonify(error=block),409
            now=stamp()
            cur=c.execute('''INSERT INTO delivery_attempts(lead_id,account,content,evidence_url,status,note,actor,created_at,checked_at,request_id)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(lid,account,content,evidence,status,note,g.growth_actor,now,now if status!='pending' else None,request_id))
            store.audit(c,lid,'delivery_attempt','发送核对：'+{'pending':'已提交待核实','not_visible':'核对未显示','failed':'平台提示失败'}[status]+'；未计为已联系。'+note,g.growth_actor)
            item=dict(c.execute('SELECT * FROM delivery_attempts WHERE id=?',(cur.lastrowid,)).fetchone())
        return jsonify(item=item,recorded=True,contact_count=lead['contact_count'],sent=False),201

    @bp.patch('/api/leads/<lid>/delivery-attempts/<int:aid>')
    @admin_guard
    def delivery_check(lid,aid):
        d=request.get_json()
        if not isinstance(d,dict) or set(d)-{'status','note','checked_in_platform'}:
            raise ValueError('发送核对结果格式无效')
        status=d.get('status');note=mask_contacts(text(d.get('note'),1000))
        if status not in ('confirmed','not_visible','failed') or d.get('checked_in_platform') is not True or len(note)<2:
            raise ValueError('请在原平台核对，并填写可见、未显示或失败的结果说明')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM leads WHERE id=?',(lid,)).fetchone()
            attempt=c.execute('SELECT * FROM delivery_attempts WHERE id=? AND lead_id=?',(aid,lid)).fetchone()
            if not row or not attempt:raise LookupError('发送核对记录不存在')
            lead=store.view(row)
            if attempt['status']==status:return jsonify(item=dict(attempt),changed=False,contact_count=lead['contact_count'],sent=False)
            if attempt['status']=='confirmed':return jsonify(error='已核实发布的记录不能改回未发布'),409
            if status=='confirmed':
                block=store.contact_guard(lead,include_delivery=False)
                if block:return jsonify(error=block),409
                c.execute("UPDATE leads SET stage='contacted',contact_count=contact_count+1,last_contact_at=?,updated_at=? WHERE id=?",(stamp(),stamp(),lid))
                store.audit(c,lid,'manual_contact','人工核实发布｜账号：'+attempt['account']+'｜'+attempt['content']+'｜凭据：'+attempt['evidence_url'],g.growth_actor)
            now=stamp()
            c.execute('UPDATE delivery_attempts SET status=?,note=?,checked_at=? WHERE id=?',(status,note,now,aid))
            store.audit(c,lid,'delivery_check','发送核对：'+{'confirmed':'人工核实可见','not_visible':'核对未显示','failed':'平台提示失败'}[status]+'。'+note,g.growth_actor)
        return jsonify(changed=True,sent=False,platform_verified=False,operator_verified=True,item=store.get(lid))

    @bp.post('/api/leads/<lid>/draft')
    @admin_guard
    def draft(lid):
        lead = store.get(lid)
        block = store.contact_guard(lead)
        if block: return jsonify(error=block), 409
        engine=app.extensions['ginkgo_growth'].get('automation')
        if engine and engine.ai.config()['enabled']:
            result=engine.analyze_lead(lead)
            return jsonify(reply=result['reply'],source_url=lead['source_url'],sent=False,
                           channel='原文公开回复' if lead['relation']=='public_request' else '原咨询会话',
                           account='须在平台确认发送账号',transport='人工平台工作台',ai=result)
        reply = make_reply(lead, catalog.current())
        with store.db() as c:
            c.execute('UPDATE leads SET latest_reply=?,reply_version=reply_version+1,updated_at=? WHERE id=?', (reply, stamp(), lid))
            store.audit(c, lid, 'draft', '生成待核对回复；未发送', g.growth_actor)
        return jsonify(reply=reply, source_url=lead['source_url'], channel='原文公开回复' if lead['relation'] == 'public_request' else '原咨询会话',
                       sent=False, account='须在平台确认发送账号', transport='人工平台工作台')

    @bp.post('/api/leads/<lid>/contact')
    @admin_guard
    def contacted(lid):
        d = request.get_json() or {}
        with store.db() as c:
            # Reserve under a database write lock so double-clicks cannot bypass contact limits.
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone()
            if not row: raise LookupError('线索不存在')
            lead = store.view(row)
            block = store.contact_guard(lead)
            if block: return jsonify(error=block), 409
            content = mask_contacts(text(d.get('content'), 800))
            evidence = validate_source(lead['platform'], d.get('evidence_url'))
            if d.get('sent_in_platform') is not True or not content or len(text(d.get('account'), 60)) < 2:
                raise ValueError('请填写实际发送账号、内容、原文凭据，并确认已在平台发送')
            c.execute("UPDATE leads SET stage='contacted',contact_count=contact_count+1,last_contact_at=?,updated_at=? WHERE id=?", (stamp(), stamp(), lid))
            store.audit(c, lid, 'manual_contact', '人工登记｜账号：' + text(d['account'],60) + '｜' + content + '｜凭据：' + evidence, g.growth_actor)
        return jsonify(item=store.get(lid), recorded=True, platform_verified=False)

    @bp.post('/api/leads/<lid>/dispatch')
    @admin_guard
    def dispatch(lid):
        store.get(lid)
        return jsonify(error='尚无已获授权的发送连接器。请在平台核对账号和原文后回复，再登记实际结果。', sent=False), 409

    @bp.post('/api/leads/<lid>/stop')
    @admin_guard
    def stop(lid):
        lead = store.get(lid)
        with store.db() as c:
            c.execute('INSERT OR IGNORE INTO suppressions(person_key,created_at) VALUES(?,?)', (lead['person_key'], stamp()))
            c.execute("UPDATE leads SET stopped=1,stage='blocked',follow_at=NULL,updated_at=? WHERE person_key=?", (stamp(), lead['person_key']))
            store.audit(c, lid, 'stop', '停止联系；同平台同名/同来源后续录入一并抑制', g.growth_actor)
        return jsonify(stopped=True)

    @bp.get('/api/catalog')
    @admin_guard
    def current_catalog(): return jsonify(catalog.current())

    @bp.post('/api/catalog/sync')
    @admin_guard
    def sync_catalog(): return jsonify(catalog.sync())

    @bp.get('/api/search-plan')
    @admin_guard
    def search_plan():
        generic = ['成都 乒乓球 哪里学', '成都 乒乓球 找教练', '成都 成人乒乓球 零基础',
                   '成都 乒乓球 比赛 报名', '成都 乒乓球 积分赛 新手', '成都 乒乓球 找搭子',
                   '成都 青羊 乒乓球 训练', '成都 白果林 乒乓球', '成都 乒乓球 团体赛', '银杏乒乓球俱乐部']
        out = []
        for platform, p in PLATFORMS.items():
            for q in generic:
                out.append({'platform': platform, 'keyword': q,
                            'url': p['search'].format(q=urllib.parse.quote(q)) if p['search'] else p['home'],
                            'note': '在微信手机端搜索此词' if platform == 'channels' else '打开后查看原文及最新评论，逐条核实'})
        return jsonify(items=out)

    @bp.get('/api/content-plan')
    @admin_guard
    def content_plan():
        themes = [
            ('第一次学乒乓球，先练哪三个动作？', '基础训练', '握拍、准备姿势、近台定点击球。拍摄教练真实示范，展示初学者能理解的练习步骤。'),
            ('成都球友第一次报积分赛，先看什么？', '比赛招募', '展示真实比赛现场、水平分组、日期与报名页。提醒费用及参赛资格以小程序实时内容为准。'),
            ('接发球总吃旋转？先分清这两件事', '技术练习', '请教练示范看触球动作与来球弧线的练习，不承诺几节课速成。'),
            ('一个人来打球，会尴尬吗？', '到店体验', '拍摄真实的公共球台与活动流程，介绍如何按水平选择比赛或训练；不要冒充学员评价。'),
            ('双人团体怎么打？低分单打、高分单打、双打', '赛制讲解', '用两位教练真实演示双人单单双顺序，说明三人团体由双方自行排阵。'),
            ('工作日晚上想练球，怎么安排？', '训练咨询', '展示当前实际课表的查看方式；邀请用户说明基础和空闲时间，再核对合适课程。'),
            ('这周来打一场适合自己的比赛', '比赛招募', '以当天开放的实际赛事为准，展示分组与参赛条件；过期或已结束的比赛不再招募。'),
        ]
        out = []
        current = catalog.current()
        for day, (heading, kind, shot) in enumerate(themes, 1):
            for p in list(PLATFORMS)[:4]:
                is_match = kind in ('比赛招募','赛制讲解')
                cta = f'在本平台「{MINIAPP}」小程序的「{"比赛" if is_match else "训练"}」查看实时安排。'
                if p == 'channels': cta = cta.replace('本平台', '微信')
                event = current['events'][0] if is_match and current['events'] else None
                detail = f'当前可查看：{event["title"]}，{event["time_text"]}。' if event else ''
                body = f'【银杏乒乓球俱乐部 · {kind}】\n{heading}\n成都球友们，{detail}想了解具体安排，可以在评论区说说你的水平和方便的时间，我们按实际需求说明。\n{cta}\n具体费用、名额及规则以小程序实时页面为准。'
                out.append({'day':day,'platform':p,'title':heading,'kind':kind,'shot_list':shot,
                            'body':body,'tags':['成都乒乓球','银杏乒乓球俱乐部','乒乓球训练' if not is_match else '乒乓球比赛'],
                            'published':False,'source':'俱乐部公告草稿；拍摄和发布前核实实际情况'})
        return jsonify(items=out, published=False)

    @bp.get('/api/campaigns')
    @admin_guard
    def campaigns():
        with store.db() as c:
            rows = [dict(r) for r in c.execute('SELECT * FROM campaigns ORDER BY created_at,id')]
        for row in rows:
            row['path'] = PREFIX + '/club/' + row['id']
            row['miniapp_page'] = 'pages/booking/club' if row['intent'] == 'training' else 'pages/match-center/index'
            row['guidance'] = '优先使用该平台「银杏奖牌」小程序卡片；H5链接只在平台许可的场景投放。'
        return jsonify(items=rows)

    @bp.get('/club/<cid>')
    def club(cid):
        with store.db() as c:
            row = c.execute('SELECT id FROM campaigns WHERE id=?', (cid,)).fetchone()
        if not row: raise LookupError('活动入口不存在')
        return send_from_directory(BASE / 'growth-web', 'club.html')

    @bp.get('/public/campaign/<cid>')
    def public_campaign(cid):
        with store.db() as c:
            row = c.execute('SELECT id,name,platform,intent FROM campaigns WHERE id=?', (cid,)).fetchone()
        if not row: raise LookupError('入口不存在')
        # Page views are not counted as people or verified registrations.
        return jsonify(campaign=dict(row), club=BUSINESS, miniapp=MINIAPP, catalog=catalog.current(),
                       privacy='仅自愿提交的信息用于本次比赛/训练咨询跟进，不用于第三方营销。')

    @bp.post('/public/inquiry')
    def inquiry():
        d = request.get_json(silent=True) or {}
        if not request.is_json: return jsonify(error='请从咨询页面提交'), 415
        if d.get('website'): return jsonify(ok=True)
        if d.get('consent') is not True or d.get('adult_or_guardian') is not True:
            raise ValueError('请由成年人本人或监护人确认咨询和联系方式使用说明')
        contact = text(d.get('contact'), 100)
        if not contact or not text(d.get('alias'), 40): raise ValueError('请填写称呼和你自愿提供的联系方式')
        if d.get('interest') not in ('training', 'competition', 'practice'): raise ValueError('请选择咨询项目')
        # Ephemeral abuse key only; IPs are never stored in leads or the database.
        key = hashlib.sha256(request.remote_addr.encode()).hexdigest()
        with rate_lock:
            rate_keys = list(rate)
            for old in rate_keys:
                if time.time() - rate[old][0] > 3600: rate.pop(old, None)
            entries = rate.setdefault(key, [time.time(), 0])
            if entries[1] >= 5: return jsonify(error='提交较多，请稍后再试'), 429
            entries[1] += 1
        cid = text(d.get('campaign_id'), 60)
        with store.db() as c:
            if not c.execute('SELECT 1 FROM campaigns WHERE id=?', (cid,)).fetchone(): raise ValueError('咨询入口无效')
            c.execute('INSERT INTO inquiries(id,campaign_id,alias,interest,district,availability,contact,consent_at,consent_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (secrets.token_hex(10), cid, text(d['alias'],40), d['interest'], text(d.get('district'),40),
                       text(d.get('availability'),120), contact, stamp(), 'inquiry-v1', stamp()))
        return jsonify(ok=True, message='咨询已记录。这不是正式报名；比赛、训练请以小程序内报名结果为准。'), 201

    @bp.get('/api/inquiries')
    @admin_guard
    def inquiries():
        with store.db() as c:
            items = [dict(row) for row in c.execute('SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 200')]
        return jsonify(items=items)

    @bp.patch('/api/inquiries/<iid>')
    @admin_guard
    def follow_inquiry(iid):
        d = request.get_json() or {}
        if d.get('stage') not in ('new', 'contacted', 'closed'): raise ValueError('咨询状态无效')
        with store.db() as c:
            row = c.execute('SELECT id FROM inquiries WHERE id=?', (iid,)).fetchone()
            if not row: raise LookupError('咨询不存在')
            c.execute('UPDATE inquiries SET stage=? WHERE id=?', (d['stage'], iid))
            store.audit(c, None, 'inquiry', '咨询 ' + iid + ' 跟进状态：' + d['stage'], g.growth_actor)
        return jsonify(ok=True)

    @bp.get('/api/export')
    @admin_guard
    def export():
        with store.db() as c:
            rows = [dict(r) for r in c.execute('SELECT platform,alias,source_url,excerpt,posted_at,stage,created_at FROM leads WHERE stage!=?', ('archived',))]
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        writer.writerow(['平台','称呼','来源原文','需求原文','发布时间','跟进状态','录入时间'])
        for row in rows:
            values = [PLATFORMS[row['platform']]['name'],row['alias'],row['source_url'],row['excerpt'],row['posted_at'],STAGES[row['stage']],row['created_at']]
            writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=','+','-','@')) else str(v or '') for v in values])
        return Response('\ufeff'+out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=ginkgo-leads.csv'})

    @bp.post('/api/backup')
    @admin_guard
    def backup():
        path = store.root / 'backups'
        path.mkdir(exist_ok=True)
        name = 'growth-' + datetime.now(CST).strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(2) + '.sqlite3'
        with store.db() as src:
            dest = sqlite3.connect(path / name)
            try: src.backup(dest)
            finally: dest.close()
        return jsonify(ok=True, filename=name)

    import growth_automation
    automation = growth_automation.register(bp,admin_guard,store,catalog,
        {'validate_source':validate_source,'classify':classify,'platforms':PLATFORMS,'intents':INTENTS},app)
    import growth_channels
    growth_channels.register(bp, admin_guard, automation, app)
    app.register_blueprint(bp, url_prefix=PREFIX)
    return bp


if __name__ == '__main__':
    from flask import Flask
    root = Path(os.getenv('GINKGO_GROWTH_DATA') or BASE / 'growth-data')
    root.mkdir(exist_ok=True)
    token_path = root / 'local-access.json'
    token = secrets.token_urlsafe(32)
    token_path.write_text(json.dumps({'token':token}), encoding='utf-8')
    application = Flask(__name__)
    register(application, data_dir=root, local_token=token)
    port = int(os.getenv('GINKGO_GROWTH_PORT', '8796'))
    print('Ginkgo acquisition workbench on localhost:' + str(port), flush=True)
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', port, application, use_reloader=False, threaded=True)
