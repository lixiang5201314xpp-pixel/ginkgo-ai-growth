"""Owner-session read checks only. Never log, copy or return a credential."""
from pathlib import Path
import ctypes
import hashlib
import importlib
import json
import os
import sqlite3
import sys
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
TARGET=Path(r'C:\Services\KaiqiuMatch_20260915')

def main():
    report={'version':'growth-ai-access-1.0.0','elevated':bool(ctypes.windll.shell32.IsUserAnAdmin()),'checks':[],
            'service_restarted':False,'api_calls':0,'business_data_changed':False}
    def check(name,action):
        try:
            action();row={'name':name,'ok':True};print('PASS: '+name)
        except Exception as e:
            row={'name':name,'ok':False,'error_type':type(e).__name__,'winerror':getattr(e,'winerror',None),
                 'errno':getattr(e,'errno',None),'path':str(getattr(e,'filename','') or '')}
            # No exception str(), traceback locals, encrypted bytes or API keys.
            print('FAIL: '+name+' / '+row['error_type']+' / path='+row['path'])
        report['checks'].append(row)
    print('Ginkgo AI access diagnostics 1.0.0. No restart, no API calls, no key displayed.')
    print('Elevated administrator token: '+str(report['elevated']))
    check('Runtime acquisition code read',lambda:(TARGET/'growth_acquisition.py').read_bytes())
    def read_database():
        c=sqlite3.connect((TARGET/'growth-data/acquisition.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=10)
        try:
            row=c.execute("SELECT value FROM settings WHERE key='ai_config'").fetchone()
            if not row:raise RuntimeError('Missing saved AI configuration')
            config=json.loads(row[0]);report['configuration_present']=True
            report['provider']=config.get('provider');report['enabled']=bool(config.get('enabled'))
        finally:c.close()
    check('Existing AI settings read-only',read_database)
    secret=TARGET/'growth-data/secrets/deepseek.dpapi'
    check('Encrypted key file read (contents never displayed)',lambda:secret.read_bytes())
    sys.path.insert(0,str(BASE/'payload'))
    module=[]
    def load_module():module.append(importlib.import_module('growth_ai'))
    check('Staged AI module import',load_module)
    if module:
        def decrypt():
            key=module[0].Vault.crypt(secret.read_bytes(),True)
            if not key.startswith(b'sk-'):raise RuntimeError('Credential format mismatch')
            del key
        check('Local-machine DPAPI key access (boolean result only)',decrypt)
    out=BASE/'ai-access-diagnostics.json';out.write_text(json.dumps(report,indent=2),'utf-8')
    print('SUCCESS: safe access report saved. Existing service and customer data were not changed.')
    print('Please report diagnostics completed. Do NOT send your API key.')

if __name__=='__main__':main()
