"""Isolated official-protocol/security/dispatch checks. No live user/API calls."""
import base64
import hashlib
import json
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / 'python-deps'))
sys.path.insert(0, str(Path(__file__).parent / 'channel-vendor'))
from flask import Flask, Blueprint
from Cryptodome.Cipher import AES
from growth_channels import Channels, decrypt_wechat, sha1_parts, APPS, register, ChannelError
from growth_acquisition import Store
from growth_ai import Vault, AIError

CIPHER = '+qdx1OKCy+5JPCBFWw70tm0fJGb2Jmeia4FCB7kao+/Q5c/ohsOzQHi8khUOb05JCpj0JB4RvQMkUyus8TPxLKJGQqcvZqzDpVzazhZv6JsXUnnR8XGT740XgXZUXQ7vJVnAG+tE8NUd4yFyjPy7GgiaviNrlCTj+l5kdfMuFUPpRSrfMZuMcp3Fn2Pede2IuQrKEYwKSqFIZoNqJ4M8EajAsjLY2km32IIjdf8YL/P50F7mStwntrA2cPDrM1kb6mOcfBgRtWygb3VIYnSeOBrebufAlr7F9mFUPAJGj04='


class FakeAI:
    def __init__(self): self.calls = 0; self.failure = None; self.during = None
    def require_ready(self): return {}, 'synthetic'
    def analyze(self, source, events, task):
        self.calls += 1
        if self.during: self.during()
        if self.failure: raise self.failure
        assert '[电话隐藏]' in source['excerpt'] or '13800138000' not in source['excerpt']
        return {'reply': '这里是银杏乒乓球俱乐部。请在本平台银杏奖牌查看训练安排。'}


