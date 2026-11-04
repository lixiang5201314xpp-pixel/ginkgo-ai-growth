"""Upgrade only acquisition files. Run in the owner's administrator RDP session."""
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
from growth_permissions import protect_credentials

BASE=Path(__file__).resolve().parent
PAYLOAD=BASE/'payload'
TARGET=Path(r'C:\Services\KaiqiuMatch_20260915')
SERVICE='KaiqiuMatchCenter'
LOG=BASE/'growth-ai-install-result.json'
FILES={'growth_acquisition.py','growth_ai.py','growth_automation.py','growth_playbook.json',
       'growth-web/index.html','growth-web/app.css','growth-web/app.js','growth-web/automation.js',
       'growth-web/club.html','growth-web/club.js','growth-web/favicon.svg'}
HOOK='    import growth_acquisition\n    growth_acquisition.register(app, require_login=require_login, is_admin=admin)'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def state():
    b=subprocess.run(['sc.exe','query',SERVICE],capture_output=True,timeout=10).stdout
    return 'RUNNING' if b'RUNNING' in b else 'STOPPED' if b'STOPPED' in b else 'UNKNOWN'

def control(action,wanted):
    subprocess.run(['sc.exe',action,SERVICE],capture_output=True,timeout=10)
    until=time.monotonic()+45
    while time.monotonic()<until:
        if state()==wanted:return
        time.sleep(1)
    raise RuntimeError('Service did not reach '+wanted)

def local(path):
    c=http.client.HTTPConnection('127.0.0.1',8011,timeout=12)
    try:
        c.request('GET','/api/match-center'+path);r=c.getresponse();return r.status,r.read(2_000_000)
    finally:c.close()

def verify_existing():
    for path in ['/health','/team-formats','/community/meta','/community/portrait-meta','/classic/meta',
                 '/ball-war/meta','/target-game/meta','/rest-defense/meta','/events?city=%E6%88%90%E9%83%BD&page=1']:
        status,_=local(path)
        if status!=200:raise RuntimeError('Existing endpoint failed: '+path)
    if local('/community/me')[0]!=401:raise RuntimeError('Existing account guard failed')

def verify():
    verify_existing();status,data=local('/growth/health')
    if status!=200 or json.loads(data)['version']!='ginkgo-growth-1.1.0':raise RuntimeError('AI growth health failed')
    for path in ['/growth/','/growth/assets/automation.js','/growth/club/douyin-training','/growth/public/campaign/kuaishou-training']:
        if local(path)[0]!=200:raise RuntimeError('AI static/public endpoint failed: '+path)
    for path in ['/growth/api/ai/settings','/growth/api/automation','/growth/api/ai/content','/growth/api/leads']:
        if local(path)[0]!=401:raise RuntimeError('Admin guard failed: '+path)

def prepare_store():
    folder=(TARGET/'growth-data').resolve()
    if folder.parent!=TARGET.resolve() or not folder.is_dir():raise RuntimeError('Existing acquisition data directory missing')
    commands=[['icacls.exe',str(folder),'/grant','*S-1-5-19:(OI)(CI)M']]
    private=folder/'secrets';private.mkdir(exist_ok=True)
    for command in commands:
        if subprocess.run(command,capture_output=True,timeout=30).returncode:
            raise RuntimeError('Dedicated acquisition data permissions failed; no restart performed')
    protect_credentials(private)
    print('PASS: LocalService data access and private key-folder permissions verified; code-tree permissions unchanged.')

def isolated_preflight():
    code="import sys,tempfile,json;sys.path.insert(0,sys.argv[1]);from flask import Flask;import growth_acquisition as m;from growth_ai import Vault;t=tempfile.TemporaryDirectory();a=Flask('isolated');a.testing=True;m.register(a,data_dir=t.name,local_token='synthetic');c=a.test_client();assert c.get(m.PREFIX+'/health').status_code==200;assert c.get(m.PREFIX+'/api/ai/settings').status_code==401;e=a.extensions['ginkgo_growth']['automation'];assert e.thread is None;v=Vault(t.name);v.put('deepseek','sk-synthetic-preflight-only');assert v.get('deepseek')=='sk-synthetic-preflight-only';json.load(open(sys.argv[1]+'/growth_playbook.json',encoding='utf-8'));t.cleanup();print('PASS: isolated SQLite, Flask admin guards, playbook and native DPAPI; no API calls.')"
    r=subprocess.run([str(TARGET/'.venv/Scripts/python.exe'),'-c',code,str(PAYLOAD)],capture_output=True,timeout=40)
    if r.returncode:
        print(r.stderr.decode('utf-8','replace')[-5000:]);raise RuntimeError('Isolated AI preflight failed; no restart performed')
    print(r.stdout.decode('utf-8','replace').strip())

