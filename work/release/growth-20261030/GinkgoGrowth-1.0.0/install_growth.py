"""Add the acquisition module to the existing service, with verified rollback.

Run from the server's administrator session. No package downloads, account migration,
SQL changes, firewall changes or social-platform actions.
"""
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
LOG=BASE/'growth-install-result.json'
ANCHOR='    app.register_blueprint(bp, url_prefix=PREFIX)'
HOOK='    import growth_acquisition\n    growth_acquisition.register(app, require_login=require_login, is_admin=admin)'
FILES={'growth_acquisition.py','growth-web/index.html','growth-web/app.css','growth-web/app.js',
       'growth-web/club.html','growth-web/club.js','growth-web/favicon.svg'}


def prepare_store():
    """Grant only the existing service identity access to its own dedicated data."""
    folder=(TARGET/'growth-data').resolve()
    if folder.parent!=TARGET.resolve() or folder.name!='growth-data':
        raise RuntimeError('Unexpected acquisition data path; no service changed')
    folder.mkdir(exist_ok=True)
    # SID S-1-5-19 is LocalService, the verified existing KaiqiuMatchCenter identity.
    # The parent code tree remains read/execute. No Everyone/Users grant is added.
    command=['icacls.exe',str(folder),'/grant','*S-1-5-19:(OI)(CI)M','/T','/C']
    result=subprocess.run(command,capture_output=True,timeout=20)
    if result.returncode:
        raise RuntimeError('Unable to grant LocalService access to growth-data; no service changed')
    probe=folder/('.installer-write-probe-'+str(os.getpid()))
    try:
        probe.write_bytes(b'acquisition-store-preflight');probe.unlink()
    except Exception:
        raise RuntimeError('Acquisition data directory is not writable; no service changed')
    print('PASS: LocalService modify access is limited to growth-data; parent code permissions unchanged.')


def isolated_preflight():
    code="import sys,tempfile;sys.path.insert(0,sys.argv[1]);import sqlite3;from flask import Flask;import growth_acquisition as m;t=tempfile.TemporaryDirectory();a=Flask('growth-preflight');m.register(a,data_dir=t.name,local_token='isolated-check');c=a.test_client();assert c.get(m.PREFIX+'/health').status_code==200;assert c.get(m.PREFIX+'/api/leads').status_code==401;assert c.get(m.PREFIX+'/api/meta',headers={'Authorization':'Bearer isolated-check'}).status_code==200;t.cleanup();print('ISOLATED_GROWTH_PREFLIGHT_PASS')"
    result=subprocess.run([str(TARGET/'.venv/Scripts/python.exe'),'-c',code,str(PAYLOAD)],capture_output=True,timeout=30)
    if result.returncode:
        # Isolated process contains only synthetic content and no runtime credentials.
        print(result.stderr.decode('utf-8','replace')[-6000:])
        raise RuntimeError('Isolated acquisition preflight failed; no service changed')
    print('PASS: native SQLite, Flask registration and admin guard verified with isolated data.')


def startup_diagnostics():
    try:
        p=TARGET/'logs/error.log'
        with p.open('rb') as f:
            f.seek(0,2);size=f.tell();f.seek(max(0,size-40000));raw=f.read().decode('utf-8','replace')
        import re
        config=json.loads((TARGET/'runtime.json').read_text('utf-8-sig'))
        for k,v in config.items():
            if re.search('password|secret|token|pwd',str(k),re.I) and isinstance(v,(str,int)) and len(str(v))>3:
                raw=raw.replace(str(v),'[hidden]')
        return re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)','[phone hidden]',raw)[-16000:]
    except Exception as error:return type(error).__name__


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def state():
    result=subprocess.run(['sc.exe','query',SERVICE],capture_output=True).stdout
    return 'RUNNING' if b'RUNNING' in result else 'STOPPED' if b'STOPPED' in result else 'UNKNOWN'


def control(action,wanted):
    subprocess.run(['sc.exe',action,SERVICE],capture_output=True)
    until=time.time()+40
    while time.time()<until:
        if state()==wanted:return
        time.sleep(1)
    raise RuntimeError('Service did not reach '+wanted)


def local(path):
    conn=http.client.HTTPConnection('127.0.0.1',8011,timeout=12)
    try:
        conn.request('GET','/api/match-center'+path)
        r=conn.getresponse();body=r.read(2_000_000)
        return r.status,body
    finally:conn.close()


def verify_existing():
    for path in ['/health','/team-formats','/community/meta','/community/portrait-meta','/classic/meta',
                 '/ball-war/meta','/target-game/meta','/rest-defense/meta','/events?city=%E6%88%90%E9%83%BD&page=1']:
        status,body=local(path)
        if status!=200:raise RuntimeError('Existing endpoint failed: '+path)
        data=json.loads(body)
        if path=='/team-formats':
            assert any(x.get('key')=='s2d1_3' and x.get('players')==3 for x in data['items'])
    status,_=local('/community/me')
    if status!=401:raise RuntimeError('Existing account access check failed')


