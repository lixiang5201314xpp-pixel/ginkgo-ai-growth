import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

base = Path(__file__).resolve().parent
now = datetime.now(timezone(timedelta(hours=8))).isoformat()
status = json.loads((base / 'status.json').read_text(encoding='utf-8-sig'))
status.update(production_leads_imported=2, production_contacts_recorded=1,
              ai_prepared_replies_live_verified=2, live_ai_calls_during_this_run=2,
              public_comments_published=1, public_comment_attempts_unconfirmed=1,
              registrations_verified=0, live_verified_at=now)
status['platform_blockers']['kuaishou'] = '主页和站内搜索可访问；内容账号未登录，已打开扫码登录页，等待本人扫码。'
(base / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

ledger = json.loads((base / 'contact-ledger.json').read_text(encoding='utf-8-sig'))
ledger['verified_contacts'][0]['followup'] = '真实需求已导入生产工作台，实际回复已登记；页面已禁止重复联系，等待对方自愿回复。'
source = json.loads((base / 'morning/xhs-public-demand.json').read_text(encoding='utf-8-sig'))['items'][0]
ledger['unconfirmed_attempts'] = [{
    'platform': 'xiaohongshu', 'source_url': source['source_url'],
    'source_title': source['excerpt'], 'original_date_label': source['posted_text'],
    'sent_by': '银杏乒乓', 'delivery': 'public_comment',
    'reply': '我们是成都青羊区的银杏乒乓球俱乐部。儿童课有2400元25次的方案，每次90分钟，来一次核销一次，折合96元/次；也有月卡和年卡可选。建议先看上课时段是否方便，再选方案。具体课表、名额和报名可在本平台“银杏奖牌”小程序的“训练”里查看。',
    'send_attempted': True, 'published_ui_verified': False,
    'backend_imported': True, 'ai_prepared': True,
    'backend_contact_recorded': False, 'registration_verified': False,
    'followup': '只点击发送一次，重新打开后仍为5条评论且未见本账号回复；不重发，等待手机核实。'
}]
(base / 'contact-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

(base / '本轮工作记录.md').write_text('''# 银杏外部平台获客工作记录

## 2026-11-01 已核实的运行状态

服务器已成功安装 growth-external-1.3.1，真实健康检查返回相同版本；管理员接口匿名访问返回401。用户已刷新本机扩展到1.3.1，且已登录获客工作台、小红书普通内容账号。无需再安装或重新填写密钥。

生产工作台已经导入2条真实需求，并完成2次真实AI分析与回复准备。已登记联系1条，已核实报名0条。微信AI接待保持运行，既有每120分钟后台任务、每日20次网页搜索和30次AI额度没有更改。外部平台自动评论和私信接口尚未连接，不能把草稿准备视为已联系。

## 已完成的实际跟进

1. 抖音作品 https://www.douyin.com/video/7701372394577607067 ：川大江安附近找球搭子。原文发布时间2026-10-27 23:38。四川大学官方交通页确认江安校区位于成都市双流区。用“银杏乒乓球俱乐部”账号发布的1条针对性回复已再次在页面核实可见，真实发送内容和原帖链接已登记到生产工作台。详情已显示“已经联系过，等待对方回复；不重复催促”。目前未见对方回复，不重复联系。
2. 小红书原帖《成都小孩乒乓球培训，大概需要多少费用》已导入并完成AI准备。只保留价格求助标题，没有将儿童年龄、性别或照片送入AI。原帖显示“10-16 四川”，所存2026-10-16是按当前年份补全的日期，不表示已知具体时分。用“银杏乒乓”账号点击发送1次训练价格回复，但浏览器没有成功提示，重新打开仍未看到本账号回复；记为“发布待核实”，没有登记成已联系，也未重发。

## 当前需要接续的事项

- 快手主页及“成都 乒乓球 找教练”搜索页已可访问；普通内容账号未登录，已打开扫码页并向用户请求本人扫码。开发后台的登录不替代内容账号登录。
- 小红书回复是否最终发布，等待手机端核对。无确认不重发、不增加联系数。
- 视频号暂无可用的站内公开检索入口；没有把小程序客服消息当成视频号外部获客。

## 凭据

- morning/workbench-live-counts.png：实际工作台2条确认需求、1条联系、0条报名。
- morning/contact-recorded.png 与 contact-recorded.txt：抖音实际联系登记和防重复提示。
- douyin-reply-published.png：已发布抖音回复。
- morning/xhs-source.png：小红书原帖及当时5条评论，不是回复发布成功凭据。
- morning/xhs-import-result.txt：小红书AI任务完成。
- contact-ledger.json：已核实联系与未确认发送分开记录。

此前代码验证包括29项接口、20项工作流、48项基础获客、9项助手权限/桥接、10项浏览器采集、8项批次解析、194项冻结包布局、8项安装/回滚检查。测试阶段使用隔离数据；上述2条生产需求属于安装后的实际运营核对。
''', encoding='utf-8')
print(json.dumps({'leads': 2, 'recorded_contacts': 1, 'verified_registrations': 0,
                  'unconfirmed_send_attempts': 1, 'updated_at': now}))
