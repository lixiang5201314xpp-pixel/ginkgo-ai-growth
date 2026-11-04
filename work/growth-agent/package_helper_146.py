"""Freeze the recent-sort fix without replacing previous tested releases."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/ginkgo-growth-autocollect/browser-helper'
RELEASE = ROOT / 'work/release/growth-dev-20261102'
DESKTOP = Path(r'C:\Users\Administrator\Desktop\银杏外部平台获客助手-1.3.0')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

new = json.loads((SRC / 'manifest.json').read_text('utf-8'))
old = json.loads((RELEASE / 'helper-1.4.5/manifest.json').read_text('utf-8'))
assert new['version'] == '1.4.6' and old['version'] == '1.4.5'
for key in ('permissions', 'host_permissions', 'background', 'action'):
    assert new[key] == old[key], key
checks = {}
for name, count in [('continuous-verification.json', 28), ('status-bridge-verification.json', 6), ('capture-browser-verification.json', 22)]:
    report = json.loads((SRC.parent / name).read_text('utf-8'))
    assert report['passed'] and report['tests'] == count
    checks[name] = count
    shutil.copy2(SRC.parent / name, RELEASE / ('1.4.6-' + name))
for path in SRC.glob('*.js'):
    subprocess.run([r'C:\Program Files\nodejs\node.exe', '--check', str(path)], check=True, capture_output=True)
assert json.loads((DESKTOP / 'manifest.json').read_text('utf-8'))['version'] == '1.4.5'
backup = RELEASE / 'desktop-helper-before-1.4.6'
if not backup.exists():
    shutil.copytree(DESKTOP, backup)
frozen = RELEASE / 'helper-1.4.6'
assert not frozen.exists(), 'Do not silently replace a frozen build'
frozen.mkdir()
files = []
for path in sorted(SRC.iterdir()):
    if not path.is_file():
        continue
    shutil.copy2(path, frozen / path.name)
    shutil.copy2(path, DESKTOP / path.name)
    assert sha(path) == sha(frozen / path.name) == sha(DESKTOP / path.name)
    files.append({'path': path.name, 'sha256': sha(path)})
archive = RELEASE / '银杏获客助手-1.4.6.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
    for path in sorted(frozen.iterdir()):
        zipped.write(path, 'browser-helper/' + path.name)
shutil.copy2(archive, Path(r'C:\Users\Administrator\Desktop') / archive.name)
report = {
    'version': '1.4.6', 'prepared_at': datetime.now(timezone.utc).isoformat(),
    'files': files, 'permissions_unchanged': True, 'desktop_source_updated': True,
    'extension_reload_pending': True, 'live_cycle_verified': False,
    'server_code_changed': False, 'live_platform_messages_sent': 0,
    'checks': checks, 'total_checks': sum(checks.values()),
    'archive': str(archive), 'archive_sha256': sha(archive),
    'compatibility': 'Existing server >=1.4.0; staged backend1.4.2 still bundles frozen helper1.4.5.'
}
(RELEASE / 'helper-package-1.4.6.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=True, indent=2))
