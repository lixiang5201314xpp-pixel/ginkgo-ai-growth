"""Build immutable GinkgoGrowth-1.4.6: source dedup + delivery receipt fix on 1.4.5 baseline."""
from pathlib import Path
import ast
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/ginkgo-growth-autocollect'
RELEASE = ROOT / 'work/release/growth-dev-20261102'
PRIOR = RELEASE / 'GinkgoGrowth-1.4.5'
PACKAGE = RELEASE / 'GinkgoGrowth-1.4.6'
FROZEN_ZIP = RELEASE / 'GinkgoGrowth-1.4.5.zip'
FILES = ['growth_acquisition.py', 'growth_collection.py', 'growth_external.py', 'growth-web/browser-helper.zip']
TESTS = [
    'test_growth.py', 'test_ai.py', 'test_workflow.py', 'test_external.py', 'test_delivery.py',
    'test_collection.py', 'test_job_intent.py', 'test_practice_intent.py',
    'test_delivery_source.py', 'test_source_dedup.py',
]
EXPECTED_ACQUISITION = '3afbc73ed2357204bc4cb8ed1e673851bf40655ce3753b06929d71de5e732c81'
INVENTORY = json.loads((ROOT / 'docs/current-source-inventory.json').read_text('utf-8'))

sys.path.insert(0, str(SRC))
from test_packaged_workflow import WORK, copy_release  # noqa: E402

