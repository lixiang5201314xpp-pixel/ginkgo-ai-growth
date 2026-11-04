"""Receipt source regressions; isolated stores, no platform calls or messages."""
import unittest
from test_delivery import DeliveryTests


class DeliverySourceTests(DeliveryTests):
    def setUp(self):
        super().setUp()
        self.url='https://www.douyin.com/video/7702708741762243570'

    def test_another_public_post_cannot_be_a_receipt_for_this_lead(self):
        lead=self.seed(source_url=self.url)
        result=self.attempt(lead,evidence_url=self.url.replace('570','571'))
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)
        self.assertEqual(self.api('/api/leads/'+lead['id']).json['delivery'],[])

    def test_manual_contact_cannot_bypass_original_source_binding(self):
        lead=self.seed(source_url=self.url)
        result=self.api('/api/leads/'+lead['id']+'/contact','POST',{
            'account':'模拟球馆','content':'模拟已发送回复','sent_in_platform':True,
            'evidence_url':self.url.replace('570','571')})
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)

    def test_legacy_pending_wrong_source_cannot_be_confirmed(self):
        lead=self.seed(source_url=self.url)
        aid=self.attempt(lead).json['item']['id']
        with self.s.db() as c:
            c.execute('UPDATE delivery_attempts SET evidence_url=? WHERE id=?',
                      (self.url.replace('570','571'),aid))
        result=self.check(lead,aid)
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)
        self.assertEqual(self.api('/api/leads/'+lead['id']).json['delivery'][0]['status'],'pending')

    def test_same_douyin_note_identity_remains_usable(self):
        lead=self.seed(source_url=self.url)
        result=self.attempt(lead,evidence_url=self.url.replace('/video/','/note/')+'?from=public-search')
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.check(lead,result.json['item']['id']).status_code,200)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],1)

    def test_same_xhs_note_alias_and_signature_remain_usable(self):
        ident='6ae233c7000000003501eedb'
        lead=self.seed(platform='xiaohongshu',source_url='https://www.xiaohongshu.com/explore/'+ident+'?xsec_token=synthetic-old')
        result=self.attempt(lead,evidence_url='https://www.xiaohongshu.com/discovery/item/'+ident+'?xsec_token=synthetic-new')
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.check(lead,result.json['item']['id']).status_code,200)

    def test_unknown_source_query_identity_cannot_be_dropped(self):
        # Synthetic opaque source illustrates why arbitrary queries cannot be
        # discarded; this is not a claimed real WeChat Channels permalink.
        lead=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=first')
        result=self.attempt(lead,evidence_url='https://channels.weixin.qq.com/example?objectId=second')
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)

    def test_wrong_xhs_id_cannot_be_hidden_behind_the_other_route(self):
        lead=self.seed(platform='xiaohongshu',source_url='https://www.xiaohongshu.com/explore/6ae233c7000000003501eedb')
        result=self.attempt(lead,evidence_url='https://www.xiaohongshu.com/discovery/item/6ae233c7000000003501eedc')
        self.assertEqual(result.status_code,400,result.json)

    def test_same_kuaishou_public_post_with_tracking_parameters_remains_usable(self):
        lead=self.seed(platform='kuaishou',source_url='https://www.kuaishou.com/short-video/3x5w7pnxqe29hpc')
        result=self.attempt(lead,evidence_url=lead['source_url']+'?source=public-share')
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.check(lead,result.json['item']['id']).status_code,200)

    def test_search_page_cannot_stand_in_for_a_post_receipt(self):
        lead=self.seed(source_url=self.url)
        result=self.attempt(lead,evidence_url='https://www.douyin.com/search/成都乒乓球')
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)

    def test_same_public_douyin_overlay_is_usable_without_a_second_send(self):
        lead=self.seed(source_url=self.url)
        result=self.attempt(lead,evidence_url='https://www.douyin.com/search/成都乒乓球?modal_id=7702708741762243570')
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.check(lead,result.json['item']['id']).status_code,200)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],1)

    def test_a_different_selected_overlay_cannot_be_used_as_evidence(self):
        lead=self.seed(source_url=self.url)
        result=self.attempt(lead,evidence_url='https://www.douyin.com/search/成都乒乓球?modal_id=7702708741762243571')
        self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.s.get(lead['id'])['contact_count'],0)

    def test_inbound_manual_evidence_keeps_existing_platform_validation(self):
        lead=self.seed(source_url=self.url,relation='inbound')
        result=self.attempt(lead,evidence_url='https://www.douyin.com/example-inbound-thread')
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.check(lead,result.json['item']['id']).status_code,200)


if __name__=='__main__':
    # Run only new cases here. Inherited delivery regressions run separately.
    names=[n for n in DeliverySourceTests.__dict__ if n.startswith('test_')]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(DeliverySourceTests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
