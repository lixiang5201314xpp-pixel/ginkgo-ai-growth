"""Frozen patch: validate pre-install/installed layouts and checked rollback using temporary files."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_packaged_workflow import copy_release,WORK,BASE

PACKAGE=WORK/'release/growth-night-20261101/GinkgoGrowth-1.3.1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class InstallerChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        spec=importlib.util.spec_from_file_location('isolated_patch_installer',PACKAGE/'install_growth_external.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.BASE=self.root/'package';self.m.PAYLOAD=self.m.BASE/'payload';self.m.TARGET=self.root/'runtime'
        self.m.LOG=self.m.BASE/'result.json';self.m.PAYLOAD.mkdir(parents=True);self.m.TARGET.mkdir()
        (self.m.TARGET/'match_center.py').write_text('existing_business=True')
        self.names=['growth_external.py','growth-web/external.js','growth-web/browser-helper.zip']
        baseline={}
        for n in self.names:
            p=self.m.PAYLOAD/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('new_code=True' if n.endswith('.py') else 'new-ui')
            q=self.m.TARGET/n;q.parent.mkdir(exist_ok=True,parents=True);q.write_text('old_code=True' if n.endswith('.py') else 'old-ui');baseline[n]=sha(q)
        manifest={'baseline':baseline,'files':[{'path':n,'sha256':sha(self.m.PAYLOAD/n)} for n in self.names]}
        (self.m.PAYLOAD/'external-manifest.json').write_text(json.dumps(manifest))
        self.actions=[];self.current='RUNNING';self.m.state=lambda:self.current
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
        (self.m.TARGET/'growth_external.py').write_text('newer_unknown=True')
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])
    def test_checksum_failure_never_stops(self):
        (self.m.PAYLOAD/'growth_external.py').write_text('tampered=True')
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])
    def test_start_failure_rolls_back(self):
        def control(a,w):
            self.actions.append(a);self.current=w
            if self.actions==['stop','start']:raise RuntimeError('start failed')
        self.m.control=control
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual((self.m.TARGET/'growth_external.py').read_text(),'old_code=True');self.assertEqual(self.current,'RUNNING')
    def test_health_failure_rolls_back(self):
        def fail():raise RuntimeError('health')
        self.m.verify=fail;self.m.time.sleep=lambda _:None
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual((self.m.TARGET/'growth-web/external.js').read_text(),'old-ui')
        self.assertTrue(json.loads(self.m.LOG.read_text())['rolled_back'])
    def test_idempotent_without_restart(self):
        self.run_install();self.actions.clear();self.run_install();self.assertEqual(self.actions,[])
    def test_unsafe_payload_rejected(self):
        manifest=json.loads((self.m.PAYLOAD/'external-manifest.json').read_text());manifest['files'][0]['path']='../runtime/evil.py'
        (self.m.PAYLOAD/'external-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])

def main():
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstallerChecks))
    assert result.wasSuccessful()
    layouts=[]
    with tempfile.TemporaryDirectory(prefix='ginkgo-patch-final-') as tmp:
        root=Path(tmp);runtime=root/'runtime';runtime.mkdir()
        for source,manifest in [(WORK/'release/growth-ai-20261030/GinkgoGrowth-1.1.0','manifest.json'),
            (WORK/'release/growth-channels-20261030/GinkgoOfficialChannels-1.0.0','channels-manifest.json'),
            (WORK/'release/growth-workflow-20261031/GinkgoGrowth-1.2.0','workflow-manifest.json'),
            (WORK/'release/growth-external-20261031/GinkgoGrowth-1.3.0','external-manifest.json')]:copy_release(source,manifest,runtime)
        frozen=root/'installer';shutil.copytree(PACKAGE,frozen)
        before={p:sha(runtime/p) for p in ('growth_channels.py','growth_ai.py','growth_playbook.json')}
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(frozen,'external-manifest.json',runtime)
            paths=([frozen/'payload'] if mode=='overlay-preflight' else [])+[runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join(map(str,paths))}
            for test in ('test_external.py','test_workflow.py','test_growth.py'):
                command=[sys.executable,str(frozen/test)]
                if test=='test_growth.py':
                    code="from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path("+repr(str(runtime))+");runpy.run_path("+repr(str(frozen/test))+",run_name='__main__')"
                    command=[sys.executable,'-c',code]
                r=subprocess.run(command,capture_output=True,timeout=75,env=env,cwd=root)
                if r.returncode:print(r.stderr.decode('utf-8','replace')[-6000:]);raise AssertionError(mode+'/'+test)
            for p,value in before.items():assert sha(runtime/p)==value,p
            layouts.append({'mode':mode,'passed':True,'suites':['external','workflow','growth']})
            print('PASS: final 1.3.1 '+mode+'; external/workflow/base checks; channels, AI and playbook retained.')
    (BASE/'external-patch-package-verification.json').write_text(json.dumps({'passed':True,'installer_checks':result.testsRun,'layouts':layouts,'production_writes':0,'live_ai_calls':0,'live_messages':0},indent=2),'utf-8')
if __name__=='__main__':main()
