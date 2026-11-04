"""Delivery attempts are operator receipts, never automatic social sends. Synthetic data only."""
import concurrent.futures
import json
from pathlib import Path
import unittest
from test_ai import Tests as Fixture
import growth_acquisition as g


class DeliveryTests(unittest.TestCase):
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    seed=Fixture.seed
    ready=Fixture.ready
    runjob=Fixture.runjob

    def api(self,path,method='GET',data=None):
        return self.c.open(g.PREFIX+path,method=method,json=data,headers=self.h)
    def attempt(self,lead,**kw):
        d={'account':'模拟球馆','content':'模拟回复：请查看本平台课程安排。','evidence_url':lead['source_url'],
           'status':'pending','note':'','submitted_in_platform':True,'request_id':'synthetic-request-0001',**kw}
        return self.api('/api/leads/'+lead['id']+'/delivery-attempts','POST',d)
    def check(self,lead,aid,**kw):
        return self.api('/api/leads/'+lead['id']+'/delivery-attempts/'+str(aid),'PATCH',
            {'status':'confirmed','checked_in_platform':True,'note':'模拟：手机端已看到准确账号及内容',**kw})
    def overview(self):return self.api('/api/overview').json

    def test_newcomer_practice_wording_can_record_receipt_and_prevent_duplicate_contact(self):
        lead=self.seed(excerpt='成华区有人一起练单球吗，本人萌新#乒乓球搭子 #成都成华区 #约乒乓球 #成都搭子')
        result=self.attempt(lead)
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.check(lead,result.json['item']['id']).status_code,200)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],1)
        self.assertEqual(self.attempt(lead,request_id='synthetic-request-0002').status_code,409)
        self.assertEqual(self.overview()['booked'],0)

    def test_private_routes_require_admin(self):
        lead=self.seed()
        for method,path in [('GET','/api/delivery-summary'),('POST','/api/leads/'+lead['id']+'/notes'),
                ('POST','/api/leads/'+lead['id']+'/delivery-attempts'),('PATCH','/api/leads/'+lead['id']+'/delivery-attempts/1')]:
            self.assertEqual(self.c.open(g.PREFIX+path,method=method,json={}).status_code,401)
    def test_pending_does_not_increment_contact_or_booking(self):
        lead=self.seed();r=self.attempt(lead)
        self.assertEqual(r.status_code,201,r.json)
        self.assertEqual(self.overview()['contacted'],0);self.assertEqual(self.overview()['booked'],0)
        self.assertEqual(self.s.get(lead['id'])['stage'],'qualified');self.assertFalse(r.json['sent'])
    def test_pending_blocks_duplicate_draft_and_direct_contact(self):
        lead=self.seed();self.attempt(lead)
        for path in ['/draft','/contact','/dispatch']:
            r=self.api('/api/leads/'+lead['id']+path,'POST',{})
            self.assertEqual(r.status_code,409,path)
    def test_same_request_id_is_idempotent(self):
        lead=self.seed();first=self.attempt(lead);second=self.attempt(lead)
        self.assertEqual(second.status_code,200);self.assertEqual(first.json['item']['id'],second.json['item']['id'])
        self.assertFalse(second.json['recorded'])
    def test_reused_request_id_cannot_change_content(self):
        lead=self.seed();self.attempt(lead)
        self.assertEqual(self.attempt(lead,content='不同的模拟消息').status_code,409)
    def test_reused_request_id_cannot_change_lead(self):
        lead=self.seed();self.attempt(lead)
        other=self.seed(source_url='https://www.douyin.com/video/another')
        self.assertEqual(self.attempt(other).status_code,409)
    def test_new_request_id_does_not_bypass_pending(self):
        lead=self.seed();self.attempt(lead)
        self.assertEqual(self.attempt(lead,request_id='synthetic-request-0002').status_code,409)
    def test_confirmed_visible_counts_exactly_once(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id']
        first=self.check(lead,aid);self.assertEqual(first.status_code,200,first.json)
        self.assertEqual(self.overview()['contacted'],1);self.assertEqual(self.overview()['booked'],0)
        second=self.check(lead,aid);self.assertFalse(second.json['changed'])
        self.assertEqual(self.s.get(lead['id'])['contact_count'],1)
        self.assertFalse(first.json['platform_verified']);self.assertTrue(first.json['operator_verified'])
    def test_confirmation_cannot_undo_published_record(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id'];self.check(lead,aid)
        self.assertEqual(self.check(lead,aid,status='failed').status_code,409)
    def test_not_visible_never_counts_and_does_not_retry(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id']
        self.assertEqual(self.check(lead,aid,status='not_visible').status_code,200)
        self.assertEqual(self.overview()['contacted'],0);self.assertEqual(self.overview()['qualified'],0)
        self.assertEqual(self.attempt(lead,request_id='synthetic-request-0002').status_code,409)
    def test_failed_never_counts_and_requires_evidence(self):
        lead=self.seed()
        self.assertEqual(self.attempt(lead,status='failed').status_code,400)
        r=self.attempt(lead,status='failed',checked_in_platform=True,note='平台显示模拟错误')
        self.assertEqual(r.status_code,201);self.assertEqual(self.overview()['contacted'],0)
    def test_late_visibility_can_be_confirmed_without_resending(self):
        lead=self.seed();aid=self.attempt(lead,status='not_visible',checked_in_platform=True,note='手机未显示').json['item']['id']
        self.assertEqual(self.check(lead,aid).status_code,200);self.assertEqual(self.overview()['contacted'],1)
    def test_confirmation_cannot_bypass_stop(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id']
        self.api('/api/leads/'+lead['id']+'/stop','POST',{})
        self.assertEqual(self.check(lead,aid).status_code,409);self.assertEqual(self.overview()['contacted'],0)
    def test_unqualified_lead_cannot_have_outbound_attempt(self):
        lead=self.seed(confirmed=False)
        self.assertEqual(self.attempt(lead).status_code,409)
    def test_different_platform_evidence_rejected(self):
        lead=self.seed()
        self.assertEqual(self.attempt(lead,evidence_url='https://www.xiaohongshu.com/explore/test').status_code,400)
    def test_submitted_confirmation_cannot_be_truthy_string(self):
        self.assertEqual(self.attempt(self.seed(),submitted_in_platform='true').status_code,400)
    def test_verified_confirmation_cannot_be_truthy_string(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id']
        self.assertEqual(self.check(lead,aid,checked_in_platform='true').status_code,400)
    def test_malformed_attempt_bodies_and_unknown_status_rejected(self):
        lead=self.seed();path='/api/leads/'+lead['id']+'/delivery-attempts'
        for data in [[],{}, {'unknown':True}]:self.assertEqual(self.api(path,'POST',data).status_code,400)
        self.assertEqual(self.attempt(lead,status='sent').status_code,400)
        self.assertEqual(self.attempt(lead,request_id='../invalid').status_code,400)
    def test_result_requires_nonempty_note(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id']
        self.assertEqual(self.check(lead,aid,note='').status_code,400)
    def test_attempt_id_is_bound_to_its_lead(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id'];other=self.seed(source_url='https://www.douyin.com/video/other')
        self.assertEqual(self.check(other,aid).status_code,404)
    def test_notes_are_redacted_and_do_not_call_ai(self):
        lead=self.seed();r=self.api('/api/leads/'+lead['id']+'/notes','POST',{'note':'手机未显示；电话13800138000 sk-synthetic-only123 邮箱fake@example.com'})
        self.assertEqual(r.status_code,200)
        history=self.api('/api/leads/'+lead['id']).json['activity'];raw=json.dumps(history)
        for private in ['13800138000','sk-synthetic-only123','fake@example.com']:self.assertNotIn(private,raw)
        self.assertEqual(self.calls,[]);self.assertEqual(self.overview()['contacted'],0)
    def test_invalid_note_and_missing_lead(self):
        lead=self.seed();path='/api/leads/'+lead['id']+'/notes'
        for data in [{},[],{'note':'a'},{'note':'ok','x':1},{'note':'a'*1001}]:self.assertEqual(self.api(path,'POST',data).status_code,400)
        self.assertEqual(self.api('/api/leads/missing/notes','POST',{'note':'ok'}).status_code,404)
    def test_pending_is_excluded_from_external_ready_count(self):
        lead=self.seed();self.attempt(lead)
        data=self.api('/api/external').json
        p=next(x for x in data['platforms'] if x['id']=='douyin')
        self.assertEqual(p['counts']['ready'],0);self.assertEqual(p['counts']['contacted'],0)
    def test_daily_worker_does_not_generate_again_for_pending(self):
        self.ready();lead=self.seed();self.attempt(lead);self.runjob('respond')
        self.assertEqual(self.calls,[])
    def test_invitation_worker_skips_pending_attempt(self):
        self.ready();lead=self.seed();self.attempt(lead)
        self.e.channel_content=lambda _: {'prepared':0,'published':0,'errors':[]}
        self.runjob('followup');self.assertEqual(self.calls,[])
    def test_summary_and_list_show_pending_separately(self):
        lead=self.seed();self.attempt(lead)
        summary=self.api('/api/delivery-summary').json
        self.assertEqual(summary['counts']['pending'],1);self.assertFalse(summary['automatic_external_sending'])
        self.assertEqual(self.api('/api/leads').json['items'][0]['delivery_status'],'pending')
    def test_parallel_confirmations_record_one_contact(self):
        lead=self.seed();aid=self.attempt(lead).json['item']['id']
        def check(_):
            with self.app.test_client() as c:
                return c.patch(g.PREFIX+'/api/leads/'+lead['id']+'/delivery-attempts/'+str(aid),headers=self.h,
                    json={'status':'confirmed','checked_in_platform':True,'note':'模拟独立核对已看到'}).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(check,range(4))),[200]*4)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],1)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path(__file__).with_name('delivery-verification.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'live_api_calls':0,'live_messages':0,'production_data_changes':0},indent=2),'utf-8')
    raise SystemExit(not result.wasSuccessful())
