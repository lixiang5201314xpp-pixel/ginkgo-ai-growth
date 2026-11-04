"""Upgrade/rollback failure injection in temporary directories; never stops a real service."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
BASE=Path(__file__).resolve().parent
PACKAGE=BASE.parent/'release/growth-ai-20261030/GinkgoGrowth-1.1.0'
OLD=BASE.parent/'release/growth-20261030/GinkgoGrowth-1.0.0/payload'

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        shutil.copytree(PACKAGE,root/'package');self.target=root/'runtime';self.target.mkdir()
        spec=importlib.util.spec_from_file_location('growth_ai_installer_test',BASE/'install_growth_ai.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.BASE=root/'package';self.m.PAYLOAD=self.m.BASE/'payload';self.m.TARGET=self.target;self.m.LOG=self.m.BASE/'result.json'
        (self.target/'match_center.py').write_text('# unchanged core\n'+self.m.HOOK+'\n','utf-8')
        self.core=(self.target/'match_center.py').read_bytes()
        for row in json.loads((OLD/'manifest.json').read_text('utf-8'))['files']:
            p=self.target/row['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/row['path'],p)
        (self.target/'growth-data/secrets').mkdir(parents=True)
        (self.target/'growth-data/secrets/deepseek.dpapi').write_bytes(b'synthetic-retain-ciphertext')
        self.controls=[];self.status='RUNNING';self.activated=0
        self.m.state=lambda:self.status
        def control(action,wanted):self.controls.append(action);self.status=wanted
        self.m.control=control;self.m.prepare_store=lambda:None;self.m.verify_existing=lambda:None
        self.m.isolated_preflight=lambda:None;self.m.verify=lambda:None;self.m.diagnostics=lambda:'synthetic-redacted-diagnostic'
        self.m.access_preflight=lambda:None
        self.m.provider_preflight=lambda:None
        def activation():self.activated+=1
        self.m.activation=activation;self.m.time.sleep=lambda _:None

    def tearDown(self):self.tmp.cleanup()
    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()):self.m.main()
    def retained(self):
        self.assertEqual((self.target/'match_center.py').read_bytes(),self.core)
        self.assertEqual((self.target/'growth-data/secrets/deepseek.dpapi').read_bytes(),b'synthetic-retain-ciphertext')

    def test_upgrade_preserves_core_key_and_data(self):
        self.run_main();self.retained();self.assertEqual(self.controls,['stop','start']);self.assertEqual(self.activated,1)
        self.assertTrue(json.loads(self.m.LOG.read_text())['success'])

    def test_idempotent_no_second_restart(self):
        self.run_main();self.controls.clear();self.run_main();self.assertEqual(self.controls,[]);self.retained()

    def test_unknown_newer_file_rejected(self):
        (self.target/'growth_ai.py').write_text('# newer unknown','utf-8')
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[])

    def test_tampered_payload_rejected(self):
        (self.m.PAYLOAD/'growth_ai.py').write_text('# tamper','utf-8')
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[])

    def test_paths_whitelist_rejected(self):
        p=self.m.PAYLOAD/'manifest.json';d=json.loads(p.read_text());d['files'][0]['path']='../runtime.json';p.write_text(json.dumps(d))
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[])

    def test_missing_hook_prevents_restart(self):
        (self.target/'match_center.py').write_text('# missing hook')
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[])

    def test_permission_preflight_failure_prevents_restart(self):
        def fail():raise RuntimeError('access denied')
        self.m.prepare_store=fail
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[]);self.retained()

    def test_import_preflight_failure_prevents_restart(self):
        def fail():raise RuntimeError('isolated module load failed')
        self.m.isolated_preflight=fail
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[]);self.retained()

    def test_key_access_failure_prevents_any_restart(self):
        def fail():raise PermissionError('synthetic encrypted key read denied')
        self.m.access_preflight=fail
        with self.assertRaises(PermissionError):self.run_main()
        self.assertEqual(self.controls,[]);self.retained()

    def test_key_repair_and_access_check_precede_stop(self):
        order=[]
        self.m.prepare_store=lambda:order.append('credential_acl')
        self.m.access_preflight=lambda:order.append('credential_read_decrypt')
        self.m.provider_preflight=lambda:order.append('real_ai_checks')
        original=self.m.control
        def control(action,wanted):order.append(action);original(action,wanted)
        self.m.control=control;self.run_main()
        self.assertEqual(order[:4],['credential_acl','credential_read_decrypt','real_ai_checks','stop'])

    def test_invalid_model_output_prevents_any_restart(self):
        def fail():raise RuntimeError('synthetic classification schema mismatch')
        self.m.provider_preflight=fail
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[]);self.retained()

    def test_stopped_service_prevents_mutation(self):
        self.status='STOPPED'
        with self.assertRaises(RuntimeError):self.run_main()
        self.assertEqual(self.controls,[]);self.retained()

    def test_failed_health_restores_baseline(self):
        def fail():raise RuntimeError('health failed')
        self.m.verify=fail
        with self.assertRaises(RuntimeError):self.run_main()
        self.retained();self.assertFalse((self.target/'growth_ai.py').exists());self.assertEqual(self.status,'RUNNING')
        self.assertTrue(json.loads(self.m.LOG.read_text())['rolled_back'])

    def test_failed_start_restores_baseline(self):
        original=self.m.control;failed=[False]
        def control(action,wanted):
            if action=='start' and not failed[0]:failed[0]=True;raise RuntimeError('startup failed')
            original(action,wanted)
        self.m.control=control
        with self.assertRaises(RuntimeError):self.run_main()
        self.retained();self.assertFalse((self.target/'growth_automation.py').exists());self.assertEqual(self.status,'RUNNING')

    def test_ai_activation_failure_restores_service_not_customer_data(self):
        def fail():raise RuntimeError('invalid key or model response')
        self.m.activation=fail
        with self.assertRaises(RuntimeError):self.run_main()
        self.retained();self.assertTrue(json.loads(self.m.LOG.read_text())['rolled_back'])

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (BASE/'ai-installer-verification.json').write_text(json.dumps({'passed':r.wasSuccessful(),'tests':r.testsRun,'production_changes':False},indent=2),'utf-8')
    raise SystemExit(not r.wasSuccessful())
