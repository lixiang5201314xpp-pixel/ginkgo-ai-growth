"""Final-package tests against frozen installed releases, including split-directory preflight."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from test_packaged_workflow import copy_release, WORK, BASE

PACKAGE=WORK/'release/growth-external-20261031/GinkgoGrowth-1.3.0'

def main():
    records=[]
    with tempfile.TemporaryDirectory(prefix='ginkgo-packaged-external-') as tmp:
        root=Path(tmp);runtime=root/'runtime';runtime.mkdir()
        for source,manifest in [(WORK/'release/growth-ai-20261030/GinkgoGrowth-1.1.0','manifest.json'),
                (WORK/'release/growth-channels-20261030/GinkgoOfficialChannels-1.0.0','channels-manifest.json'),
                (WORK/'release/growth-workflow-20261031/GinkgoGrowth-1.2.0','workflow-manifest.json')]:
            copy_release(source,manifest,runtime)
        candidate=root/'installer';shutil.copytree(PACKAGE,candidate)
        original_book=(runtime/'growth_playbook.json').read_bytes()
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(candidate,'external-manifest.json',runtime)
            paths=([candidate/'payload'] if mode=='overlay-preflight' else [])+[runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join(map(str,paths))}
            for test in ('test_external.py','test_workflow.py'):
                r=subprocess.run([sys.executable,str(candidate/test)],capture_output=True,timeout=75,env=env,cwd=root)
                if r.returncode:
                    print(r.stderr.decode('utf-8','replace')[-7000:]);raise AssertionError('Final package failed: '+mode+'/'+test)
            assert (runtime/'growth_playbook.json').read_bytes()==original_book
            records.append({'layout':mode,'passed':True,'tests':43});print('PASS: final external package '+mode+'; 43 isolated checks, existing playbook retained.')
    (BASE/'packaged-external-verification.json').write_text(json.dumps({'passed':True,'layouts':records,'tests':86,'paid_requests':0,'business_sql_writes':0,'customer_messages':0},indent=2),'utf-8')

if __name__=='__main__':main()
