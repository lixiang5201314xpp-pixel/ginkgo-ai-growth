"""Build a reproducible server payload; never include local access tokens or leads."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import ast

BASE=Path(__file__).resolve().parent
WORK=BASE.parent
RELEASE=WORK/'release'/'growth-20261030'
PACKAGE=RELEASE/'GinkgoGrowth-1.0.0'
FILES=['growth_acquisition.py','growth-web/index.html','growth-web/app.css','growth-web/app.js',
       'growth-web/club.html','growth-web/club.js','growth-web/favicon.svg']
BASELINE=WORK/'release'/'team-variants-20261030'/'payload'/'match_center.py'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    verified=json.loads((BASE/'verification.json').read_text('utf-8'))
    assert verified['passed'] and verified['production_writes'] is False
    (PACKAGE/'payload').mkdir(parents=True,exist_ok=True)
    manifest={'version':'ginkgo-growth-1.0.0','match_center_baseline_sha256':digest(BASELINE),'files':[]}
    for name in FILES:
        dest=PACKAGE/'payload'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,dest)
        manifest['files'].append({'path':name,'sha256':digest(dest)})
    for name in ['install_growth.py','Install-Growth.cmd','使用说明.md']:
        shutil.copy2(BASE/name,PACKAGE/name)
    shutil.copytree(BASE/'browser-helper',PACKAGE/'browser-helper',dirs_exist_ok=True)
    (PACKAGE/'payload'/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    ast.parse((PACKAGE/'payload'/'growth_acquisition.py').read_text('utf-8'))
    source=BASELINE.read_text('utf-8')
    anchor='    app.register_blueprint(bp, url_prefix=PREFIX)'
    hook='    import growth_acquisition\n    growth_acquisition.register(app, require_login=require_login, is_admin=admin)'
    assert source.count(anchor)==1
    ast.parse(source.replace(anchor,anchor+'\n'+hook,1))
    shutil.copy2(BASE/'verification.json',RELEASE/'verification.json')
    archive=RELEASE/'GinkgoGrowth-1.0.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(PACKAGE.parent))
    status={'version':'ginkgo-growth-1.0.0','backend_installed':False,'frontend_modified':False,
            'platform_messages_sent':0,'automatic_platform_ingestion':False,'auto_send':False,
            'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest(archive),
            'isolated_tests':verified['tests'],'actual_customer_leads_imported':0}
    (RELEASE/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
