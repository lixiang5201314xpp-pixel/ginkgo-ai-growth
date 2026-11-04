import unittest
import sys
from pathlib import Path
from test_ai import Tests as Base
from growth_ai import AIError
from set_search_limit_20 import configure_and_probe


class LimitTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    ready=Base.ready

    def test_only_search_limit_changes_and_one_search_occurs(self):
        self.ready();before=self.ai.config();key=self.ai.vault.get('deepseek')
        result=configure_and_probe(self.s,self.ai)
        self.assertEqual(result['daily_search_limit'],20)
        self.assertTrue(result['probe']['ok']);self.assertEqual(len(self.calls),1)
        for k,v in before.items():
            if k!='daily_search_limit':self.assertEqual(self.ai.config()[k],v)
        self.assertEqual(key,self.ai.vault.get('deepseek'))
        self.assertNotIn(key,str(result));self.assertFalse(result['usage_reset'])

    def test_existing_usage_not_deleted(self):
        self.ready()
        for _ in range(8):self.ai.reserve('search',self.ai.config())
        result=configure_and_probe(self.s,self.ai)
        self.assertEqual(sum(x['n'] for x in result['usage_before_probe']),8)
        self.assertEqual(sum(x['n'] for x in result['usage_after_probe']),9)

    def test_failure_is_reported_and_does_not_undo_limit(self):
        self.ready();self.fail='forbidden'
        result=configure_and_probe(self.s,self.ai)
        self.assertEqual(self.ai.config()['daily_search_limit'],20)
        self.assertFalse(result['probe']['ok']);self.assertEqual(result['probe']['error_code'],'forbidden')


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LimitTests))
    sys.exit(not result.wasSuccessful())
