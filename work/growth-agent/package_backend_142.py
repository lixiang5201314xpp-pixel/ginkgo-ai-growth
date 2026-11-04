"""Prepare a three-file acquisition-only upgrade from the verified 1.4.1 package."""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/ginkgo-growth-autocollect'
RELEASE = ROOT / 'work/release/growth-dev-20261102'
PRIOR = ROOT / 'work/release/growth-collection-patch-20261101/GinkgoGrowth-1.4.1'
PACKAGE = RELEASE / 'GinkgoGrowth-1.4.2'
FILES = ['growth_collection.py', 'growth_external.py', 'growth-web/browser-helper.zip']
TESTS = ['test_growth.py', 'test_ai.py', 'test_workflow.py', 'test_external.py', 'test_delivery.py', 'test_collection.py']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    old = json.loads((PRIOR / 'payload/external-manifest.json').read_text('utf-8'))
    hashes = {x['path']: x['sha256'] for x in old['files']}
    for name in FILES:
        assert sha(PRIOR / 'payload' / name) == hashes[name], name
    helper = RELEASE / '银杏获客助手-1.4.5.zip'
    proof = json.loads((RELEASE / 'helper-package-1.4.5.json').read_text('utf-8'))
    assert sha(helper) == proof['archive_sha256']
    assert proof['permissions_unchanged']
    with zipfile.ZipFile(helper) as zipped:
        assert json.loads(zipped.read('browser-helper/manifest.json'))['version'] == '1.4.5'
    payload = PACKAGE / 'payload'
    payload.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 'growth-external-1.4.2', 'installer_version': '1.4.2',
                'baseline': {name: [hashes[name]] for name in FILES}, 'files': []}
    for name in FILES:
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(helper if name.endswith('.zip') else SRC / name, target)
        if name.endswith('.py'):
            ast.parse(target.read_text('utf-8'))
        manifest['files'].append({'path': name, 'sha256': sha(target)})
    (payload / 'external-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    installer = (PRIOR / 'install_growth_external.py').read_text('utf-8').replace('1.4.1', '1.4.2')
    installer = installer.replace(
        'Skips confirmed old public content and deduplicates formatting-only post titles.',
        'Recovers exact committed batch receipts after response loss; expired new observations remain rejected.')
    installer = installer.replace(
        'SUCCESS: old-content filtering and same-post duplicate protection installed and verified. Existing reception and helper retained.',
        'SUCCESS: exact receipt recovery and helper download 1.4.5 installed and verified. Existing reception retained.')
    installer = installer.replace('Helper 1.4.3 is compatible.', 'Reload local helper 1.4.5 to apply its loading recovery fixes.')
    (PACKAGE / 'install_growth_external.py').write_text(installer, encoding='utf-8')
    shutil.copy2(PRIOR / 'Install-Growth-External.cmd', PACKAGE / 'Install-Growth-External.cmd')
    for name in TESTS:
        shutil.copy2(SRC / name, PACKAGE / name)
    (PACKAGE / '使用说明.txt').write_text(
        '银杏获客后台1.4.2，适用于已安装1.4.1的服务器。\n'
        '仅更新采集模块、外部模块版本和助手下载ZIP三个文件；不修改业务数据库、客户资料、密钥、限额或微信AI客服配置。\n'
        '修复批次已入库但响应丢失后，原始采集凭据过期导致无法查询同一回执的问题。完全相同且已提交的批次只返回原回执，不重复入库或调用AI；新过期批次仍然拒绝。\n'
        '管理员运行Install-Growth-External.cmd，先校验、预检与备份，短暂重启后核对；失败自动恢复。无需重新填密钥。\n'
        '本机助手1.4.5已包含加载恢复修复，需在既有扩展卡片刷新一次应用。下载包升级不代表浏览器已加载。\n'
        '外部自动发送及视频号自动采集仍未接通。本包不是完整获客验收完成。\n', encoding='utf-8')
    archive = RELEASE / 'GinkgoGrowth-1.4.2.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(PACKAGE.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                zipped.write(path, path.relative_to(PACKAGE.parent))
    result = {'archive': str(archive), 'sha256': sha(archive), 'bytes': archive.stat().st_size,
              'payload_files': FILES, 'live_deployment': False}
    (RELEASE / 'backend-package-1.4.2.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))

if __name__ == '__main__':
    main()
