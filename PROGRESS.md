# 银杏AI获客平台进度

- 记录时间：2026-11-04（PR #1 合入 main 后）；**1.4.6 不可变包** 2026-11-04 UTC（Cursor Cloud Agent）
- Git 仓：`lixiang5201314xpp-pixel/ginkgo-ai-growth`（main 含 autocollect 去重+回执修复）
- **未宣称**全平台真实搜索/发布/报名已跑通；**未在用户服务器执行安装器**。

## 版本现状

| 层 | 状态 |
|---|---|
| 仓内 autocollect `growth_acquisition.py` | `3afbc73…`（去重 + round-010 回执） |
| **GinkgoGrowth-1.4.6**（新不可变包） | ZIP `f88d15f180d777b639a949401b1d30c5d04f2817075cc40718cff2a8795da539`；`growth-external-1.4.6` |
| 冻结 **GinkgoGrowth-1.4.5.zip** | **未改写** SHA256 `948e30c1…` |
| 正式外部获客（服务器，待管理员复核） | 交接事实仍为 growth-external-**1.4.1**；1.4.6 **未安装** |
| 微信客服 / miniapp | 保护 hash 见 `source-retention-1.4.6.json`；miniapp-update**1.4.0** 不在 payload |
| 助手下载包 | browser-helper.zip **1.4.9**（`e19c304f…`）；Chrome 重载仍待本人 |
| Codex 外部扫描 Agent | **未启动** |

## 1.4.6 包内容（仅 4 文件 payload）

| 文件 | SHA256 |
|---|---|
| `growth_acquisition.py` | `3afbc73ed2357204bc4cb8ed1e673851bf40655ce3753b06929d71de5e732c81` |
| `growth_collection.py` | `893ad4ee166175d764426d4f922c46507e301de3cf8e112d71f8d4bd5080e8ee` |
| `growth_external.py` | `a67de83c385987bb977b6d5b3de942278b3a980d323b50cf2a4b8990f5178063` |
| `growth-web/browser-helper.zip` | `e19c304ffe0ca931dbc6d55ab8b101d4286f78c2e121c1080b81381dccfc8851` |

路径：

- 目录：`work/release/growth-dev-20261102/GinkgoGrowth-1.4.6/`
- ZIP：`work/release/growth-dev-20261102/GinkgoGrowth-1.4.6.zip`
- 元数据：`backend-package-1.4.6.json`、`backend-1.4.6-verification.json`
- 安装说明：**`docs/INSTALL-1.4.6.md`**

安装器预检新增 `test_delivery_source.py`、`test_source_dedup.py`；离线布局验证 2338 次执行（见 verification JSON，非独立功能数）。

## 已通过（离线 / 打包）

- autocollect：`test_source_dedup` 6/6、`test_delivery_source` 12/12、docs/05 套件 570 OK（`qa/offline-unittest-20261104-cloud.txt`）
- 1.4.6：安装器模拟 10 项 + 多基线 overlay/installed 预检（`backend-1.4.6-verification.json`）
- 保护：payload 不含 `growth_ai` / `growth_channels` / `growth_playbook` / `identity` / miniapp 核心；20/30 限额不在安装器修改范围

## 仍未通过（需管理员 / 本机）

- 在 `C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.6` **运行** `Install-Growth-External.cmd` 并拉取 `external-install-result.json`
- 安装后 hash：payload 四文件 + retained 客服三文件 + `identity.py`
- Chrome 刷新助手 1.4.9；各平台真实闭环（docs/02 矩阵）
- 抖音 `7702708741762243570`：**仅补回执**与时间 `2026-10-31 14:03:54`，**禁止重发**
- 小红书登录超限、快手分享链、视频号浏览器等待办

## 管理员待办清单（摘要）

完整步骤见 **`docs/INSTALL-1.4.6.md`**。

1. 拷贝并校验 `GinkgoGrowth-1.4.6.zip` SHA256  
2. 解压到 `C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.6`  
3. **确认**可接受短暂停服 → 运行 `Install-Growth-External.cmd`  
4. 核对 `growth-external-1.4.6` 健康与 `retained_file_sha256`  
5. 刷新 Chrome 助手 1.4.9；工作台验证  
6. 补登抖音已有回复回执（不重发）  
7. 全平台真实证据齐备前 **不写最终交付完成**

## 构建脚本（仓内）

- `work/growth-agent/package_backend_146.py` — 生成 1.4.6（禁止改 1.4.5 ZIP）
- `work/growth-agent/verify_backend_146.py` — 离线验证
