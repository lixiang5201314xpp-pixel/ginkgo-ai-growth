"""Freeze tested helper recovery without changing extension permissions."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'work/ginkgo-growth-autocollect/browser-helper'
RELEASE=ROOT/'work/release/growth-dev-20261102'
DESKTOP=Path(r'C:\Users\Administrator\Desktop\银杏外部平台获客助手-1.3.0')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
new=json.loads((SRC/'manifest.json').read_text('utf-8'))
old=json.loads((RELEASE/'helper-before-1.4.4/manifest.json').read_text('utf-8'))
assert new['version']=='1.4.4' and old['version']=='1.4.3'
for key in ('permissions','host_permissions','background','action'):
    assert new[key]==old[key],key
for name,count in [('continuous-verification.json',22),('status-bridge-verification.json',6)]:
    r=json.loads((SRC.parent/name).read_text('utf-8'));assert r['passed'] and r['tests']==count
    shutil.copy2(SRC.parent/name,RELEASE/name)
for path in SRC.glob('*.js'):
    subprocess.run([r'C:\Program Files\nodejs\node.exe','--check',str(path)],check=True,capture_output=True)
current=json.loads((DESKTOP/'manifest.json').read_text('utf-8'))
assert current['version'] in ('1.4.3','1.4.4')
backup=RELEASE/'desktop-helper-before-1.4.4'
if not backup.exists():shutil.copytree(DESKTOP,backup)
frozen=RELEASE/'helper-1.4.4';frozen.mkdir(exist_ok=True)
files=[]
for path in sorted(SRC.iterdir()):
    if not path.is_file():continue
    shutil.copy2(path,frozen/path.name);shutil.copy2(path,DESKTOP/path.name)
    assert sha(path)==sha(frozen/path.name)==sha(DESKTOP/path.name)
    files.append({'path':path.name,'sha256':sha(path)})
archive=RELEASE/'银杏获客助手-1.4.4.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(frozen.iterdir()):z.write(path,'browser-helper/'+path.name)
shutil.copy2(archive,Path(r'C:\Users\Administrator\Desktop')/archive.name)
report={'version':'1.4.4','prepared_at':datetime.now(timezone.utc).isoformat(),
    'files':files,'permissions_unchanged':True,'desktop_source_updated':True,
    'extension_reload_pending':True,'live_cycle_verified':False,
    'server_code_changed':False,'live_platform_messages_sent':0,
    'checks':{'scheduler_recovery':22,'read_only_status_bridge':6,'isolated_intake_and_inherited':74},
    'archive':str(archive),'archive_sha256':sha(archive)}
(RELEASE/'helper-package.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=True,indent=2))
