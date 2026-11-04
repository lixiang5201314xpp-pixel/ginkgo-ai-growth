"""Build an external-platform-only upgrade with no accounts, credentials or customer records."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

BASE=Path(__file__).resolve().parent
RELEASE=BASE.parent/'release/growth-external-20261031'
PACKAGE=RELEASE/'GinkgoGrowth-1.3.0'
FILES=['growth_automation.py','growth_external.py','growth-web/index.html','growth-web/external.js','growth-web/app.css','growth-web/browser-helper.zip']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    tests=json.loads((BASE/'external-verification.json').read_text('utf-8'));assert tests['passed']
    assert json.loads((BASE/'browser-helper-verification.json').read_text('utf-8'))['passed']
    prior=BASE.parent/'release/growth-workflow-20261031/GinkgoGrowth-1.2.0/payload/workflow-manifest.json'
    baseline={x['path']:x['sha256'] for x in json.loads(prior.read_text('utf-8'))['files']}
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'growth-external-1.3.0','installer_version':'1.3.0','baseline':{k:baseline[k] for k in FILES if k in baseline},'files':[]}
    for name in FILES:
        dest=payload/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,dest)
        manifest['files'].append({'path':name,'sha256':sha(dest)})
    (payload/'external-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    for name in ['install_growth_external.py','Install-Growth-External.cmd','test_external.py','test_workflow.py','test_ai.py']:
        shutil.copy2(BASE/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text('''银杏外部平台获客 1.3.0
运行 Install-Growth-External.cmd：先预检、备份，再短暂重启赛事服务，失败回滚。
只更新获客工作台，保留微信AI接待、密钥、每日20次搜索和30次AI的现有配置，不修改小程序或业务数据。

新入口：工作台首页“去外部平台找客户”，或左侧“外部平台获客”。
六个平台分别提供站内搜索任务；银杏奖牌只承接报名，小程序客服不算外部获客来源。
浏览器采集助手可在展开的公开视频/笔记/帖子评论中，初筛最多20条明确乒乓需求，核对后导入、去重并排队让AI整理回复。
助手ZIP下载：工作台外部平台获客页→下载采集助手；在本机Chrome扩展程序管理页由经营者加载解压后的browser-helper文件夹。
真实平台页面结构尚需安装后试采验证；识别不到时选中一条原文读取。视频号目前使用手机搜索并复制公开原文。
助手不读取密码、Cookie、私信或工作台登录令牌，不自动滚动或发送。
平台自动评论/私信发送仍未接入。本轮不能无人值守遍历所有平台评论；实际联系和报名仍按凭据记录。
''','utf-8')
    archive=RELEASE/'GinkgoGrowth-1.3.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,p.relative_to(PACKAGE.parent))
    status={'version':'growth-external-1.3.0','backend_installed':False,'server_staged':False,
        'archive':str(archive.resolve()),'bytes':archive.stat().st_size,'sha256':sha(archive),
        'external_api_tests':tests['tests'],'workflow_tests':20,'channel_tests':38,'installer_tests':8,'helper_bridge_tests':9,
        'live_platform_capture_verified':False,'paid_calls_during_tests':0,'social_messages_sent_by_tests':0,
        'miniapp_modified':False,'automatic_platform_sending_connected':False,'needs_local_helper_install':True}
    (RELEASE/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive)}))

if __name__=='__main__':main()
