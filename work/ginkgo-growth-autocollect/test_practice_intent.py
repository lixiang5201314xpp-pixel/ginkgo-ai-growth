"""Actual wording regression; isolated data, no live generation or contacts."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'python-deps'))
import growth_acquisition as growth


class PracticeIntentTests(unittest.TestCase):
    def assess(self, value):
        return growth.classify(value, posted_at=datetime.now(timezone.utc).isoformat())

    def test_actual_newcomer_single_ball_request(self):
        result = self.assess('成华区有人一起练单球吗，本人萌新#乒乓球搭子 #成都成华区 #约乒乓球 #成都搭子')
        self.assertTrue(result['eligible'])
        self.assertEqual(result['intent'], 'practice')

    def test_someone_to_play_in_chengdu(self):
        self.assertTrue(self.assess('成都有人愿意一起打乒乓球吗，周末有空')['eligible'])

    def test_basic_practice_partner_request(self):
        self.assertTrue(self.assess('成都来个练基本功的搭子#乒乓球训练')['eligible'])

    def test_refusal_still_blocks(self):
        self.assertFalse(self.assess('成都有人一起练单球吗#乒乓球搭子，但不要联系我')['eligible'])

    def test_no_chengdu_evidence_does_not_qualify(self):
        self.assertFalse(self.assess('有人一起练单球吗#乒乓球搭子')['eligible'])

    def test_completed_activity_is_not_an_invitation(self):
        self.assertFalse(self.assess('成都今天和朋友一起练单球很开心#乒乓球搭子')['eligible'])

    def test_generic_sport_interest_is_not_a_need(self):
        self.assertFalse(self.assess('成都乒乓球真好玩，喜欢一起练球的感觉')['eligible'])

    def test_recruiter_does_not_become_a_customer(self):
        self.assertFalse(self.assess('成都招聘乒乓球教练，有人一起打球吗')['eligible'])

    def test_club_reception_reply_does_not_become_a_customer(self):
        self.assertTrue(self.assess('你好，我是银杏乒乓球俱乐部工作人员。看到你在成都想练单球，可以先选适合的组别认识球友。')['rejected'])

    def test_club_member_can_still_seek_a_partner(self):
        self.assertTrue(self.assess('我是成都某乒乓球俱乐部会员，有人一起打乒乓球吗')['eligible'])


if __name__ == '__main__':
    unittest.main()
