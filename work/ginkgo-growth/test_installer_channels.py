import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).with_name('install_growth_channels.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class InstallerChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        spec=importlib.util.spec_from_file_location('isolated_installer',SOURCE);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.BASE=self.root/'package';self.m.PAYLOAD=self.m.BASE/'payload';self.m.TARGET=self.root/'runtime'
        self.m.LOG=self.m.BASE/'result.json';self.m.PAYLOAD.mkdir(parents=True);self.m.TARGET.mkdir()
        (self.m.TARGET/'match_center.py').write_text('existing_business=True')
        self.names=['growth_acquisition.py','growth_channels.py','growth-web/index.html','growth-web/channels.js']
        baseline={}
        for n in self.names:
            p=self.m.PAYLOAD/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('new_code=True' if n.endswith('.py') else 'new-ui')
            if n in ('growth_acquisition.py','growth-web/index.html'):
                q=self.m.TARGET/n;q.parent.mkdir(exist_ok=True,parents=True);q.write_text('old_code=True' if n.endswith('.py') else 'old-ui');baseline[n]=sha(q)
        manifest={'baseline':baseline,'files':[{'path':n,'sha256':sha(self.m.PAYLOAD/n)} for n in self.names]}
        (self.m.PAYLOAD/'channels-manifest.json').write_text(json.dumps(manifest))
        self.actions=[];self.current='RUNNING'
        self.m.state=lambda:self.current
        def control(a,w):self.actions.append(a);self.current=w
        self.m.control=control;self.m.verify_existing=lambda:None;self.m.preflight=lambda:None;self.m.verify=lambda:None
    def tearDown(self):self.temp.cleanup()
    def run_install(self):
        with contextlib.redirect_stdout(io.StringIO()):self.m.main()
    def test_installs_only_payload(self):
        before=(self.m.TARGET/'match_center.py').read_bytes();self.run_install()
        self.assertEqual(self.actions,['stop','start']);self.assertTrue(json.loads(self.m.LOG.read_text())['success'])
        self.assertEqual(before,(self.m.TARGET/'match_center.py').read_bytes())
    def test_preflight_failure_never_stops(self):
        def fail():raise RuntimeError('preflight')
        self.m.preflight=fail
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])
    def test_unknown_newer_file_rejected(self):
        (self.m.TARGET/'growth_acquisition.py').write_text('newer_unknown=True')
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])
    def test_checksum_failure_never_stops(self):
        (self.m.PAYLOAD/'growth_channels.py').write_text('tampered=True')
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])
    def test_start_failure_rolls_back(self):
        def control(a,w):
            self.actions.append(a);self.current=w
            if self.actions==['stop','start']:raise RuntimeError('start failed')
        self.m.control=control
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual((self.m.TARGET/'growth_acquisition.py').read_text(),'old_code=True')
        self.assertFalse((self.m.TARGET/'growth_channels.py').exists());self.assertEqual(self.current,'RUNNING')
    def test_health_failure_rolls_back(self):
        def fail():raise RuntimeError('health')
        self.m.verify=fail;self.m.time.sleep=lambda _:None
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual((self.m.TARGET/'growth-web/index.html').read_text(),'old-ui')
        self.assertTrue(json.loads(self.m.LOG.read_text())['rolled_back'])
    def test_idempotent_without_restart(self):
        self.run_install();self.actions.clear();self.run_install();self.assertEqual(self.actions,[])
    def test_unsafe_payload_rejected(self):
        manifest=json.loads((self.m.PAYLOAD/'channels-manifest.json').read_text());manifest['files'][0]['path']='../runtime/evil.py'
        (self.m.PAYLOAD/'channels-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])

if __name__=='__main__':unittest.main(verbosity=2)
