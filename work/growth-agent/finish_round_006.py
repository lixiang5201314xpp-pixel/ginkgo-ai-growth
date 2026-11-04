from pathlib import Path
from datetime import datetime,timezone,timedelta
import json

root=Path(__file__).resolve().parents[2]
release=root/'work/release/growth-dev-20261102'
proof=json.loads((release/'backend-1.4.3-verification.json').read_text('utf-8'))
package=json.loads((release/'backend-package-1.4.3.json').read_text('utf-8'))
assert proof['passed'] and package['staged_on_server'] and not package['installer_executed']
state_path=release/'status.json'
state=json.loads(state_path.read_text('utf-8-sig'))
assert state['active_run']['id']=='round-006-role-filter-release'
now=datetime.now(timezone.utc)
state.update(status='待继续',active_run=None,last_completed_at=now.isoformat(),
             next_run_at=(now+timedelta(minutes=8)).isoformat(),completed_development_rounds=6,
             checks_passed_this_round=proof['total_test_executions'],
             last_report='work/release/growth-dev-20261102/round-006.md')
state['blocking_conditions'][1]='合并后台1.4.3已暂存并校验，待管理员安装；无需先装旧1.4.2，正式仍1.4.1'
acceptance_path=release/'acceptance.json'
acceptance=json.loads(acceptance_path.read_text('utf-8-sig'))
acceptance.update(status='未完成',completed=False,last_report=state['last_report'])
for item in acceptance['items']:
    if item['id']=='intake_dedup':
        item.update(status='合并包1.4.3含回执恢复和求职排除，四种基线/布局验证通过；正式安装待完成',evidence='work/release/growth-dev-20261102/backend-1.4.3-verification.json')
    elif item['id']=='ai_playbook':
        item.update(status='求职角色排除及13项正反例通过；AI额度/拒绝联系等隔离回归通过，完整真实联调仍待完成',evidence=state['last_report'])
    elif item['id']=='deployment_and_recovery':
        item['status']='合并后台1.4.3（含助手1.4.7）已在服务器暂存并校验，未安装；正式1.4.1与微信渠道1.0.0健康，Chrome待刷新'
for path,value in ((acceptance_path,acceptance),(state_path,state)):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
handoff_path=root/'work/growth-agent/DEVELOPMENT.md'
lines=handoff_path.read_text('utf-8').splitlines()
for i,line in enumerate(lines):
    if line.startswith('现状：'):
        lines[i]='现状：正式growth-external-1.4.1及微信渠道1.0.0健康；桌面助手文件1.4.7待Chrome刷新。合并后台1.4.3（角色误判排除、精确回执恢复、助手下载1.4.7）已通过1037次基线/布局及回滚检查，并在服务器C:/Services/GinkgoTrainingAutoCancel/GinkgoGrowth-1.4.3暂存/逐文件校验；未安装。旧1.4.2无需先装。实际部署和真实完整采集/发布/报名仍未验收。保留微信AI客服及用户暂缓其它三平台小程序客服的决定。'
lines += ['', '第六轮：已修复求职/招生角色误当训练客户的问题，13项正反例和自动入库不调用AI回归通过。合并1.4.3包含最新助手1.4.7，支持从1.4.1或1.4.2直接升级；先预检、备份、失败还原并核对实际下载ZIP。已暂存，未运行安装器。详见round-006.md；以本段及上方现状为准，前面历史轮次的旧安装包建议已被替代。下一步应在用户恢复登录/安装/扩展刷新后核对真实联调；不要重复已知失效连接或把隔离检查算真实获客。']
handoff_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'active_run':None,'next_run_at':state['next_run_at'],'completed':False,'staged':'1.4.3','live':'1.4.1'}))
