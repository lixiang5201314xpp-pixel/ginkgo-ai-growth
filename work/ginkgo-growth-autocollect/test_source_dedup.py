"""Stable-source intake regressions using temporary acquisition stores only."""
import hashlib
import re
import unittest
from test_growth import GrowthTests


class SourceDedupTests(GrowthTests):
    def test_different_opaque_post_queries_are_not_one_lead(self):
        first=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=first')
        second=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=second')
        self.assertNotEqual(first['id'],second['id'])

    def test_equivalent_query_order_keeps_one_lead(self):
        first=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=first&lang=zh')
        second=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?lang=zh&objectId=first')
        self.assertEqual(first['id'],second['id'])

    def legacy(self,row,url=None):
        import sqlite3
        from contextlib import closing
        from pathlib import Path
        url=url or row['source_url']
        from urllib.parse import urlsplit
        p=urlsplit(url)
        fp=hashlib.sha256((row['platform']+'|'+p.scheme+'://'+p.netloc+p.path.rstrip('/')+'|'+re.sub(r'\s+','',row['excerpt'])).encode()).hexdigest()
        with closing(sqlite3.connect(str(Path(self.tmp.name)/'acquisition.sqlite3'))) as c:
            c.execute("UPDATE leads SET source_url=?,fingerprint=?,stage='closed',stopped=1,contact_count=1 WHERE id=?",(url,fp,row['id']))
            c.commit()

    def test_legacy_query_collision_does_not_hide_a_different_original(self):
        first=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=first')
        self.legacy(first)
        second=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=second')
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(second['contact_count'],0)
        old=self.get('/api/leads/'+first['id']).json['item']
        self.assertEqual(old['contact_count'],1)
        self.assertEqual(old['stage'],'closed')

    def test_same_legacy_query_keeps_stop_and_contact_state_after_whitespace_change(self):
        first=self.seed(platform='channels',source_url='https://channels.weixin.qq.com/example?objectId=first')
        self.legacy(first)
        second=self.seed(platform='channels',source_url=first['source_url'],excerpt=first['excerpt'].replace('成都','成 都'))
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(second['contact_count'],1)
        self.assertEqual(second['stopped'],1)

    def test_same_xhs_route_aliases_share_intake_identity(self):
        ident='6ae233c7000000003501eedb'
        first=self.seed(platform='xiaohongshu',source_url='https://www.xiaohongshu.com/explore/'+ident)
        second=self.seed(platform='xiaohongshu',source_url='https://www.xiaohongshu.com/discovery/item/'+ident+'?xsec_token=synthetic')
        self.assertEqual(first['id'],second['id'])

    def test_legacy_xhs_alias_and_whitespace_do_not_reopen_a_contacted_lead(self):
        ident='6ae233c7000000003501eedb'
        first=self.seed(platform='xiaohongshu',source_url='https://www.xiaohongshu.com/explore/'+ident)
        self.legacy(first,'https://www.xiaohongshu.com/discovery/item/'+ident)
        second=self.seed(platform='xiaohongshu',source_url=first['source_url'],excerpt=first['excerpt'].replace('成都','成 都'))
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(second['contact_count'],1)
        self.assertEqual(second['stopped'],1)


if __name__=='__main__':
    names=[n for n in SourceDedupTests.__dict__ if n.startswith('test_')]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(SourceDedupTests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
