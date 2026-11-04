"""Isolated temp-store tests; no production accounts, customers or messages."""
import csv
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'python-deps'))
from flask import Flask, g
import growth_acquisition as growth


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.testing = True
        self.events = {'items': [{'id':'cb1d0012-8191-4447-999d-5881657dd6bf','title':'测试银杏比赛',
            'city':'成都','venue':'银杏乒乓球俱乐部','status':'open','signup_open':True,
            'starts_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),
            'signup_until':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}]}
        growth.register(self.app, data_dir=self.tmp.name, local_token='test-token', catalog_fetcher=lambda:self.events)
        self.client = self.app.test_client()
        self.headers = {'Authorization':'Bearer test-token'}

    def tearDown(self): self.tmp.cleanup()

    def post(self, path, data): return self.client.post(growth.PREFIX+path, json=data, headers=self.headers)
    def get(self,path): return self.client.get(growth.PREFIX+path, headers=self.headers)
    def patch(self,lid,data): return self.client.patch(growth.PREFIX+'/api/leads/'+lid,json=data,headers=self.headers)
    def seed(self, **kwargs):
        d = {'platform':'douyin','source_url':'https://www.douyin.com/video/123456789',
             'excerpt':'我在成都青羊区，想找乒乓球教练练基础，哪里有推荐？','alias':'测试球友',
             'posted_at':datetime.now(timezone.utc).isoformat(),'confirmed':True, **kwargs}
        r = self.post('/api/leads',d)
        self.assertIn(r.status_code,(200,201),r.json)
        return r.json['item']

    def test_unauthorized_endpoints(self):
        for p in ['/api/leads','/api/meta','/api/overview','/api/export','/api/inquiries','/api/campaigns']:
            self.assertEqual(self.client.get(growth.PREFIX+p).status_code,401,p)

    def test_health_does_not_expose_data(self):
        r=self.client.get(growth.PREFIX+'/health');self.assertEqual(r.status_code,200)
        self.assertFalse(r.json['auto_send']);self.assertNotIn('token',r.text)

    def test_browser_session_alone_does_not_grant_access(self):
        r=self.client.get(growth.PREFIX+'/api/leads',headers={'Cookie':'some_platform=logged_in'})
        self.assertEqual(r.status_code,401)

    def test_admin_session_adapter(self):
        app=Flask('production-auth')
        app.testing=True
        def auth(fn):
            def wrapped(*a,**kw):
                if request_token[0]=='absent': return {'error':'login'},401
                g.match_user={'name':'管理员' if request_token[0]=='admin' else '普通球友'}
                return fn(*a,**kw)
            wrapped.__name__=fn.__name__;return wrapped
        request_token=['absent']
        growth.register(app,data_dir=Path(self.tmp.name)/'host-auth',require_login=auth,is_admin=lambda u:u['name']=='管理员')
        client=app.test_client();self.assertEqual(client.get(growth.PREFIX+'/api/meta').status_code,401)
        request_token[0]='member';self.assertEqual(client.get(growth.PREFIX+'/api/meta').status_code,403)
        request_token[0]='admin';self.assertEqual(client.get(growth.PREFIX+'/api/meta').status_code,200)

    def test_dns_rebinding_host_rejected(self):
        self.assertEqual(self.client.get(growth.PREFIX+'/api/meta',headers={**self.headers,'Host':'attacker.example'}).status_code,403)

    def test_valid_training_request(self):
        l=self.seed();self.assertEqual(l['assessment']['intent'],'training');self.assertEqual(l['stage'],'qualified')
        self.assertTrue(l['assessment']['eligible']);self.assertEqual(l['assessment']['district'],'青羊')

    def test_valid_competition_request(self):
        l=self.seed(excerpt='成都有可以报名的乒乓球积分赛吗？想报名比赛')
        self.assertEqual(l['assessment']['intent'],'competition');self.assertTrue(l['assessment']['eligible'])

    def test_generic_interest_not_a_lead(self):
        l=self.seed(excerpt='成都乒乓球运动真有意思，今天看了很多精彩对拉')
        self.assertFalse(l['assessment']['eligible']);self.assertEqual(l['stage'],'new')

    def test_no_city_no_contact(self):
        l=self.seed(excerpt='想学乒乓球，请问哪里有合适的教练？')
        self.assertFalse(l['assessment']['eligible']);self.assertEqual(self.post('/api/leads/'+l['id']+'/draft',{}).status_code,409)

    def test_search_phrase_is_not_automatic_city_evidence(self):
        l=self.seed(excerpt='想学乒乓球，有教练吗？',city_evidence='搜索词：成都乒乓球')
        self.assertFalse(l['assessment']['local'])

    def test_ip_location_and_nonlocal_negation(self):
        l=self.seed(excerpt='想学乒乓球，有教练吗？',city_evidence='IP属地：成都')
        self.assertFalse(l['assessment']['local'])
        self.assertFalse(growth.classify('我不在成都，想学乒乓球，请问有教练吗？',posted_at=growth.stamp())['eligible'])

    def test_explicit_context_city(self):
        l=self.seed(excerpt='想学乒乓球，请问哪里有教练？',city_evidence='作者原帖写明住成都')
        self.assertTrue(l['assessment']['eligible'])

    def test_refusal_never_qualifies(self):
        for s in ['成都乒乓球不需要教练，不要推销','我在成都想打乒乓球但别联系，勿扰']:
            self.assertFalse(growth.classify(s,posted_at=growth.stamp())['eligible'])

    def test_recruiting_not_a_customer(self):
        l=self.seed(excerpt='成都招聘乒乓球教练，请问有人愿意来吗？')
        self.assertTrue(l['assessment']['rejected']);self.assertFalse(l['assessment']['eligible'])

    def test_spectator_tickets_excluded(self):
        l=self.seed(excerpt='成都世乒赛观赛门票哪里有？想报名乒乓球观赛')
        self.assertFalse(l['assessment']['eligible'])

    def test_old_and_missing_date(self):
        for date in [None,(datetime.now(timezone.utc)-timedelta(days=35)).isoformat()]:
            l=self.seed(posted_at=date,source_url='https://www.douyin.com/video/'+str(date))
            self.assertFalse(l['assessment']['eligible'])

    def test_invalid_and_future_dates(self):
        for date in ['abc','2026-99-77',(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()]:
            r=self.post('/api/classify',{'excerpt':'成都想学乒乓球', 'posted_at':date})
            self.assertEqual(r.status_code,400)

    def test_cross_platform_source_rejected(self):
        r=self.post('/api/leads',{'platform':'douyin','source_url':'https://xiaohongshu.com/explore/123','excerpt':'我在成都想找乒乓球教练'})
        self.assertEqual(r.status_code,400)

    def test_unsafe_source_urls(self):
        for url in ['javascript:alert(1)','http://www.douyin.com/a','https://www.douyin.com.attacker.com/a','https://127.0.0.1/a','https://user:pass@www.douyin.com/a','https://www.douyin.com:8443/a']:
            r=self.post('/api/leads',{'platform':'douyin','source_url':url,'excerpt':'成都想学乒乓球'})
            self.assertEqual(r.status_code,400,url)

    def test_redaction_before_storage(self):
        l=self.seed(excerpt='成都想找乒乓球教练，电话13800138000 微信:abc123456')
        self.assertNotIn('13800138000',l['excerpt']);self.assertNotIn('abc123456',l['excerpt'])

    def test_deduplication(self):
        a=self.seed();b=self.seed();self.assertEqual(a['id'],b['id'])
        self.assertEqual(self.get('/api/overview').json['total'],1)

    def test_public_third_party_bulk_rejected(self):
        self.assertEqual(self.post('/api/import',{'rows':[{}]}).status_code,400)

    def test_import_rejects_over_limit(self):
        self.assertEqual(self.post('/api/import',{'own_account_export':True,'rows':[{}]*51}).status_code,400)

    def test_import_validates_before_writes(self):
        rows=[{'platform':'douyin','source_url':'https://www.douyin.com/v/12','excerpt':'成都想学乒乓球'} ,{'platform':'douyin','source_url':'https://evil.invalid','excerpt':'成都想学乒乓球'}]
        self.assertEqual(self.post('/api/import',{'own_account_export':True,'rows':rows}).status_code,400)
        self.assertEqual(self.get('/api/overview').json['total'],0)

    def test_own_inquiries_import(self):
        row={'platform':'douyin','source_url':'https://www.douyin.com/v/12','excerpt':'成都想学乒乓球，请问有培训吗？','posted_at':growth.stamp()}
        r=self.post('/api/import',{'own_account_export':True,'rows':[row,row]})
        self.assertEqual(r.json['added'],1);self.assertEqual(r.json['duplicates'],1);self.assertEqual(r.json['sent'],0)

    def test_draft_is_not_send(self):
        l=self.seed();r=self.post('/api/leads/'+l['id']+'/draft',{})
        self.assertFalse(r.json['sent']);self.assertIn('工作人员',r.json['reply'])
        self.assertNotIn('微信号',r.json['reply']);self.assertEqual(self.get('/api/overview').json['contacted'],0)

    def test_dispatch_fails_closed(self):
        l=self.seed();r=self.post('/api/leads/'+l['id']+'/dispatch',{})
        self.assertEqual(r.status_code,409);self.assertFalse(r.json['sent'])

    def test_unconfirmed_cannot_draft(self):
        l=self.seed(confirmed=False);self.assertEqual(self.post('/api/leads/'+l['id']+'/draft',{}).status_code,409)

    def test_manual_contact_requires_evidence(self):
        l=self.seed();self.assertEqual(self.post('/api/leads/'+l['id']+'/contact',{'content':'你好'}).status_code,400)

    def contact(self,l):
        return self.post('/api/leads/'+l['id']+'/contact',{'content':'你好，我是银杏工作人员。','account':'银杏官方','evidence_url':l['source_url'],'sent_in_platform':True})

    def test_contact_register_and_no_repeat(self):
        l=self.seed();r=self.contact(l);self.assertEqual(r.status_code,200);self.assertFalse(r.json['platform_verified'])
        self.assertEqual(self.contact(l).status_code,409);self.assertEqual(self.post('/api/leads/'+l['id']+'/draft',{}).status_code,409)

    def test_block_prevents_reentry_contact(self):
        l=self.seed();self.post('/api/leads/'+l['id']+'/stop',{})
        self.assertEqual(self.post('/api/leads/'+l['id']+'/draft',{}).status_code,409)
        self.assertEqual(self.patch(l['id'],{'stage':'new'}).status_code,400)
        another=self.seed(source_url='https://www.douyin.com/video/second',excerpt='成都想学乒乓球，求推荐一位教练')
        self.assertTrue(another['stopped']);self.assertEqual(another['stage'],'blocked')

    def test_not_merging_across_platforms(self):
        l=self.seed();self.post('/api/leads/'+l['id']+'/stop',{})
        another=self.seed(platform='xiaohongshu',source_url='https://www.xiaohongshu.com/explore/test')
        self.assertFalse(another['stopped'])

    def test_stage_cannot_fake_sent(self):
        l=self.seed();self.assertEqual(self.patch(l['id'],{'stage':'contacted'}).status_code,400)

    def test_booking_requires_reference(self):
        l=self.seed();self.assertEqual(self.patch(l['id'],{'stage':'booked'}).status_code,400)
        self.assertEqual(self.patch(l['id'],{'stage':'booked','booking_ref':'人工核实报名编号123'}).status_code,200)
        self.assertEqual(self.get('/api/overview').json['booked'],1)

    def test_events_only_open_ginkgo_chengdu(self):
        sample=self.events['items'][0]
        self.events['items'] += [{**sample,'city':'北京'},{**sample,'venue':'其他球馆'}, {**sample,'status':'closed'}, {**sample,'signup_open':False},{**sample,'starts_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}]
        r=self.post('/api/catalog/sync',{});self.assertEqual(len(r.json['events']),1)

    def test_real_time_event_draft(self):
        self.post('/api/catalog/sync',{})
        l=self.seed(excerpt='我在成都，想报名乒乓球比赛，请问哪里有？')
        self.assertIn('测试银杏比赛',self.post('/api/leads/'+l['id']+'/draft',{}).json['reply'])

    def test_catalog_failure_drops_old_recommendation(self):
        self.post('/api/catalog/sync',{})
        def broken(): raise TimeoutError()
        catalog=self.app.extensions['ginkgo_growth']['catalog'];catalog.fetcher=broken
        catalog.sync();self.assertEqual(catalog.current()['events'],[])

    def test_search_plan_and_channel_truth(self):
        r=self.get('/api/search-plan');self.assertEqual(len(r.json['items']),60)
        self.assertFalse(self.get('/api/meta').json['dispatch_connected'])

    def test_seven_day_content_plan_not_published(self):
        r=self.get('/api/content-plan')
        self.assertEqual(len(r.json['items']),28)
        self.assertFalse(r.json['published'])
        self.assertTrue(all('俱乐部' in x['body'] and not x['published'] for x in r.json['items']))

    def test_public_page_does_not_leak_leads(self):
        self.seed();r=self.client.get(growth.PREFIX+'/public/campaign/douyin-training')
        self.assertEqual(r.status_code,200);self.assertNotIn('测试球友',r.text)

    def inquiry(self,**extra):
        return self.client.post(growth.PREFIX+'/public/inquiry',json={'campaign_id':'douyin-training','alias':'测试咨询','contact':'平台内联系测试号','interest':'training','consent':True,'adult_or_guardian':True,**extra})

    def test_inquiry_requires_purpose_consent(self):
        self.assertEqual(self.inquiry(consent=False).status_code,400)
        self.assertEqual(self.inquiry(adult_or_guardian=False).status_code,400)
        self.assertEqual(self.get('/api/inquiries').json['items'],[])

    def test_opt_in_inquiry_is_not_booking(self):
        r=self.inquiry();self.assertEqual(r.status_code,201)
        self.assertIn('不是正式报名',r.json['message']);self.assertEqual(self.get('/api/overview').json['booked'],0)
        self.assertEqual(len(self.get('/api/inquiries').json['items']),1)

    def test_inquiry_rate_limit(self):
        for _ in range(5): self.assertEqual(self.inquiry().status_code,201)
        self.assertEqual(self.inquiry().status_code,429)

    def test_backup_and_csv_formula_defence(self):
        self.seed(alias='=HYPERLINK(1)');r=self.get('/api/export')
        self.assertIn("'=HYPERLINK(1)",r.text)
        b=self.post('/api/backup',{});self.assertTrue(b.json['ok']);self.assertTrue((Path(self.tmp.name)/'backups'/b.json['filename']).is_file())

    def test_no_form_csrf_no_cors(self):
        r=self.client.post(growth.PREFIX+'/api/leads',data={'a':'b'},headers=self.headers)
        self.assertEqual(r.status_code,415)
        self.assertIsNone(r.headers.get('Access-Control-Allow-Origin'))

    def test_security_headers(self):
        r=self.get('/');self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['X-Frame-Options'],'DENY');self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])

    def test_unknown_and_path_traversal(self):
        self.assertEqual(self.get('/api/leads/missing').status_code,404)
        self.assertEqual(self.get('/assets/../../growth_acquisition.py').status_code,404)

    def test_oversize_rejected(self):
        r=self.client.post(growth.PREFIX+'/api/leads',data='x'*130000,headers={**self.headers,'Content-Type':'application/json'})
        self.assertEqual(r.status_code,413)


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(GrowthTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path(__file__).with_name('verification.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'production_writes':False,'platform_messages_sent':0},ensure_ascii=False,indent=2),'utf-8')
    sys.exit(not result.wasSuccessful())
