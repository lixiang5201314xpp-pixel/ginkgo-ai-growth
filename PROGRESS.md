# 银杏AI获客平台进度（离线修复轮）

- 记录时间：2026-11-04 11:12 Asia/Shanghai (CST, UTC+8)；**云端入仓复验** 2026-11-04 UTC（Cursor Cloud Agent）
- Git 仓：`lixiang5201314xpp-pixel/ginkgo-ai-growth`；PR [#1](https://github.com/lixiang5201314xpp-pixel/ginkgo-ai-growth/pull/1)（`cursor/offline-dedup-receipt-1099` → `main`）
- 仓内源码：`work/ginkgo-growth-autocollect/`（含合入后的 `growth_acquisition.py`）
- 本地 venv 复验副本：`/workspace/yinxing-dev/ginkgo-growth-autocollect`（与仓内同步）
- 导出只读对照：`/workspace/yinxing-handoff-utf8/银杏AI获客平台_Claude交接_20261104`（未入 git）
- 环境：Linux；Python 3.12 venv + `requirements-handoff.txt`（Flask/pycryptodome）
- **未宣称**全平台真实搜索/发布/报名已跑通；本轮为交接入仓 + 离线逻辑修复复验。

## 版本现状（以本轮核对为准）

| 层 | 状态 |
|---|---|
| 正式外部获客后台 | 仍按交接事实为 growth-external-1.4.1（本机未连服务器复核） |
| 冻结暂存包 1.4.5 | 未安装、未改写；不含本轮去重修复 |
| 本机候选 growth_acquisition.py（导出时） | SHA256 `3e3f9d61273f231823b29798fa26d1380df130e026d4f007196a8d13bfd85582`（含 round-010 回执来源校验） |
| **本轮候选（未打包）** | SHA256 `3afbc73ed2357204bc4cb8ed1e673851bf40655ce3753b06929d71de5e732c81`；建议下次不可变包号 **1.4.6+** |
| growth_external.py 字符串 | 仍为 `growth-external-1.4.3`（历史事实；打包时再升） |
| 客服保护三文件 | 未改：growth_ai / growth_channels / growth_playbook 与 inventory 一致 |
| 助手 1.4.9 / Chrome 重载 | 本轮未做浏览器验收 |
| Codex 外部扫描 Agent | 未启动 |

## 本轮修改文件

1. `work/ginkgo-growth-autocollect/growth_acquisition.py`（仓内；与候选 SHA256 一致）
   - 新增 `normalize_excerpt` / `intake_identity_key` / `source_fingerprint`
   - `Store.add` 指纹改为：已知原帖 ID（抖音 video/note、小红书 explore|discovery/item、快手 short-video）或 **host|path + 排序后 query**
   - 旧行兼容：同平台 + 空白归一 excerpt + 同一 `intake_identity_key` 命中即返回原线索；**不改写** fingerprint / contact_count / stopped / stage
   - 回执侧既有 `public_original_identity` / `validate_delivery_evidence` 保留

交接 ZIP 内导出副本仍为旧 hash `3e3f9d6…`（只读）；仓内已合入 `3afbc73…`。

## 复现与回归证据

### 修复前（干净复现）

```text
python test_source_dedup.py
→ 6 ran; 2 ok / 4 FAIL
FAIL: test_different_opaque_post_queries_are_not_one_lead
FAIL: test_legacy_query_collision_does_not_hide_a_different_original
FAIL: test_same_xhs_route_aliases_share_intake_identity
FAIL: test_legacy_xhs_alias_and_whitespace_do_not_reopen_a_contacted_lead
OK:   test_equivalent_query_order_keeps_one_lead
OK:   test_same_legacy_query_keeps_stop_and_contact_state_after_whitespace_change
```

根因：指纹丢弃全部 query；小红书 explore 与 discovery/item 未统一；旧兼容只比 path，导致不同 objectId 误合并、别名无法合并。

### 修复后

```text
cd work/ginkgo-growth-autocollect
/workspace/yinxing-dev/.venv/bin/python test_source_dedup.py      → 6 ran; OK
/workspace/yinxing-dev/.venv/bin/python test_delivery_source.py   → 12 ran; OK
/workspace/yinxing-dev/.venv/bin/python -m unittest test_growth test_ai test_workflow \
  test_external test_delivery test_collection test_job_intent test_practice_intent \
  test_delivery_source test_source_dedup                             → 570 ran; OK (skipped=4)
```

完整输出：`qa/offline-unittest-20261104-cloud.txt`（云端 2026-11-04 重跑，非历史报告）

## 通过 / 未通过

### 本轮通过（离线）

- 来源去重 6/6（query 指纹、等价 query 顺序、小红书 route 别名、legacy 碰撞不吞帖、stopped/contact_count 保留）
- 回执来源 12/12（含抖音 note/video、modal_id、错误原帖拒绝、搜索页拒绝等）
- docs/05 所列安全离线套件合计 570 项（含继承用例重复装载；无失败）

### 本轮未做 / 仍未通过（真实闭环）

- 正式部署 hash ≠ 本候选；未装 1.4.6 包（冻结 1.4.5 ZIP 未安装、未改写）
- 助手 1.4.9 Chrome 重载与连续真实轮次
- 抖音/快手/小红书/视频号：真实搜索→评论范围→AI 回复→平台可见发布→银杏奖牌入口→报名凭证
- 抖音帖 `7702708741762243570` 回执与准确日期补登（禁止重发；需本机工作台）
- 小红书设备登录超限、快手分享链、视频号浏览器适配
- 服务器管理员目录安装、备份/回滚、重启后健康与客服三文件 hash 核对

## 保护项核对

- 未运行旧纯扫描 Agent / 未安装旧 1.4.5
- 未触碰客户库、密钥、Cookie
- growth_ai.py / growth_channels.py / growth_playbook.json hash 与 `docs/current-source-inventory.json` 一致
- 去重命中旧线索时直接返回，不重置 contact_count / stopped

## 下一步（需用户本机 / 授权）

1. **本机控制**：设置 → Computer / 本地执行，批准对本机 `CH-202207021931` 的操作。
2. **核对本机路径**：`C:/Users/Administrator/Documents/Codex/2026-09-15/new-chat` 与候选 hash；将本轮 `growth_acquisition.py` 合入工作区（不要覆盖客服三文件与 miniapp 核心）。
3. **打包 1.4.6+ 不可变包**：合并本去重修复 + round-010 回执校验 + `test_source_dedup.py` / `test_delivery_source.py`；预检保留 identity/AI/渠道/限额与数据；**禁止重写冻结 1.4.5 ZIP**。
4. **管理员安装**：在 `C:/Services/GinkgoTrainingAutoCancel` 新版本目录备份→短暂停服→安装→拉 hash/健康回执；确认客服 1.1.0 与 miniapp-update1.4.0 仍在。
5. **浏览器**：Chrome 重载助手 1.4.9；逐平台授权/扫码（小红书超限需本人处理）。
6. **仅补登**已有抖音公开回复回执与准确时间 `2026-10-31 14:03:54`，不重发。
7. 再按 docs/02 矩阵逐平台填真实证据后才可写交付报告。

## ginkgo-growth vs ginkgo-growth-autocollect

- **autocollect**：本机当前候选（含回执校验 + 本轮去重）；测试入口在此目录。
- **ginkgo-growth**：较旧运行底座/安装脚本；`growth_acquisition.py` hash 不同，本轮未改。
- 冻结 payload：`work/release/growth-dev-20261102/GinkgoGrowth-1.4.5/` 仅历史参考。
