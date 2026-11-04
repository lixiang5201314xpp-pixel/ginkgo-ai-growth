import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from agent_state import transition

class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.time = datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
        self.s = {'version': 'existing', 'production_leads_imported': 2}

    def finish(self, n=0, blocked='', completed=True):
        rid = self.s['active_round']['round_id']
        report = Path(self.temp.name) / 'round.json'
        report.write_text(json.dumps({'round_id': rid, 'scan_completed': completed,
            'new_valid_leads': [dict(key='new1', source_url='https://example.com/1',
                published_at='2026-11-01', source_text='成都找球搭子', city_evidence='原文成都',
                backend_record_id=3)] if n else []}), encoding='utf-8')
        return transition(self.s, 'finish', clock=self.time, round_id=rid, count=n,
                          reason=blocked, report=str(report))

    def test_completion_always_stops(self):
        self.s['status'] = '已完成'
        for action in ['start', 'finish', 'resume']:
            self.assertEqual(transition(self.s, action)['action'], 'stop')

    def test_no_overlapping_rounds(self):
        self.assertEqual(transition(self.s, 'start', clock=self.time)['action'], 'scan')
        self.assertEqual(transition(self.s, 'start', clock=self.time)['action'], 'skip')

    def test_eight_minutes_after_completion(self):
        transition(self.s, 'start', clock=self.time - timedelta(minutes=17))
        self.finish()
        self.assertEqual(datetime.fromisoformat(self.s['next_run_at']), self.time + timedelta(minutes=8))
        self.assertEqual(transition(self.s, 'start', clock=self.time + timedelta(minutes=7))['action'], 'wait')
        self.assertEqual(transition(self.s, 'start', clock=self.time + timedelta(minutes=8))['action'], 'scan')

    def test_third_empty_pauses_and_only_manual_resume_resets(self):
        for i in range(3):
            transition(self.s, 'start', clock=self.time)
            result = self.finish()
            self.time += timedelta(minutes=8)
        self.assertTrue(result['pause_automation'])
        self.assertEqual(self.s['consecutive_empty_rounds'], 3)
        self.assertEqual(transition(self.s, 'start')['action'], 'pause')
        transition(self.s, 'resume')
        self.assertEqual(self.s['consecutive_empty_rounds'], 0)

    def test_new_lead_resets_counter_preserves_business_values(self):
        self.s['consecutive_empty_rounds'] = 2
        transition(self.s, 'start', clock=self.time)
        self.finish(n=1)
        self.assertEqual(self.s['consecutive_empty_rounds'], 0)
        self.assertEqual(self.s['production_leads_imported'], 2)
        self.assertEqual(self.s['version'], 'existing')

    def test_blocked_does_not_increment_empty(self):
        transition(self.s, 'start', clock=self.time)
        self.finish(blocked='需要扫码', completed=False)
        self.assertEqual(self.s['status'], '已暂停')
        self.assertEqual(self.s['consecutive_empty_rounds'], 0)

    def test_idempotent_finish(self):
        rid = transition(self.s, 'start', clock=self.time)['round_id']
        self.finish()
        result = transition(self.s, 'finish', round_id=rid)
        self.assertEqual(result['action'], 'already_recorded')
        self.assertEqual(self.s['consecutive_empty_rounds'], 1)

    def test_mismatched_round_cannot_finish(self):
        transition(self.s, 'start', clock=self.time)
        with self.assertRaises(ValueError):
            transition(self.s, 'finish', round_id='wrong')

    def test_user_cancel_does_not_count_as_empty_then_can_restart(self):
        rid = transition(self.s, 'start', clock=self.time)['round_id']
        transition(self.s, 'cancel', clock=self.time)
        self.assertEqual(self.s['consecutive_empty_rounds'], 0)
        self.assertEqual(self.s['round_history'][-1]['outcome'], '用户中止')
        transition(self.s, 'resume', clock=self.time)
        new = transition(self.s, 'start', clock=self.time)
        self.assertNotEqual(new['round_id'], rid)

if __name__ == '__main__':
    unittest.main()
