# 第一轮开发与验收交接

2026年11月2日。用户已明确今晚自行跑全部流程，并再次登录Chrome和内置浏览器工作台；本轮不向用户提问。

## Agent

已通过Codex automation_update实际创建，id=agent，名称“银杏外部获客开发验收 Agent”，heartbeat，ACTIVE，每8分钟唤醒本聊天。旧id在app中已不存在，更新报不存在后才创建，因此没有重复任务。配置见C:/Users/Administrator/.codex/automations/agent/automation.toml（以实际目录为准）。本轮结束后状态门禁next_run_at设为结束后8分钟；未到时间不开始新一轮。

## 已核对的正式情况

- 内置浏览器工作台已登录，自动入库与AI准备已开启，UI显示5条需求、1条已登记联系、0条有凭据报名。
- 采集回执最近12批都显示有效新增0、排除旧原文1、发送0。不能将这些批次算新客户。
- 正式/growth/external/health为growth-external-1.4.1、status=ok；/growth/channels/health为growth-channels-1.0.0、status=ok。
- 工作台明确显示：四平台外部自动评论/私信尚未接通，视频号浏览器采集未适配。不是部署完成了整个获客目标。
- 用户暂不做其余三平台的小程序客服接入，这与外部平台获客不是同一个功能。

## 本轮修复

源目录work/ginkgo-growth-autocollect/browser-helper，原1.4.3已完整复制到helper-before-1.4.4，桌面原目录为C:/Users/Administrator/Desktop/银杏外部平台获客助手-1.3.0（目录名未改）。

已生成1.4.4，解决两种可复现行为：
1. 页面已有可核对的搜索结果或唯一原帖内容时，不再等待视频等无关资源全部加载完成。
2. 已确认详情目标连续3次未就绪后，记录失败并处理队列内其余目标。部分失败轮次单独计数，不算“完整空线索轮”；连续3轮有加载故障且无有效新增时单独暂停。

保留登录/验证码/外域/不确定点击即暂停、批次发送幂等、8分钟冷却、3个真实空轮暂停。网页传输失败且有pending_batch时不跳过，不丢弃可能已入库但未确认的批次。权限、主机范围均未增加。

先加用例在1.4.3复现失败，再修复：调度22项、只读状态桥6项、采集与继承API隔离74项，共102项通过；5个JS文件通过node --check。无真实AI请求、无客户消息。桌面源文件已逐文件核对一致，ZIP在本目录和桌面。报告helper-package.json、continuous-verification.json、status-bridge-verification.json。

重要：只是桌面源文件更新，浏览器是否已加载1.4.4尚未验证，extension_reload_pending=true；未宣称实机轮次已通过。既有服务端下载包仍为旧版本，本轮没有改正式后端文件。不要重跑旧package_collection_patch.py覆盖旧1.4.1快照；它固定要求helper1.4.3。

## 浏览器连接恢复注意

本轮最初cua.getTab/getAXState多次30秒超时。改用已有文档支持的agent.browsers API后能够读取登录工作台和Chrome抖音搜索。

legacy cua.getState输出的数字浏览器ID与agent.browsers.list的ID不是同一映射！本轮legacy显示Chrome3/Edge4，而agent.browsers.list实际为Chrome4/Edge3。未来必须从当前使用API的list返回结果按name/profile/extensionInstanceId选浏览器，不要照抄数字ID。Chrome profile为“您的 Chrome”，extensionInstanceId=e26da803-bb18-4afb-8c28-1448af3d13cc。

成功路径：通过cua_repl执行agent.browsers.list，取真实Chrome，读其documentation，立即nameSession，再chrome.user.openTabs/claimTab。IAB成功使用browser.tabs.get('14').playwright.domSnapshot，句柄仅当仍有效时复用。

已读computer-use、OpenAI Docs技能；也已读browser-troubleshooting。不要使用终端CDP、浏览器配置文件、Cookie或原始私有状态绕开控制。此前回合扩展管理页曾被浏览器策略阻止；本轮没有重新尝试刷新扩展。下一轮可在当前工具允许范围内检查已有扩展页是否可操作；若策略明确禁止，不能换通道绕过，记录一次所需本人刷新动作。

Chrome已观察的用户标签：工作台401229998、抖音搜索401230074、小红书401230083、快手401230080、扩展页401230071。ID必须重新列出确认后再用。

抖音搜索“成都 乒乓球 找教练”可读取，登录UI可见消息数量但未打开私信。默认综合结果主要为2021年、2025年和2026年8月旧教学视频，不能当近期需求。本轮最后尝试点击可见“筛选”后，调用超时、REPL重置；筛选是否展开未知，不能盲目重复点击。下一轮先读新DOM再决定。未发送任何评论。

## 下一轮优先级

1. 恢复浏览器句柄后读取当前状态，尝试在允许范围完成既有助手的正常刷新并核对1.4.4；若暂不能加载，继续独立开发，不反复向睡觉用户提问。
2. 从可见搜索筛选UI选择近期发布，避免每轮重复打开同一批多年旧视频；按真实DOM完善采集适配，不依赖隐藏React状态。
3. 跑一轮真实可用公开内容采集，核对工作台回执、有效/待核实/旧内容排除与冷却。记录实际版本，不能把单元测试当实机通过。
4. 对外部平台实际发送和回执链路做明确设计与实现；先核对各平台当前官方能力。小程序客服token不能冒充普通内容账号评论/私信权限。针对用户明确授权的近期成都需求可做普通业务回应，但不群发、不重复发送，缺少发布确认就记uncertain。
5. 继续各平台小程序引导和报名/结果记录全链路验收，保留微信AI接待。

状态未完成。不能把平台授权未取得、验证码未完成、安装未应用、未核实的发布或报名当通过。
