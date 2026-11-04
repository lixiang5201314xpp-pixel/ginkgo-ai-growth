"""Failure-injection tests on a temporary Windows directory only."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parent
PACKAGE=BASE.parent/'release'/'growth-20261030'/'GinkgoGrowth-1.0.0'
SOURCE=BASE.parent/'release'/'team-variants-20261030'/'payload'/'match_center.py'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        shutil.copytree(PACKAGE,root/'package')
        self.target=root/'runtime';self.target.mkdir()
        shutil.copy2(SOURCE,self.target/'match_center.py')
        self.original=(self.target/'match_center.py').read_bytes()
        spec=importlib.util.spec_from_file_location('growth_installer_test',BASE/'install_growth.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.BASE=root/'package';self.m.PAYLOAD=self.m.BASE/'payload';self.m.TARGET=self.target
        self.m.LOG=self.m.BASE/'result.json';self.states=['RUNNING'];self.controls=[]
        self.m.state=lambda:self.states[0]
        def control(action,wanted):self.controls.append(action);self.states[0]=wanted
        self.m.control=control;self.m.verify_existing=lambda:None;self.m.verify=lambda:None
        self.m.isolated_preflight=lambda:None
        self.m.prepare_store=lambda:(self.target/'growth-data').mkdir(exist_ok=True)
        self.m.time.sleep=lambda _:None

    def tearDown(self):self.tmp.cleanup()

    def test_install_additive_and_registers_existing_admin(self):
        self.m.main()
        self.assertIn(self.m.HOOK,(self.target/'match_center.py').read_text('utf-8'))
        self.assertEqual(self.controls,['stop','start'])
        self.assertTrue(json.loads(self.m.LOG.read_text())['success'])
        self.assertTrue((self.target/'growth-data').is_dir())

    def test_idempotent_repeat_does_not_restart(self):
        self.m.main();self.controls.clear();self.m.main();self.assertEqual(self.controls,[])

    def test_unknown_live_version_no_service_change(self):
        (self.target/'match_center.py').write_text('# unexpected newer source','utf-8')
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual(self.controls,[])

    def test_tampered_payload_no_service_change(self):
        (self.m.PAYLOAD/'growth_acquisition.py').write_text('invalid tamper','utf-8')
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual(self.controls,[])

    def test_existing_health_failure_no_service_change(self):
        def bad():raise RuntimeError('existing endpoint offline')
        self.m.verify_existing=bad
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual(self.controls,[])

    def test_new_health_failure_restores_core_and_retains_customer_store(self):
        data=self.target/'growth-data';data.mkdir();(data/'customer-marker.txt').write_text('retain','utf-8')
        def bad():raise RuntimeError('new module health failed')
        self.m.verify=bad
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual((self.target/'match_center.py').read_bytes(),self.original)
        self.assertFalse((self.target/'growth-web').exists())
        self.assertEqual((data/'customer-marker.txt').read_text(),'retain')
        self.assertTrue(json.loads(self.m.LOG.read_text())['rolled_back'])

    def test_start_failure_rolls_back(self):
        original_control=self.m.control;failed=[False]
        def control(action,wanted):
            if action=='start' and not failed[0]:failed[0]=True;raise RuntimeError('startup failed')
            original_control(action,wanted)
        self.m.control=control
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual((self.target/'match_center.py').read_bytes(),self.original)
        self.assertEqual(self.states[0],'RUNNING')

    def test_payload_paths_are_whitelisted(self):
        path=self.m.PAYLOAD/'manifest.json';d=json.loads(path.read_text('utf-8'))
        d['files'][0]['path']='../runtime.json';path.write_text(json.dumps(d),'utf-8')
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual(self.controls,[])

    def test_data_permission_failure_prevents_restart(self):
        def bad():raise RuntimeError('LocalService data grant failed')
        self.m.prepare_store=bad
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual(self.controls,[])
        self.assertEqual((self.target/'match_center.py').read_bytes(),self.original)

    def test_dependency_preflight_failure_prevents_restart(self):
        def bad():raise RuntimeError('isolated import failed')
        self.m.isolated_preflight=bad
        with self.assertRaises(RuntimeError):self.m.main()
        self.assertEqual(self.controls,[])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstallerTests))
    (PACKAGE.parent/'installer-verification.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'production_changes':False},indent=2),'utf-8')
    raise SystemExit(not result.wasSuccessful())
