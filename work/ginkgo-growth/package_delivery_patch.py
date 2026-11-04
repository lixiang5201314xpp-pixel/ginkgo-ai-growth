"""Freeze a five-file upgrade against the known 1.3.1 installed composition."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

BASE=Path(__file__).resolve().parent
WORK=BASE.parent
RELEASE=WORK/'release/growth-delivery-20261101'
PACKAGE=RELEASE/'GinkgoGrowth-1.3.2'
FILES=['growth_acquisition.py','growth_automation.py','growth_external.py','growth-web/app.js','growth-web/external.js']
TESTS=['test_growth.py','test_ai.py','test_workflow.py','test_external.py','test_delivery.py']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert json.loads((BASE/'delivery-verification.json').read_text())['passed']
    baseline={}
    chain=[('growth-ai-20261030/GinkgoGrowth-1.1.0','manifest.json'),
        ('growth-channels-20261030/GinkgoOfficialChannels-1.0.0','channels-manifest.json'),
        ('growth-workflow-20261031/GinkgoGrowth-1.2.0','workflow-manifest.json'),
        ('growth-external-20261031/GinkgoGrowth-1.3.0','external-manifest.json'),
        ('growth-night-20261101/GinkgoGrowth-1.3.1','external-manifest.json')]
    for folder,manifest_name in chain:
        root=WORK/'release'/folder/'payload'
        manifest=json.loads((root/manifest_name).read_text('utf-8'))
        for item in manifest['files']:
            assert sha(root/item['path'])==item['sha256'],item['path']
            baseline[item['path']]=item['sha256']
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'growth-external-1.3.2','installer_version':'1.3.2','baseline':{p:baseline[p] for p in FILES},'files':[]}
    for name in FILES:
        target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,target)
        manifest['files'].append({'path':name,'sha256':sha(target)})
    (payload/'external-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    old=WORK/'release/growth-night-20261101/GinkgoGrowth-1.3.1/install_growth_external.py'
    source=old.read_text('utf-8').replace('1.3.1','1.3.2')
    source=source.replace("allowed={'growth_acquisition.py','growth_external.py','growth-web/external.js','growth-web/browser-helper.zip'}",'allowed='+repr(set(FILES)))
    source=source.replace("['test_external.py','test_workflow.py','test_growth.py']",repr(['test_external.py','test_workflow.py','test_growth.py','test_delivery.py']))
    source=source.replace("if local('/growth/assets/external.js')[0]!=200", "if local('/growth/api/delivery-summary')[0]!=401:raise RuntimeError('Delivery admin guard failed')\n    if local('/growth/assets/external.js')[0]!=200")
    source=source.replace('SUCCESS: external-platform search tasks, public-comment intake, evidence review and AI preparation installed and verified.',
        'SUCCESS: delivery review, notes, duplicate protection and source-date fixes installed and verified.')
    source=source.replace('NEXT: refresh External Platforms; batch paste and updated current-post/comment helper are ready. Automatic platform sending is NOT connected.',
        'NEXT: refresh the workbench. Review pending/hidden/failed sends separately. No browser extension reload is needed. Automatic platform sending remains unconnected.')
    source=source.replace('No channel settings or mini-app uploads are changed.',
        'Adds a delivery receipt table in the acquisition store only. No channel settings, existing customer records or mini-app uploads are changed.')
    (PACKAGE/'install_growth_external.py').write_text(source,'utf-8')
    shutil.copy2(BASE/'Install-Growth-External.cmd',PACKAGE/'Install-Growth-External.cmd')
    for name in TESTS:shutil.copy2(BASE/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text('''银杏获客更新 1.3.2
在远程服务器管理员会话运行 Install-Growth-External.cmd。
仅更新五份获客程序。保留微信AI客服、平台配置、DeepSeek密钥、每日20次网页搜索和30次AI额度。
无需重新加载或安装浏览器扩展，无需重新上传小程序。

新增：
1. 记录已点发送后的“待核实、核对未显示、平台提示失败”，这些状态不计为已联系。
2. 待核实或未显示记录阻止重复联系、重复草稿及相关AI邀请准备。
3. 人工在原平台核实可见后登记一次实际联系；双击或重复请求不重复计数。
4. 跟进备注、发送状态筛选和首页执行状态。
5. 修复快手搜索链接、小红书带省份日期识别。

安装器先检查原文件校验值和隔离测试，再备份并短暂重启服务，失败自动回滚程序。
新增表仅位于独立获客SQLite库；不修改赛事SQL数据库、账号、奖牌或积分。旧程序可忽略新增表。
本包不会自动补记小红书的实际发送尝试。安装成功后在工作台“需求与跟进”中录入核对结果。
外部平台自动评论和私信仍需对应官方接口授权；本包不伪装为已经接通。
''','utf-8')
    archive=RELEASE/'GinkgoGrowth-1.3.2.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,p.relative_to(PACKAGE.parent))
    print(json.dumps({'package':str(PACKAGE),'archive':str(archive),'files':len(FILES),'sha256':sha(archive),'bytes':archive.stat().st_size}))

if __name__=='__main__':main()
