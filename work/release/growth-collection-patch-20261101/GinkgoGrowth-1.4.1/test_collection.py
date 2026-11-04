import uuid
from datetime import datetime, timedelta, timezone
from test_external import ExternalTests
import growth_acquisition as g

class CollectionTests(ExternalTests):
    def enable(self):
        return self.api('/api/collection', 'PUT', {'enabled': True})

    def batch(self, row=None, **overrides):
        row = row or self.row(source_url='https://www.douyin.com/video/7701372394577607000')
        return dict(batch_id=uuid.uuid4().hex, items=[row], observation={
            'read_scope': 'rendered_public_page', 'page_url': row['source_url'],
            'observed_at': datetime.now(timezone.utc).isoformat()}, **overrides)

    def submit(self, data):
        return self.api('/api/collection/batches', 'POST', data)

    def test_collection_admin_and_default_off(self):
        self.assertEqual(self.c.get(g.PREFIX+'/api/collection').status_code, 401)
        self.assertEqual(self.c.put(g.PREFIX+'/api/collection', json={'enabled':True}).status_code,401)
        self.assertEqual(self.c.post(g.PREFIX+'/api/collection/batches', json=self.batch()).status_code,401)
        self.assertFalse(self.api('/api/collection').json['enabled'])
        self.assertEqual(self.submit(self.batch()).status_code,409)

    def test_visible_public_need_auto_imports_and_queues_without_sending(self):
        self.enable(); self.ready()
        r = self.submit(self.batch())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['added_valid'],1)
        self.assertTrue(r.json['job_id'])
        self.assertEqual(r.json['sent'],0)
        self.assertEqual(self.calls,[])
        self.e.run(r.json['job_id'])
        row = self.s.get(r.json['lead_ids'][0])
        self.assertTrue(row['latest_reply'])
        self.assertEqual(row['contact_count'],0)

    def test_batch_replay_is_idempotent_and_mismatch_rejected(self):
        self.enable(); data=self.batch()
        first=self.submit(data); second=self.submit(data)
        self.assertEqual(second.json['lead_ids'], first.json['lead_ids'])
        self.assertTrue(second.json['replayed'])
        data['items'][0]['excerpt'] += '想学反手'
        self.assertEqual(self.submit(data).status_code,400)
        self.assertEqual(self.total(),1)

    def test_unproven_city_or_date_stays_pending_no_ai_job(self):
        self.enable()
        for row in [self.row(excerpt='想找乒乓球教练，请问哪里能学？'),self.row(posted_text='')]:
            r=self.submit(self.batch(row))
            self.assertEqual(r.json['added_valid'],0)
            self.assertEqual(r.json['pending_review'],1)
            self.assertIsNone(r.json['job_id'])

    def test_stale_observation_and_mixed_source_rejected(self):
        self.enable(); data=self.batch()
        data['observation']['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        self.assertEqual(self.submit(data).status_code,400)
        data=self.batch();data['observation']['page_url']='https://www.douyin.com/video/7701372394577607001'
        self.assertEqual(self.submit(data).status_code,400)
        self.assertEqual(self.total(),0)

    def test_disabled_or_empty_or_bad_config(self):
        self.enable(); data=self.batch();data['items']=[]
        self.assertEqual(self.submit(data).status_code,400)
        for cfg in [{'enabled':1},{'enabled':True,'send':True},[]]:
            self.assertEqual(self.api('/api/collection','PUT',cfg).status_code,400)
        self.api('/api/collection','PUT',{'enabled':False})
        self.assertEqual(self.submit(self.batch()).status_code,409)

    def test_ads_and_rejection_never_imported(self):
        self.enable()
        for quote in ['成都乒乓球培训班招生，欢迎报名','成都乒乓球不要联系我，不想找教练']:
            r=self.submit(self.batch(self.row(excerpt=quote)))
            self.assertEqual(r.json['skipped'],1)
        self.assertEqual(self.total(),0)

    def test_rotated_tracking_url_does_not_duplicate_existing_demand(self):
        self.enable()
        first=self.row(source_url='https://www.xiaohongshu.com/explore/6ae233c7000000003501eedb?xsec_token=first',platform='xiaohongshu')
        second={**first,'source_url':first['source_url'].replace('first','second')}
        self.assertEqual(self.submit(self.batch(first)).json['added_valid'],1)
        result=self.submit(self.batch(second)).json
        self.assertEqual(result['added_valid'],0)
        self.assertEqual(result['duplicates'],1)
        self.assertEqual(self.total(),1)

    def test_old_manual_image_transcription_does_not_become_second_post(self):
        self.enable()
        url='https://www.xiaohongshu.com/explore/6ae233c7000000003501eedb'
        self.s.add(dict(platform='xiaohongshu',source_url=url,excerpt='找一位成都乒乓球教练。图片补充：提高正手。',posted_at=datetime.now(timezone.utc).isoformat(),confirmed=True),'模拟旧版本')
        row=self.row(platform='xiaohongshu',source_url=url+'?xsec_token=rotated',source_kind='post',excerpt='找一位成都乒乓球教练 #成都 #乒乓球')
        result=self.submit(self.batch(row)).json
        self.assertEqual(result['duplicates'],1)
        self.assertEqual(result['added_valid'],0)
        self.assertEqual(self.total(),1)

    def test_caption_city_does_not_auto_locate_comment_author(self):
        self.enable()
        row=self.row(excerpt='想找乒乓球教练，请问哪里能学？',source_context='成都青羊区乒乓球训练')
        r=self.submit(self.batch(row)).json
        self.assertEqual(r['added_valid'],0)
        self.assertEqual(r['pending_review'],1)

    def test_post_title_formatting_does_not_reopen_archived_source(self):
        self.enable()
        url='https://www.douyin.com/video/7539834374747032889'
        old,_=self.s.add(dict(platform='douyin',source_url=url,excerpt='第9集：成年业余乒乓球需要找教练吗#乒乓球',confirmed=False),'旧版模拟')
        with self.s.db() as c:c.execute("UPDATE leads SET stage='archived' WHERE id=?",(old['id'],))
        row=self.row(source_url=url,source_kind='post',excerpt='第9集 | 成年业余乒乓球需要找教练吗#乒乓球')
        r=self.submit(self.batch(row)).json
        self.assertEqual(r['duplicates'],1)
        self.assertEqual(r['added'],0)
        self.assertEqual(self.total(),1)
        self.assertEqual(self.s.get(old['id'])['stage'],'archived')

    def test_known_old_post_and_comment_are_skipped_without_ai_or_pending_record(self):
        self.enable()
        old=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()
        for kind in ('post','comment'):
            row=self.row(source_kind=kind,posted_at=old)
            r=self.submit(self.batch(row)).json
            self.assertEqual(r['skipped'],1)
            self.assertEqual(r['pending_review'],0)
            self.assertEqual(r['added'],0)
            self.assertIsNone(r['job_id'])
        self.assertEqual(self.total(),0)
        self.assertEqual(self.calls,[])

    def test_fresh_comments_on_same_old_post_remain_distinct_requests(self):
        self.enable()
        first=self.row(source_kind='comment',excerpt='我在成都，想找乒乓球教练，周末有空。')
        second={**first,'excerpt':'成都想找乒乓球球友，工作日晚上能打吗？'}
        self.assertEqual(self.submit(self.batch(first)).json['added_valid'],1)
        self.assertEqual(self.submit(self.batch(second)).json['added_valid'],1)
        self.assertEqual(self.total(),2)

    def test_same_title_on_different_posts_does_not_merge(self):
        self.enable()
        first=self.row(source_kind='post',excerpt='成都想找乒乓球教练，请问哪里能学？')
        second={**first,'source_url':'https://www.douyin.com/video/7701372394577607001'}
        self.assertEqual(self.submit(self.batch(first)).json['added_valid'],1)
        self.assertEqual(self.submit(self.batch(second)).json['added_valid'],1)
        self.assertEqual(self.total(),2)

if __name__ == '__main__':
    import unittest
    unittest.main()
