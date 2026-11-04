"""Synthetic operational regressions. No paid calls, messages or business DB."""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from test_ai import Tests as Base
import growth_acquisition as g
from growth_ai import CST


class WorkflowTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    ready=Base.ready
    seed=Base.seed
    def runjob(self,kind):
        result=Base.runjob(self,kind)
        self.assertNotEqual(result['status'],'failed','Synthetic job failed: '+result.get('error','unknown'))
        return result

    def api(self,path,method='GET',data=None):
        return self.c.open(g.PREFIX+path,method=method,headers=self.h,json=data)

    def inquiry(self):
        r=self.c.post(g.PREFIX+'/public/inquiry',json={'campaign_id':'douyin-training','alias':'模拟家长',
            'contact':'13800138000','interest':'training','availability':'周末晚上','district':'青羊',
            'consent':True,'adult_or_guardian':True})
        self.assertEqual(r.status_code,201)
        with self.s.db() as c:return dict(c.execute('SELECT * FROM inquiries').fetchone())

    def plans(self):return self.api('/api/workflow/plans').json['items']
    def contents(self):return self.api('/api/workflow/content').json['items']

    def test_all_new_admin_routes_require_login(self):
        for path in ['/api/workflow','/api/workflow/plans','/api/workflow/content','/api/workflow/content/export']:
            self.assertEqual(self.c.get(g.PREFIX+path).status_code,401)
        for path,method in [('/api/candidates/a','PATCH'),('/api/workflow/plans/a','PATCH'),('/api/workflow/content/a/published','POST')]:
            self.assertEqual(self.c.open(g.PREFIX+path,method=method,json={}).status_code,401)
        self.assertEqual(self.c.get(g.PREFIX+'/workflow/health').json['version'],'growth-workflow-1.2.0')

    def test_search_quota_does_not_pause_text_jobs(self):
        self.ready(daily_search_limit=1)
        self.ai.search('site:douyin.com 成都 乒乓球')
        self.assertFalse(self.e.budget_paused())
        self.seed();job=self.runjob('all')
        self.assertEqual(job['result']['respond']['drafts_prepared'],1)
        self.assertEqual(job['result']['followup']['channel_drafts']['prepared'],4)
        self.assertEqual(job['result']['discover']['error_code'],'daily_limit')

    def test_background_text_limit_still_reserves_inbound(self):
        self.ready(daily_ai_limit=3)
        for _ in range(2):self.ai.reserve('chat',self.ai.config(),background=True)
        self.assertTrue(self.e.budget_paused())
        self.ai.reserve('chat',self.ai.config())

    def test_daily_searches_training_then_competition_never_repeat(self):
        self.ready();a=self.runjob('discover');b=self.runjob('discover');c=self.runjob('discover')
        self.assertEqual([x['result']['discover']['queries_completed'] for x in (a,b,c)],[4,4,0])
        self.assertEqual(c['result']['discover']['searches_skipped'],4)
        searches=[x[3]['query'] for x in self.calls if x[1].endswith('/search')]
        self.assertEqual(len(set(searches)),8)
        self.assertTrue(all(len(x)<=128 for x in searches))

    def test_failed_search_can_retry_after_backoff(self):
        self.ready();self.fail='network';self.runjob('discover');self.fail=None
        with self.s.db() as c:c.execute('UPDATE growth_search_runs SET updated_at=?',((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),))
        self.assertEqual(self.runjob('discover')['result']['discover']['queries_completed'],4)

    def test_previously_screened_candidates_not_billed_again(self):
        self.ready();self.runjob('discover');before=len([x for x in self.calls if x[1].endswith('/chat/completions')])
        b=self.runjob('discover')
        self.assertEqual(b['result']['discover']['ai_screened'],0)
        self.assertEqual(len([x for x in self.calls if x[1].endswith('/chat/completions')]),before)

    def test_unchanged_lead_skipped_without_rewriting_draft(self):
        self.ready();lead=self.seed();self.runjob('respond');before=self.s.get(lead['id'])
        result=self.runjob('respond')['result']['respond']
        self.assertEqual(result['analyzed'],0);self.assertEqual(result['unchanged_skipped'],1)
        self.assertEqual(self.s.get(lead['id'])['reply_version'],before['reply_version'])

    def test_changed_lead_gets_fresh_analysis(self):
        self.ready();lead=self.seed();self.runjob('respond')
        with self.s.db() as c:c.execute("UPDATE leads SET city_evidence='成都金牛周末' WHERE id=?",(lead['id'],))
        self.assertEqual(self.runjob('respond')['result']['respond']['analyzed'],1)

    def test_old_unchanged_leads_do_not_starve_new_lead(self):
        self.ready()
        for i in range(12):self.seed(source_url='https://www.douyin.com/video/'+str(i),excerpt='成都想学乒乓球找教练'+str(i))
        for _ in range(3):self.runjob('respond')
        self.seed(source_url='https://www.douyin.com/video/new',excerpt='成都新咨询找乒乓球教练')
        result=self.runjob('respond')['result']['respond']
        self.assertEqual(result['analyzed'],1);self.assertEqual(result['unchanged_skipped'],12)

    def test_followup_due_time_not_postponed_on_repeat(self):
        self.ready();self.seed();self.runjob('followup');a=self.plans()[0]
        r=self.runjob('followup')['result']['followup'];b=self.plans()[0]
        self.assertEqual(r['plans_prepared'],0);self.assertEqual(r['unchanged_skipped'],1)
        self.assertEqual(a['due_at'],b['due_at']);self.assertEqual(a['id'],b['id'])

    def test_inquiry_prioritized_and_contacts_redacted(self):
        self.ready();self.seed();self.inquiry();self.runjob('followup')
        payload=json.loads(self.calls[0][3]['messages'][1]['content'])
        self.assertIn('周末晚上',payload['request_text']);self.assertNotIn('13800138000',json.dumps(self.calls))

    def test_stopped_subject_plan_hidden_and_cannot_reactivate(self):
        self.ready();lead=self.seed();self.runjob('followup');pid=self.plans()[0]['id']
        with self.s.db() as c:c.execute("UPDATE leads SET stage='blocked',stopped=1 WHERE id=?",(lead['id'],))
        self.assertEqual(self.plans(),[])
        self.assertEqual(self.api('/api/workflow/plans/'+pid,'PATCH',{'status':'pending'}).status_code,404)

    def test_inquiry_closed_during_generation_does_not_save_plan(self):
        self.ready();row=self.inquiry();original=self.ai.transport
        def close(*args,**kw):
            with self.s.db() as c:c.execute("UPDATE inquiries SET stage='closed' WHERE id=?",(row['id'],))
            return original(*args,**kw)
        self.ai.transport=close;self.runjob('followup');self.assertEqual(self.plans(),[])

    def test_plan_done_not_contacted_or_booked(self):
        self.ready();lead=self.seed();self.runjob('followup');pid=self.plans()[0]['id']
        r=self.api('/api/workflow/plans/'+pid,'PATCH',{'status':'done'})
        self.assertEqual(r.status_code,200);self.assertFalse(r.json['sent'])
        self.assertEqual(self.api('/api/workflow').json['pending_plans'],0)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)
        self.runjob('followup');self.assertEqual(self.plans()[0]['status'],'done')

    def test_published_requires_same_platform_actual_url(self):
        self.ready();self.runjob('followup');x=self.contents()[0]
        for url in ['https://evil.invalid/post/1','http://www.douyin.com/post/1']:
            self.assertEqual(self.api('/api/workflow/content/'+x['id']+'/published','POST',{'url':url}).status_code,400)
        self.assertEqual(self.contents()[0]['status'],'draft')

    def test_content_receipt_and_export_do_not_count_booking(self):
        self.ready();self.runjob('followup');x=next(x for x in self.contents() if x['platform']=='douyin')
        r=self.api('/api/workflow/content/'+x['id']+'/published','POST',{'url':'https://www.douyin.com/video/synthetic'})
        self.assertEqual(r.status_code,200);self.assertFalse(r.json['automatically_verified'])
        d=self.api('/api/workflow').json;self.assertEqual(d['published_content'],1);self.assertEqual(d['bookings_with_receipt'],0)
        self.assertIn('银杏奖牌',self.api('/api/workflow/content/export').text)
        self.assertIn('text/csv',self.api('/api/workflow/content/export?format=csv').content_type)

    def test_same_day_content_not_overwritten_after_publication(self):
        self.ready();self.runjob('followup');x=next(x for x in self.contents() if x['platform']=='douyin')
        self.api('/api/workflow/content/'+x['id']+'/published','POST',{'url':'https://www.douyin.com/video/synthetic'})
        self.runjob('followup');y=next(y for y in self.contents() if y['id']==x['id'])
        self.assertEqual(y['body'],x['body']);self.assertEqual(y['status'],'published')

    def test_archive_candidate_removed_from_backlog(self):
        self.ready();self.runjob('discover');cid=self.api('/api/candidates').json['items'][0]['id']
        self.assertEqual(self.api('/api/candidates/'+cid,'PATCH',{'status':'ignored'}).status_code,200)
        self.assertEqual(self.api('/api/workflow').json['pending_sources'],3)
        self.assertEqual(self.api('/api/candidates/'+cid,'PATCH',{'status':'customer'}).status_code,400)

    def test_optional_channel_absence_is_not_reported_as_connected(self):
        d=self.api('/api/workflow').json
        self.assertEqual(d['active_reception'],[]);self.assertEqual(d['bookings_with_receipt'],0)

    def test_wechat_reception_state_and_key_not_modified(self):
        class Channel:
            def status(self):return {'items':[{'name':'微信','automatic':True,'verified_at':42}],
                'counts':[{'state':'sent','n':12},{'state':'human','n':2}]}
        self.app.extensions['ginkgo_growth']['channels']=Channel()
        with self.s.db() as c:c.execute("INSERT INTO settings VALUES('preserve-key','encrypted-synthetic')")
        d=self.api('/api/workflow').json;self.assertEqual(d['active_reception'],['微信'])
        self.assertEqual(d['customer_service_human'],2)
        self.ready();self.runjob('all')
        with self.s.db() as c:self.assertEqual(c.execute("SELECT value FROM settings WHERE key='preserve-key'").fetchone()[0],'encrypted-synthetic')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path(__file__).with_name('workflow-verification.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'paid_calls':0,'business_sql_writes':0,'platform_messages_sent':0},indent=2),'utf-8')
    sys.exit(not result.wasSuccessful())
