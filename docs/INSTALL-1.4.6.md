# GinkgoGrowth-1.4.6 管理员安装说明（Windows 服务器）

**适用范围：** 已在 `C:\Services\KaiqiuMatch_20260915` 运行银杏比赛/获客后台，正式外部模块仍为 `growth-external-1.4.1` 或已暂存未装的 `1.4.5` 场景。

**本包做什么：** 仅替换 4 个获客文件（`growth_acquisition.py`、`growth_collection.py`、`growth_external.py`、`growth-web/browser-helper.zip`），合并 **来源去重** 与 **公开原帖回执绑定** 修复；安装器预检含 `test_delivery_source.py`、`test_source_dedup.py`。

**本包不做什么：** 不覆盖微信客服三文件、不修改 `identity.py` / miniapp-update1.4.0 核心、不改业务 SQLite、不调用真实 AI、不向平台发消息、**不启动** Codex 外部扫描 Agent。

---

## 包位置与完整性（云端已构建，未在服务器安装）

| 项 | 值 |
|---|---|
| 目录 | `work/release/growth-dev-20261102/GinkgoGrowth-1.4.6/` |
| ZIP | `work/release/growth-dev-20261102/GinkgoGrowth-1.4.6.zip` |
| ZIP SHA256 | 见 `work/release/growth-dev-20261102/backend-package-1.4.6.json` |
| 冻结 1.4.5 ZIP | **不得改写**；SHA256 须仍为 `948e30c1825f7dba3fac13159947ccdd3b90488b31333e9c1fb7652e15a05777` |
| 离线验证 | `work/release/growth-dev-20261102/backend-1.4.6-verification.json` |

### Payload SHA256（安装后应一致）

| 文件 | SHA256 |
|---|---|
| `growth_acquisition.py` | `3afbc73ed2357204bc4cb8ed1e673851bf40655ce3753b06929d71de5e732c81` |
| `growth_collection.py` | `893ad4ee166175d764426d4f922c46507e301de3cf8e112d71f8d4bd5080e8ee` |
| `growth_external.py` | `a67de83c385987bb977b6d5b3de942278b3a980d323b50cf2a4b8990f5178063` |
| `growth-web/browser-helper.zip` | `e19c304ffe0ca931dbc6d55ab8b101d4286f78c2e121c1080b81381dccfc8851`（助手 **1.4.9**） |

### 安装后必须仍为原 hash 的保护文件（节选）

见包内 `source-retention-1.4.6.json` 与 `docs/current-source-inventory.json`：

- `growth_ai.py` → `26705798430fb47a2a864340d8d289dda266b90838788229919981034591fade`
- `growth_channels.py` → `3ef7007c38bbf14b3c3afb4d8f1a090311d78f961e1a173e6d635b76db1d9a8b`
- `growth_playbook.json` → `3b0305be9101115de11d951df9ae756f8530b0f76ed914e4192404e87b812081`
- `identity.py` → `a9c924c81686b12cbd01e2c5e311f2ac725a728cc934a9c3608bd855f5421295`（以安装回执为准）

每日 **20 搜索 / 30 AI** 限额由既有配置保留；安装器不修改配额字段。

---

## 管理员操作顺序（需本人确认）

以下步骤在 **Windows 管理员会话** 执行；云端 Agent **不会**代跑安装器或远程写 `C:\Services\...`。

### 0. 前置确认（必须）

- [ ] 服务 `KaiqiuMatchCenter` 当前为 **RUNNING**
- [ ] 已备份最近 miniapp-update1.4.0 / 客服 1.1.0 相关回执（参考 `work/release/score-modes-20261103/server-install-result.json`）
- [ ] 已将 `GinkgoGrowth-1.4.6.zip` 拷到服务器并解压到  
      `C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.6\`
- [ ] 核对 ZIP SHA256 与 `backend-package-1.4.6.json` 一致
- [ ] **未**改写 `GinkgoGrowth-1.4.5.zip` 冻结包

### 1. 暂存与预检（不停服）

在解压目录打开 **管理员 PowerShell**：

```powershell
cd C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.6
C:\Services\KaiqiuMatch_20260915\.venv\Scripts\python.exe install_growth_external.py
```

若输出 `already installed and verified` 或预检失败，**不要**强行复制文件；阅读 `external-install-result.json` 与 stderr，修复后重试。

预检通过时会打印 `PASS: external-intake...` 且 **尚未**停服。

### 2. 正式安装（短暂停服）

- [ ] **管理员确认** 可接受约 1–2 分钟停服窗口
- [ ] 双击或运行 `Install-Growth-External.cmd`（内部调用同一 `install_growth_external.py` 完整流程）

安装器将：

1. 校验 manifest 与现有文件 hash 是否在允许基线内  
2. 在 `backups\external-YYYYMMDD-HHMMSS\` 备份将被替换的 4 个文件  
3. **停止** `KaiqiuMatchCenter` → 复制 payload → **启动**服务  
4. 调用 `/growth/external/health` 期望 `growth-external-1.4.6`  
5. 核对 `growth_ai.py` / `growth_channels.py` / `growth_playbook.json` / `identity.py` 等 **未被改动**  
6. 写入 `external-install-result.json`

### 3. 安装后健康与 hash 核对

- [ ] `external-install-result.json` 中 `"success": true`
- [ ] `GET http://127.0.0.1:8011/api/match-center/growth/external/health` → `"version":"growth-external-1.4.6"`
- [ ] `installed_payload_sha256` 与上表 payload 一致
- [ ] `retained_file_sha256` 中客服三文件与 `identity.py` 与安装前一致
- [ ] 微信客服 `/growth/channels/health` 仍为 200（安装器 combined preflight 已测注册共存）
- [ ] **未**出现真实平台发送或 AI 生成日志

### 4. 浏览器与业务（需本人，非安装器）

- [ ] Chrome：**扩展程序页刷新** 银杏助手，manifest 版本 **1.4.9**（下载 ZIP 升级 ≠ 已加载）
- [ ] 工作台重新打开获客页，确认 UI 正常
- [ ] 抖音帖 `7702708741762243570`：**仅补登**已有公开回复回执与时间 `2026-10-31 14:03:54`，**禁止重发**
- [ ] 小红书/快手/视频号扫码与登录超限问题仍按 PROGRESS 待办，不因 1.4.6 宣称已闭环

### 5. 回滚（安装失败或健康检查失败时）

安装器失败时会自动：

1. 从 `backups\external-*\` 还原 4 个文件  
2. 重启服务并验证既有 `/health` 等端点  

若自动回滚也失败：

- 停止服务，**手工**从最新 `backups\external-*\` 复制 4 个文件回 `C:\Services\KaiqiuMatch_20260915\`  
- 启动服务，保存 `external-install-result.json` 与事件日志供审查  
- **不要**用 1.4.5 冻结 ZIP 覆盖 1.4.6 目录来“假装回滚成功”

---

## 与 1.4.5 的关系

- **1.4.5** 为已验证冻结包，可暂存于 `GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.5`，但**不含**本轮去重+回执修复。  
- **1.4.6** 为新的不可变包号；从 1.4.1 正式线或 1.4.5 暂存线均可升级，**跳过** 1.4.5 安装直接上 1.4.6 亦可（基线 hash 已收录）。  
- 仍 **未宣称** 全平台真实搜索→发布→报名交付完成；安装成功只代表后台代码与离线回归通过。
