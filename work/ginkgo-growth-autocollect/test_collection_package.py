"""Frozen installed/candidate layouts and checked service rollback; no live services."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_external_patch_package as rollback
from test_packaged_workflow import copy_release
from package_collection import BASE,WORK,PACKAGE,CHAIN

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class InstallerChecks(rollback.InstallerChecks):
    def setUp(self):
        super().setUp()
        p=self.m.PAYLOAD/'external-manifest.json'
        d=json.loads(p.read_text())
        d['baseline']={k:[v] for k,v in d['baseline'].items()}
        p.write_text(json.dumps(d))

def main():
    rollback.PACKAGE=PACKAGE
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstallerChecks))
    assert result.wasSuccessful()
    layouts=[]
    with tempfile.TemporaryDirectory(prefix='ginkgo-collection-frozen-') as temp:
        root=Path(temp);runtime=root/'runtime';runtime.mkdir()
        for folder,manifest in CHAIN:copy_release(WORK/'release'/folder,manifest,runtime)
        frozen=root/'installer';shutil.copytree(PACKAGE,frozen)
        manifest=json.loads((frozen/'payload/external-manifest.json').read_text(encoding='utf-8'))
        for name,values in manifest['baseline'].items():assert sha(runtime/name) in values,name
        retained={n:sha(runtime/n) for n in ('growth_ai.py','growth_channels.py','growth_playbook.json')}
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(frozen,'external-manifest.json',runtime)
            paths=([frozen/'payload'] if mode=='overlay-preflight' else [])+[runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join(map(str,paths))}
            for test in ('test_external.py','test_workflow.py','test_growth.py','test_delivery.py','test_collection.py'):
                command=[sys.executable,str(frozen/test)]
                if test=='test_growth.py':
                    code="from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path("+repr(str(runtime))+");runpy.run_path("+repr(str(frozen/test))+",run_name='__main__')"
                    command=[sys.executable,'-c',code]
                r=subprocess.run(command,capture_output=True,timeout=75,env=env,cwd=root)
                if r.returncode:
                    print(r.stderr.decode('utf-8','replace')[-6500:]);raise AssertionError(mode+'/'+test)
            for name,value in retained.items():assert sha(runtime/name)==value,name
            layouts.append({'mode':mode,'passed':True})
            print('PASS: frozen 1.4.0 '+mode+'; existing WeChat AI/key configuration modules retained.')
    (BASE/'collection-package-verification.json').write_text(json.dumps({'passed':True,'installer_checks':result.testsRun,'layouts':layouts,'live_api_calls':0,'customer_messages':0},indent=2),encoding='utf-8')

if __name__=='__main__':main()
