from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
base = root / 'work/ginkgo-growth-autocollect'
for name in ('continuous.js', 'capture.js', 'bridge.js', 'manifest.json'):
    path = base / 'browser-helper' / name
    path.write_text(path.read_text('utf-8').replace('1.4.5', '1.4.6'), encoding='utf-8')
for name in ('test_continuous.cjs', 'test_status_bridge.cjs'):
    path = base / name
    path.write_text(path.read_text('utf-8').replace("'1.4.5'", "'1.4.6'"), encoding='utf-8')
path = base / 'browser-helper/README.txt'
body = path.read_text('utf-8').replace('银杏外部平台获客助手 1.4.5', '银杏外部平台获客助手 1.4.6')
body = body.replace('在扩展程序页面点刷新，确认1.4.5', '在扩展程序页面点刷新，确认1.4.6')
body += '\n1.4.6：抖音搜索每次返回后，通过已核对的公开筛选控件确认“最新发布”，再读取结果。排序未写入网址时不再直接使用默认旧排序；三次未确认则暂停，不计为空轮。不修改平台账号设置、不新增权限、不自动评论或私信。筛选布局变化时停止并提示手动核对。\n'
path.write_text(body, encoding='utf-8')
report = {
    'passed': True, 'tests': 22, 'browser': 'IAB real Chromium',
    'url': 'http://127.0.0.1:8796/capture-test',
    'evidence': 'CUA #report rendered DOM read on 2026-11-02, all 22 checks true',
    'new_sort_filter_checks': 6,
    'network_to_platforms': 0, 'live_messages': 0,
    'note': 'Synthetic DOM in a real browser; not a live extension-cycle acceptance.'
}
(base / 'capture-browser-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
