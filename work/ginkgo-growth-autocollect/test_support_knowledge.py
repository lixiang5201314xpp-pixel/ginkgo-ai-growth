"""Synthetic support-clock/cache/knowledge regressions; no network or customer writes."""
import hashlib
import json
import time
import unittest
from pathlib import Path
from test_ai import Tests as AIFixture
from growth_ai import AI_PROTOCOL, ground_training_schedule, TIMETABLE_REPLY
import growth_ai

class SupportTests(AIFixture):
    def test_prompts_and_knowledge_never_supply_retired_clock(self):
        self.ready(); self.ai.analyze({'excerpt':'孩子几点训练，怎么报名？','platform':'channels'},[],'inbound_question')
        body=self.calls[-1][3];wire=json.dumps(body,ensure_ascii=False)
        self.assertNotIn('15:00',wire); self.assertNotIn('16:30',wire)
        self.assertIn('课程安排表',wire); self.assertIn('software_help',wire)
        self.assertIn('银杏客服',wire)
        self.assertIn('手机号授权',wire); self.assertIn('同名候选',wire)

    def test_model_cannot_repeat_retired_or_fabricated_clocks(self):
        self.ready()
        for number,clock in enumerate(['15:00—16:30','15：00-16：30','上午9点到10点','18:00-19:30']):
            self.override={'reply':'这里是银杏乒乓球俱乐部。儿童上课每天'+clock+'。'}
            result=self.ai.analyze({'excerpt':'测试'+str(number)},[],'inbound_question')
            self.assertEqual(result['reply'],TIMETABLE_REPLY)

    def test_queued_or_cached_reply_clock_guard(self):
        self.assertEqual(ground_training_schedule('【AI接待】儿童训练每天15:00-16:30。'),TIMETABLE_REPLY)

    def test_only_explicit_current_event_can_ground_competition_clock(self):
        event={'id':'test','title':'周末积分赛','starts_at':'2026-11-03 10:00'}
        reply='银杏俱乐部的周末积分赛10:00开赛。'
        self.assertEqual(ground_training_schedule(reply,[event]),reply)
        self.assertEqual(ground_training_schedule(reply,[]),TIMETABLE_REPLY)
        self.assertEqual(ground_training_schedule('银杏俱乐部的周末积分赛10:00还有训练。',[event]),TIMETABLE_REPLY)

    def test_approved_prices_and_durations_are_retained(self):
        book=json.loads(Path(growth_ai.__file__).with_name('growth_playbook.json').read_text('utf-8'))
        offers=book['approved_offers']['children']
        self.assertEqual([x['price_yuan'] for x in offers],[1900,2400,8900])
        self.assertEqual(offers[1]['lesson_minutes'],90)
        self.assertIn('课程安排表',offers[0]['schedule'])
        self.assertEqual(ground_training_schedule('儿童25次课2400元，每课90分钟，合96元。'),'儿童25次课2400元，每课90分钟，合96元。')

    def test_old_protocol_cache_is_not_reused(self):
        self.ready(); self.ai.analyze({'excerpt':'怎么用'},[],'inbound_question')
        with self.s.db() as c:
            row=c.execute('SELECT * FROM ai_cache').fetchone()
            c.execute('DELETE FROM ai_cache')
            payload=json.loads(self.calls[-1][3]['messages'][1]['content'])
            cfg=self.ai.config()
            old=hashlib.sha256(json.dumps(['growth-ai-json-1.1.2',cfg['provider'],cfg['model'],payload],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            c.execute('INSERT INTO ai_cache VALUES(?,?,?)',(old,time.time()+600,row['result']))
        result=self.ai.analyze({'excerpt':'怎么用'},[],'inbound_question')
        self.assertFalse(result['cached']); self.assertEqual(len(self.calls),2)

if __name__=='__main__':unittest.main()
