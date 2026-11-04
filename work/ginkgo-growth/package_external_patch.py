"""Freeze the verified 1.3.1 intake patch against the exact installed 1.3.0 release."""
from pathlib import Path
import json
import hashlib
import shutil
import zipfile

BASE=Path(__file__).resolve().parent
RELEASE=BASE.parent/'release/growth-night-20261101'
PACKAGE=RELEASE/'GinkgoGrowth-1.3.1'
FILES=['growth_acquisition.py','growth_external.py','growth-web/external.js','growth-web/browser-helper.zip']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for name in ('external-verification.json','browser-helper-verification.json','capture-browser-verification.json','external-batch-verification.json'):
        assert json.loads((BASE/name).read_text('utf-8'))['passed'],name
    with zipfile.ZipFile(BASE/'growth-web/browser-helper.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in (BASE/'browser-helper').iterdir():
            if p.is_file():z.write(p,'browser-helper/'+p.name)
    prior=BASE.parent/'release/growth-external-20261031/GinkgoGrowth-1.3.0/payload/external-manifest.json'
    baseline={x['path']:x['sha256'] for x in json.loads(prior.read_text('utf-8'))['files']}
    channels=BASE.parent/'release/growth-channels-20261030/GinkgoOfficialChannels-1.0.0/payload/channels-manifest.json'
    baseline.update({x['path']:x['sha256'] for x in json.loads(channels.read_text('utf-8'))['files'] if x['path']=='growth_acquisition.py'})
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'growth-external-1.3.1','installer_version':'1.3.1',
              'baseline':{k:baseline[k] for k in FILES},'files':[]}
    for name in FILES:
        dest=payload/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,dest)
        manifest['files'].append({'path':name,'sha256':sha(dest)})
    (payload/'external-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    installer=(BASE/'install_growth_external.py').read_text('utf-8').replace('1.3.0','1.3.1')
    installer=installer.replace('43 isolated external-intake and workflow checks','external-intake, workflow and base acquisition checks')
    installer=installer.replace("['test_external.py','test_workflow.py']", "['test_external.py','test_workflow.py','test_growth.py']")
    installer=installer.replace("r=subprocess.run([str(python),str(BASE/test)],capture_output=True,timeout=75,env=env)", """command=[str(python),str(BASE/test)]
        if test=='test_growth.py':
            # Candidate Python uses the existing runtime web assets during overlay preflight.
            code=\"from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path(\"+repr(str(TARGET))+\");runpy.run_path(\"+repr(str(BASE/test))+\",run_name='__main__')\"
            command=[str(python),'-c',code]
        r=subprocess.run(command,capture_output=True,timeout=75,env=env)""")
    installer=installer.replace("allowed={'growth_automation.py','growth_external.py','growth-web/index.html','growth-web/external.js','growth-web/app.css','growth-web/browser-helper.zip'}", "allowed={'growth_acquisition.py','growth_external.py','growth-web/external.js','growth-web/browser-helper.zip'}")
    installer=installer.replace('NEXT: refresh the workbench and open External Platforms. Install the browser helper locally to capture expanded public comments. Automatic platform sending is NOT connected.',
        'NEXT: refresh External Platforms; batch paste and updated current-post/comment helper are ready. Automatic platform sending is NOT connected.')
    (PACKAGE/'install_growth_external.py').write_text(installer,'utf-8')
    for name in ('Install-Growth-External.cmd','test_external.py','test_workflow.py','test_ai.py','test_growth.py'):
        shutil.copy2(BASE/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text('''银杏外部平台获客修正 1.3.1（尚未安装）
在服务器管理员远程会话运行 Install-Growth-External.cmd。
只替换四份获客文件：获客需求规则、原文解析、外部平台页面、采集助手ZIP；不替换赛事主模块、AI接待、密钥、客户数据库或调用限额。
先检查已安装1.3.0的精确校验值和独立测试，再备份并短暂重启；失败自动还原。

修正：
1. 抖音搜索弹窗链接自动转为具体作品链接，避免导入被拒绝，并对弹窗/详情去重。
2. 只读取当前作品和屏幕内评论，避免串入相邻视频；嵌套回复不冒领到父评论。
3. 识别当前抖音两种评论布局；解析带“·四川”的时间，但不把IP或省份当成都证据。
4. 助手增加“读取当前作品求助（抖音）”，作品时间未知时保持待核实。
5. 工作台“外部平台获客”增加“粘贴采集批次”；最多20条，先核对再去重导入。
6. 修正“有没有厉害的球搭子”等真实约球问句未进入需求判定的问题。

本机原助手文件夹已更新到1.3.1，刷新扩展后生效，无新增权限。
平台自动收发接口仍未接入；不会无人值守遍历平台、自动发广告或把搜索结果当报名。
不会自动导入本轮的真实求助或重复发送已发布的评论。
''','utf-8')
    archive=RELEASE/'GinkgoGrowth-1.3.1.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,p.relative_to(PACKAGE.parent))
    print(json.dumps({'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size}))
if __name__=='__main__':main()
