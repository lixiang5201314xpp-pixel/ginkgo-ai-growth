"""Freeze the identity-pinned Douyin note/video patch; no live extension reload."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'work/ginkgo-growth-autocollect/browser-helper'
RELEASE=ROOT/'work/release/growth-dev-20261102'
DESKTOP=Path(r'C:\Users\Administrator\Desktop\银杏外部平台获客助手-1.3.0')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

new=json.loads((SRC/'manifest.json').read_text('utf-8'))
old=json.loads((RELEASE/'helper-1.4.8/manifest.json').read_text('utf-8'))
assert new['version']=='1.4.9' and old['version']=='1.4.8'
for key in ('permissions','host_permissions','background','action'):assert new[key]==old[key],key
checks={}
for name,count in [('continuous-verification.json',31),('status-bridge-verification.json',6),('capture-browser-verification.json',38),('kuaishou-scope-verification.json',10)]:
    data=json.loads((SRC.parent/name).read_text('utf-8'))
    assert data['passed'] and data['tests']==count
    checks[name]=count
    shutil.copy2(SRC.parent/name,RELEASE/('1.4.9-'+name))
for path in SRC.glob('*.js'):
    subprocess.run([r'C:\Program Files\nodejs\node.exe','--check',str(path)],check=True,capture_output=True)
assert json.loads((DESKTOP/'manifest.json').read_text('utf-8'))['version']=='1.4.8'
backup=RELEASE/'desktop-helper-before-1.4.9'
if not backup.exists():shutil.copytree(DESKTOP,backup)
frozen=RELEASE/'helper-1.4.9'
assert not frozen.exists(),'Do not replace a frozen build'
frozen.mkdir()
files=[]
for path in sorted(SRC.iterdir()):
    if not path.is_file():continue
    shutil.copy2(path,frozen/path.name)
    shutil.copy2(path,DESKTOP/path.name)
    assert sha(path)==sha(frozen/path.name)==sha(DESKTOP/path.name)
    files.append({'path':path.name,'sha256':sha(path)})
archive=RELEASE/'银杏获客助手-1.4.9.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(frozen.iterdir()):z.write(path,'browser-helper/'+path.name)
shutil.copy2(archive,Path(r'C:\Users\Administrator\Desktop')/archive.name)
report={'version':'1.4.9','prepared_at':datetime.now(timezone.utc).isoformat(),
        'files':files,'permissions_unchanged':True,'desktop_source_updated':True,
        'extension_reload_pending':True,'live_cycle_verified':False,
        'server_code_changed':False,'live_platform_messages_sent':0,
        'checks':checks,'total_checks':sum(checks.values()),
        'archive':str(archive),'archive_sha256':sha(archive),
        'douyin_status':'Identity-pinned rendered overlay stays in place; live extension cycle still pending.',
        'compatibility':'Source helper only; staged backend1.4.3 remains frozen with helper1.4.7. Direct note/video same-ID canonical identity patch requires combined backend upgrade.'}
(RELEASE/'helper-package-1.4.9.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=True,indent=2))
