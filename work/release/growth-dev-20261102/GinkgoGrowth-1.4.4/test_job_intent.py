"""Job-seeker versus lesson-customer checks, using no live data or API calls."""
from datetime import datetime,timezone
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'python-deps'))
import growth_acquisition as growth

class JobIntentTests(unittest.TestCase):
    def assess(self,value):return growth.classify(value,posted_at=datetime.now(timezone.utc).isoformat())
    def test_job_seeker_post_is_not_a_training_customer(self):
        value='成都有没有招乒乓球教练的，1600有教练证，想找工作'
        result=self.assess(value)
        self.assertTrue(result['rejected']);self.assertFalse(result['eligible'])
    def test_short_question_about_hiring_a_coach_is_not_a_lesson_request(self):
        result=self.assess('成都招乒乓球教练吗？')
        self.assertTrue(result['rejected']);self.assertFalse(result['eligible'])
    def test_practice_partner_job_is_not_a_customer(self):
        result=self.assess('成都想找乒乓球陪练工作，请问哪里有岗位？')
        self.assertTrue(result['rejected']);self.assertFalse(result['eligible'])
    def test_job_application_is_not_a_customer(self):
        result=self.assess('我想应聘成都乒乓球教练，请问有合适岗位吗？')
        self.assertTrue(result['rejected']);self.assertFalse(result['eligible'])
    def test_a_coach_looking_for_students_is_not_a_customer(self):
        result=self.assess('我是成都乒乓球教练，想找学生上课，欢迎学员咨询')
        self.assertTrue(result['rejected']);self.assertFalse(result['eligible'])
    def test_existing_coach_recruitment_stays_excluded(self):
        self.assertTrue(self.assess('成都招聘乒乓球教练，请问有人愿意来吗？')['rejected'])
    def test_parent_can_require_coach_certification(self):
        result=self.assess('成都想找有教练证的乒乓球教练带8岁孩子，请问哪里有？')
        self.assertFalse(result['rejected']);self.assertTrue(result['eligible'])
    def test_working_adult_remains_a_customer(self):
        result=self.assess('成都想学乒乓球，下班后练球，请问哪里有成人课程？')
        self.assertFalse(result['rejected']);self.assertTrue(result['eligible'])
    def test_coach_work_experience_is_not_job_seeking(self):
        result=self.assess('成都想给孩子找乒乓球教练，教练工作经验要丰富')
        self.assertFalse(result['rejected']);self.assertTrue(result['eligible'])
    def test_learning_shots_is_not_mistaken_for_hiring(self):
        result=self.assess('成都想找教乒乓球招式的教练，有推荐吗？')
        self.assertFalse(result['rejected']);self.assertTrue(result['eligible'])
    def test_student_first_person_need_remains_qualified(self):
        result=self.assess('成都有教练可以教我乒乓球吗？我想改善正手')
        self.assertFalse(result['rejected']);self.assertTrue(result['eligible'])
    def test_local_tournament_entry_remains_qualified(self):
        self.assertTrue(self.assess('成都有可以报名的乒乓球积分赛吗？想报名比赛')['eligible'])
    def test_local_practice_partner_request_remains_qualified(self):
        self.assertTrue(self.assess('成都周末有没有乒乓球球搭子？想打球')['eligible'])

if __name__=='__main__':unittest.main()