def encrypt(data, key, appid):
    value = json.dumps(data, ensure_ascii=False).encode()
    plain = b'1234567890abcdef' + struct.pack('!I', len(value)) + value + appid.encode()
    n = 32 - len(plain) % 32
    aeskey = base64.b64decode(key + '=')
    return base64.b64encode(AES.new(aeskey, AES.MODE_CBC, aeskey[:16]).encrypt(plain + bytes([n]) * n)).decode()


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.ai = FakeAI()
        self.engine = SimpleNamespace(store=self.store, ai=self.ai,
            catalog=SimpleNamespace(current=lambda: {'updated_at':'now', 'events':[]}, sync=lambda: None))
        self.clock = 1800000000.0
        self.calls = []
        def transport(host, path, body, headers=None):
            self.calls.append((host, path, body, headers))
            if 'business_token' in path: return {'biz_token':'synthetic', 'biz_expires_in':7200}
            if 'stable_token' in path: return {'access_token':'synthetic', 'expires_in':7200}
            return {'errcode':0} if host == 'api.weixin.qq.com' else {'data':{'error_code':0}, 'extra':{'error_code':0}, 'msg_id':'sent-id'}
        self.channels = Channels(self.engine, transport=transport, clock=lambda: self.clock)
        self.channels.update('wechat', {'generate_wechat_keys':True, 'receive':True})
        self.channels.update('douyin', {'webhook_secret':'synthetic-webhook-secret', 'business_openid':'business-owner-0001', 'receive':True})
        self.app = Flask('protocol'); self.app.testing = True
        self.app.extensions['ginkgo_growth'] = {}
        bp = Blueprint('test_callback', __name__)
        import growth_channels
        original = growth_channels.Channels
        growth_channels.Channels = lambda engine: self.channels
        def admin(fn):
            from functools import wraps
            from flask import request, jsonify, g
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if request.headers.get('Authorization') != 'Bearer synthetic-admin': return jsonify(error='auth'), 401
                g.growth_actor = 'synthetic'
                return fn(*args, **kwargs)
            return wrapped
        try: register(bp, admin, self.engine, self.app)
        finally: growth_channels.Channels = original
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()
        self.saved_env = os.environ.get('MATCH_WECHAT_SECRET')
        os.environ['MATCH_WECHAT_SECRET'] = 'synthetic-existing-secret'

    def tearDown(self):
        if self.saved_env is None: os.environ.pop('MATCH_WECHAT_SECRET', None)
        else: os.environ['MATCH_WECHAT_SECRET'] = self.saved_env
        self.temp.cleanup()

    def activate(self, p): self.channels.verified(p); self.channels.update(p, {'automatic':True})

    def dy_data(self, **kwargs):
        content = {'conversation_short_id':'conversation-1', 'server_message_id':'incoming-1', 'conversation_type':1,
                   'create_time':int(self.clock*1000), 'message_type':'text', 'text':'想了解儿童25次课多少钱？'}
        content.update(kwargs)
        return {'event':'im_receive_msg', 'client_key':APPS['douyin'], 'from_user_id':'customer-001',
                'to_user_id':'business-owner-0001', 'content':content}

    def post_dy(self, data, signature=None):
        raw = json.dumps(data).encode()
        signature = signature if signature is not None else hashlib.sha1(b'synthetic-webhook-secret' + raw).hexdigest()
        return self.client.post('/callbacks/douyin', data=raw, content_type='application/json', headers={'X-Douyin-Signature':signature})

    def post_wx(self, data, appid=None, sig=None):
        cfg = self.channels.config('wechat')
        cipher = encrypt(data, cfg['aes_key'], appid or cfg['appid'])
        signature = sig or sha1_parts(cfg['token'], str(int(self.clock)), 'nonce-1', cipher)
        return self.client.post('/callbacks/wechat', query_string={'encrypt_type':'aes', 'timestamp':str(int(self.clock)), 'nonce':'nonce-1','msg_signature':signature}, json={'Encrypt':cipher})

    def message(self, p, ident='m1', **kwargs):
        msg = {'message_id':ident, 'sender':'customer-1', 'text':'想了解训练', 'created':self.clock, 'conversation_id':'conv'}
        msg.update(kwargs)
        return self.channels.enqueue(p, msg)

    def state(self, ident):
        with self.channels.db() as c: return c.execute('SELECT state FROM inbox WHERE id=?',(ident,)).fetchone()[0]

    def test_official_wechat_decrypt_vector(self):
        result = decrypt_wechat(CIPHER, 'A'*43, 'wxba5fad812f8e6fb9')
        self.assertEqual(result['Event'], 'debug_demo'); self.assertEqual(result['debug_str'], 'hello world')

    def test_official_wechat_signature_vector(self):
        self.assertEqual(sha1_parts('AAAAA','1714112445','415670741',CIPHER), '046e02f8204d34f8ba5fa3b1db94908f3df2e9b3')

    def test_wrong_decryption_recipient(self):
        with self.assertRaises(ValueError): decrypt_wechat(CIPHER, 'A'*43, APPS['wechat'])

    def test_wrong_padding(self):
        with self.assertRaises(ValueError): decrypt_wechat(CIPHER[:-4]+'AAAA', 'A'*43, 'wxba5fad812f8e6fb9')

    def test_encrypted_callback_accepted_no_ai_in_request(self):
        r=self.post_wx({'MsgType':'text','FromUserName':'customer','MsgId':'wx1','Content':'问训练','CreateTime':self.clock})
        self.assertEqual(r.status_code,200);self.assertEqual(self.ai.calls,0);self.assertEqual(self.calls,[])

    def test_wrong_wechat_signature(self): self.assertEqual(self.post_wx({'a':1},sig='bad').status_code,403)
    def test_wrong_wechat_application(self): self.assertEqual(self.post_wx({'a':1},appid='wrong-app').status_code,400)
    def test_plaintext_rejected(self):
        r=self.client.post('/callbacks/wechat?timestamp=1800000000&nonce=a',json={'Content':'x'})
        self.assertEqual(r.status_code,400)

    def test_get_handshake(self):
        cfg=self.channels.config('wechat');ts=str(int(self.clock));nonce='n'
        r=self.client.get('/callbacks/wechat',query_string={'timestamp':ts,'nonce':nonce,'signature':sha1_parts(cfg['token'],ts,nonce),'echostr':'exact-echo'})
        self.assertEqual(r.data,b'exact-echo')

    def test_stale_handshake_rejected(self):
        self.assertEqual(self.client.get('/callbacks/wechat?timestamp=1&nonce=n&signature=x').status_code,403)

    def test_douyin_signed_callback(self): self.assertEqual(self.post_dy(self.dy_data()).status_code,200)
    def test_douyin_unsigned_rejected(self): self.assertEqual(self.post_dy(self.dy_data(), 'bad').status_code,403)
    def test_douyin_wrong_app(self):
        data=self.dy_data();data['client_key']='other';self.assertEqual(self.post_dy(data).status_code,403)
    def test_douyin_wrong_business(self):
        data=self.dy_data();data['to_user_id']='other';self.assertEqual(self.post_dy(data).status_code,403)
    def test_douyin_verify(self):
        r=self.post_dy({'event':'verify_webhook','client_key':'','content':{'challenge':1284}})
        self.assertEqual(json.loads(r.data),{'challenge':1284})
    def test_unknown_event_no_silent_loss(self):
        data=self.dy_data();data['event']='unknown';self.assertEqual(self.post_dy(data).status_code,200)
        with self.channels.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM inbox WHERE state='event'").fetchone()[0],1)

    def test_duplicate_only_one_reply(self):
        self.activate('douyin');self.post_dy(self.dy_data());self.post_dy(self.dy_data())
        self.assertTrue(self.channels.process_one());self.assertFalse(self.channels.process_one());self.assertEqual(self.ai.calls,1)
        self.assertEqual(len([x for x in self.calls if '/im/send/msg/' in x[1]]),1)

    def test_stop_is_persistent(self):
        self.activate('douyin');ident=self.message('douyin',text='转人工，退款')
        self.assertEqual(self.state(ident),'human');self.message('douyin','second');self.assertFalse(self.channels.process_one());self.assertEqual(self.ai.calls,0)

    def test_outgoing_bot_does_not_loop(self):
        self.activate('douyin');data=self.dy_data();data['event']='im_send_msg';data['from_user_id']='business-owner-0001';data['to_user_id']='customer-001';data['content']['source']=APPS['douyin']
        self.post_dy(data);self.assertFalse(self.channels.process_one());self.assertEqual(self.ai.calls,0)

    def test_outgoing_human_takes_over(self):
        self.activate('douyin');self.post_dy(self.dy_data());data=self.dy_data();data.update(event='im_send_msg',from_user_id='business-owner-0001',to_user_id='customer-001');data['content']['source']=''
        self.post_dy(data);self.assertFalse(self.channels.process_one());self.assertEqual(self.ai.calls,0)

    def test_disabled_platform_does_not_block_enabled(self):
        self.message('wechat');self.activate('douyin');ident=self.message('douyin');self.assertTrue(self.channels.process_one());self.assertEqual(self.state(ident),'sent')

    def test_disabled_never_sends(self):
        self.message('douyin');self.assertFalse(self.channels.process_one());self.assertEqual(self.calls,[])

    def test_budget_failure_no_paid_retry(self):
        self.activate('douyin');ident=self.message('douyin');self.ai.failure=AIError('已达每日上限','budget')
        self.channels.process_one();self.channels.process_one();self.assertEqual(self.ai.calls,1);self.assertEqual(self.state(ident),'human');self.assertEqual(self.calls,[])

    def test_uncertain_send_never_auto_retried(self):
        self.activate('douyin');ident=self.message('douyin');original=self.channels.send
        def fail(*args): raise TimeoutError('ambiguous')
        self.channels.send=fail;self.channels.process_one();self.channels.send=original;self.channels.process_one()
        self.assertEqual(self.state(ident),'uncertain');self.assertEqual(self.ai.calls,1)

    def test_expiry_after_queueing(self):
        self.activate('douyin');ident=self.message('douyin');self.clock+=24*3600;self.channels.process_one();self.assertEqual(self.state(ident),'expired');self.assertEqual(self.ai.calls,0)
    def test_future_message_rejected(self):
        with self.assertRaises(ValueError):self.message('douyin',created=self.clock+1000)
    def test_old_message_rejected(self):
        with self.assertRaises(ValueError):self.message('douyin',created=self.clock-25*3600)
    def test_pause_during_ai(self):
        self.activate('douyin');self.message('douyin');self.ai.during=lambda:self.channels.update('douyin',{'automatic':False})
        self.channels.process_one();self.assertFalse(any('/im/send/msg/' in x[1] for x in self.calls))
    def test_phone_redacted(self):
        self.activate('douyin');self.message('douyin',text='13800138000 想训练');self.channels.process_one();self.assertEqual(self.ai.calls,1)
    def test_key_rotation_disables_and_invalidates(self):
        self.activate('douyin');self.channels.update('douyin',{'webhook_secret':'another-synthetic-secret'})
        self.assertFalse(self.channels.config('douyin')['automatic'])
        with self.assertRaises(ValueError):self.channels.update('douyin',{'automatic':True})
    def test_cannot_enable_before_verification(self):
        with self.assertRaises(ValueError):self.channels.update('douyin',{'automatic':True})
    def test_unsupported_not_falsely_connected(self):
        for p in ('kuaishou','xiaohongshu'):
            with self.assertRaises(ValueError):self.channels.update(p,{'automatic':True})
            self.assertEqual(self.client.post('/callbacks/'+p,json={}).status_code,503)
    def test_admin_guard(self):
        for path in ('/api/channels','/api/channels/inbox'):
            self.assertEqual(self.client.get(path).status_code,401)
    def test_public_health_no_credentials(self):
        raw=self.client.get('/channels/health').data
        self.assertNotIn(b'secret',raw);self.assertEqual(self.client.get('/channels/health').status_code,200)
    def test_status_no_keys(self):
        data=json.dumps(self.channels.status());self.assertNotIn('synthetic-webhook-secret',data);self.assertNotIn(self.channels.config('wechat')['aes_key'],data)
    def test_encrypted_disk_no_plaintext(self):
        self.message('douyin',text='测试专属文字')
        self.assertNotIn('测试专属文字'.encode(),self.channels.path.read_bytes());self.assertNotIn(b'synthetic-webhook-secret',self.channels.private.read_bytes())
    def test_sent_only_after_official_ack(self):
        self.activate('douyin');ident=self.message('douyin');self.channels.process_one();self.assertEqual(self.state(ident),'sent')
        send=[x for x in self.calls if '/im/send/msg/' in x[1]][0];self.assertEqual(send[2]['scene'],'im_reply_msg');self.assertEqual(send[2]['to_user_id'],'customer-1')
    def test_wechat_stable_token_no_force_refresh(self):
        self.activate('wechat');ident=self.message('wechat');self.channels.process_one();self.assertEqual(self.state(ident),'sent');self.assertFalse(self.calls[0][2]['force_refresh'])


if __name__=='__main__':unittest.main(verbosity=2)