def run_activation(mode):
    args=[str(TARGET/'.venv/Scripts/python.exe'),str(BASE/'activate_growth_ai.py'),str(TARGET)]
    args.append(mode)
    r=subprocess.run(args,capture_output=True,timeout=140,
                     env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'})
    output=r.stdout.decode('utf-8','replace')
    print(output.strip())
    if r.returncode:raise RuntimeError('AI activation failed; see the safe validation message above')

def access_preflight():run_activation('--check-access')
def provider_preflight():
    print('Checking three synthetic AI replies BEFORE restart; this can take up to two minutes. Existing service remains running.',flush=True)
    run_activation('--verify-ai')
def activation():run_activation('--enable-only')

def diagnostics():
    try:
        with (TARGET/'logs/error.log').open('rb') as f:
            f.seek(0,2);size=f.tell();f.seek(max(0,size-20000));raw=f.read().decode('utf-8','replace')
        import re
        config=json.loads((TARGET/'runtime.json').read_text('utf-8-sig'))
        for k,v in config.items():
            if re.search('password|secret|token|pwd',str(k),re.I) and isinstance(v,(str,int)) and len(str(v))>3:raw=raw.replace(str(v),'[hidden]')
        raw=re.sub(r'sk-[A-Za-z0-9_-]+','[key hidden]',raw)
        return re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)','[phone hidden]',raw)[-10000:]
    except Exception as e:return type(e).__name__

def main():
    print('Installing ginkgo-growth-1.1.0 / installer-1.1.2 / typed replies and pre-restart AI checks; existing accounts, customer store and API key retained.')
    manifest=json.loads((PAYLOAD/'manifest.json').read_text('utf-8'))
    if {x['path'] for x in manifest['files']}!=FILES:raise RuntimeError('Unexpected payload files')
    for item in manifest['files']:
        if sha(PAYLOAD/item['path'])!=item['sha256']:raise RuntimeError('Payload checksum mismatch: '+item['path'])
        if item['path'].endswith('.py'):ast.parse((PAYLOAD/item['path']).read_text('utf-8'))
    core=(TARGET/'match_center.py').read_bytes()
    if HOOK not in core.decode('utf-8-sig').replace('\r\n','\n'):raise RuntimeError('Existing acquisition registration missing; no service changed')
    baseline=manifest['baseline_files']
    current={x['path']:x['sha256'] for x in manifest['files']}
    for name in FILES:
        live=TARGET/name
        if live.exists() and sha(live) not in {current[name],baseline.get(name)}:
            raise RuntimeError('Unrecognized newer acquisition file: '+name+'; no service changed')
        if name in baseline and not live.is_file():raise RuntimeError('Existing acquisition baseline incomplete')
    if all((TARGET/k).is_file() and sha(TARGET/k)==v for k,v in current.items()):
        prepare_store();access_preflight();provider_preflight();verify();activation();print('SUCCESS: AI workflow already installed and verified.');return
    if state()!='RUNNING':raise RuntimeError('Existing service must be RUNNING before upgrade')
    try:
        verify_existing();isolated_preflight();prepare_store();access_preflight();provider_preflight()
    except Exception:
        print('PRECHECK FAILED: existing service was NOT stopped or restarted. No customer message was sent.')
        raise
    backup=BASE/'backups'/('growth-ai-'+datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True,exist_ok=False)
    for name in FILES:
        p=TARGET/name
        if p.is_file():dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    result={'version':'ginkgo-growth-1.1.0','success':False,'backup':str(backup),'business_database_modified':False,'platform_messages_sent':0}
    try:
        control('stop','STOPPED')
        for item in manifest['files']:
            dest=TARGET/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PAYLOAD/item['path'],dest)
            if sha(dest)!=item['sha256']:raise RuntimeError('Installed checksum mismatch')
        control('start','RUNNING');failure=None
        for _ in range(5):
            try:verify();failure=None;break
            except Exception as e:failure=e;time.sleep(2)
        if failure:raise failure
        activation()
        if (TARGET/'match_center.py').read_bytes()!=core:raise RuntimeError('Core changed during installation; investigate before proceeding')
        result.update(success=True,service=state(),automatic=True,url='https://qiuchen.yinxingpingpang.com/api/match-center/growth/')
        LOG.write_text(json.dumps(result,indent=2),'utf-8')
        print('SUCCESS: AI workflow, immediate opt-in chat and four-platform mini-app guidance installed and verified.')
        print('Automatic runs every configured interval. Calls remain within configured daily caps.')
        print('Platform comments/private messages and content publishing need their official connectors; not falsely marked as sent.')
        print('URL: '+result['url']);print('Backup: '+str(backup));print('Service: '+SERVICE+' RUNNING')
    except Exception:
        result.update(error=traceback.format_exc(),startup_diagnostics=diagnostics())
        try:
            if state()!='STOPPED':control('stop','STOPPED')
            for name in FILES:
                dest=(TARGET/name).resolve()
                if not dest.is_relative_to(TARGET.resolve()):raise RuntimeError('Unexpected rollback path')
                old=backup/name
                if old.is_file():shutil.copy2(old,dest)
                elif dest.is_file():dest.unlink()
            control('start','RUNNING');verify_existing();result['rolled_back']=True
            print('ROLLBACK COMPLETE: previous acquisition code restored; data, key and existing business services retained.')
        except Exception:result.update(rolled_back=False,rollback_error=traceback.format_exc())
        LOG.write_text(json.dumps(result,indent=2),'utf-8');raise

if __name__=='__main__':main()
