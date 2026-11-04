"""Package only code and public UI. No keys, local tokens or customer data."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from install_growth_ai import FILES
BASE=Path(__file__).resolve().parent
RELEASE=BASE.parent/'release/growth-ai-20261030'
PACKAGE=RELEASE/'GinkgoGrowth-1.1.0'
OLD=BASE.parent/'release/growth-20261030/GinkgoGrowth-1.0.0/payload/manifest.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for filename in ['verification.json','ai-verification.json']:
        data=json.loads((BASE/filename).read_text('utf-8'));assert data['passed']
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    manifest={'version':'ginkgo-growth-1.1.0','baseline_files':{x['path']:x['sha256'] for x in json.loads(OLD.read_text('utf-8'))['files']},'files':[]}
    for name in sorted(FILES):
        dest=payload/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,dest)
        manifest['files'].append({'path':name,'sha256':digest(dest)})
    (payload/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    for name in ['install_growth_ai.py','activate_growth_ai.py','growth_permissions.py','Install-AI-Growth.cmd','configure_ai.py','Configure-AI.cmd']:
        shutil.copy2(BASE/name,PACKAGE/name)
    note='''银杏 AI 获客工作台 1.1.0

运行 Install-AI-Growth.cmd：仅升级获客模块，先预检和备份，失败回滚。
保留账号、客户数据、加密 DeepSeek 密钥，赛事主模块不替换。
安装会在停止服务之前，用三个模拟问题验证儿童费用、成人自动发课和后台需求分析，受已确认的每日次数上限约束；全部通过才重启。
成功后开启定时自动任务（默认120分钟），后台保留约三分之一文本额度供即时咨询。

入口：https://qiuchen.yinxingpingpang.com/api/match-center/growth/
继续使用银杏奖牌已有管理员登录。
主页三步可点击，也有 AI 自动执行、AI 设置、四平台内容草稿。
公开咨询页新增 AI 连续问答，各平台分别引导同平台银杏奖牌小程序。
儿童训练三项价格及成人前三名小程序自动发课已写入 growth_playbook.json。
未配置课程的次数、期限、未知场次收费不猜测。投资方案不进入招生机器人。

搜索仅覆盖公开网页索引，不保证平台站内评论可被搜索。
平台评论/私信收发、视频发布没有官方接口连接；草稿和待发送不会标记已发布或已联系。
要回复平台站内消息，还需要该经营账号对应的官方消息权限/回调。
不把普通平台登录态当成接口权限，不提取 Cookie。

密钥配置可运行 Configure-AI.cmd；明文输入窗口由经营者要求启用，勿截图分享。
服务器用 DPAPI 加密保存，专用目录仅管理员、System和运行服务账户可用。
每日次数是本软件请求限额，并非服务商金额硬限额，可在 AI 设置中调整或关闭。
'''
    (PACKAGE/'使用说明.txt').write_text(note,'utf-8')
    archive=RELEASE/'GinkgoGrowth-1.1.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(PACKAGE.parent))
    status={'version':'ginkgo-growth-1.1.0','backend_installed':False,'archive':str(archive),'sha256':digest(archive),
            'bytes':archive.stat().st_size,'platform_messages_sent':0,'paid_calls_during_local_tests':0,'miniapp_modified':False}
    (RELEASE/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
