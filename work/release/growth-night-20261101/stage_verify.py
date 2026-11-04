"""Verify and unpack only the staged package; never install or touch the runtime directory."""
from pathlib import Path
import ast
import hashlib
import http.client
import json
import zipfile

ROOT=Path(r'C:\Services\GinkgoTrainingAutoCancel')
ARCHIVE=ROOT/'GinkgoGrowth-1.3.1.zip'
EXPECTED='1e924aceb163bc375a9168c1231535b5ffb8034a3b9e13f6539a6770f1af3d50'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(ARCHIVE)==EXPECTED,'Archive hash mismatch'
with zipfile.ZipFile(ARCHIVE) as z:
    for info in z.infolist():
        target=(ROOT/info.filename).resolve()
        assert target.is_relative_to((ROOT/'GinkgoGrowth-1.3.1').resolve()),'Unsafe archive path'
    z.extractall(ROOT)
package=ROOT/'GinkgoGrowth-1.3.1'
manifest=json.loads((package/'payload/external-manifest.json').read_text('utf-8'))
for item in manifest['files']:
    p=package/'payload'/item['path'];assert sha(p)==item['sha256'],item['path']
for p in package.rglob('*.py'):ast.parse(p.read_text('utf-8-sig'))
health={}
for path in ('/health','/growth/health','/growth/external/health','/growth/channels/health'):
    c=http.client.HTTPConnection('127.0.0.1',8011,timeout=10)
    try:
        c.request('GET','/api/match-center'+path);r=c.getresponse();raw=r.read(100000)
        health[path]={'status':r.status,'version':json.loads(raw).get('version') if r.status==200 else None}
    finally:c.close()
report={'staged':True,'installed':False,'runtime_modified':False,'service_restarted':False,
    'archive_sha256':EXPECTED,'payload_files_verified':len(manifest['files']),'health':health}
(package/'staged-verification.json').write_text(json.dumps(report,indent=2),'utf-8')
print(json.dumps(report,indent=2))
