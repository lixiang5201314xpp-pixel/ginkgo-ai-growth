"""Combine the tested acquisition fixes without rewriting older frozen packages."""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'work/ginkgo-growth-autocollect'
RELEASE=ROOT/'work/release/growth-dev-20261102'
PRIOR=RELEASE/'GinkgoGrowth-1.4.2'
PACKAGE=RELEASE/'GinkgoGrowth-1.4.3'
FILES=['growth_acquisition.py','growth_collection.py','growth_external.py','growth-web/browser-helper.zip']
TESTS=['test_growth.py','test_ai.py','test_workflow.py','test_external.py','test_delivery.py','test_collection.py','test_job_intent.py']
sys.path.insert(0,str(SRC))
from test_packaged_workflow import copy_release
from package_collection_patch import CHAIN,WORK
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if PACKAGE.exists():
        assert not (RELEASE/'backend-1.4.3-verification.json').exists(),'Do not overwrite a verified frozen package'
        previous=json.loads((RELEASE/'backend-package-1.4.3.json').read_text('utf-8'))
        assert not previous.get('staged_on_server') and not previous.get('live_deployment'),'Do not rewrite a distributed package'
    baseline={name:[] for name in FILES}
    with tempfile.TemporaryDirectory(prefix='ginkgo-143-baseline-') as temporary:
        runtime=Path(temporary)
        for folder,manifest in CHAIN+[('growth-collection-patch-20261101/GinkgoGrowth-1.4.1','external-manifest.json')]:
            copy_release(WORK/'release'/folder,manifest,runtime)
        for name in FILES:baseline[name].append(sha(runtime/name))
        copy_release(PRIOR,'external-manifest.json',runtime)
        for name in FILES:
            value=sha(runtime/name)
            if value not in baseline[name]:baseline[name].append(value)
    helper=RELEASE/'银杏获客助手-1.4.7.zip'
    proof=json.loads((RELEASE/'helper-package-1.4.7.json').read_text('utf-8'))
    assert sha(helper)==proof['archive_sha256'] and proof['permissions_unchanged']
    with zipfile.ZipFile(helper) as z:assert json.loads(z.read('browser-helper/manifest.json'))['version']=='1.4.7'
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'growth-external-1.4.3','installer_version':'1.4.3','baseline':baseline,'files':[]}
    for name in FILES:
        target=payload/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(helper if name.endswith('.zip') else SRC/name,target)
        if name.endswith('.py'):ast.parse(target.read_text('utf-8'))
        manifest['files'].append({'path':name,'sha256':sha(target)})
    (payload/'external-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    installer=(PRIOR/'install_growth_external.py').read_text('utf-8').replace('1.4.2','1.4.3').replace('1.4.5','1.4.7')
    installer=installer.replace('import http.client','import http.client\nimport io\nimport zipfile')
    installer=installer.replace("str(PAYLOAD),str(TARGET/'channel-vendor')","str(PAYLOAD),str(BASE),str(TARGET/'channel-vendor')")
    installer=installer.replace('Recovers exact committed batch receipts after response loss; expired new observations remain rejected.',
        'Recovers exact receipts, excludes coach job-seeking advertisements and verifies helper download 1.4.7.')
    installer=installer.replace("['test_external.py','test_workflow.py','test_growth.py','test_delivery.py','test_collection.py']",repr(TESTS))
    installer=installer.replace("if test=='test_growth.py':",'if True:')
    installer=installer.replace('import growth_acquisition as m;t=tempfile','import growth_acquisition as m;m.BASE=Path("+repr(str(TARGET))+");t=tempfile')
    installer=installer.replace('import tempfile;from flask import Flask;', 'import tempfile;from pathlib import Path;from flask import Flask;')
    installer=installer.replace('    # No live customer message or model generation during install.',
        "    status,raw=local('/growth/assets/browser-helper.zip')\n"
        "    if status!=200:raise RuntimeError('Helper download failed')\n"
        "    with zipfile.ZipFile(io.BytesIO(raw)) as helper:\n"
        "        if json.loads(helper.read('browser-helper/manifest.json')).get('version')!='1.4.7':raise RuntimeError('Helper download version mismatch')\n"
        '    # No live customer message or model generation during install.')
    installer=installer.replace('SUCCESS: exact receipt recovery and helper download 1.4.7 installed and verified. Existing reception retained.',
        'SUCCESS: source-role filtering, exact receipt recovery and helper download 1.4.7 installed and verified. Existing reception retained.')
    ast.parse(installer)
    (PACKAGE/'install_growth_external.py').write_text(installer,encoding='utf-8')
    shutil.copy2(PRIOR/'Install-Growth-External.cmd',PACKAGE/'Install-Growth-External.cmd')
    for name in TESTS:shutil.copy2(SRC/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text(
        '银杏获客后台1.4.3，支持已安装1.4.1或1.4.2，不需先安装旧的暂存包。\n'
        '只更新4个获客文件：需求角色筛选、采集回执恢复、外部模块版本、助手下载ZIP。\n'
        '求职、招教练与教练找学生不进入客户或AI回复队列；正常家长、成人学球和参赛仍可通过。\n'
        '助手1.4.7包含抖音加载/最新排序恢复及快手来源保护；保护不等于快手完整采集已接通。\n'
        '管理员运行Install-Growth-External.cmd。先校验/隔离预检/备份，短暂重启，失败还原；无需重填密钥。\n'
        '不修改业务账号、比赛、积分、奖牌、AI密钥或20/30调用上限。\n'
        '安装器会验证实际下载包版本，但Chrome仍需在既有助手卡片正常刷新后加载新版本。\n'
        '外部评论/私信自动发送与视频号采集仍未接通。本包不是最终完整获客交付。\n',encoding='utf-8')
    archive=RELEASE/'GinkgoGrowth-1.4.3.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(PACKAGE.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:z.write(path,path.relative_to(PACKAGE.parent))
    result={'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'payload_files':FILES,
            'compatible_baselines':['1.4.1','1.4.2'],'helper_version':'1.4.7','live_deployment':False}
    (RELEASE/'backend-package-1.4.3.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
