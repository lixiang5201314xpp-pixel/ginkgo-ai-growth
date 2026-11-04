"""Official inbound customer-service connectors; never a social crawler.

WeChat: encrypted JSON callbacks, official AES-256-CBC envelope.
Douyin: signed private-message webhooks and business-token reply API.
XHS stays disabled until its message-encryption SDK is verified. Kuaishou's
current console exposes human service/shortcuts, not a documented AI webhook.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import sqlite3
import struct
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode

from flask import Response, g, jsonify, request
from growth_ai import AIError, Vault, redacted, tls_context, ground_training_schedule

VERSION = 'growth-channels-1.0.1'
APPS = {'wechat': 'wx740dd63e687f4ad3', 'douyin': 'tt192a6f978753aed601',
        'xiaohongshu': '6ac85eecb0598000019f06e1', 'kuaishou': 'ks718042668477656413'}
LABELS = {'wechat': '微信', 'douyin': '抖音', 'xiaohongshu': '小红书', 'kuaishou': '快手'}
SUPPORTED = {'wechat', 'douyin'}
ORIGIN = 'https://qiuchen.yinxingpingpang.com/api/match-center/growth'
STOP = re.compile(r'转人工|人工客服|别再回复|停止回复|停止联系|不要联系|勿扰|投诉|退款|退费')


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def sha1_parts(*parts):
    return hashlib.sha1(''.join(sorted(str(x) for x in parts)).encode()).hexdigest()


def decrypt_wechat(ciphertext, encoding_key, appid):
    # The standalone Cryptodome namespace is isolated from existing dependencies.
    vendor = Path(__file__).with_name('channel-vendor')
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    from Cryptodome.Cipher import AES
    key = base64.b64decode(encoding_key + '=', validate=True)
    if len(key) != 32:
        raise ValueError('Invalid encoding key')
    encrypted = base64.b64decode(ciphertext, validate=True)
    if not encrypted or len(encrypted) % 16 or len(encrypted) > 128000:
        raise ValueError('Invalid encrypted body')
    plain = AES.new(key, AES.MODE_CBC, key[:16]).decrypt(encrypted)
    pad = plain[-1]
    if not 1 <= pad <= 32 or plain[-pad:] != bytes([pad]) * pad:
        raise ValueError('Invalid message padding')
    plain = plain[:-pad]
    if len(plain) < 20:
        raise ValueError('Truncated message')
    length = struct.unpack('!I', plain[16:20])[0]
    if length > len(plain) - 20:
        raise ValueError('Truncated content')
    if not hmac.compare_digest(plain[20 + length:], appid.encode()):
        raise ValueError('Wrong recipient application')
    data = json.loads(plain[20:20 + length])
    if not isinstance(data, dict):
        raise ValueError('Message must be an object')
    return data


class ChannelError(RuntimeError):
    pass


def official_request(host, path, body, headers=None):
    """Pinned official hosts, validated TLS, no proxy, redirects or raw error logs."""
    if host not in {'api.weixin.qq.com', 'open.douyin.com'}:
        raise ChannelError('Unapproved official host')
    conn = http.client.HTTPSConnection(host, timeout=12, context=tls_context())
    try:
        payload = json.dumps(body, ensure_ascii=False).encode()
        conn.request('POST', path, payload, {'Content-Type': 'application/json', **(headers or {})})
        response = conn.getresponse()
        raw = response.read(300001)
        if response.status != 200 or len(raw) > 300000:
            raise ChannelError('官方接口 HTTP ' + str(response.status))
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except ChannelError:
        raise
    except (OSError, ValueError, http.client.HTTPException):
        raise ChannelError('官方接口连接或返回格式异常') from None
    finally:
        conn.close()


class Channels:
    def __init__(self, engine, crypt=None, transport=None, clock=None):
        self.engine = engine
        self.root = engine.store.root
        self.path = self.root / 'channel-inbox.sqlite3'
        self.private = self.root / 'secrets' / 'channels.dpapi'
        self.crypt = crypt or Vault.crypt
        self.transport = transport or official_request
        self.clock = clock or time.time
        self.lock = threading.Lock()
        self.wakeup = threading.Event()
        self.thread = None
        self.tokens = {}
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS inbox(
              id TEXT PRIMARY KEY, platform TEXT NOT NULL, sender TEXT NOT NULL,
              created REAL NOT NULL, received REAL NOT NULL, state TEXT NOT NULL,
              payload BLOB NOT NULL, reply BLOB, detail TEXT NOT NULL DEFAULT '', updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS inbox_pending ON inbox(state,received);
            CREATE TABLE IF NOT EXISTS control(platform TEXT PRIMARY KEY, verified REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS handoff(platform TEXT NOT NULL,sender TEXT NOT NULL,created REAL NOT NULL,
              PRIMARY KEY(platform,sender));
            ''')

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=2)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def seal(self, data):
        return self.crypt(json.dumps(data, ensure_ascii=False).encode())

    def unseal(self, data):
        return json.loads(self.crypt(bytes(data), True))

    def configs(self):
        if not self.private.exists():
            return {}
        return self.unseal(self.private.read_bytes())

    def save(self, configs):
        self.private.parent.mkdir(exist_ok=True)
        temporary = self.private.with_suffix('.tmp-' + secrets.token_hex(4))
        temporary.write_bytes(self.seal(configs))
        os.replace(temporary, self.private)
        self.tokens.clear()

    def config(self, platform):
        return {'appid': APPS[platform], 'receive': False, 'automatic': False,
                **self.configs().get(platform, {})}

    def update(self, platform, data):
        if platform not in SUPPORTED:
            raise ValueError('此平台尚未完成官方接口接入，不能启用自动收发')
        if not isinstance(data, dict):
            raise ValueError('配置格式无效')
        cfg = self.config(platform)
        previous = dict(cfg)
        if 'appid' in data and data['appid'] != APPS[platform]:
            raise ValueError('仅允许配置已核对的银杏小程序')
        for field in ('token', 'aes_key', 'webhook_secret', 'business_openid'):
            if field in data and data[field]:
                cfg[field] = str(data[field]).strip()
        if data.get('generate_wechat_keys') is True and platform == 'wechat':
            if cfg.get('token') or cfg.get('aes_key'):
                raise ValueError('已有回调密钥，不会自动覆盖')
            cfg['token'] = secrets.token_hex(16)
            cfg['aes_key'] = base64.b64encode(secrets.token_bytes(32)).decode().rstrip('=')
        if platform == 'wechat':
            if not re.fullmatch('[A-Za-z0-9]{3,32}', cfg.get('token', '')):
                raise ValueError('微信 Token 应为3至32位英文字母或数字')
            if not re.fullmatch('[A-Za-z0-9+/]{43}', cfg.get('aes_key', '')):
                raise ValueError('EncodingAESKey 应为43位有效密钥')
        else:
            if not re.fullmatch('[A-Za-z0-9_-]{12,256}', cfg.get('webhook_secret', '')):
                raise ValueError('请填写抖音 Webhook 专用密钥，不能使用小程序登录 AppSecret')
            if not re.fullmatch('[A-Za-z0-9_-]{8,128}', cfg.get('business_openid', '')):
                raise ValueError('请填写已授权经营账号对应的 OpenID')
        for field in ('receive', 'automatic'):
            if field in data:
                if not isinstance(data[field], bool):
                    raise ValueError('开关必须为布尔值')
                cfg[field] = data[field]
        changed_key = any(previous.get(k) != cfg.get(k) for k in ('token', 'aes_key', 'webhook_secret', 'business_openid'))
        if changed_key:
            cfg['automatic'] = False
            with self.db() as c:
                c.execute('DELETE FROM control WHERE platform=?', (platform,))
        if cfg['automatic']:
            if not cfg['receive']:
                raise ValueError('请先启用接收并完成平台验证')
            with self.db() as c:
                verified = c.execute('SELECT verified FROM control WHERE platform=?', (platform,)).fetchone()
            if not verified or not verified[0]:
                raise ValueError('平台尚未完成真实回调验证，自动回复未开启')
            self.engine.ai.require_ready()
        configs = self.configs()
        configs[platform] = cfg
        self.save(configs)
        return self.status()

    def status(self):
        configs = self.configs()
        with self.db() as c:
            counts = [dict(r) for r in c.execute('SELECT platform,state,count(*) AS n FROM inbox GROUP BY platform,state')]
            verified = {r['platform']: r['verified'] for r in c.execute('SELECT * FROM control')}
        return {'version': VERSION, 'items': [
            {'platform': p, 'name': LABELS[p], 'appid': APPS[p], 'supported': p in SUPPORTED,
             'configured': bool(configs.get(p)), 'receive': configs.get(p, {}).get('receive', False),
             'automatic': configs.get(p, {}).get('automatic', False), 'verified_at': verified.get(p, 0),
             'callback': ORIGIN + '/callbacks/' + p if p in SUPPORTED else '',
             'reason': ('微信加密客服消息' if p == 'wechat' else '抖音已授权经营账号的私信回复' if p == 'douyin'
                        else '待官方消息解密 SDK／测试向量核实，未启用推送' if p == 'xiaohongshu'
                        else '当前官方工作台只有客服与话术管理，尚无已验证的第三方收发接口')}
            for p in APPS], 'counts': counts, 'worker_running': bool(self.thread and self.thread.is_alive())}

    def verified(self, platform):
        with self.db() as c:
            c.execute('INSERT INTO control(platform,verified) VALUES(?,?) ON CONFLICT(platform) DO UPDATE SET verified=excluded.verified',
                      (platform, self.clock()))

    def enqueue(self, platform, message):
        required = ('message_id', 'sender', 'text', 'created')
        if any(not message.get(x) for x in required):
            raise ValueError('Incomplete customer message')
        created = float(message['created'])
        if created > self.clock() + 300 or created < self.clock() - (48 if platform == 'wechat' else 24) * 3600:
            raise ValueError('Message outside reply window')
        ident = digest(platform + ':' + str(message['message_id']))
        sender = digest(platform + ':' + str(message['sender']))
        message['text'] = redacted(message['text'])[:800]
        payload = self.seal(message)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            # A replay never triggers additional processing or AI usage.
            if c.execute('SELECT 1 FROM inbox WHERE id=?', (ident,)).fetchone():
                return ident
            handoff = c.execute('SELECT 1 FROM handoff WHERE platform=? AND sender=?', (platform, sender)).fetchone()
            state = 'human' if handoff or STOP.search(message['text']) else 'queued'
            if state == 'human':
                c.execute('INSERT OR IGNORE INTO handoff VALUES(?,?,?)', (platform, sender, self.clock()))
                c.execute("UPDATE inbox SET state='human' WHERE platform=? AND sender=? AND state IN ('queued','prepared')", (platform, sender))
            c.execute('INSERT INTO inbox(id,platform,sender,created,received,state,payload,updated) VALUES(?,?,?,?,?,?,?,?)',
                      (ident, platform, sender, created, self.clock(), state, payload, self.clock()))
        self.wakeup.set()
        return ident

    def receive_wechat(self, cfg):
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        if not timestamp.isdigit() or abs(self.clock() - int(timestamp)) > 600 or not 1 <= len(nonce) <= 256:
            return Response('invalid timestamp', status=403)
        if request.method == 'GET':
            actual = request.args.get('signature', '')
            expected = sha1_parts(cfg['token'], timestamp, nonce)
            if not hmac.compare_digest(actual, expected):
                return Response('invalid signature', status=403)
            echo = request.args.get('echostr', '')
            if len(echo) > 1024:
                return Response('invalid challenge', status=400)
            self.verified('wechat')
            return Response(echo, mimetype='text/plain')
        envelope = request.get_json(silent=True)
        if not isinstance(envelope, dict) or request.args.get('encrypt_type') != 'aes':
            return Response('encrypted JSON required', status=400)
        encrypted = envelope.get('Encrypt')
        if not isinstance(encrypted, str) or len(encrypted) > 128000:
            return Response('invalid envelope', status=400)
        expected = sha1_parts(cfg['token'], timestamp, nonce, encrypted)
        if not hmac.compare_digest(request.args.get('msg_signature', ''), expected):
            return Response('invalid signature', status=403)
        data = decrypt_wechat(encrypted, cfg['aes_key'], cfg['appid'])
        self.verified('wechat')
        if data.get('MsgType') == 'text':
            self.enqueue('wechat', {'message_id': str(data.get('MsgId', '')), 'sender': data.get('FromUserName'),
                                   'text': data.get('Content'), 'created': data.get('CreateTime')})
        # Non-text events are preserved for administrator review, never sent to AI.
        else:
            self.record_event('wechat', data)
        return Response('success', mimetype='text/plain')

    def record_event(self, platform, data):
        ident = digest(platform + ':event:' + json.dumps(data, sort_keys=True, ensure_ascii=False))
        with self.db() as c:
            c.execute('INSERT OR IGNORE INTO inbox(id,platform,sender,created,received,state,payload,updated) VALUES(?,?,?,?,?,?,?,?)',
                      (ident, platform, '', self.clock(), self.clock(), 'event', self.seal(data), self.clock()))

    def receive_douyin(self, cfg):
        raw = request.get_data(cache=True)
        expected = hashlib.sha1(cfg['webhook_secret'].encode() + raw).hexdigest()
        if not hmac.compare_digest(request.headers.get('X-Douyin-Signature', ''), expected):
            return Response('invalid signature', status=403)
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('client_key') not in ('', cfg['appid']):
            return Response('wrong application', status=403)
        if data.get('event') == 'verify_webhook':
            challenge = data.get('content', {}).get('challenge')
            if not isinstance(challenge, (int, str)) or len(str(challenge)) > 256:
                return Response('invalid challenge', status=400)
            self.verified('douyin')
            return Response(json.dumps({'challenge': challenge}), mimetype='text/plain')
        if data.get('client_key') != cfg['appid']:
            return Response('wrong application', status=403)
        content = data.get('content')
        if not isinstance(content, dict):
            return Response('invalid content', status=400)
        # Outgoing events are also delivered: never turn the robot's own reply into a new question.
        if data.get('event') == 'im_send_msg':
            if data.get('from_user_id') == cfg['business_openid'] and not content.get('source'):
                sender = digest('douyin:' + str(data.get('to_user_id', '')))
                with self.db() as c:
                    c.execute('INSERT OR IGNORE INTO handoff VALUES(?,?,?)', ('douyin', sender, self.clock()))
                    c.execute("UPDATE inbox SET state='human' WHERE platform='douyin' AND sender=? AND state IN ('queued','prepared')", (sender,))
            self.record_event('douyin', data)
            return Response('success', mimetype='text/plain')
        if data.get('event') == 'im_receive_msg':
            if data.get('to_user_id') != cfg['business_openid'] or data.get('from_user_id') == cfg['business_openid']:
                return Response('wrong business account', status=403)
            if content.get('message_type') == 'text' and content.get('conversation_type') == 1:
                self.enqueue('douyin', {'message_id': content.get('server_message_id'), 'sender': data.get('from_user_id'),
                    'conversation_id': content.get('conversation_short_id'), 'text': content.get('text'),
                    'created': float(content.get('create_time', 0)) / 1000})
            else:
                self.record_event('douyin', data)
        else:
            self.record_event('douyin', data)
        return Response('success', mimetype='text/plain')

    def access_token(self, platform, cfg):
        cache_key = platform + ':' + digest(json.dumps(cfg, sort_keys=True))
        cache = self.tokens.get(cache_key)
        if cache and cache[1] > self.clock() + 120:
            return cache[0]
        if platform == 'wechat':
            secret = os.getenv('MATCH_WECHAT_SECRET', '')
            if not secret:
                raise ChannelError('服务器缺少现有微信接口凭据，请检查配置，不要重置密钥')
            data = self.transport('api.weixin.qq.com', '/cgi-bin/stable_token',
                {'grant_type': 'client_credential', 'appid': cfg['appid'], 'secret': secret, 'force_refresh': False})
            token, expiry = data.get('access_token'), data.get('expires_in')
        else:
            data = self.transport('open.douyin.com', '/oauth/business_token/',
                {'client_key': cfg['appid'], 'client_secret': cfg['webhook_secret'],
                 'open_id': cfg['business_openid'], 'scope': 'im.direct_message'})
            token, expiry = data.get('biz_token'), data.get('biz_expires_in')
        if not isinstance(token, str) or not isinstance(expiry, (int, float)) or expiry <= 120:
            raise ChannelError('官方授权令牌验证失败，请核对账号与权限')
        self.tokens[cache_key] = (token, self.clock() + min(expiry, 86400))
        return token

    def send(self, platform, cfg, message, reply):
        token = self.access_token(platform, cfg)
        if platform == 'wechat':
            result = self.transport('api.weixin.qq.com', '/cgi-bin/message/custom/send?' + urlencode({'access_token': token}),
                {'touser': message['sender'], 'msgtype': 'text', 'text': {'content': reply}})
            if result.get('errcode') != 0:
                raise ChannelError('微信发送未确认，错误码 ' + str(result.get('errcode')))
            return
        result = self.transport('open.douyin.com', '/im/send/msg/?' + urlencode({'open_id': cfg['business_openid']}),
            {'scene': 'im_reply_msg', 'to_user_id': message['sender'], 'conversation_id': message['conversation_id'],
             'msg_id': message['message_id'], 'content': {'msg_type': 1, 'text': {'text': reply}}}, {'access-token': token})
        if result.get('data', {}).get('error_code') != 0 or result.get('extra', {}).get('error_code', 0) != 0 or not result.get('msg_id'):
            raise ChannelError('抖音发送未确认，错误码 ' + str(result.get('data', {}).get('error_code')))

    def process_one(self):
        with self.lock:
            enabled = [p for p in SUPPORTED if self.config(p)['automatic'] and self.config(p)['receive']]
            if not enabled:
                return False
            with self.db() as c:
                # A crash during send cannot safely be retried: prefer human review to double sending.
                c.execute("UPDATE inbox SET state='uncertain',detail='上次发送中断，请人工核对，未自动重发' WHERE state='sending' AND updated<?", (self.clock() - 180,))
                marks = ','.join('?' for _ in enabled)
                row = c.execute("SELECT * FROM inbox WHERE state IN ('queued','prepared') AND platform IN (" + marks + ") ORDER BY received LIMIT 1", enabled).fetchone()
            if not row:
                return False
            cfg = self.config(row['platform'])
            if not cfg['automatic'] or not cfg['receive']:
                return False
            platform = row['platform']
            window = (48 if platform == 'wechat' else 24) * 3600
            if row['created'] < self.clock() - window + 60:
                self.set_state(row['id'], 'expired', '超过平台回复时限，未发送')
                return True
            with self.db() as c:
                stopped = c.execute('SELECT 1 FROM handoff WHERE platform=? AND sender=?', (platform, row['sender'])).fetchone()
                recent = c.execute("SELECT count(*) FROM inbox WHERE platform=? AND sender=? AND state IN ('sent','sending','uncertain') AND received>?", (platform, row['sender'], self.clock() - 3600)).fetchone()[0]
            if stopped or recent >= 6:
                self.set_state(row['id'], 'human', '已转人工或本小时接待次数已满')
                return True
            message = self.unseal(row['payload'])
            try:
                if row['reply']:
                    reply = self.unseal(row['reply'])['text']
                else:
                    current = self.engine.catalog.current()
                    if not current.get('updated_at'):
                        self.engine.catalog.sync()
                    source = {'platform': 'channels' if platform == 'wechat' else platform, 'excerpt': message['text']}
                    analysis = self.engine.ai.analyze(source, self.engine.catalog.current()['events'], 'inbound_question')
                    reply = analysis['reply']
                    if not analysis.get('reply'):
                        raise AIError('需要人工确认', 'human_needed')
                    with self.db() as c:
                        c.execute("UPDATE inbox SET state='prepared',reply=?,updated=? WHERE id=?", (self.seal({'text': reply}), self.clock(), row['id']))
                # Revalidate queued replies too; the encrypted inbox may contain pre-upgrade text.
                reply = re.sub(r'^(?:【(?:AI接待|银杏客服)】\s*)+', '', reply)
                reply = '【银杏客服】' + ground_training_schedule(reply, self.engine.catalog.current().get('events', []))
                with self.db() as c:
                    c.execute("UPDATE inbox SET reply=?,updated=? WHERE id=?", (self.seal({'text': reply}), self.clock(), row['id']))
                # Re-read stop/config switches after the potentially slow AI call.
                cfg = self.config(platform)
                with self.db() as c:
                    current_state = c.execute('SELECT state FROM inbox WHERE id=?', (row['id'],)).fetchone()[0]
                if not cfg['automatic'] or not cfg['receive'] or current_state == 'human':
                    return False
                # Verify token BEFORE marking sending. No customer message in this step.
                self.access_token(platform, cfg)
                self.set_state(row['id'], 'sending', '')
                try:
                    self.send(platform, cfg, message, reply)
                except Exception:
                    self.set_state(row['id'], 'uncertain', '官方发送未确认，请人工核对，未自动重发')
                    return True
                self.set_state(row['id'], 'sent', '官方接口已确认发送成功')
            except (AIError, ChannelError) as error:
                # No busy retries or extra paid calls when a daily cap/credential check fails.
                self.set_state(row['id'], 'human', str(error)[:180])
            except Exception:
                self.set_state(row['id'], 'human', '处理异常，已转人工；未自动重试')
            return True

    def set_state(self, ident, state, detail):
        with self.db() as c:
            c.execute('UPDATE inbox SET state=?,detail=?,updated=? WHERE id=?', (state, detail, self.clock(), ident))

    def start(self):
        def worker():
            while True:
                try:
                    if self.process_one():
                        continue
                    with self.db() as c:
                        c.execute('DELETE FROM inbox WHERE received<?', (self.clock() - 7 * 86400,))
                except Exception:
                    pass
                self.wakeup.wait(3)
                self.wakeup.clear()
        self.thread = threading.Thread(target=worker, name='GinkgoOfficialMessages', daemon=True)
        self.thread.start()


def register(bp, admin_guard, engine, app):
    channels = Channels(engine)
    app.extensions['ginkgo_growth']['channels'] = channels

    @bp.get('/channels/health')
    def channel_health():
        return jsonify(status='ok', version=VERSION)

    @bp.get('/api/channels')
    @admin_guard
    def channel_status():
        return jsonify(channels.status())

    @bp.post('/api/channels/<platform>')
    @admin_guard
    def channel_config(platform):
        result = channels.update(platform, request.get_json() or {})
        with channels.engine.store.db() as c:
            channels.engine.store.audit(c, None, 'channel_config', '更新' + LABELS.get(platform, '') + '客服配置（无密钥）', g.growth_actor)
        return jsonify(result)

    @bp.get('/api/channels/inbox')
    @admin_guard
    def channel_inbox():
        with channels.db() as c:
            rows = c.execute('SELECT * FROM inbox ORDER BY received DESC LIMIT 80').fetchall()
        items = []
        for row in rows:
            content = channels.unseal(row['payload'])
            items.append({'id': row['id'], 'platform': row['platform'], 'state': row['state'],
                          'received': row['received'], 'detail': row['detail'], 'text': content.get('text', '[非文本事件]'),
                          'reply': channels.unseal(row['reply'])['text'] if row['reply'] else ''})
        return jsonify(items=items)

    @bp.post('/api/channels/inbox/<ident>/handoff')
    @admin_guard
    def channel_handoff(ident):
        action = (request.get_json() or {}).get('action')
        if action not in ('pause', 'resume'):
            raise ValueError('请选择转人工或恢复接待')
        with channels.db() as c:
            row = c.execute('SELECT platform,sender FROM inbox WHERE id=?', (ident,)).fetchone()
            if not row or not row['sender']:
                raise LookupError('咨询不存在')
            if action == 'pause':
                c.execute('INSERT OR IGNORE INTO handoff VALUES(?,?,?)', (row['platform'], row['sender'], channels.clock()))
                c.execute("UPDATE inbox SET state='human' WHERE platform=? AND sender=? AND state IN ('queued','prepared')", (row['platform'], row['sender']))
            else:
                c.execute('DELETE FROM handoff WHERE platform=? AND sender=?', (row['platform'], row['sender']))
        # Resuming affects only new incoming messages; never re-send old/uncertain replies.
        return jsonify(ok=True)

    @bp.route('/callbacks/<platform>', methods=['GET', 'POST'])
    def channel_callback(platform):
        if platform not in SUPPORTED:
            return Response('not connected', status=503)
        try:
            cfg = channels.config(platform)
            if not cfg['receive']:
                return Response('not configured', status=503)
            if platform == 'wechat':
                return channels.receive_wechat(cfg)
            if request.method != 'POST':
                return Response('POST required', status=405)
            return channels.receive_douyin(cfg)
        except (ValueError, KeyError, TypeError, struct.error):
            return Response('invalid callback', status=400)
        except Exception:
            return Response('temporary receive failure', status=503)

    if not app.testing:
        channels.start()
    return channels
