"""Verify and expand a fixed staging archive only; no service or business writes."""
import hashlib
import json
from pathlib import Path
import zipfile

base=Path(r'C:\Services\GinkgoTrainingAutoCancel')
archive=base/'GinkgoGrowth-1.4.1.zip'
expected='09b1cc74738bb18224d5d51b2f3a90bebc18397bf89a17ab82d6e1b0238eb8ce'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,'Staging archive hash mismatch'
target=(base/'GinkgoGrowth-1.4.1').resolve()
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():assert (base/name).resolve().is_relative_to(target),'Archive escaped fixed staging folder'
    z.extractall(base)
payload=target/'payload'
manifest=json.loads((payload/'external-manifest.json').read_text(encoding='utf-8'))
assert len(manifest['files'])==4
for item in manifest['files']:
    path=(payload/item['path']).resolve()
    assert path.is_relative_to(payload.resolve())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],item['path']
print('PASS: backend 1.4.1 archive and all 4 staged payload hashes verified. No service, settings, credentials or business data changed.')
