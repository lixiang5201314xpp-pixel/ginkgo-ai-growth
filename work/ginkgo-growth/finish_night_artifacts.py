"""Save a factual handoff and update only the already-installed local helper files."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import shutil

BASE=Path(__file__).resolve().parent
OUT=BASE.parent/'release/growth-night-20261101'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=json.loads((BASE/'external-patch-package-verification.json').read_text('utf-8'))
    assert checks['passed']
    desktop=Path(r'C:\Users\Administrator\Desktop\银杏外部平台获客助手-1.3.0')
    updated=False
    if (desktop/'manifest.json').is_file():
        old=json.loads((desktop/'manifest.json').read_text('utf-8-sig'))
        new=json.loads((BASE/'browser-helper/manifest.json').read_text('utf-8'))
        for k in ('permissions','host_permissions'):assert old[k]==new[k],k
        backup=OUT/'local-helper-backup';backup.mkdir(exist_ok=True)
        for p in (BASE/'browser-helper').iterdir():
            if not p.is_file():continue
            dest=desktop/p.name
            if dest.is_file() and not (backup/p.name).exists():shutil.copy2(dest,backup/p.name)
            shutil.copy2(p,dest);assert sha(p)==sha(dest)
        updated=True
    record={'platform':'douyin','source_url':'https://www.douyin.com/video/7701372394577607067',
        'public_author':'🌈Cuiyang888🌈','published_at':'2026-10-27T23:38:00+08:00','source_kind':'post',
        'need':'川大江安附近找有水平的球搭子，约表演赛',
        'reply':'你好，我们是银杏乒乓球俱乐部。看到你在江安附近找球搭子，我们在青羊区，距离会远一些。你也考虑周末参加分组比赛吗？可以先在抖音「银杏奖牌」小程序看看时间和分组，合适再报名。',
        'sent_by':'银杏乒乓球俱乐部','delivery':'public_comment','published_ui_verified':True,
        'proof_file':'douyin-reply-published.png','backend_imported':False,'registration_verified':False,
        'followup':'等待对方自愿回复；未回复不重复催促。现有工作台用户标签页无法接管，未导入生产数据。'}
    (OUT/'contact-ledger.json').write_text(json.dumps({'verified_contacts':[record],'verified_registrations':0},ensure_ascii=False,indent=2),'utf-8')
    status={'version':'growth-external-1.3.1','prepared_at':datetime.now(timezone.utc).isoformat(),
        'backend_installed':False,'server_staged':False,'owner_install_pending':True,
        'local_helper_files_updated':updated,'local_extension_reload_pending':updated,
        'production_leads_imported':0,'public_comments_published':1,'registrations_verified':0,
        'api_tests':29,'workflow_tests':20,'base_acquisition_tests':48,'helper_permission_bridge_tests':9,'capture_browser_tests':10,
        'batch_parser_tests':8,'final_package_layout_checks':194,'installer_rollback_checks':8,
        'batch_ui_flow':{'invalid_json_blocked':True,'source_review_required':True,'import_succeeded_in_isolated_local_store':True,'duplicate_not_added':True},
        'live_ai_calls_during_this_run':0,'wechat_ai_configuration_modified':False,
        'platform_blockers':{'xiaohongshu':'搜索要求重新扫码登录','kuaishou':'站内搜索连接超时','channels':'暂无可用站内公开搜索接口；没有读取私信'},
        'workbench_blocker':'原已登录的用户标签页返回 browser.user unavailable；新标签页需正常登录，未提取或迁移认证信息。',
        'automatic_platform_sending_connected':False}
    stage=OUT/'staged-verification.json'
    if stage.is_file():
        staged=json.loads(stage.read_text('utf-8'))
        if staged.get('staged') and staged.get('archive_sha256')==sha(OUT/'GinkgoGrowth-1.3.1.zip'):
            status.update(server_staged=True,staged_payload_files=staged['payload_files_verified'],existing_service_health=staged['health'])
    (OUT/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf-8')
    (OUT/'本轮工作记录.md').write_text('''# 银杏外部平台获客工作记录

已在内置浏览器核对一条近期公开约球作品，并用“银杏乒乓球俱乐部”抖音账号发送1条针对性回复。作品发布时间2026-10-27 23:38，来源及回复截图保存在本文件夹。未核实到报名，不把联系数当作客户成交数。

已修正抖音搜索弹窗URL、当前作品范围、两种评论布局、嵌套回复、带省份时间标签等漏收问题；补上“有没有厉害的球搭子”问句的需求判定。新增作品正文求助读取、采集批次粘贴。完整安装包 GinkgoGrowth-1.3.1.zip 只更新四份获客文件。

验证：29项接口、20项工作流、48项基础获客、9项助手权限/桥接、10项浏览器采集、8项批次解析、194项冻结包两种目录布局、8项安装/回滚检查通过。模拟工作台已验证无效JSON拦截、核对确认、导入和重复去重，未调用真实AI或写生产客户数据。

## 尚未完成的步骤

- 云端1.3.1尚未安装：运行目录权限仍限制当前文件通道，未绕过权限、未重启服务。安装包放在服务器 C:\\Services\\GinkgoTrainingAutoCancel\\GinkgoGrowth-1.3.1，暂存文件已核对。computer-use 技能的 guidance.md 明确禁止通过UI直接或间接运行Windows终端命令，所以不能代点CMD安装器。原获客、外部原文入口和客服接口健康检查均返回200。
- 本机已有助手文件更新到1.3.1（文件夹名仍为1.3.0），扩展需在原扩展卡片点击刷新才能加载新代码；无新增权限。
- 工作台原已登录标签页当前无法被控制，新标签页要求登录。因此这条真实求助与已发回复仅保存在本地证据和跟进记录，没有伪称已经导入生产工作台。
- 小红书搜索要求扫码重登；快手搜索超时；视频号暂无可用站内公开检索通道。没有绕过登录、验证码或平台限制。
- 外部平台自动评论/私信仍未接入。微信小程序AI接待和既有后台任务保持原配置。

## 明早接续顺序

1. 在服务器管理员远程会话运行 GinkgoGrowth-1.3.1 中的 Install-Growth-External.cmd，确认1.3.1和SUCCESS。
2. 刷新本机原“银杏外部平台获客助手”扩展，不需要重新授权。
3. 正常登录可操作的获客工作台；核对 douyin-public-demand.json 和 contact-ledger.json，导入后登记已发布的回复，防止重复联系。该作品只明示川大江安，成都证据如需补充应以真实原文或核实上下文为准，不能把搜索词/IP当证据。
4. 等待此用户回复再继续，不重复催促；完成小红书正常登录后继续站内找明确需求。
''','utf-8')
    print(json.dumps({'local_helper_updated':updated,'backend_installed':False,'contacts':1,'bookings':0}))
if __name__=='__main__':main()
