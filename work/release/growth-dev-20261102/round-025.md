# 36.17.0安装核对与开发版上传

当前状态：miniapp-update1.4.0 / installer1.0.5正式后台已安装核对，配套36.17.0开发版已官方CLI上传，真实后台体验二维码wechat-preview-live.png已生成并目视检查。未提审、未发布。开发及部署交付完成，手机体验与平台审核仍待完成。

## 实际安装证据

用户安装SUCCESS，备份C:\Services\GinkgoTrainingAutoCancel\GinkgoMiniapp-36.17.0\backups\miniapp-20261103-235504，服务KaiqiuMatchCenter RUNNING。已从该包目录拉取真实miniapp-install-result.json及schema-result.json。11更新文件hash与已通过3606项验收的冻结候选完全一致；10保留文件hash与既有版本一致；11条既有结构声明幂等提交，回执business_data_modified=false，platform_messages_sent=0。

线上score-entry1.0.0明确返回games_default、points_optional、all_formats；four-team1.2.0、batch1.2.0、settings1.0.0、team-rating1.0.0、机构1.1.0、客服channels1.0.1及external1.4.1共8模块逐个核对。9既有字段、个人盘级积分唯一索引、队伍(entry_id,seat)唯一索引及账本锁通过只读核对。6个未登录换人/赛程修改接口返回401；匿名不能看到完整电话或获得换人权限。

本场公开名单仍完整表示128名参赛者。未进行真实换人、录分、重置、报名、客服发送或AI调用。测试数据仍只来自上一轮私有SQL回滚；本次部署核对没有冒充真实微信授权/支付或比赛结果。

## 已上传功能

全部赛制默认直接记录局分，如三局两胜2:0、2:1；逐局小分输入默认不渲染、不占版面，点击展开后才显示。支持单打、双打、双人团体单单双、三人团体单单双和四人团体单双单。默认显示本场局制，原有其它局制比分另有明确入口。后台兼容旧“记录小分”项目直接交局分；不伪造小分，改记局分会清除冲突的旧小分。更正权限、单打个人当前积分、双打不计分和年度独立规则保留。

首页增加12秒超时退出及重新加载保护，旧请求不能覆盖新结果。上一轮已在原生模拟器验证超时显示重试、恢复真实HTTPS后显示20场比赛。36.16.1匿名首页原本可正常加载，未确认审核截图的原始原因，不能承诺因此必然过审。原生QA跳过无关旧奖牌自动登录写入，真实微信手机号授权和支付仍待真实流程验收。

357份源文件在上传前、上传后及预览后hash一致。上传主包1362038、总1676077字节；预览主包1346042、总1660081字节，两份官方info回执分别保留。源码快照WeChat-36.17.0-source.zip。所有QA故障注入、临时会话和本机接口均位于测试工程，未进入上传源码。

上一轮3606项记录继续保留，未计作本轮新执行：1905后台回归、968本场四人128人64场及换人、486双打/双人/三人两种录分配置完整SQL/HTTP流程、113前端回归、64计分模式前端、6首页超时重试、48离线、8回滚、6原生实际录分、2原生首页恢复；65页/5组件/124JS编译通过。原开发报告另存README-开发验收.md。

## 手机体验和提审

使用本目录新wechat-preview-live.png扫码体验36.17.0。确认默认局分、展开/收起小分、保存返回成绩与积分、首页首次打开/重试。真机键盘和长名单输入稳定性仍需手机体验。尚未替用户提交审核或发布，无需重复安装后台或上传旧36.16.1。

外部获客Agent按用户指示继续PAUSED，active_run和next_run_at清空。证据见server-install-result.json、server-schema-result.json、deployed-acceptance.json、live-public-acceptance.json、frontend-upload.json、deployment.json及acceptance.json。
