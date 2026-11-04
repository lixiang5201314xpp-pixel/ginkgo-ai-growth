"""Owner-run upgrade, offline dependencies, backup and checked rollback."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import http.client
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
LOG=BASE/'channels-install-result.json'

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
    status,raw=local('/growth/channels/health')
    if status!=200 or json.loads(raw).get('version')!='growth-channels-1.0.0':raise RuntimeError('Channel health check failed')
    for path in ['/growth/api/channels','/growth/api/channels/inbox']:
        if local(path)[0]!=401:raise RuntimeError('Channel admin guard failed')
    if local('/growth/assets/channels.js')[0]!=200:raise RuntimeError('Channel management UI missing')
    # No live customer message or model generation during install.
def preflight():
    python=TARGET/'.venv/Scripts/python.exe'
    env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPATH':os.pathsep.join([str(PAYLOAD),str(PAYLOAD/'channel-vendor'),str(TARGET)])}
    r=subprocess.run([str(python),str(BASE/'test_channels.py')],capture_output=True,timeout=55,env=env)
    if r.returncode:
        print(r.stderr.decode('utf-8','replace')[-9000:]);raise RuntimeError('Isolated channel tests failed BEFORE service restart')
    print('PASS: 38 isolated callback/encryption/queue/reply checks; native DPAPI and offline AES verified. No live messages or AI calls.')
    code="import tempfile,sys;from flask import Flask;import growth_acquisition as m;t=tempfile.TemporaryDirectory();a=Flask('preflight');a.testing=True;m.register(a,data_dir=t.name,local_token='synthetic');c=a.test_client();assert c.get(m.PREFIX+'/channels/health').status_code==200;assert c.get(m.PREFIX+'/api/channels').status_code==401;assert a.extensions['ginkgo_growth']['channels'].thread is None;print('PASS: combined acquisition and channel registration; default sending is OFF.')"
    r=subprocess.run([str(python),'-c',code],capture_output=True,timeout=30,env=env)
    if r.returncode:
        print(r.stderr.decode('utf-8','replace')[-4000:]);raise RuntimeError('Combined registration preflight failed')
    print(r.stdout.decode('utf-8','replace').strip())
def main():
    print('Installing growth-channels-1.0.0 / OFFLINE. Existing accounts, AI key and business data retained.')
    print('WeChat/Douyin connectors are installed OFF until owner configuration and official callback verification. XHS/Kuaishou are not falsely enabled.')
    manifest=json.loads((PAYLOAD/'channels-manifest.json').read_text('utf-8'))
    files=manifest['files'];baseline=manifest['baseline']
    if not files or len(files)>2000:raise RuntimeError('Unexpected payload size')
    names=[x['path'] for x in files]
    if len(names)!=len(set(names)):raise RuntimeError('Duplicate payload path')
    allowed={'growth_acquisition.py','growth_channels.py','growth-web/index.html','growth-web/channels.js'}
    for item in files:
        name=item['path'];src=(PAYLOAD/name).resolve();dest=(TARGET/name).resolve()
        if name not in allowed and not name.startswith('channel-vendor/'):raise RuntimeError('Unexpected payload entry')
        if not src.is_relative_to(PAYLOAD.resolve()) or not dest.is_relative_to(TARGET.resolve()):raise RuntimeError('Unsafe payload path')
        if sha(src)!=item['sha256']:raise RuntimeError('Payload checksum mismatch')
        if dest.exists() and sha(dest) not in {item['sha256'],baseline.get(name)}:raise RuntimeError('Unrecognized existing file: '+name)
        if name.endswith('.py'):ast.parse(src.read_text('utf-8-sig'))
    for name in baseline:
        if not (TARGET/name).is_file():raise RuntimeError('Existing acquisition baseline incomplete')
    if state()!='RUNNING':raise RuntimeError('Existing match service must be RUNNING before install')
    verify_existing();preflight()
    if all((TARGET/x['path']).is_file() and sha(TARGET/x['path'])==x['sha256'] for x in files):
        verify();print('SUCCESS: official channel code already installed and verified. Settings retained.');return
    backup=BASE/'backups'/('channels-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True)
    for item in files:
        old=TARGET/item['path']
        if old.is_file():
            dest=backup/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old,dest)
    core_hash=sha(TARGET/'match_center.py')
    result={'version':'growth-channels-1.0.0','success':False,'backup':str(backup),'business_data_modified':False,'platform_messages_sent':0}
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
        if sha(TARGET/'match_center.py')!=core_hash:raise RuntimeError('Core service source changed unexpectedly')
        result.update(success=True,service=state())
        LOG.write_text(json.dumps(result,indent=2),'utf-8')
        print('SUCCESS: official channel code, offline encryption, queue and admin controls installed and verified.')
        print('NEXT: run Configure-Channels.cmd. Platform callbacks and real-message testing still required; AI sending remains OFF.')
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
