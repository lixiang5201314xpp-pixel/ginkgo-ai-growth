"""Verify the small patch against the exact installed 1.4.0 chain, offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_external_patch_package as rollback
from test_collection_package import InstallerChecks
from test_packaged_workflow import copy_release
from package_collection_patch import BASE,WORK,PACKAGE,CHAIN,sha

def main():
    rollback.PACKAGE=PACKAGE
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstallerChecks))
    assert result.wasSuccessful()
    layouts=[]
    with tempfile.TemporaryDirectory(prefix='ginkgo-collection-patch-') as temp:
        root=Path(temp);runtime=root/'runtime';runtime.mkdir()
        for folder,name in CHAIN:copy_release(WORK/'release'/folder,name,runtime)
        frozen=root/'installer';shutil.copytree(PACKAGE,frozen)
        manifest=json.loads((frozen/'payload/external-manifest.json').read_text(encoding='utf-8'))
        for name,values in manifest['baseline'].items():assert sha(runtime/name) in values,name
        retained={n:sha(runtime/n) for n in ('growth_acquisition.py','growth_automation.py','growth_ai.py','growth_channels.py','growth_playbook.json')}
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(frozen,'external-manifest.json',runtime)
            paths=([frozen/'payload'] if mode=='overlay-preflight' else [])+[runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join(map(str,paths))}
            for test in ('test_external.py','test_workflow.py','test_growth.py','test_delivery.py','test_collection.py'):
                command=[sys.executable,str(frozen/test)]
                if test=='test_growth.py':
                    code="from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path("+repr(str(runtime))+");runpy.run_path("+repr(str(frozen/test))+",run_name='__main__')"
                    command=[sys.executable,'-c',code]
                check=subprocess.run(command,capture_output=True,timeout=75,env=env,cwd=root)
                if check.returncode:
                    print(check.stderr.decode('utf-8','replace')[-6500:]);raise AssertionError(mode+'/'+test)
            for name,value in retained.items():assert sha(runtime/name)==value,name
            layouts.append({'mode':mode,'passed':True})
            print('PASS: frozen backend 1.4.1 '+mode+'; accounts, AI, channels, workflow and playbook retained.')
    (BASE/'collection-patch-package-verification.json').write_text(json.dumps({
        'passed':True,'installer_checks':result.testsRun,'layouts':layouts,
        'live_ai_calls':0,'customer_messages':0,'business_database_writes':0},indent=2),encoding='utf-8')

if __name__=='__main__':main()
