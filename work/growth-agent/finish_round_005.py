from pathlib import Path
from datetime import datetime,timezone,timedelta
import json

root=Path(__file__).resolve().parents[2]
release=root/'work/release/growth-dev-20261102'
state_path=release/'status.json'
state=json.loads(state_path.read_text('utf-8-sig'))
assert state['active_run']['id']=='round-005-kuaishou-scope'
now=datetime.now(timezone.utc)
state.update(status='待继续',active_run=None,last_completed_at=now.isoformat(),
             next_run_at=(now+timedelta(minutes=8)).isoformat(),completed_development_rounds=5,
             checks_passed_this_round=70,last_report='work/release/growth-dev-20261102/round-005.md')
state['blocking_conditions'][0]='助手1.4.7桌面文件已更新，Chrome刷新与真实完整轮次待核对'
state['blocking_conditions'][3]='快手已加原帖/评论范围保护，但当前无可核对作品链接的搜索布局和连播采集仍未验收'
acceptance_path=release/'acceptance.json'
acceptance=json.loads(acceptance_path.read_text('utf-8-sig'))
acceptance.update(status='未完成',completed=False,last_report=state['last_report'])
for item in acceptance['items']:
    if item['id']=='collector_recovery':
        item.update(status='1.4.7含加载/近期排序恢复与快手范围保护，70项检查通过；浏览器刷新及真实完整轮次待验收',evidence='work/release/growth-dev-20261102/helper-package-1.4.7.json')
    elif item['id']=='external_platform_matrix':
        item.update(status='快手无唯一原帖时停止读取的保护通过，真实采集/发布仍未验收；小红书本人登录待恢复',evidence=state['last_report'])
    elif item['id']=='deployment_and_recovery':
        item['status']='正式1.4.1未改；1.4.2暂存包仍含助手1.4.5；本机助手1.4.7待刷新，下载包需后续对齐'
for path,value in ((acceptance_path,acceptance),(state_path,state)):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
handoff_path=root/'work/growth-agent/DEVELOPMENT.md'
handoff=handoff_path.read_text('utf-8').replace('桌面助手源文件已更新1.4.6','桌面助手源文件已更新1.4.7')
handoff+='\n第五轮：助手1.4.7已加快手唯一面板/公开链接身份与选中原文范围保护，通过70项相关检查，但真实快手自动采集未通过。正常新建IAB本机测试页可用，新建快手搜索页也可用；旧页面有browser.user失效，复杂外站组合操作仍超时。不要笼统宣称全部断开或重复重连。详见round-005.md。下一轮可独立审查求职语句误判，并准备合并最新助手的新冻结后台发布包。\n'
handoff_path.write_text(handoff,encoding='utf-8')
print(json.dumps({'active_run':None,'next_run_at':state['next_run_at'],'completed':False}))
