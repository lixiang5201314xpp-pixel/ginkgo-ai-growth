"""Read startup traceback and run an isolated import probe; no service restart."""
from pathlib import Path
import json
import re
import subprocess
import sys

BASE=Path(__file__).resolve().parent
TARGET=Path(r'C:\Services\KaiqiuMatch_20260915')
out={'diagnostic':'growth-startup-1.0.0','services_modified':False,'business_data_modified':False}
secrets=[]
try:
    config=json.loads((TARGET/'runtime.json').read_text('utf-8-sig'))
    secrets=[str(v) for k,v in config.items() if re.search('password|secret|token|pwd',k,re.I) and isinstance(v,(str,int)) and len(str(v))>3]
except Exception:pass
def clean(s):
    for secret in secrets:s=s.replace(secret,'[hidden]')
    s=re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)','[phone hidden]',s)
    return s
try:
    p=TARGET/'logs'/'error.log'
    with p.open('rb') as f:
        f.seek(0,2);size=f.tell();f.seek(max(0,size-100_000));raw=f.read().decode('utf-8','replace')
    lines=raw.splitlines()
    starts=[i for i,line in enumerate(lines) if 'Traceback (most recent call last)' in line]
    out['startup_tracebacks']=clean('\n'.join(lines[starts[-4]:] if len(starts)>=4 else lines[starts[0]:] if starts else lines[-100:]))[-60_000:]
except Exception as error:out['log_error']=type(error).__name__
try:
    for name in ['growth-data','growth_acquisition.py']:
        p=TARGET/name
        r=subprocess.run(['icacls.exe',str(p)],capture_output=True,timeout=10)
        out['acl_'+name]=r.stdout.decode('mbcs','replace')
except Exception as error:out['acl_error']=type(error).__name__
try:
    code="import sys,tempfile;sys.path.insert(0,sys.argv[1]);import sqlite3;from flask import Flask;import growth_acquisition as m;t=tempfile.TemporaryDirectory();a=Flask('growth-probe');m.register(a,data_dir=t.name,local_token='isolated-probe');r=a.test_client().get(m.PREFIX+'/health');assert r.status_code==200;print('ISOLATED_GROWTH_IMPORT_PASS');t.cleanup()"
    r=subprocess.run([str(TARGET/'.venv/Scripts/python.exe'),'-c',code,str(BASE/'payload')],capture_output=True,timeout=30)
    out['isolated_import']={'returncode':r.returncode,'stdout':clean(r.stdout.decode('utf-8','replace')),'stderr':clean(r.stderr.decode('utf-8','replace'))}
except Exception as error:out['import_probe_error']=type(error).__name__
(BASE/'growth-startup-diagnostics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),'utf-8')
print('SUCCESS: startup diagnostics saved. Existing service was NOT restarted or changed.')
print('Please tell me the diagnostic completed; I can read the saved report.')
