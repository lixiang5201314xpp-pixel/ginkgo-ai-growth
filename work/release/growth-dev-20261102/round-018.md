# 第十八轮：手填性别/生日或年龄，按信息完整度排序

最新用户两项要求均已实现并测试：身份证缺失或错误时由组织者补充性别、出生日期；不知道生日时也保留前一条要求的比赛当天年龄。名单按“信息完整→缺当前/年度积分或同名待选→身份证缺失/错误及其它无效资料”排序；保留原始行号和按行号复制/选择/回执映射。确认补充资料后重新核验，不在输入一半时静默导入。

新独立源码 work/release/manual-demographics-20261103/candidate；从已真实安装的36.14.2-r2/miniapp-update1.0.1的11文件hash开始。原冻结包未覆盖。新增build_manual_demographics.py仅从该安装快照重建主文件；player_idcard.py、batch_signup.py、batch_signup_identity.py、event_settings.py是新candidate内的支持模块源码，不可运行旧build_miniapp_update.py覆盖。

实现：

- 有效身份证仍优先自动识别，不允许用矛盾的手填覆盖有效号码的识别结果。
- 无证或无效证件提供manual_gender + manual_birthday，或者manual_age。缺手机号仍须补齐，积分同名仍须明确选择，不造分数/身份证。
- 生日直接记录真实日期；仅年龄时增加MC_Users.manual_age、manual_age_on、demographics_source，MC_Entries.on_behalf_age保留该场快照，不制造生日。年龄只对应比赛日期，之后比赛需要本人准确生日或组织者重新确认年龄。个人资料显示年龄、对应日及来源。
- 性别/年龄/人数限制、组织者权限、费用、去重及真实微信号码授权继续有效。重复报名更新人口信息但不改积分或复制订单。
- frontend批量页增加填写控件与确认；姓名复制和宽积分面板保留。排序只在核对后执行，不随每个输入字符移动行。身份证手填类别补全后仍留最后一组便于组织者复核。
- batch-signup新版本1.2.0，manual_demographics=true、id_card_optional=true；旧id_card_required=true保留为旧ID客户端能力兼容标记，新客户端只看manual_demographics。

验证通过：1905整体SQL/HTTP回归；65新增手填/权限/限制/资料输出/不虚构生日/去重检查；原表205隔离检查；45离线；11真实迁移入口/重复/失败回滚；8安装代码恢复；93前端行为；65页/124JS官方编译；5项官方原生手填生日/仅年龄/排序/四行一键导入。所有写入均在连接私有临时表，未正式导入原表。full suite启动后仅将年龄0校验表达等价改写以便阅读，完整回归旧helper hash如实保留，最后文件又经65定向SQL、45离线、原表205验证，coverage-provenance.json及freeze双重hash覆盖记录，未改写旧测试证据。

模拟器一度simulator launch failed/stack空，Windows UI输入geometry unavailable，未绕过；正常关闭QA工程，改QA启动页为batch-signup并重开后恢复，5项通过。目视发现年龄输入框被全局padding压扁，已固定84rpx高度、重新编译与原生运行，wechat-manual-form.png已目视核对。QA窗口已关闭，正式源工程无假API、假用户或禁用确认污染。

原文件仍为 C:/Users/Administrator/Desktop/测试名单.xlsx（Sheet1 A1:E160，158人）。新流程仍90人完成测试账号/报名/订单，43同名待选、13需给分、1人年龄不符；最后11行现在细分为6人可手填身份资料、5人需先补手机号。原表分组为91信息完整、56积分需处理、11身份/其它资料待处理；91内含1名不满足比赛年龄的人，最终仍会拒绝。正式128名额及真实资料不能擅自取舍。原表核对结果.md已更新，未伪造六人的性别、生日或年龄。

新包GinkgoMiniapp-36.14.3，miniapp-update1.1.0 / installer1.0.2；新增4个可空字段，沿用已修好的独立AST迁移helper，11条语句逐条编译、整体事务提交。以r2真实安装回执做11文件基线，保留身份/机构/客服10文件。冻结SHA256 010c3e945df11b52322a713ea42bfdf4cc6d8c7ae684757b475f28ba0c274cff，176748bytes，已在服务器同名目录暂存逐文件核验。

已向用户发一次必要动作：管理员会话运行 C:/Services/GinkgoTrainingAutoCancel/GinkgoMiniapp-36.14.3/Install-Miniapp-Update.cmd，首行miniapp-update1.1.0/installer1.0.2。当前通道运行目录权限未变，未绕过。收到SUCCESS后必须拉取新目录安装/schema回执、核对11文件hash和4新列、batch1.2.0及manual能力/原客服，再上传已测36.14.3前端（主包1310785，总1624824预览通过），本人体验后提审。

当前真实运行仍miniapp-update1.0.1，36.14.2开发版已上传；36.14.3未部署/上传。原获客目标也仍未完成，不把测试报名算真实获客。
