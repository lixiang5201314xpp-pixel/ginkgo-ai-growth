# 第十七轮：后台真实部署核验与36.14.2开发版上传

用户确认r2安装SUCCESS并提供完整输出。已从服务器拉取实际r2/miniapp-install-result.json和schema-result.json，验证success=true、服务RUNNING、迁移7语句committed。备份 miniapp-20261103-010728。

已核对：11个实际安装文件hash等于冻结的测试清单，10个保留文件hash符合安装前记录及身份/机构/银杏客服保护；公开接口batch-signup1.1.0且id_card_required=true、event-settings1.0.0、team-singles-rating1.0.0、organizer-grants1.1.0、channels1.0.1、external1.4.1均正常。真实数据库5个新列、过滤唯一索引、一个专用锁记录存在；历史rubber opt-in和新rubber积分流水均为0，未补算历史。证据 deployed-acceptance.json。系统信任库可验证HTTPS；单独Python CA库偶发issuer错误，改用Windows原生校验证书的Invoke-RestMethod，没有关闭证书验证。

前端源文件逐项hash与已测快照一致。通过官方CLI将36.14.2上传为开发版本，输出upload成功，upload-info.json记录主包1321631字节、总1635670字节；较preview增加的是上传打包开销，源文件hash不变。frontend-upload.json记录结果。未提交审核或发布。

已生成新的真实后端预览二维码 wechat-preview-live.png，preview-live-info.json主包1305635/总1619674。可供本人手机扫码体验后提审。

只读真实前端联调尝试：从未修改的实际工程复制一次性live-runtime-project，保留真实API和原登录逻辑，仅本机调试配置关闭多框架热重载。通过官方automator检查已有赛事会话，结果无现有match_center_token，立即停止，没有自动创建赛事登录、伪造手机号/权限、提交报名或修改比赛；未把这个阻塞算通过。live-miniapp-readonly.json已保存，测试窗口已关闭。需要本人或已授权组织者在手机微信登录体验。

待体验：管理员修改设置重开仍保持、姓名复制、同名积分完整面板、真实身份证名单核对和已接受裁判姓名。代码的相关官方原生14项及65页编译已通过；真实手机确认仍待用户。原表158人未正式导入，43同名选择、13分数、11无效资料、1年龄不符和128名额限制继续由组织者明确，详见测试名单核对结果.md。不要因开发版上传成功就宣称所有原表人员已真实报名。

最新路径 work/release/miniapp-update-20261102/deployment.json：后台已部署、前端开发版已上传、手机体验/审核/发布未完成。后续获客安装必须保留当前11个业务文件和新版重算/团体计分代码；原Growth1.4.5只更新4个获客文件，仍未部署，不能误写为本轮也安装了外部获客。原获客验收目标继续未完成，既有抖音回复禁止重发。
