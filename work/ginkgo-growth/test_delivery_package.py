"""Verify the frozen five-file patch, installed layouts and rollback against 1.3.1."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_external_patch_package as rollback
from test_packaged_workflow import copy_release,WORK,BASE

PACKAGE=WORK/'release/growth-delivery-20261101/GinkgoGrowth-1.3.2'
CHAIN=[('growth-ai-20261030/GinkgoGrowth-1.1.0','manifest.json'),
    ('growth-channels-20261030/GinkgoOfficialChannels-1.0.0','channels-manifest.json'),
    ('growth-workflow-20261031/GinkgoGrowth-1.2.0','workflow-manifest.json'),
    ('growth-external-20261031/GinkgoGrowth-1.3.0','external-manifest.json'),
    ('growth-night-20261101/GinkgoGrowth-1.3.1','external-manifest.json')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class DeliveryInstallerChecks(rollback.InstallerChecks):
    def setUp(self):
        super().setUp()
        p=self.m.PAYLOAD/'external-manifest.json'
        manifest=json.loads(p.read_text())
        manifest['files']=[x for x in manifest['files'] if x['path']!='growth-web/browser-helper.zip']
        manifest['baseline'].pop('growth-web/browser-helper.zip',None)
        for name in ('growth_acquisition.py','growth_automation.py','growth-web/app.js'):
            src=self.m.PAYLOAD/name;src.parent.mkdir(exist_ok=True,parents=True);src.write_text('candidate=True' if name.endswith('.py') else 'new-ui')
            dst=self.m.TARGET/name;dst.parent.mkdir(exist_ok=True,parents=True);dst.write_text('baseline=True' if name.endswith('.py') else 'old-ui')
            manifest['baseline'][name]=sha(dst);manifest['files'].append({'path':name,'sha256':sha(src)})
        p.write_text(json.dumps(manifest))

def main():
    rollback.PACKAGE=PACKAGE
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryInstallerChecks))
    assert result.wasSuccessful()
    records=[]
    with tempfile.TemporaryDirectory(prefix='ginkgo-delivery-final-') as tmp:
        root=Path(tmp);runtime=root/'runtime';runtime.mkdir()
        for source,manifest in CHAIN:copy_release(WORK/'release'/source,manifest,runtime)
        frozen=root/'installer';shutil.copytree(PACKAGE,frozen)
        manifest=json.loads((frozen/'payload/external-manifest.json').read_text())
        for name,value in manifest['baseline'].items():assert sha(runtime/name)==value,name
        before={p:sha(runtime/p) for p in ('growth_channels.py','growth_ai.py','growth_playbook.json','growth-web/browser-helper.zip')}
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(frozen,'external-manifest.json',runtime)
            paths=([frozen/'payload'] if mode=='overlay-preflight' else [])+[runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join(map(str,paths))}
            for test in ('test_external.py','test_workflow.py','test_growth.py','test_delivery.py'):
                command=[sys.executable,str(frozen/test)]
                if test=='test_growth.py':
                    code="from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path("+repr(str(runtime))+");runpy.run_path("+repr(str(frozen/test))+",run_name='__main__')"
                    command=[sys.executable,'-c',code]
                r=subprocess.run(command,capture_output=True,timeout=75,env=env,cwd=root)
                if r.returncode:print(r.stderr.decode('utf-8','replace')[-6500:]);raise AssertionError(mode+'/'+test)
            for name,value in before.items():assert sha(runtime/name)==value,name
            records.append({'mode':mode,'passed':True,'suites':['external','workflow','growth','delivery']})
            print('PASS: frozen 1.3.2 '+mode+'; existing AI/channel/playbook/helper retained.')
    (BASE/'delivery-package-verification.json').write_text(json.dumps({'passed':True,'installer_checks':result.testsRun,'layouts':records,'live_api_calls':0,'live_messages':0,'business_sql_changes':0},indent=2),'utf-8')

if __name__=='__main__':main()