PACKAGE_ORDER = [
    ('1.4.1', WORK / 'release/growth-collection-patch-20261101/GinkgoGrowth-1.4.1'),
    ('1.4.2', RELEASE / 'GinkgoGrowth-1.4.2'),
    ('1.4.3', RELEASE / 'GinkgoGrowth-1.4.3'),
    ('1.4.4', RELEASE / 'GinkgoGrowth-1.4.4'),
    ('1.4.5', RELEASE / 'GinkgoGrowth-1.4.5'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def absorb_manifest(baseline, package_dir):
    manifest = json.loads((package_dir / 'payload/external-manifest.json').read_text('utf-8'))
    for name in FILES:
        for value in manifest.get('baseline', {}).get(name, []):
            if value not in baseline[name]:
                baseline[name].append(value)
        for item in manifest['files']:
            if item['path'] == name and item['sha256'] not in baseline[name]:
                baseline[name].append(item['sha256'])


def main():
    assert FROZEN_ZIP.is_file(), 'Missing frozen 1.4.5 archive'
    assert sha(FROZEN_ZIP) == '948e30c1825f7dba3fac13159947ccdd3b90488b31333e9c1fb7652e15a05777', 'Do not rewrite frozen 1.4.5.zip'
    assert (RELEASE / 'backend-1.4.5-verification.json').is_file(), '1.4.5 must stay verified before building 1.4.6'
    if PACKAGE.exists():
        raise RuntimeError('Remove GinkgoGrowth-1.4.6 manually before rebuild; never overwrite in place silently')
    assert sha(SRC / 'growth_acquisition.py') == EXPECTED_ACQUISITION

    baseline = {name: [] for name in FILES}
    frozen_manifest = json.loads((PRIOR / 'payload/external-manifest.json').read_text('utf-8'))
    for name in FILES:
        for value in frozen_manifest['baseline'].get(name, []):
            if value not in baseline[name]:
                baseline[name].append(value)
        payload_hash = next(x['sha256'] for x in frozen_manifest['files'] if x['path'] == name)
        if payload_hash not in baseline[name]:
            baseline[name].append(payload_hash)

    for _, package_dir in PACKAGE_ORDER:
        if package_dir.is_dir():
            absorb_manifest(baseline, package_dir)
    with tempfile.TemporaryDirectory(prefix='ginkgo-146-baseline-') as temporary:
        runtime = Path(temporary)
        for _, package_dir in PACKAGE_ORDER:
            copy_release(package_dir, 'external-manifest.json', runtime)
        for name in FILES:
            path = runtime / name
            if path.is_file():
                value = sha(path)
                if value not in baseline[name]:
                    baseline[name].append(value)

    helper = RELEASE / '银杏获客助手-1.4.9.zip'
    proof = json.loads((RELEASE / 'helper-package-1.4.9.json').read_text('utf-8'))
    assert sha(helper) == proof['archive_sha256'] and proof['permissions_unchanged']
    with zipfile.ZipFile(helper) as z:
        assert json.loads(z.read('browser-helper/manifest.json'))['version'] == '1.4.9'

    payload = PACKAGE / 'payload'
    payload.mkdir(parents=True, exist_ok=True)
    manifest = {
        'version': 'growth-external-1.4.6',
        'installer_version': '1.4.6',
        'baseline': baseline,
        'files': [],
    }
    for name in FILES:
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(helper if name.endswith('.zip') else SRC / name, target)
        if name == 'growth_external.py':
            source = target.read_text('utf-8')
            assert 'growth-external-1.4.3' in source
            target.write_text(source.replace('growth-external-1.4.3', 'growth-external-1.4.6'), encoding='utf-8')
        if name.endswith('.py'):
            ast.parse(target.read_text('utf-8'))
        manifest['files'].append({'path': name, 'sha256': sha(target)})

    assert manifest['files'][0]['sha256'] == EXPECTED_ACQUISITION
    (payload / 'external-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    installer = (PRIOR / 'install_growth_external.py').read_text('utf-8').replace('1.4.5', '1.4.6')
    old_tests = "'test_job_intent.py', 'test_practice_intent.py']"
    new_tests = "'test_job_intent.py', 'test_practice_intent.py', 'test_delivery_source.py', 'test_source_dedup.py']"
    if old_tests not in installer:
        raise RuntimeError('Unexpected installer preflight list in 1.4.5 template')
    installer = installer.replace(old_tests, new_tests)
    installer = installer.replace(
        'recognizes explicit practice requests and excludes provider replies/job-seeking advertisements and verifies helper download 1.4.9',
        'binds public original-post receipts, fixes source dedup aliases/query fingerprints, keeps stopped/contact_count, and verifies helper download 1.4.9',
    )
    installer = installer.replace(
        'source-role filtering, exact receipt recovery and helper download 1.4.9 installed and verified',
        'source dedup, public-post receipt binding and helper download 1.4.9 installed and verified',
    )
    ast.parse(installer)
    (PACKAGE / 'install_growth_external.py').write_text(installer, encoding='utf-8')
    shutil.copy2(PRIOR / 'Install-Growth-External.cmd', PACKAGE / 'Install-Growth-External.cmd')
    for name in TESTS:
        shutil.copy2(SRC / name, PACKAGE / name)

    retention = {
        'protected_support_files': {
            k: INVENTORY['local_source'][k]
            for k in ('growth_ai.py', 'growth_channels.py', 'growth_playbook.json')
        },
        'known_installed_retained_hashes': INVENTORY['known_installed_retained_hashes'],
        'miniapp_update': 'miniapp-update-1.4.0',
        'limits_note': 'Installer preflight does not modify daily search/AI quotas (20/30) or business SQLite.',
        'payload_only': FILES,
    }
    (PACKAGE / 'source-retention-1.4.6.json').write_text(json.dumps(retention, indent=2), encoding='utf-8')

    (PACKAGE / '使用说明.txt').write_text(
        '银杏获客后台 1.4.6，可从正式 1.4.1 或已暂存 1.4.5 直接升级；不要改写冻结 1.4.5 ZIP。\n'
        '合并 round-010 公开原帖回执绑定与来源去重修复（含 test_delivery_source / test_source_dedup 预检）。\n'
        '命中旧线索时保留 stopped 与 contact_count，不重置联系状态。\n'
        '只更换 4 个获客文件；identity.py、miniapp-update1.4.0 核心、微信客服 growth_ai/channels/playbook、20/30 限额与业务数据均保留。\n'
        '管理员在 C:/Services/GinkgoTrainingAutoCancel/GinkgoGrowth-1.4.6 运行 Install-Growth-External.cmd；先预检、备份、短暂停服，失败自动回滚。\n'
        'Chrome 需本人刷新既有银杏助手 1.4.9；下载包升级不等于浏览器已加载。\n'
        '抖音原帖 7702708741762243570 已人工回复可见，部署后只补登记回执与时间 2026-10-31 14:03:54，禁止重发。\n'
        '外部自动发送及全平台闭环仍未接通，不是最终交付完成声明。\n',
        encoding='utf-8',
    )

    archive = RELEASE / 'GinkgoGrowth-1.4.6.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(PACKAGE.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                z.write(path, path.relative_to(PACKAGE.parent))

    result = {
        'archive': str(archive),
        'sha256': sha(archive),
        'bytes': archive.stat().st_size,
        'payload_files': FILES,
        'payload_sha256': {x['path']: x['sha256'] for x in manifest['files']},
        'compatible_baselines': ['1.4.1', '1.4.2', '1.4.3', '1.4.5', 'growth-external-1.4.1-live'],
        'helper_version': '1.4.9',
        'frozen_1.4.5_zip_unchanged': sha(FROZEN_ZIP),
        'live_deployment': False,
        'platform_auto_sending_connected': False,
    }
    (RELEASE / 'backend-package-1.4.6.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
