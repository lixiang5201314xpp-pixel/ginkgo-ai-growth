# 第十一轮：优先用户新提出的小程序客服与计分需求

已完成并冻结客服修正版ginkgo-support-1.1.0：只有growth_ai.py、growth_channels.py、growth_playbook.json三个文件。
- 删除知识库和inbound提示词中的旧训练钟点；日期和时段统一指向训练标签页课程安排表。
- AI_PROTOCOL和知识版本更新，旧缓存键失效；模型输出/缓存读取/已准备但未发送队列均校验训练钟点。未经当前赛事资料明确支撑的钟点改成课表引导。
- 回复改为【银杏客服】，包括旧prepared队列的【AI接待】前缀；如问是否人工，知识要求如实说明智能客服。
- 补充共用账号、手机号授权、整队报名、同名候选、比赛创建/修改、排阵、积分、约课、报备、奖牌、摄影及故障反馈知识。
- 保留1900/2400/8900和90分钟课程时长；不修改价格、现有设置、限额或密钥。

验证：overlay和installed两个冻结安装布局各87项，安装/幂等/失败回滚8项，合计182项通过。没有真实AI调用、客户发送或业务数据修改。
包已上传服务器C:/Services/GinkgoTrainingAutoCancel/GinkgoSupport-1.1.0，stage-support-1.1.0.ps1完成逐文件校验。未运行安装器，已只请求一次管理员运行Install-Support.cmd；无需先装获客1.4.5。本包保留获客模块、身份修正和所有业务文件。

前端：当前work/source/银杏乒乓_完整可运行_0824新增公共online-support组件，app.json全局注册；64个注册页面均插入普通文档流咨询条，去掉我的页重复咨询卡。没有悬浮覆盖游戏/录分按钮。64页/5组件WXML/WXSS及121个JS官方编译通过，官方preview打包成功，主包1272787字节，总包1586606字节，未上传或提审。
运行时实测尚未通过：旧automator9480未见新组件；用官方cli auto启用9494后出现getPageMetaByWebviewId rawPath=null，属于未完成验收，不标通过。运行超时的本轮测试Node PID9968已按精确命令行核对后结束，不动其他进程。源码变更备份在本轮frontend-before-support。下一轮须先解决编译/模拟器加载实例，真实看到原生contact入口再完成前端交付。

团体单打个人当前积分新要求尚未实施或部署，优先级高于继续获客优化，不再沿用旧的团体全部不计分规则。已查最新match_center基线为work/release/four-team-20261101/payload/match_center.py；现有score_tie_game只汇总团体比分，无个人结算。MC_RatingLog.match_id有FK指向MC_Matches，因此不能直接把MC_TieGames.id塞进现有日志。需要设计可区分每盘的nullable tie_game_id等稳定关联，扩展更正/撤销/同日重算与日志展示，保留年度独立、双打不计、同一队员实际账号、不误计队长。最新roster_rating_replay必须取profile-phone-20261031/GinkgoProfilePhone-36.13.7/profile-phone-payload/roster_rating_replay.py (1.1.1)，不能用backend根旧1.1.0。普通rating_recalc的匹配查询仅singles，roster replay目前会丢额外tie字段，均需纳入。现有rated/非积分赛开关语义需核对，不要偷偷取消。

获客原目标未完成：保留round010本机待合并回执绑定修复和round011 source dedup测试；没有恢复旧纯扫描Agent，也未触碰无关积分数据。新的全页客服、团体单打计分是用户新增明确任务，需要后续继续完成，不能把本轮客服后台待安装当成全部交付。
