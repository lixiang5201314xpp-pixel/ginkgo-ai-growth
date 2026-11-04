"""Isolated AI/job tests. Synthetic requests only; no external API calls or billing."""
import concurrent.futures
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'python-deps'))
from flask import Flask
import growth_acquisition as g
from growth_ai import AIError,AIService,Vault,transport,redacted


class MemoryVault:
    def __init__(self):self.keys={}
    def put(self,p,k):self.keys[p]=k
    def get(self,p):return self.keys.get(p,'')


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.app=Flask('ai-test');self.app.testing=True
        g.register(self.app,data_dir=self.root,local_token='synthetic-admin',catalog_fetcher=lambda:{'items':[]})
        self.e=self.app.extensions['ginkgo_growth']['automation'];self.s=self.e.store
        self.calls=[];self.fail=None;self.override=None
        def fake(provider,path,key,body=None,method='POST'):
            self.calls.append((provider,path,key,body,method))
            if self.fail:raise AIError('模拟网络或账户故障',self.fail)
            if path.endswith('/models'):return {'data':[{'id':'deepseek-flash'}]}
            if path.endswith('/search'):
                site=body['query'].split('site:')[1].split()[0]
                return {'results':[{'title':'成都乒乓求教练','url':'https://www.'+site+'/test/123','snippet':'想找教练，原文时间待核实'},
                                   {'url':'https://evil.invalid/x','title':'拒绝异站结果'}]}
            payload=json.loads(body['messages'][1]['content']) if provider=='deepseek' else json.loads(body['input'])
            result={'intent':'training','summary':'基础训练咨询','explicit_need':True,'confidence':.85,
                    'evidence_quote':payload['request_text'][:20],
                    'reply':'我们是银杏乒乓球俱乐部。请在本平台银杏奖牌小程序查看训练安排。',
                    'event_id':None,'next_action':'按用户方便的时段核对课程','followup_hours':24}
            if self.override:result.update(self.override)
            if payload['task']=='inbound_question':result={'reply':result['reply']}
            if provider=='deepseek':return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result,ensure_ascii=False)}}],'usage':{'prompt_tokens':100,'completion_tokens':40}}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result)}]}]}
        self.ai=AIService(self.s,request_transport=fake,vault=MemoryVault());self.e.ai=self.ai
        self.config={'api_key':'sk-synthetic-not-real-12345678','enabled':True,'search_enabled':True,
                     'paid_usage_authorized':True,'data_processing_authorized':True}
        self.h={'Authorization':'Bearer synthetic-admin'};self.c=self.app.test_client()

    def tearDown(self):self.tmp.cleanup()
    def ready(self,**kw):self.ai.configure({**self.config,**kw})
    def seed(self,**kw):return self.s.add({'platform':'douyin','source_url':'https://www.douyin.com/video/test',
        'excerpt':'成都青羊想学乒乓球，请问哪里有基础教练？','posted_at':g.stamp(),'confirmed':True,**kw},'synthetic')[0]
    def runjob(self,kind):j,_=self.e.create(kind,'synthetic');self.e.run(j['id']);return self.e.job(j['id'])

    def test_auth_guards_all_new_private_routes(self):
        for path in ['/api/ai/settings','/api/automation','/api/candidates','/api/followup-plans','/api/ai/content']:
            self.assertEqual(self.c.get(g.PREFIX+path).status_code,401)
        self.assertEqual(self.c.post(g.PREFIX+'/api/automation/jobs',json={'kind':'all'}).status_code,401)

    def test_key_never_in_status_database_or_usage(self):
        self.ready();status=self.ai.status();self.assertNotIn(self.config['api_key'],json.dumps(status))
        with self.s.db() as c:data=''.join(r[0] for r in c.execute('SELECT value FROM settings'))
        self.assertNotIn(self.config['api_key'],data);self.assertTrue(status['key_configured'])

    def test_disabled_ai_makes_no_requests(self):
        with self.assertRaises(AIError):self.ai.analyze({},[])
        self.assertEqual(self.calls,[])

    def test_consent_limits_and_unknown_fields(self):
        for kwargs in [{'daily_ai_limit':True},{'daily_ai_limit':201},{'interval_minutes':1},{'base_url':'https://evil.invalid'}, {'paid_usage_authorized':False}]:
            with self.assertRaises(ValueError):self.ready(**kwargs)

    def test_connection_is_get_without_generation_usage(self):
        self.ready();self.assertTrue(self.ai.test_connection()['ok']);self.assertEqual(self.calls[0][4],'GET')
        self.assertEqual(self.ai.status()['usage'],[])

    def test_model_not_available_has_clear_error(self):
        self.ready(model='deepseek-v4-pro');self.assertEqual(self.ai.test_connection()['code'],'model_not_allowed')

    def test_redacted_payload_and_native_destination(self):
        self.ready();self.ai.analyze({'excerpt':'成都想学乒乓球，电话13800138000 微信:abcdef123 邮箱a@b.com',
            'alias':'不应发送的昵称','contact':'不应发送的联系号','platform':'kuaishou'},[])
        payload=json.dumps(self.calls[-1][3],ensure_ascii=False)
        for x in ['13800138000','abcdef123','a@b.com','不应发送的昵称','不应发送的联系号']:self.assertNotIn(x,payload)
        self.assertIn('在快手内打开',payload);self.assertIn('reception_playbook',payload)

    def test_cache_avoids_repeated_billing(self):
        self.ready();a=self.ai.analyze({'excerpt':'成都想学乒乓球'},[]);b=self.ai.analyze({'excerpt':'成都想学乒乓球'},[])
        self.assertFalse(a['cached']);self.assertTrue(b['cached']);self.assertEqual(len(self.calls),1)

    def test_atomic_daily_limit_across_threads(self):
        self.ready(daily_ai_limit=2);cfg=self.ai.config()
        def attempt(_):
            try:self.ai.reserve('chat',cfg);return True
            except AIError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(attempt,range(8)))
        self.assertEqual(sum(results),2)

    def test_failures_count_and_do_not_cache(self):
        for code in ['invalid_key','balance','forbidden','rate_limited','network']:
            self.ready();self.fail=code
            with self.assertRaises(AIError):self.ai.analyze({'excerpt':code},[])
        with self.s.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM ai_usage WHERE status='failed'").fetchone()[0],5)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM ai_cache').fetchone()[0],0)

    def test_fabricated_evidence_and_event_rejected(self):
        self.ready()
        for i,override in enumerate([{'evidence_quote':'不存在的证据'},{'event_id':'invented-event'}]):
            self.override=override
            with self.assertRaises(AIError):self.ai.analyze({'excerpt':'成都想学乒乓球'+str(i)},[])

    def test_unsafe_claims_and_prices_rejected(self):
        self.ready()
        for reply in ['俱乐部保证包会','俱乐部请加我微信','俱乐部报名99元','俱乐部大家免费训练','俱乐部年化24%']:
            self.override={'reply':reply}
            with self.assertRaises(AIError):self.ai.analyze({'excerpt':reply},[])

    def test_verified_children_prices_accepted(self):
        self.ready();self.override={'reply':'银杏乒乓球俱乐部儿童25次课2400元，每次90分钟，折合每次96元。'}
        self.assertIn('2400元',self.ai.analyze({'excerpt':'儿童收费'},[])['reply'])

    def test_adult_award_uses_automatic_miniapp_record(self):
        self.ready();self.override={'reply':'银杏乒乓球俱乐部成人参加1600分组以下限分比赛获得前三名，可免费训练，小程序自动发课，请查看课程记录。'}
        self.assertIn('自动发课',self.ai.analyze({'excerpt':'成人奖励'},[])['reply'])

    def test_openai_region_guard_and_response_schema(self):
        with self.assertRaises(ValueError):self.ready(provider='openai',model='gpt-5.4-mini',search_enabled=False)
        with patch.dict(os.environ,{'GINKGO_OPENAI_SUPPORTED_ENVIRONMENT':'1'}):
            self.ready(provider='openai',model='gpt-5.4-mini',search_enabled=False)
            self.ai.analyze({'excerpt':'成都想学乒乓球'},[])
        body=self.calls[-1][3];self.assertFalse(body['store']);self.assertTrue(body['text']['format']['strict'])

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_native_dpapi_roundtrip_no_plaintext(self):
        v=Vault(self.root);v.put('deepseek',self.config['api_key'])
        self.assertEqual(v.get('deepseek'),self.config['api_key'])
        self.assertNotIn(self.config['api_key'].encode(),(self.root/'secrets/deepseek.dpapi').read_bytes())

    def test_transport_errors_never_expose_provider_body(self):
        for code in [401,402,403,404,429,500]:
            with patch('growth_ai.http.client.HTTPSConnection') as connection,patch('growth_ai.tls_context'):
                connection.return_value.getresponse.return_value.status=code
                with self.assertRaises(AIError) as raised:transport('deepseek','/chat/completions','sk-secret')
                self.assertNotIn('sk-secret',str(raised.exception));connection.return_value.close.assert_called_once()

    def test_job_double_click_is_deduplicated(self):
        a,new=self.e.create('all','synthetic');b,new2=self.e.create('respond','synthetic')
        self.assertTrue(new);self.assertFalse(new2);self.assertEqual(a['id'],b['id'])

    def test_search_candidates_not_contacts_or_customer_leads(self):
        self.ready();j=self.runjob('discover');self.assertEqual(j['status'],'completed')
        self.assertEqual(j['result']['discover']['queries_completed'],4)
        self.assertEqual(self.e.sources()['existing_leads'],0);self.assertEqual(self.e.sources()['web_candidates'],4)
        with self.s.db() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM growth_candidates WHERE status!='needs_review'").fetchone()[0],0)

    def test_no_config_job_explains_setup_without_network(self):
        j=self.runjob('all');self.assertEqual(j['status'],'needs_setup');self.assertEqual(self.calls,[])

    def test_reply_draft_not_marked_sent_or_booked(self):
        self.ready();lead=self.seed();j=self.runjob('respond')
        self.assertEqual(j['result']['respond']['drafts_prepared'],1)
        latest=self.s.get(lead['id']);self.assertIn('俱乐部',latest['latest_reply']);self.assertEqual(latest['contact_count'],0)
        self.assertEqual(latest['stage'],'qualified')

    def test_unconfirmed_stays_unconfirmed(self):
        self.ready();lead=self.seed(confirmed=False);j=self.runjob('respond')
        self.assertEqual(j['result']['respond']['needs_source_review'],1)
        self.assertFalse(self.s.get(lead['id'])['confirmed']);self.assertEqual(self.s.get(lead['id'])['latest_reply'],'')

    def test_stop_during_ai_does_not_write_reply(self):
        self.ready();lead=self.seed();original=self.ai.transport
        def stopping(*args,**kw):
            with self.s.db() as c:c.execute('UPDATE leads SET stopped=1 WHERE id=?',(lead['id'],))
            return original(*args,**kw)
        self.ai.transport=stopping
        with self.assertRaises(AIError):self.e.analyze_lead(lead)
        self.assertEqual(self.s.get(lead['id'])['latest_reply'],'')

    def test_cancellation_before_run(self):
        self.ready();j,_=self.e.create('discover','synthetic')
        with self.s.db() as c:c.execute('UPDATE growth_jobs SET cancelled=1 WHERE id=?',(j['id'],))
        self.e.run(j['id']);self.assertEqual(self.e.job(j['id'])['status'],'cancelled');self.assertEqual(self.calls,[])

    def test_followup_generates_four_native_channel_drafts_only_once(self):
        self.ready();j=self.runjob('followup');self.assertEqual(j['status'],'completed')
        self.assertEqual(j['result']['followup']['channel_drafts']['prepared'],4)
        self.assertEqual(j['result']['followup']['sent'],0)
        j2=self.runjob('followup');self.assertEqual(j2['result']['followup']['channel_drafts']['prepared'],0)
        rows=self.c.get(g.PREFIX+'/api/ai/content',headers=self.h).json['items'];self.assertEqual(len(rows),4)
        self.assertTrue(all(r['status']=='draft' and '银杏奖牌' in r['body'] for r in rows))

    def test_owned_exports_validate_before_import(self):
        p=self.root/'inbox/test.json';p.write_text(json.dumps({'rows':[{}]}),'utf-8')
        n,errors=self.e.import_owned_files('synthetic');self.assertEqual(n,0);self.assertTrue(errors)

    def test_existing_key_survives_model_settings_update(self):
        self.ready();self.ai.configure({'automatic':True});self.assertTrue(self.ai.status()['key_configured'])

    def chat(self,**kw):return self.c.post(g.PREFIX+'/public/chat',json={'campaign_id':'douyin-training','question':'孩子想学乒乓球，怎么选课？','consent':True,**kw})

    def test_public_chat_requires_consent_and_valid_entry(self):
        self.ready();self.assertEqual(self.chat(consent=False).status_code,400)
        self.assertEqual(self.chat(campaign_id='evil').status_code,404);self.assertEqual(self.calls,[])

    def test_public_chat_returns_real_ai_and_own_platform(self):
        self.ready();r=self.chat();self.assertEqual(r.status_code,200,r.json)
        self.assertTrue(r.json['ai_generated']);self.assertFalse(r.json['booking_created']);self.assertEqual(r.json['destination']['platform'],'抖音')

    def test_public_chat_continuation_uses_redacted_context(self):
        self.ready();a=self.chat(question='我孩子想学乒乓球 电话13800138000')
        b=self.chat(question='那周末有课吗？',conversation_token=a.json['conversation_token'])
        self.assertEqual(b.status_code,200)
        body=self.calls[-1][3]['messages'][1]['content'];self.assertIn('孩子',body);self.assertNotIn('13800138000',body)

    def test_public_chat_cannot_read_other_session_or_cross_platform(self):
        self.ready();a=self.chat();token=a.json['conversation_token']
        self.assertEqual(self.chat(campaign_id='kuaishou-training',conversation_token=token).status_code,400)
        self.assertEqual(self.chat(conversation_token='guess').status_code,400)

    def test_public_chat_has_session_and_daily_limits(self):
        self.ready(daily_ai_limit=20);a=self.chat();token=a.json['conversation_token']
        for i in range(5):self.assertEqual(self.chat(question='孩子想学乒乓球'+str(i),conversation_token=token).status_code,200)
        self.assertEqual(self.chat(conversation_token=token).status_code,429)

    def test_public_chat_network_error_is_not_fake_success(self):
        self.ready();self.fail='network';r=self.chat();self.assertEqual(r.status_code,409)
        self.assertNotIn('conversation_token',r.json);self.assertNotIn('sk-',r.text)

    def test_background_reserves_capacity_for_immediate_inquiries(self):
        self.ready(daily_ai_limit=6);cfg=self.ai.config()
        for _ in range(4):self.ai.reserve('chat',cfg,background=True)
        with self.assertRaises(AIError):self.ai.reserve('chat',cfg,background=True)
        self.ai.reserve('chat',cfg);self.ai.reserve('chat',cfg)
        with self.assertRaises(AIError):self.ai.reserve('chat',cfg)

    def test_malformed_event_type_rejected_cleanly(self):
        self.ready();self.override={'event_id':{'invented':True}}
        with self.assertRaises(AIError):self.ai.analyze({'excerpt':'成都想报名乒乓球比赛'},[])

    def test_inbound_reply_does_not_require_auxiliary_classification(self):
        self.ready();r=self.ai.analyze({'excerpt':'孩子每周来两次怎么选课程？'},[],'inbound_question')
        self.assertIn('俱乐部',r['reply']);self.assertEqual(r['intent'],'unknown');self.assertFalse(r['explicit_need'])
        system=self.calls[-1][3]['messages'][0]['content']
        self.assertIn('只有 reply 字段',system)

    def test_known_enum_and_boolean_string_variants_are_normalized(self):
        self.ready();self.override={'intent':'训练咨询','explicit_need':'true'}
        r=self.ai.analyze({'excerpt':'成都想找乒乓球教练'},[])
        self.assertEqual(r['intent'],'training');self.assertIs(r['explicit_need'],True)
        self.override={'intent':'TRAINING','explicit_need':'false'}
        r=self.ai.analyze({'excerpt':'成都乒乓球普通讨论'},[])
        self.assertIs(r['explicit_need'],False)

    def test_unknown_classification_does_not_silently_become_a_customer(self):
        self.ready();self.override={'intent':'anything_else','explicit_need':True}
        with self.assertRaises(AIError):self.ai.analyze({'excerpt':'成都乒乓球普通讨论'},[])

    def test_inbound_keeps_price_and_promise_validation(self):
        self.ready();self.override={'reply':'银杏乒乓球俱乐部儿童课程99元，保证包会。'}
        with self.assertRaises(AIError):self.ai.analyze({'excerpt':'儿童课程多少钱？'},[],'inbound_question')

    def test_inbound_discloses_club_identity_and_child_price_context(self):
        self.ready();self.override={'reply':'25次课2400元，每次90分钟，折合96元。'}
        r=self.ai.analyze({'excerpt':'孩子25次课多少钱？'},[],'inbound_question')
        self.assertIn('儿童训练',r['reply']);self.assertIn('俱乐部',r['reply'])

    def test_child_price_not_assigned_to_unspecified_adult(self):
        self.ready();self.override={'reply':'25次课2400元，每次90分钟，折合96元。'}
        with self.assertRaises(AIError):self.ai.analyze({'excerpt':'成人训练多少钱？'},[],'inbound_question')


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    Path(__file__).with_name('ai-verification.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'production_writes':False,'paid_requests':0},indent=2),'utf-8')
    sys.exit(not result.wasSuccessful())
