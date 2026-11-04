# 外部平台能力核对（开发用途，不是已接通证明）

核对时间：2026-11-02。只采用平台官网资料；不采购第三方逆向数据服务，不导出Cookie，不把小程序客服凭据冒充内容账号权限。

| 平台 | 本轮核实的信息 | 对当前目标的影响 |
| --- | --- | --- |
| 抖音 | 官方“回复视频评论”接口 scope 为 item.comment，需申请及用户授权，而且只允许回复授权用户自己发布的视频。 | 不能拿该接口去任意别人的原帖留言。现有小程序business_token也不能替代此OAuth授权。对明确求助原帖的回应仍需核实可用的原平台操作路径。 |
| 快手 | 网站应用使用独立OAuth授权，scope必须申请；应用管理规范分别讨论私信自动回复及前台发布确认。另有小玩法直播间评论接口，但只用于指定直播场景且需白名单。 | 登录快手内容账号或小程序上线，不表示已取得任意短视频评论权限；不得把直播评论API套用到短视频留言。尚未核实到符合本需求的通用评论发送能力，状态继续未接通。 |
| 小红书 | 小程序“接收消息与发送消息”说明的是用户向小程序商家客服会话发消息后的回复能力；介绍文档另有专业号、私信通资料入口。 | 不等于对任意笔记评论或陌生账号主动私信权限。用户已暂缓此小程序客服接入，不重新推进该项。普通笔记原文获客的流程仍需独立验收。 |
| 微信视频号 | 本轮未在官方开发文档中验证到可供该应用任意搜索、采集、回复全站视频号评论的接口。 | 不能将公众号/小程序客服API或第三方“视频号API”当作已获官方授权。现有功能仍为手机公开搜索后提供原文，自动适配未通过。 |

来源：

- [抖音：回复视频评论](https://open.douyin.com/platform/resource/docs/openapi/interaction-management/comment-management-user/video-comment-reply)
- [快手：网站应用OAuth](https://open.kuaishou.com/platformDocs/develop/web-app)
- [快手：应用管理规范](https://open.kuaishou.com/platformDocs/newGuide/applicationManagementSpecifica)
- [快手：小玩法直播相关能力](https://open.kuaishou.com/miniPlayDocs/technologyrelated/Affiliatedability/basicability/dibulan)
- [小红书：接收消息与发送消息](https://miniapp.xiaohongshu.com/doc/DC897608)
- [小红书：小程序介绍及官方资料入口](https://miniapp.xiaohongshu.com/doc/DC137160)

以上是明确查到的能力及未验证部分，不作“所有官方API均不存在”的推断。本轮没有新授权、凭据申请、客户消息、支付或账号设置变更。

后续需要把“自有内容评论运营”“别人的公开求助回应”“小程序主动咨询”三种场景分别验收与统计；不能再用接通第三种来宣称前两种已实现。平台网页上出现验证码、登录失效或发布不可见时，记录阻塞及不确定结果，不重复点击发送。
