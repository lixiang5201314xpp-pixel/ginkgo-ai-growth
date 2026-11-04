"""Verify final candidate layouts and rollback with temporary stores only."""
from pathlib import Path
import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'work/ginkgo-growth-autocollect'
RELEASE=ROOT/'work/release/growth-dev-20261102'
PACKAGE=RELEASE/'GinkgoGrowth-1.4.4'
sys.path.insert(0,str(SRC))
import test_external_patch_package as rollback
from test_collection_package import InstallerChecks
from test_packaged_workflow import copy_release
from package_collection_patch import CHAIN,WORK,sha
rollback.PACKAGE=PACKAGE

class FinalInstallerChecks(InstallerChecks):
    def setUp(self):
        super().setUp()
        # The shared historical fixture includes a UI update. This frozen
        # release intentionally keeps that UI file and only replaces four files.
        manifest_path=self.m.PAYLOAD/'external-manifest.json'
        manifest=json.loads(manifest_path.read_text())
        manifest['files']=[x for x in manifest['files'] if x['path']!='growth-web/external.js']
        manifest['baseline'].pop('growth-web/external.js')
        self.names.remove('growth-web/external.js')
        name='growth_collection.py';self.names.append(name)
        (self.m.TARGET/name).write_text('old_collection=True')
        (self.m.PAYLOAD/name).write_text('new_collection=True')
        manifest['baseline'][name]=[sha(self.m.TARGET/name)]
        manifest['files'].append({'path':name,'sha256':sha(self.m.PAYLOAD/name)})
        manifest_path.write_text(json.dumps(manifest))
        name='growth_acquisition.py';self.names.append(name)
        (self.m.TARGET/name).write_text('old_classifier=True')
        (self.m.PAYLOAD/name).write_text('new_classifier=True')
        p=self.m.PAYLOAD/'external-manifest.json';d=json.loads(p.read_text())
        d['baseline'][name]=[sha(self.m.TARGET/name)]
        d['files'].append({'path':name,'sha256':sha(self.m.PAYLOAD/name)})
        p.write_text(json.dumps(d))
        (self.m.TARGET/'identity.py').write_text('existing_phone_identity_102=True')
    def test_installs_only_payload(self):
        super().test_installs_only_payload()
        self.assertEqual((self.m.TARGET/'growth_acquisition.py').read_text(),'new_classifier=True')
        self.assertEqual((self.m.TARGET/'identity.py').read_text(),'existing_phone_identity_102=True')
    def test_start_failure_rolls_back(self):
        super().test_start_failure_rolls_back()
        self.assertEqual((self.m.TARGET/'growth_acquisition.py').read_text(),'old_classifier=True')
    def test_health_failure_rolls_back(self):
        super().test_health_failure_rolls_back()
        self.assertEqual((self.m.TARGET/'growth_acquisition.py').read_text(),'old_classifier=True')
    def test_unrelated_identity_cannot_be_added_to_payload(self):
        path=self.m.PAYLOAD/'external-manifest.json';manifest=json.loads(path.read_text())
        (self.m.PAYLOAD/'identity.py').write_text('unexpected_identity=True')
        manifest['files'].append({'path':'identity.py','sha256':sha(self.m.PAYLOAD/'identity.py')})
        path.write_text(json.dumps(manifest))
        with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual(self.actions,[])
        self.assertEqual((self.m.TARGET/'identity.py').read_text(),'existing_phone_identity_102=True')
    def test_every_embedded_preflight_command_compiles_and_uses_runtime_assets(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('final_preflight',PACKAGE/'install_growth_external.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.BASE=self.m.BASE;m.TARGET=self.m.TARGET
        commands=[]
        def fake(command,**kwargs):
            self.assertIn('-c',command)
            self.assertIn(str(m.BASE),kwargs['env']['PYTHONPATH'].split(os.pathsep))
            code=command[command.index('-c')+1];ast.parse(code)
            self.assertIn(repr(str(m.TARGET)),code)
            commands.append(command)
            return subprocess.CompletedProcess(command,0,stdout=b'isolated preflight',stderr=b'')
        original=m.subprocess.run
        try:
            m.subprocess.run=fake
            with contextlib.redirect_stdout(io.StringIO()):m.preflight()
        finally:m.subprocess.run=original
        self.assertEqual(len(commands),9)

checks=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(FinalInstallerChecks))
assert checks.wasSuccessful()
manifest=json.loads((PACKAGE/'payload/external-manifest.json').read_text('utf-8'))
with zipfile.ZipFile(PACKAGE/'payload/growth-web/browser-helper.zip') as z:
    assert json.loads(z.read('browser-helper/manifest.json'))['version']=='1.4.8'
    assert len(z.namelist())==8
results=[]
with tempfile.TemporaryDirectory(prefix='ginkgo-144-frozen-') as temporary:
    base=Path(temporary)
    for baseline in ('1.4.1','1.4.2','1.4.3'):
        runtime=base/baseline;runtime.mkdir()
        for folder,name in CHAIN+[('growth-collection-patch-20261101/GinkgoGrowth-1.4.1','external-manifest.json')]:
            copy_release(WORK/'release'/folder,name,runtime)
        if baseline!='1.4.1':copy_release(RELEASE/('GinkgoGrowth-'+baseline),'external-manifest.json',runtime)
        shutil.copy2(ROOT/'work/release/identity-link-20261102/GinkgoIdentityLink-1.0.0/identity-link-payload/identity.py',runtime/'identity.py')
        for name,values in manifest['baseline'].items():assert sha(runtime/name) in values,(baseline,name)
        retained={name:sha(runtime/name) for name in ('growth_ai.py','growth_channels.py','growth_automation.py','growth_playbook.json','identity.py')}
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(PACKAGE,'external-manifest.json',runtime)
            paths=([PACKAGE/'payload'] if mode=='overlay-preflight' else [])+[PACKAGE,runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join(map(str,paths))}
            for name in ('test_growth.py','test_ai.py','test_workflow.py','test_external.py','test_delivery.py','test_collection.py','test_job_intent.py','test_practice_intent.py'):
                code='from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path('+repr(str(runtime))+');runpy.run_path('+repr(str(PACKAGE/name))+',run_name="__main__")'
                r=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=90,env=env,cwd=base)
                output=r.stderr.decode('utf-8','replace')
                if r.returncode:print(output[-6500:],flush=True);raise AssertionError(baseline+'/'+mode+'/'+name)
                count=re.search(r'Ran (\d+) tests?',output)
                results.append({'baseline':baseline,'layout':mode,'suite':name,'tests':int(count[1]) if count else None,'passed':True})
            for name,value in retained.items():assert sha(runtime/name)==value,name
            print('PASS: '+baseline+' '+mode+'; isolated suites, AI/channel source retention.',flush=True)
report={'passed':True,'installer_checks':checks.testsRun,'layouts':results,
        'total_test_executions':checks.testsRun+sum(x['tests'] or 0 for x in results),
        'helper_version':'1.4.8','live_api_calls':0,'platform_messages':0,'business_database_writes':0,
        'live_deployment':False,'note':'Repeated suites across supported baseline/layout combinations; not unique feature count.'}
(RELEASE/'backend-1.4.4-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
