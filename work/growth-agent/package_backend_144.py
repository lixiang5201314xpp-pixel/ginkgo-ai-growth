"""Combine the observed practice-request fixes and the frozen helper 1.4.8."""
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
PRIOR=RELEASE/'GinkgoGrowth-1.4.3'
PACKAGE=RELEASE/'GinkgoGrowth-1.4.4'
FILES=['growth_acquisition.py','growth_collection.py','growth_external.py','growth-web/browser-helper.zip']
TESTS=['test_growth.py','test_ai.py','test_workflow.py','test_external.py','test_delivery.py','test_collection.py','test_job_intent.py','test_practice_intent.py']
sys.path.insert(0,str(SRC))
from test_packaged_workflow import copy_release
from package_collection_patch import CHAIN,WORK
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if PACKAGE.exists():
        assert not (RELEASE/'backend-1.4.4-verification.json').exists(),'Do not overwrite a verified frozen package'
        prior=json.loads((RELEASE/'backend-package-1.4.4.json').read_text('utf-8'))
        assert not prior.get('staged_on_server') and not prior.get('live_deployment'),'Do not rewrite a distributed package'
    baseline={name:[] for name in FILES}
    with tempfile.TemporaryDirectory(prefix='ginkgo-144-baseline-') as temporary:
        runtime=Path(temporary)
        releases=CHAIN+[('growth-collection-patch-20261101/GinkgoGrowth-1.4.1','external-manifest.json')]
        for folder,manifest in releases:copy_release(WORK/'release'/folder,manifest,runtime)
        for version in ('1.4.1','1.4.2','1.4.3'):
            if version!='1.4.1':copy_release(RELEASE/('GinkgoGrowth-'+version),'external-manifest.json',runtime)
            for name in FILES:
                value=sha(runtime/name)
                if value not in baseline[name]:baseline[name].append(value)
    helper=RELEASE/'银杏获客助手-1.4.8.zip'
    proof=json.loads((RELEASE/'helper-package-1.4.8.json').read_text('utf-8'))
    assert sha(helper)==proof['archive_sha256'] and proof['permissions_unchanged']
    with zipfile.ZipFile(helper) as z:assert json.loads(z.read('browser-helper/manifest.json'))['version']=='1.4.8'
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'growth-external-1.4.4','installer_version':'1.4.4','baseline':baseline,'files':[]}
    for name in FILES:
        target=payload/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(helper if name.endswith('.zip') else SRC/name,target)
        if name=='growth_external.py':
            source=target.read_text('utf-8')
            assert "growth-external-1.4.3" in source
            target.write_text(source.replace('growth-external-1.4.3','growth-external-1.4.4'),encoding='utf-8')
        if name.endswith('.py'):ast.parse(target.read_text('utf-8'))
        manifest['files'].append({'path':name,'sha256':sha(target)})
    (payload/'external-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    installer=(PRIOR/'install_growth_external.py').read_text('utf-8').replace('1.4.3','1.4.4').replace('1.4.7','1.4.8')
    installer=installer.replace("'test_job_intent.py']","'test_job_intent.py', 'test_practice_intent.py']")
    installer=installer.replace('excludes coach job-seeking advertisements','recognizes explicit practice requests and excludes provider replies/job-seeking advertisements')
    start=installer.index('    allowed=')
    end=installer.index('\n',start)
    installer=installer[:start]+'    allowed='+repr(set(FILES))+installer[end:]
    installer=installer.replace("    core_hash=sha(TARGET/'match_center.py')",
        "    retained_names=['match_center.py','identity.py','roster_rating_replay.py','growth_ai.py','growth_channels.py','growth_automation.py','growth_playbook.json']\n"
        "    retained={name:sha(TARGET/name) for name in retained_names if (TARGET/name).is_file()}")
    installer=installer.replace("if sha(TARGET/'match_center.py')!=core_hash:raise RuntimeError('Core service source changed unexpectedly')",
        "if any(sha(TARGET/name)!=value for name,value in retained.items()):raise RuntimeError('Unrelated identity/core/AI source changed unexpectedly')")
    installer=installer.replace("result.update(success=True,service=state())",
        "result.update(success=True,service=state(),installed_payload_sha256={x['path']:sha(TARGET/x['path']) for x in files},retained_file_sha256=retained)")
    ast.parse(installer)
    (PACKAGE/'install_growth_external.py').write_text(installer,encoding='utf-8')
    shutil.copy2(PRIOR/'Install-Growth-External.cmd',PACKAGE/'Install-Growth-External.cmd')
    for name in TESTS:shutil.copy2(SRC/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text(
        '银杏获客后台1.4.4，可从1.4.1/1.4.2/1.4.3直接升级，无需先装旧暂存包。\n'
        '识别已核对的“一起练单球吗”“来个搭子”等明确需求，排除求职、招生和工作人员接待回复。\n'
        '保留精确批次回执恢复与旧内容过滤，更新助手下载为1.4.8：可核对身份的抖音弹层就地读取，不强制跳转；原帖日期与评论日期独立。\n'
        '只更换4个获客文件；identity.py手机号资料修复、积分、比赛、微信AI、密钥及20/30限额均保留。\n'
        '管理员运行Install-Growth-External.cmd，先预检和备份，短暂重启，失败还原。无需上传小程序。\n'
        'Chrome需刷新既有银杏助手加载1.4.8。旧版本不自行更新成新版本。\n'
        '原帖7702708741762243570已人工回复，部署后只补登记既有可见发布回执，禁止再发一遍。\n'
        '外部平台自动发送及视频号采集仍未接通，不是全功能验收交付。\n',encoding='utf-8')
    archive=RELEASE/'GinkgoGrowth-1.4.4.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(PACKAGE.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:z.write(path,path.relative_to(PACKAGE.parent))
    result={'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'payload_files':FILES,
        'compatible_baselines':['1.4.1','1.4.2','1.4.3'],'helper_version':'1.4.8','live_deployment':False,
        'identity_source_unchanged':True,'platform_auto_sending_connected':False}
    (RELEASE/'backend-package-1.4.4.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
