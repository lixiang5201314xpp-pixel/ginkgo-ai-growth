# ginkgo-ai-growth

银杏乒乓球俱乐部 AI 获客平台 — 云端开发仓（交接自 2026-11-04 Claude 导出包）。

## 先读

1. [README-先读这里.md](./README-先读这里.md)
2. [CLAUDE.md](./CLAUDE.md)
3. [docs/01-当前事实与版本.md](./docs/01-当前事实与版本.md) · [02](./docs/02-用户需求与验收矩阵.md) · [04](./docs/04-已知缺陷与接手顺序.md) · [05](./docs/05-环境测试与部署.md)
4. 进度与待办：[PROGRESS.md](./PROGRESS.md)

## 源码布局

| 路径 | 说明 |
|---|---|
| `work/ginkgo-growth-autocollect/` | 当前候选：扩展、Web 工作台、测试；**本轮去重 + 回执修复在此** |
| `work/ginkgo-growth/` | 历史运行底座与安装脚本 |
| `work/release/` | 版本链、冻结包 1.4.5（只读参考，勿安装/改写）、回归证据 |
| `docs/current-source-inventory.json` | 客服三文件等保护 hash |

## 离线测试（docs/05）

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-handoff.txt
cd work/ginkgo-growth-autocollect
../.venv/bin/python test_source_dedup.py
../.venv/bin/python test_delivery_source.py
../.venv/bin/python -m unittest test_growth test_ai test_workflow test_external test_delivery \
  test_collection test_job_intent test_practice_intent test_delivery_source test_source_dedup
```

**未宣称**全平台真实搜索/发布/报名已跑通；正式部署需本机管理员目录与浏览器授权。
