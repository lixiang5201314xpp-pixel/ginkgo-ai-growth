"""External intake regression tests: synthetic public requests only, no live AI or contacts."""
import json
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from test_ai import Tests as Base
import growth_acquisition as g
from growth_external import publication_time
from growth_ai import CST


class ExternalTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    ready=Base.ready
    runjob=Base.runjob
    def api(self,path,method='GET',data=None):return self.c.open(g.PREFIX+path,method=method,headers=self.h,json=data)
    def row(self,**kw):return {'platform':'douyin','source_url':'https://www.douyin.com/video/synthetic',
        'excerpt':'我在成都，想找乒乓球教练，请问哪里能学？','posted_text':'2小时前',
        'captured_at':datetime.now(CST).isoformat(),**kw}
    def preview(self,*rows):return self.api('/api/external/preview','POST',{'items':list(rows)})
    def intake(self,*rows,**kw):return self.api('/api/external/import','POST',{'items':list(rows),'source_reviewed':True,**kw})
    def total(self):
        with self.s.db() as c:return c.execute('SELECT COUNT(*) FROM leads').fetchone()[0]

    def test_admin_guards(self):
        self.assertEqual(self.c.get(g.PREFIX+'/external/health').status_code,200)
        self.assertEqual(self.c.get(g.PREFIX+'/api/external').status_code,401)
        for route in ('preview','import'):self.assertEqual(self.c.post(g.PREFIX+'/api/external/'+route,json={'items':[self.row()]}).status_code,401)
    def test_six_external_channels_and_native_searches(self):
        d=self.api('/api/external').json
        self.assertEqual(len(d['platforms']),6);self.assertFalse(d['sending_connected'])
        for p in d['platforms']:
            self.assertEqual(len(p['searches']),4)
            if p['id']=='channels':self.assertTrue(all(x['url'] is None for x in p['searches']))
            else:self.assertTrue(all(x['url'].startswith('https://') for x in p['searches']))
        self.assertEqual(self.calls,[])
    def test_preview_never_imports(self):
        r=self.preview(self.row());self.assertEqual(r.status_code,200);self.assertTrue(r.json['items'][0]['assessment']['eligible'])
        self.assertEqual(self.total(),0);self.assertEqual(self.calls,[])
    def test_import_requires_source_review(self):
        self.assertEqual(self.intake(self.row(),source_reviewed=False).status_code,400);self.assertEqual(self.total(),0)
    def test_reviewed_comment_is_external_need_not_internal_inquiry(self):
        r=self.intake(self.row());self.assertEqual(r.status_code,201);self.assertEqual(r.json['added'],1)
        with self.s.db() as c:
            row=c.execute('SELECT * FROM leads').fetchone();self.assertEqual(row['relation'],'public_request');self.assertEqual(row['contact_count'],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inquiries').fetchone()[0],0)
        self.assertFalse(r.json['booking_created']);self.assertEqual(self.calls,[])
    def test_dedup_repeated_comment_and_batch(self):
        self.assertEqual(self.intake(self.row(),self.row()).json['duplicates'],1)
        self.assertEqual(self.intake(self.row()).json['added'],0);self.assertEqual(self.total(),1)
    def test_new_external_need_queues_existing_ai_preparation(self):
        self.ready();r=self.intake(self.row(),prepare_replies=True);job=r.json['job']
        self.assertEqual(job['kind'],'respond');self.assertEqual(self.calls,[])
        self.e.run(job['id']);self.assertNotEqual(self.e.job(job['id'])['status'],'failed')
        with self.s.db() as c:
            row=c.execute('SELECT * FROM leads').fetchone();self.assertTrue(row['latest_reply']);self.assertEqual(row['contact_count'],0)
    def test_whole_batch_validated_before_writes(self):
        r=self.intake(self.row(),self.row(source_url='https://evil.invalid/a'))
        self.assertEqual(r.status_code,400);self.assertEqual(self.total(),0)
    def test_rejection_and_advertising_not_imported(self):
        for text in ['成都乒乓球不要联系我，不想找教练','成都乒乓球培训班招生，欢迎报名','成都乒乓球打得真好看']:
            self.assertEqual(self.intake(self.row(excerpt=text)).status_code,400,text)
        self.assertEqual(self.total(),0)
    def test_comment_without_city_is_pending(self):
        r=self.intake(self.row(excerpt='想找乒乓球教练，请问哪里能学？'))
        self.assertEqual(r.json['items'][0]['stage'],'new')
    def test_caption_city_context_can_be_reviewed(self):
        r=self.preview(self.row(excerpt='请问哪里可以学乒乓球？',source_context='成都青羊的乒乓球训练日常'))
        self.assertTrue(r.json['items'][0]['assessment']['local'])
    def test_ip_and_search_keywords_do_not_prove_city(self):
        for context in ['IP属地：成都','搜索关键词：成都乒乓球']:
            r=self.preview(self.row(excerpt='请问哪里可以学乒乓球？',source_context=context))
            self.assertFalse(r.json['items'][0]['assessment']['local'])
    def test_does_not_invent_time_from_capture(self):
        r=self.intake(self.row(posted_text=''))
        self.assertEqual(r.json['items'][0]['stage'],'new')
        with self.s.db() as c:self.assertIsNone(c.execute('SELECT posted_at FROM leads').fetchone()[0])
    def test_future_publication_rejected(self):
        r=self.intake(self.row(posted_at=(datetime.now(CST)+timedelta(days=3)).isoformat()))
        self.assertEqual(r.status_code,400);self.assertEqual(self.total(),0)
    def test_future_capture_rejected(self):
        self.assertEqual(self.preview(self.row(captured_at=(datetime.now(CST)+timedelta(days=2)).isoformat())).status_code,400)
    def test_contacts_and_keys_redacted_before_ai(self):
        self.ready();r=self.intake(self.row(excerpt='成都想找乒乓球教练，电话13800138000 微信abcdef123 sk-notarealkey1234'),prepare_replies=True)
        self.e.run(r.json['job']['id']);raw=str(self.calls)
        self.assertNotIn('13800138000',raw);self.assertNotIn('abcdef123',raw);self.assertNotIn('sk-notarealkey1234',raw)
    def test_batch_count_limits(self):
        for items in ([],[self.row()]*21):self.assertEqual(self.api('/api/external/preview','POST',{'items':items}).status_code,400)
    def test_invalid_body_is_not_server_error(self):
        self.assertEqual(self.api('/api/external/preview','POST',['invalid']).status_code,400)
    def test_url_platform_mismatch_rejected(self):
        self.assertEqual(self.preview(self.row(platform='kuaishou')).status_code,400)
    def test_miniapp_and_search_list_are_not_external_source_posts(self):
        for url in ['https://www.douyin.com/search/test','https://developer.open-douyin.com/docs/test']:
            self.assertEqual(self.preview(self.row(source_url=url)).status_code,400)
        r=self.preview(self.row(platform='xiaohongshu',source_url='https://miniapp.xiaohongshu.com/mini/app'))
        self.assertEqual(r.status_code,400)
    def test_declared_chengdu_departure_not_a_local_customer(self):
        r=self.preview(self.row(excerpt='已经离开成都，想找乒乓球教练'))
        self.assertFalse(r.json['items'][0]['assessment']['local'])
    def test_overview_separates_public_need_counts_from_internal_inquiries(self):
        self.intake(self.row());d=self.api('/api/external').json
        p=next(x for x in d['platforms'] if x['id']=='douyin')
        self.assertEqual(p['counts']['recorded'],1);self.assertEqual(p['counts']['contacted'],0);self.assertEqual(p['counts']['booked'],0)
    def test_time_parsing_keeps_china_calendar_and_rejects_bad_labels(self):
        now=datetime(2026,10,31,1,30,tzinfo=CST)
        self.assertEqual(publication_time('2小时前',now,None,g.parse_time),datetime(2026,10,30,23,30,tzinfo=CST).isoformat())
        self.assertEqual(publication_time('昨天 18:20',now,None,g.parse_time),datetime(2026,10,30,18,20,tzinfo=CST).isoformat())
        self.assertIn('2026-10-30',publication_time('2026-10-30T11:12:13.123Z',now,None,g.parse_time))
        self.assertIsNone(publication_time('IP属地四川',now,None,g.parse_time))
    def test_douyin_modal_is_canonical_and_deduplicates_detail(self):
        url='https://www.douyin.com/search/synthetic?modal_id=7701372394577607067&type=general'
        r=self.preview(self.row(source_url=url))
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['items'][0]['source_url'],'https://www.douyin.com/video/7701372394577607067')
        self.assertEqual(self.intake(self.row(source_url=url)).json['added'],1)
        self.assertEqual(self.intake(self.row(source_url='https://www.douyin.com/video/7701372394577607067')).json['duplicates'],1)
    def test_invalid_or_multiple_modal_ids_do_not_make_search_a_source(self):
        for query in ['modal_id=not-an-id','modal_id=12','modal_id=7701372394577607067&modal_id=7701372394577607068']:
            self.assertEqual(self.preview(self.row(source_url='https://www.douyin.com/search/x?'+query)).status_code,400)
    def test_province_suffix_parses_time_without_inventing_city(self):
        now=datetime(2026,11,1,1,30,tzinfo=CST)
        self.assertEqual(publication_time('3天前·四川',now,None,g.parse_time),datetime(2026,10,29,1,30,tzinfo=CST).isoformat())
        self.assertEqual(publication_time('10-27 · 四川',now,None,g.parse_time),datetime(2026,10,27,tzinfo=CST).isoformat())
        r=self.preview(self.row(excerpt='哪里能找乒乓球教练？',posted_text='3天前·四川'))
        self.assertTrue(r.json['items'][0]['posted_at']);self.assertFalse(r.json['items'][0]['assessment']['local'])
    def test_xhs_date_with_province_and_no_separator(self):
        now=datetime(2026,11,1,10,30,tzinfo=CST)
        for label in ['10-16 四川','10-16四川','10-16 09:10四川','3天前四川']:
            with self.subTest(label=label):
                self.assertIsNotNone(publication_time(label,now,None,g.parse_time))
                r=self.preview(self.row(excerpt='请问哪里能学乒乓球？',posted_text=label))
                self.assertFalse(r.json['items'][0]['assessment']['local'])
        self.assertIsNone(publication_time('IP属地四川',now,None,g.parse_time))
        self.assertIsNone(publication_time('10-16 未知地区',now,None,g.parse_time))
    def test_post_date_label_and_type_survive_review(self):
        r=self.preview(self.row(source_kind='post',posted_text='发布时间：2026-10-27 23:38'))
        self.assertEqual(r.json['items'][0]['source_kind'],'post')
        self.assertEqual(r.json['items'][0]['posted_at'],'2026-10-27T23:38:00+08:00')
        r2=self.intake(r.json['items'][0]);self.assertEqual(r2.json['added'],1)
    def test_unrecognized_source_kind_is_rejected(self):
        self.assertEqual(self.preview(self.row(source_kind='private_message')).status_code,400)
    def test_ball_partner_question_from_real_page_shape_is_not_lost(self):
        quote='川大江安附近有没有厉害的球搭子，约个表演赛！#业余乒乓球对决'
        r=self.preview(self.row(excerpt=quote,source_kind='post'))
        self.assertTrue(r.json['items'][0]['assessment']['explicit_demand'])
        self.assertFalse(r.json['items'][0]['assessment']['local'])
        # Location needs separately reviewed evidence, not a search query or province.
        r=self.preview(self.row(excerpt=quote,source_kind='post',city_evidence='模拟核实：作者原文明示成都双流'))
        self.assertTrue(r.json['items'][0]['assessment']['eligible'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExternalTests))
    Path(__file__).with_name('external-verification.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'paid_requests':0,'live_messages':0,'business_database_changes':0},indent=2),'utf-8')
    sys.exit(not result.wasSuccessful())
