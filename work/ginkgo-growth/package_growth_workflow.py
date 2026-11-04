"""Build the small workflow-only upgrade; never package credentials or customer data."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

BASE=Path(__file__).resolve().parent
RELEASE=BASE.parent/'release/growth-workflow-20261031'
PACKAGE=RELEASE/'GinkgoGrowth-1.2.0'
FILES=['growth_automation.py','growth_workflow.py','growth-web/index.html','growth-web/automation.js','growth-web/workflow.js','growth-web/app.css']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result=json.loads((BASE/'packaged-workflow-verification.json').read_text('utf-8'))
    assert result['passed'] and result['tests']==40
    payload=PACKAGE/'payload';manifest=json.loads((payload/'workflow-manifest.json').read_text('utf-8'))
    for name in FILES:
        dest=payload/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,dest)
    manifest['files']=[{'path':name,'sha256':sha(payload/name)} for name in FILES]
    manifest['installer_version']='1.2.1'
    (payload/'workflow-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    for name in ['install_growth_workflow.py','Install-Growth-Workflow.cmd','test_workflow.py','test_ai.py']:
        shutil.copy2(BASE/name,PACKAGE/name)
    archive=RELEASE/'GinkgoGrowth-1.2.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,p.relative_to(PACKAGE.parent))
    status=json.loads((RELEASE/'status.json').read_text('utf-8'))
    status.update(installer_version='1.2.1',backend_installed=False,server_staged=False,
        sha256=sha(archive),bytes=archive.stat().st_size,
        previous_attempt='Preflight rejected before service restart: playbook path resolved relative to overlay module.',
        fix='Fingerprint reads the same installed playbook as AIService; final overlay and installed-layout suites passed.',
        packaged_layout_tests=40,installer_tests=8,
        awaiting='Fixed installer not yet run by owner.')
    (RELEASE/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'installer_version':'1.2.1'}))


if __name__=='__main__':main()