def verify():
    verify_existing()
    status,body=local('/growth/health')
    assert status==200 and json.loads(body)['version']=='ginkgo-growth-1.0.0','Growth health'
    for path in ['/growth/','/growth/assets/app.js','/growth/club/douyin-training','/growth/public/campaign/douyin-training']:
        status,_=local(path);assert status==200,'Growth static/public route '+path
    for path in ['/growth/api/leads','/growth/api/overview','/growth/api/inquiries']:
        status,_=local(path);assert status==401,'Customer records require admin login'


def safe_remove(path):
    resolved=path.resolve();root=TARGET.resolve()
    if resolved.parent!=root or resolved.name not in ('growth-web',):
        raise RuntimeError('Refusing unexpected rollback removal path')
    if resolved.exists():shutil.rmtree(resolved)


def main():
    print('Installing ginkgo-growth-1.0.0 / installer-1.0.1: dedicated LocalService data permissions verified before restart.')
    manifest=json.loads((PAYLOAD/'manifest.json').read_text('utf-8'))
    if {x['path'] for x in manifest['files']}!=FILES:raise RuntimeError('Unexpected payload files')
    for item in manifest['files']:
        path=PAYLOAD/item['path']
        if sha(path)!=item['sha256']:raise RuntimeError('Payload checksum mismatch: '+item['path'])
    ast.parse((PAYLOAD/'growth_acquisition.py').read_text('utf-8'))
    live=TARGET/'match_center.py'
    original=live.read_bytes()
    source=original.decode('utf-8-sig')
    if HOOK in source:
        if all((TARGET/x['path']).is_file() and sha(TARGET/x['path'])==x['sha256'] for x in manifest['files']):
            verify();print('SUCCESS: acquisition module already installed and verified.');return
        raise RuntimeError('Different acquisition version already installed; no service changed')
    if hashlib.sha256(original).hexdigest()!=manifest['match_center_baseline_sha256']:
        raise RuntimeError('Existing match_center.py changed; installer will not replace newer work')
    if source.count(ANCHOR)!=1:raise RuntimeError('Registration anchor mismatch')
    patched=source.replace(ANCHOR,ANCHOR+'\n'+HOOK,1)
    ast.parse(patched)
    if state()!='RUNNING':raise RuntimeError('Existing service is not RUNNING; no service changed')
    verify_existing()
    isolated_preflight()
    prepare_store()
    backup=BASE/'backups'/('growth-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    (backup/'match_center.py').write_bytes(original)
    for name in ['growth_acquisition.py','growth-web']:
        p=TARGET/name
        if p.is_dir():shutil.copytree(p,backup/name)
        elif p.is_file():shutil.copy2(p,backup/name)
    result={'version':'ginkgo-growth-1.0.0','success':False,'backup':str(backup),
            'business_database_modified':False,'platform_messages_sent':0}
    try:
        control('stop','STOPPED')
        for item in manifest['files']:
            dest=TARGET/item['path'];dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(PAYLOAD/item['path'],dest)
            if sha(dest)!=item['sha256']:raise RuntimeError('Installed hash mismatch')
        live.write_text(patched,encoding='utf-8',newline='')
        control('start','RUNNING')
        failure=None
        for _ in range(5):
            try:verify();failure=None;break
            except Exception as error:failure=error;time.sleep(2)
        if failure:raise failure
        result.update(success=True,status=state(),verified_at=datetime.now().isoformat(),installer_version='1.0.1',
                      url='https://qiuchen.yinxingpingpang.com/api/match-center/growth/',auto_send=False)
        LOG.write_text(json.dumps(result,indent=2),'utf-8')
        print('SUCCESS: acquisition workbench installed and verified. Customer data requires existing admin login.')
        print('Search tasks, need review, drafts, manual follow-up and opt-in inquiries are ready.')
        print('Platform automatic sending is NOT connected. No customer has been messaged.')
        print('URL: '+result['url']);print('Backup: '+str(backup));print('Service: '+SERVICE+' RUNNING')
    except Exception:
        result['error']=traceback.format_exc()
        result['startup_diagnostics']=startup_diagnostics()
        try:
            if state()!='STOPPED':control('stop','STOPPED')
            live.write_bytes(original)
            for name in ['growth_acquisition.py','growth-web']:
                saved=backup/name;dest=TARGET/name
                if dest.is_dir():safe_remove(dest)
                elif dest.is_file():dest.unlink()
                if saved.is_dir():shutil.copytree(saved,dest)
                elif saved.is_file():shutil.copy2(saved,dest)
            # growth-data is never deleted, including when setup fails.
            control('start','RUNNING');verify_existing()
            result.update(rolled_back=True,status=state())
            print('ROLLBACK COMPLETE: previous application restored. Customer store retained.')
        except Exception:result.update(rolled_back=False,rollback_error=traceback.format_exc(),status=state())
        LOG.write_text(json.dumps(result,indent=2),'utf-8');raise


if __name__=='__main__':main()
