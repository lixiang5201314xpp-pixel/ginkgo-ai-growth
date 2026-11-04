# 第十六轮：修复实际后台安装失败

用户返回36.14.2安装失败，路由与28项纯数据检查通过，但 schema 子进程失败并成功还原旧代码。已拉取服务器实际 miniapp-install-result.json，success=false、rolled_back=true，备份 miniapp-20261103-001733。线上 health、batch-signup1.0.0、银杏客服channels1.0.1均返回200，旧服务正常。未让用户重复执行旧安装器。

本机服务布局复现两个安装问题：

1. miniapp_schema.py直接import event_settings，但子进程未包含运行目录，缺少team_rating_limits；此前只测业务和模拟schema失败回滚，漏测了实际迁移子进程路径。
2. SQL Server15.0.2000.5同批次先ALTER新增tie_game_id再CREATE引用该列的过滤索引时，编译报207 Invalid column name。即使补上路径仍会遇到此问题。

证据 work/release/miniapp-update-20261102/schema-failure-diagnosis.json。所有复现DDL在连接私有临时表执行并回滚；正式库没有这些新列，没有修改任何正式报名、订单或积分。

修复：独立schema runner通过AST只读取清单中两个受hash保护文件的常量SQL，不导入应用及其业务依赖；所有DDL逐条编译，在同一事务中执行并核对列/索引/锁记录后提交，指定过滤索引需要的会话选项。增加停服务前的真实helper/config预检。失败回执仅输出阶段、异常类、SQL码，绝不输出配置值、参数或密钥。保留代码备份和失败恢复。

新目录 GinkgoMiniapp-36.14.2-r2；后台包版本miniapp-update-1.0.1、installer-1.0.1，前端仍36.14.2。11个应用文件、基线hash和保留文件保护与上轮已通过1905项SQL/HTTP的版本完全相同，本次只修安装器，不改赛事业务。原冻结36.14.2未覆盖。

新增验证：37项离线（含依赖缺失时在停服务前退出、辅助进程环境一致、诊断保密）；11项真实SQL迁移入口/重复执行/旧记录默认值/唯一索引/中途失败整体回滚；8项安装失败和代码恢复。真实子进程在没有应用依赖的临时布局执行check成功；真实runner在私有SQL表执行并重复成功。schema-runner-verification.json记录了实际测过的helper hash，冻结时已再次核对。前端没有变动，沿用上轮65页编译、14项原生、姓名复制及原表205项测试证据，没有把这些算正式上线。

冻结包SHA256 4ca21e90455f31a7d5d05a0016d25df2fda4292dfc17f36b3390790b288d4676，170787字节。已上传服务器 C:/Services/GinkgoTrainingAutoCancel/GinkgoMiniapp-36.14.2-r2 并逐文件校验。未执行运行目录安装、未换身份或更改ACL。已向用户发一次明确动作：管理员会话运行新r2目录 Install-Miniapp-Update.cmd，首行应含 miniapp-update-1.0.1 / installer-1.0.1。

用户回复后：先拉r2/miniapp-install-result.json与schema-result.json，核对success、11文件hash、旧身份/机构/银杏客服保留hash，以及batch-signup1.1.0、event-settings1.0.0、team-singles-rating1.0.0；只有真实通过再上传匹配前端、体验和提审。若失败按安全阶段码查，不重试旧r1。

原表同名/缺失积分/无效证件/年龄不符、128名额和原获客平台阻塞沿用round015；不选择冒名积分、不伪造微信授权、不算真实外部成交。当前仍未完成交付。
