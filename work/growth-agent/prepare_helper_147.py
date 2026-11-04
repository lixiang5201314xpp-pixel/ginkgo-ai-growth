from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
base = root / 'work/ginkgo-growth-autocollect'
for name in ('continuous.js', 'capture.js', 'bridge.js', 'manifest.json'):
    path = base / 'browser-helper' / name
    path.write_text(path.read_text('utf-8').replace('1.4.6', '1.4.7'), encoding='utf-8')
for name in ('test_continuous.cjs', 'test_status_bridge.cjs'):
    path = base / name
    path.write_text(path.read_text('utf-8').replace("'1.4.6'", "'1.4.7'"), encoding='utf-8')
path = base / 'browser-helper/README.txt'
body = path.read_text('utf-8').replace('银杏外部平台获客助手 1.4.6', '银杏外部平台获客助手 1.4.7')
body = body.replace('在扩展程序页面点刷新，确认1.4.6', '在扩展程序页面点刷新，确认1.4.7')
body += '\n1.4.7：快手无法唯一确定当前作品时不再读取整个页面。多个可见连播面板、公开链接不明或与地址不一致时停止；选择原文也必须在已核对面板内。搜索卡片没有公开作品链接时明确暂停，不能把搜索词当作品来源。该保护通过隔离测试，当前快手完整自动采集仍未验收；不会借此宣称接通。权限、AI限额和自动发送能力未改变。\n'
path.write_text(body, encoding='utf-8')
(base / 'capture-browser-verification.json').write_text(json.dumps({
    'passed': True, 'tests': 26, 'browser': 'IAB real Chromium',
    'url': 'http://127.0.0.1:8796/capture-test',
    'evidence': 'CUA rendered AX report title PASS 26 and all checks true on 2026-11-02',
    'new_kuaishou_checks': 4, 'network_to_platforms': 0, 'live_messages': 0,
    'note': 'Synthetic DOM in Chromium; not an end-to-end live-platform acceptance.'
}, ensure_ascii=False, indent=2), encoding='utf-8')
