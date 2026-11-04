"""Owner-run upgrade, offline dependencies, backup and checked rollback."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import http.client
import io
import zipfile
import json
import os
import shutil
import subprocess
import time
import traceback

BASE=Path(__file__).resolve().parent
PAYLOAD=BASE/'payload'
TARGET=Path(r'C:\Services\KaiqiuMatch_20260915')
SERVICE='KaiqiuMatchCenter'
LOG=BASE/'external-install-result.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def state():
    r=subprocess.run(['sc.exe','query',SERVICE],capture_output=True,timeout=10)
    return 'RUNNING' if b'RUNNING' in r.stdout else 'STOPPED' if b'STOPPED' in r.stdout else 'UNKNOWN'
def control(action,wanted):
    subprocess.run(['sc.exe',action,SERVICE],capture_output=True,timeout=10)
    until=time.monotonic()+45
    while time.monotonic()<until:
        if state()==wanted:return
        time.sleep(1)
    raise RuntimeError('Service did not reach '+wanted)
def local(path):
    conn=http.client.HTTPConnection('127.0.0.1',8011,timeout=12)
    try:
        conn.request('GET','/api/match-center'+path)
        response=conn.getresponse();return response.status,response.read(2000000)
    finally:conn.close()
def verify_existing():
    for path in ['/health','/team-formats','/community/meta','/community/portrait-meta','/classic/meta',
                 '/ball-war/meta','/target-game/meta','/rest-defense/meta','/growth/health','/growth/']:
        if local(path)[0]!=200:raise RuntimeError('Existing endpoint failed: '+path)
    for path in ['/community/me','/growth/api/leads','/growth/api/ai/settings']:
        if local(path)[0]!=401:raise RuntimeError('Existing login guard failed: '+path)
def verify():
    verify_existing()
    status,raw=local('/growth/external/health')
    if status!=200 or json.loads(raw).get('version')!='growth-external-1.4.4':raise RuntimeError('External workflow health check failed')
    for path in ['/growth/api/external','/growth/api/workflow','/growth/api/ai/settings']:
        if local(path)[0]!=401:raise RuntimeError('External workflow admin guard failed')
    if local('/growth/api/collection')[0]!=401:raise RuntimeError('Automatic collection admin guard failed')
    if local('/growth/assets/collection.js')[0]!=200:raise RuntimeError('Collection UI missing')
    if local('/growth/api/delivery-summary')[0]!=401:raise RuntimeError('Delivery admin guard failed')
    if local('/growth/assets/external.js')[0]!=200:raise RuntimeError('External workflow UI missing')
    status,raw=local('/growth/assets/browser-helper.zip')
    if status!=200:raise RuntimeError('Helper download failed')
    with zipfile.ZipFile(io.BytesIO(raw)) as helper:
        if json.loads(helper.read('browser-helper/manifest.json')).get('version')!='1.4.8':raise RuntimeError('Helper download version mismatch')
    # No live customer message or model generation during install.
def preflight():
    python=TARGET/'.venv/Scripts/python.exe'
    env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPATH':os.pathsep.join([str(PAYLOAD),str(BASE),str(TARGET/'channel-vendor'),str(TARGET)])}
    for test in ['test_growth.py', 'test_ai.py', 'test_workflow.py', 'test_external.py', 'test_delivery.py', 'test_collection.py', 'test_job_intent.py', 'test_practice_intent.py']:
        command=[str(python),str(BASE/test)]
        if True:
            # Candidate Python uses the existing runtime web assets during overlay preflight.
            code="from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path("+repr(str(TARGET))+");runpy.run_path("+repr(str(BASE/test))+",run_name='__main__')"
            command=[str(python),'-c',code]
        r=subprocess.run(command,capture_output=True,timeout=75,env=env)
        if r.returncode:
            print(r.stderr.decode('utf-8','replace')[-9000:]);raise RuntimeError('Isolated '+test+' preflight failed BEFORE service restart')
    print('PASS: external-intake, workflow and base acquisition checks; no live AI, customer contacts or business SQL.')
    code="import tempfile;from pathlib import Path;from flask import Flask;import growth_acquisition as m;m.BASE=Path("+repr(str(TARGET))+");t=tempfile.TemporaryDirectory();a=Flask('preflight');a.testing=True;m.register(a,data_dir=t.name,local_token='synthetic');c=a.test_client();assert c.get(m.PREFIX+'/external/health').status_code==200;assert c.get(m.PREFIX+'/api/external').status_code==401;assert c.get(m.PREFIX+'/channels/health').status_code==200;assert a.extensions['ginkgo_growth']['channels'].thread is None;print('PASS: new external workflow and existing channels register together without starting workers.')"
    r=subprocess.run([str(python),'-c',code],capture_output=True,timeout=30,env=env)
    if r.returncode:
        print(r.stderr.decode('utf-8','replace')[-4000:]);raise RuntimeError('Combined registration preflight failed')
    print(r.stdout.decode('utf-8','replace').strip())

def main():
    print('Installing growth-external-1.4.4 / installer-1.4.4 / OFFLINE. Existing WeChat AI reception, credentials and business data retained.')
    print('Recovers exact receipts, recognizes explicit practice requests and excludes provider replies/job-seeking advertisements and verifies helper download 1.4.8. No account, schema, credential, existing-record repair or mini-app upload changes. Preflight uses synthetic data with no live AI calls; existing background tasks resume under current settings.')
    manifest=json.loads((PAYLOAD/'external-manifest.json').read_text('utf-8'))
    files=manifest['files'];baseline=manifest['baseline']
    if not files or len(files)>2000:raise RuntimeError('Unexpected payload size')
    names=[x['path'] for x in files]
    if len(names)!=len(set(names)):raise RuntimeError('Duplicate payload path')
    allowed={'growth_acquisition.py', 'growth_collection.py', 'growth-web/browser-helper.zip', 'growth_external.py'}
    for item in files:
        name=item['path'];src=(PAYLOAD/name).resolve();dest=(TARGET/name).resolve()
        if name not in allowed:raise RuntimeError('Unexpected payload entry')
        if not src.is_relative_to(PAYLOAD.resolve()) or not dest.is_relative_to(TARGET.resolve()):raise RuntimeError('Unsafe payload path')
        if sha(src)!=item['sha256']:raise RuntimeError('Payload checksum mismatch')
        if dest.exists() and sha(dest) not in {item['sha256'],*baseline.get(name,[])}:raise RuntimeError('Unrecognized existing file: '+name)
        if name.endswith('.py'):ast.parse(src.read_text('utf-8-sig'))
    for name in baseline:
        if not (TARGET/name).is_file():raise RuntimeError('Existing acquisition baseline incomplete')
    if state()!='RUNNING':raise RuntimeError('Existing match service must be RUNNING before install')
    verify_existing();preflight()
    if all((TARGET/x['path']).is_file() and sha(TARGET/x['path'])==x['sha256'] for x in files):
        verify();print('SUCCESS: external-platform workflow already installed and verified. Existing reception settings retained.');return
    backup=BASE/'backups'/('external-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True)
    for item in files:
        old=TARGET/item['path']
        if old.is_file():
            dest=backup/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old,dest)
    retained_names=['match_center.py','identity.py','roster_rating_replay.py','growth_ai.py','growth_channels.py','growth_automation.py','growth_playbook.json']
    retained={name:sha(TARGET/name) for name in retained_names if (TARGET/name).is_file()}
    result={'version':'growth-external-1.4.4','success':False,'backup':str(backup),'business_data_modified':False,'platform_messages_sent':0}
    try:
        control('stop','STOPPED')
        for item in files:
            dest=TARGET/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PAYLOAD/item['path'],dest)
            if sha(dest)!=item['sha256']:raise RuntimeError('Installed checksum mismatch')
        control('start','RUNNING')
        error=None
        for _ in range(5):
            try:verify();error=None;break
            except Exception as e:error=e;time.sleep(2)
        if error:raise error
        if any(sha(TARGET/name)!=value for name,value in retained.items()):raise RuntimeError('Unrelated identity/core/AI source changed unexpectedly')
        result.update(success=True,service=state(),installed_payload_sha256={x['path']:sha(TARGET/x['path']) for x in files},retained_file_sha256=retained)
        LOG.write_text(json.dumps(result,indent=2),'utf-8')
        print('SUCCESS: source-role filtering, exact receipt recovery and helper download 1.4.8 installed and verified. Existing reception retained.')
        print('NEXT: refresh the workbench. Reload local helper 1.4.8 to apply its loading recovery fixes. External auto-sending and Channels collection are NOT connected.')
        print('Backup: '+str(backup));print('Service: KaiqiuMatchCenter RUNNING')
    except Exception:
        result['error']=traceback.format_exc()
        try:
            if state()!='STOPPED':control('stop','STOPPED')
            for item in files:
                name=item['path'];dest=(TARGET/name).resolve();old=backup/name
                if not dest.is_relative_to(TARGET.resolve()):raise RuntimeError('Unsafe rollback path')
                if old.is_file():shutil.copy2(old,dest)
                elif dest.is_file():dest.unlink()
            control('start','RUNNING');verify_existing();result['rolled_back']=True
            print('ROLLBACK COMPLETE: previous code restored; data and existing AI key retained.')
        except Exception:
            result.update(rolled_back=False,rollback_error=traceback.format_exc())
        LOG.write_text(json.dumps(result,indent=2),'utf-8');raise
if __name__=='__main__':main()
