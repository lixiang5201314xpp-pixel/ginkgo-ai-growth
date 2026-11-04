from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

root = Path(__file__).resolve().parents[2]
release = root / 'work/release/growth-dev-20261102'
state_path = release / 'status.json'
state = json.loads(state_path.read_text('utf-8-sig'))
assert state['active_run']['id'] == 'round-004-c33c71ad', 'Another round owns the state'
now = datetime.now(timezone.utc)
state.update(status='待继续', active_run=None,
             last_completed_at=now.isoformat(),
             next_run_at=(now + timedelta(minutes=8)).isoformat(),
             completed_development_rounds=4, checks_passed_this_round=56,
             last_report='work/release/growth-dev-20261102/round-004.md',
             blocking_conditions=[
                 '助手1.4.6桌面文件已更新，Chrome正常刷新与真实完整轮次待核对',
                 '后台1.4.2已暂存，需管理员安装；正式仍1.4.1',
                 '小红书原帖显示电脑设备登录超限，需本人恢复内容账号登录',
                 '快手搜索弹层缺少已核对原帖链接且有相邻连播，需补唯一身份与评论范围适配',
                 '外部平台自动发送与视频号采集未接通'
             ])
acceptance_path = release / 'acceptance.json'
acceptance = json.loads(acceptance_path.read_text('utf-8-sig'))
acceptance.update(status='未完成', completed=False, last_report=state['last_report'])
for item in acceptance['items']:
    if item['id'] == 'collector_recovery':
        item.update(status='1.4.6加载/近期排序修复及56项相关检查通过；浏览器刷新与真实完整轮次待验收', evidence='work/release/growth-dev-20261102/helper-package-1.4.6.json')
    elif item['id'] == 'external_platform_matrix':
        item.update(status='抖音最新排序和快手搜索已实测；小红书登录超限，快手原帖身份/评论范围待修复，视频号未验收', evidence=state['last_report'])
    elif item['id'] == 'deployment_and_recovery':
        item['status']='正式1.4.1与微信渠道1.0.0健康；1.4.2暂存未安装，内含助手1.4.5；本机助手文件1.4.6待Chrome刷新'
for path, value in ((acceptance_path, acceptance), (state_path, state)):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
handoff_path = root / 'work/growth-agent/DEVELOPMENT.md'
handoff = handoff_path.read_text('utf-8').replace('桌面助手源文件已更新1.4.5', '桌面助手源文件已更新1.4.6')
handoff += '\n最新实际发现（第四轮）：内置浏览器单步调用需60秒超时，筛选按钮可用。抖音最新排序不编码在URL，1.4.6已通过公开控件恢复排序并测试。小红书成人训练原帖提示电脑设备登录超限，停止登录尝试；快手卡片无href、弹层URL不含作品ID且连播预加载相邻面板，需补唯一原帖身份和评论范围，不能宣称适配通过。详见round-004.md。服务器1.4.2冻结包仍含助手1.4.5；本机最新1.4.6刷新待确认，后续下载资源需单独对齐。\n'
handoff_path.write_text(handoff, encoding='utf-8')
print(json.dumps({'status': state['status'], 'active_run': None, 'next_run_at': state['next_run_at'], 'completed': False}, ensure_ascii=False))
