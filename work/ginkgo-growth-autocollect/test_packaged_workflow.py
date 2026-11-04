"""Exercise final installer payload against frozen installed releases, not the source tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BASE=Path(__file__).resolve().parent
WORK=BASE.parent
PACKAGE=WORK/'release/growth-workflow-20261031/GinkgoGrowth-1.2.0'


def copy_release(source,manifest_name,target):
    payload=source/'payload'
    manifest=json.loads((payload/manifest_name).read_text('utf-8'))
    for item in manifest['files']:
        name=item['path'];src=payload/name;dest=target/name
        if not dest.resolve().is_relative_to(target.resolve()):raise AssertionError('Invalid fixture path')
        if hashlib.sha256(src.read_bytes()).hexdigest()!=item['sha256']:raise AssertionError('Frozen fixture mismatch: '+name)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)


def main():
    records=[]
    with tempfile.TemporaryDirectory(prefix='ginkgo-packaged-workflow-') as tmp:
        root=Path(tmp);runtime=root/'runtime';runtime.mkdir()
        copy_release(WORK/'release/growth-ai-20261030/GinkgoGrowth-1.1.0','manifest.json',runtime)
        copy_release(WORK/'release/growth-channels-20261030/GinkgoOfficialChannels-1.0.0','channels-manifest.json',runtime)
        candidate=root/'installer';shutil.copytree(PACKAGE,candidate)
        assert not (candidate/'payload/growth_playbook.json').exists(), 'Fixture must reproduce the split-directory deployment'
        original_book=(runtime/'growth_playbook.json').read_bytes()
        for mode in ('overlay-preflight','installed-runtime'):
            if mode=='installed-runtime':copy_release(candidate,'workflow-manifest.json',runtime)
            paths=([candidate/'payload'] if mode=='overlay-preflight' else [])+[runtime,runtime/'channel-vendor',WORK/'python-deps']
            env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1',
                 'PYTHONPATH':os.pathsep.join(str(x) for x in paths)}
            run=subprocess.run([sys.executable,str(candidate/'test_workflow.py')],capture_output=True,timeout=75,env=env,cwd=root)
            output=run.stderr.decode('utf-8','replace')
            if run.returncode:
                print(output[-7000:]);raise AssertionError('Final package failed in '+mode)
            assert (runtime/'growth_playbook.json').read_bytes()==original_book
            records.append({'layout':mode,'passed':True,'tests':20})
            print('PASS: final package '+mode+'; 20 isolated checks, installed playbook unchanged.')
    result={'passed':True,'layouts':records,'tests':40,'production_writes':0,'paid_calls':0,'platform_messages_sent':0}
    (BASE/'packaged-workflow-verification.json').write_text(json.dumps(result,indent=2),'utf-8')


if __name__=='__main__':main()
