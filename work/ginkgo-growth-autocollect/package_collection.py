from pathlib import Path
import hashlib
import json
import shutil
import zipfile

BASE=Path(__file__).resolve().parent
WORK=BASE.parent
RELEASE=WORK/'release/growth-collection-20261101'
PACKAGE=RELEASE/'GinkgoGrowth-1.4.0'
FILES=['growth_acquisition.py','growth_automation.py','growth_external.py','growth_collection.py',
       'growth-web/app.js','growth-web/external.js','growth-web/collection.js','growth-web/index.html',
       'growth-web/browser-helper.zip']
TESTS=['test_growth.py','test_ai.py','test_workflow.py','test_external.py','test_delivery.py','test_collection.py']
CHAIN=[('growth-ai-20261030/GinkgoGrowth-1.1.0','manifest.json'),
       ('growth-channels-20261030/GinkgoOfficialChannels-1.0.0','channels-manifest.json'),
       ('growth-workflow-20261031/GinkgoGrowth-1.2.0','workflow-manifest.json'),
       ('growth-external-20261031/GinkgoGrowth-1.3.0','external-manifest.json'),
       ('growth-night-20261101/GinkgoGrowth-1.3.1','external-manifest.json')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert json.loads((BASE/'continuous-verification.json').read_text(encoding='utf-8'))['passed']
    assert json.loads((BASE/'capture-browser-verification.json').read_text(encoding='utf-8'))['passed']
    with zipfile.ZipFile(BASE/'growth-web/browser-helper.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in (BASE/'browser-helper').iterdir():
            if p.is_file():z.write(p,'browser-helper/'+p.name)
    current={}
    for folder,name in CHAIN:
        root=WORK/'release'/folder/'payload'
        for item in json.loads((root/name).read_text(encoding='utf-8'))['files']:
            assert sha(root/item['path'])==item['sha256']
            current[item['path']]=item['sha256']
    baseline={p:[current[p]] for p in FILES if p in current}
    prior=WORK/'release/growth-delivery-20261101/GinkgoGrowth-1.3.2'
    for item in json.loads((prior/'payload/external-manifest.json').read_text(encoding='utf-8'))['files']:
        if item['path'] in baseline and item['sha256'] not in baseline[item['path']]:baseline[item['path']].append(item['sha256'])
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'growth-external-1.4.0','installer_version':'1.4.0','baseline':baseline,'files':[]}
    for name in FILES:
        dest=payload/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,dest)
        manifest['files'].append({'path':name,'sha256':sha(dest)})
    (payload/'external-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    src=(prior/'install_growth_external.py').read_text(encoding='utf-8').replace('1.3.2','1.4.0')
    old="allowed={'growth_automation.py', 'growth-web/external.js', 'growth_acquisition.py', 'growth-web/app.js', 'growth_external.py'}"
    assert old in src;src=src.replace(old,'allowed='+repr(set(FILES)))
    src=src.replace("{item['sha256'],baseline.get(name)}","{item['sha256'],*baseline.get(name,[])}")
    src=src.replace("['test_external.py', 'test_workflow.py', 'test_growth.py', 'test_delivery.py']", "['test_external.py','test_workflow.py','test_growth.py','test_delivery.py','test_collection.py']")
    src=src.replace("if local('/growth/api/delivery-summary')[0]!=401:","if local('/growth/api/collection')[0]!=401:raise RuntimeError('Automatic collection admin guard failed')\n    if local('/growth/assets/collection.js')[0]!=200:raise RuntimeError('Collection UI missing')\n    if local('/growth/api/delivery-summary')[0]!=401:")
    src=src.replace('SUCCESS: delivery review, notes, duplicate protection and source-date fixes installed and verified.',
                    'SUCCESS: bounded browser collection, automatic intake/AI preparation and delivery review installed and verified.')
    src=src.replace('NEXT: refresh the workbench. Review pending/hidden/failed sends separately. No browser extension reload is needed. Automatic platform sending remains unconnected.',
                    'NEXT: refresh the workbench, enable Automatic Intake and reload the local browser helper 1.4.0. Start collection on a logged-in public search page. External auto-sending and Channels collection are NOT connected.')
    (PACKAGE/'install_growth_external.py').write_text(src,encoding='utf-8')
    shutil.copy2(prior/'Install-Growth-External.cmd',PACKAGE/'Install-Growth-External.cmd')
    for name in TESTS:shutil.copy2(BASE/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text('''银杏获客工作台 1.4.0
兼容已知 1.3.1 / 1.3.2 文件版本；只更新获客程序，不修改赛事服务主文件、业务数据库、密钥和原微信AI接待配置。
在服务器管理员远程会话运行 Install-Growth-External.cmd。安装前隔离检查，备份后短暂重启，失败自动回滚程序。
本版本包含 1.3.2 的发送核对、跟进备注、防重发和日期识别修复，不需要先安装 1.3.2。

启用：
1. 刷新获客工作台，打开“外部平台获客”，点“开启自动入库与AI准备”。
2. 更新本机已有银杏助手为1.4.0，新增的alarms权限只用于本机定时，不新增社交平台全站读取权限。
3. 保留一个已登录工作台标签，在已登录的普通内容平台公开搜索页点击助手“启动本平台连续采集”。
4. 每轮最多处理5个已展示的原帖链接；明确包含成都的原文经规则校验后自动去重入库，排队生成AI回复；城市、日期或意图证据不足的保留待核实。
5. 每轮结束等待8分钟；连续3轮无有效新增则暂停。浏览器关闭、离开平台、登录失效、验证码或页面变化时暂停，需本人恢复。
6. 当前只有一个连续采集会话；切换平台时在对应页面重新启动。运行依赖本机浏览器，不是纯云端全站爬取。
7. 不读取私信、Cookie、密码，不自动发送评论或私信。微信视频号仍需手机搜索复制原文，不能假称四个平台全自动接通。
8. 待核实发布、手机核对未显示或平台失败的发送记录会阻止再次准备邀请和重发；已联系等待用户回复。

保留每日20次网页搜索、30次AI调用上限。平台站内搜索与模型网页索引额度分开。草稿、点击发送、核实发布、真实报名分别记录。
''',encoding='utf-8')
    with zipfile.ZipFile(RELEASE/'GinkgoGrowth-1.4.0.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,p.relative_to(PACKAGE.parent))
    archive=RELEASE/'GinkgoGrowth-1.4.0.zip'
    print(json.dumps({'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'files':len(FILES)}))

if __name__=='__main__':main()
