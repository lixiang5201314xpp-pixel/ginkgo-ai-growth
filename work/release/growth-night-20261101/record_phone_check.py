import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

base = Path(__file__).resolve().parent
checked = datetime.now(timezone(timedelta(hours=8))).isoformat()
status = json.loads((base / 'status.json').read_text(encoding='utf-8-sig'))
status['platform_blockers']['xiaohongshu'] = '手机端本人核对没有看到价格回复；原因未明，未登记为已联系，也未重复发送。'
status['platform_blockers']['kuaishou'] = ''
status['kuaishou_content_login_verified'] = True
status['kuaishou_search_verified'] = True
status['kuaishou_public_comments_readable'] = True
status['kuaishou_new_qualified_leads_this_check'] = 0
status['last_operations_check_at'] = checked
(base / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

ledger = json.loads((base / 'contact-ledger.json').read_text(encoding='utf-8-sig'))
for item in ledger.get('unconfirmed_attempts', []):
    if item['platform'] == 'xiaohongshu':
        item['phone_check_result'] = '用户本人确认：没有看到这条回复。'
        item['phone_check_recorded_at'] = checked
        item['followup'] = '浏览器只点击发送一次，手机端本人确认未看到该回复。发布原因未明，不登记为已联系，不重复发送。'
(base / 'contact-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

report = base / '本轮工作记录.md'
report.write_text(report.read_text(encoding='utf-8') + '''

## 手机端核对与快手登录后检查

- 用户本人已确认小红书手机端“没有看到这条回复”。生产工作台仍为“可回应”，草稿明确标为“未发送”；没有登记联系，也没有重发。具体失败原因没有证据，不归因为隐私设置、账号处罚或平台审核。
- 快手普通内容账号“银杏乒乓”登录成功；站内搜索“成都 乒乓球 找教练”已可用。打开黄晨乒乓球的《来成都踢馆美女乒乓球教练》原作品，作品标为7个月前，评论区总数212。本轮实际展开的评论主要为视频讨论，没有确认出当前成都训练或报名需求，没有新增客户，也没有向这些评论发广告。
- 此轮没有重新调用AI、没有重新安装服务、没有修改自动发送权限。总数保持确认需求2条、登记联系1条、确认报名0条。
- 凭据：morning/xhs-followup-unsent.png。快手搜索和原作品评论页已保留，后续可以继续正常站内查找。
''', encoding='utf-8')
print('Saved: XHS phone check not visible; Kuaishou login/search/comments verified; counts unchanged 2/1/0.')
