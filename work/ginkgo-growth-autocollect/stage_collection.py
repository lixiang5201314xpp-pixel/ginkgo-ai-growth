"""Unpack and verify staging only. Never touches the running service or database."""
import hashlib
import json
from pathlib import Path
import zipfile

base=Path(r'C:\Services\GinkgoTrainingAutoCancel')
archive=base/'GinkgoGrowth-1.4.0.zip'
expected='e3c4b475a15560e8cee4c3f9494758ef1ad1bc9a364ebd72bf3ce8f2e53bf616'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,'Staging archive hash mismatch'
target=(base/'GinkgoGrowth-1.4.0').resolve()
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        assert (base/name).resolve().is_relative_to(target),'Archive escaped fixed staging folder'
    z.extractall(base)
payload=target/'payload'
manifest=json.loads((payload/'external-manifest.json').read_text(encoding='utf-8'))
for item in manifest['files']:
    path=(payload/item['path']).resolve()
    assert path.is_relative_to(payload.resolve())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],item['path']
print('PASS: archive and all '+str(len(manifest['files']))+' payload hashes verified in staging. No service, configuration or business data was changed.')
