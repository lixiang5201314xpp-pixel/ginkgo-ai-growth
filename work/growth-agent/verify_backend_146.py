"""Verify GinkgoGrowth-1.4.6 layouts, retention, and extended preflight suites (offline only)."""
from pathlib import Path
import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import hashlib

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/ginkgo-growth-autocollect'
RELEASE = ROOT / 'work/release/growth-dev-20261102'
PRIOR = RELEASE / 'GinkgoGrowth-1.4.5'
PACKAGE = RELEASE / 'GinkgoGrowth-1.4.6'
FROZEN = RELEASE / 'GinkgoGrowth-1.4.5.zip'
sys.path.insert(0, str(SRC))
import test_external_patch_package as rollback  # noqa: E402
from test_collection_package import InstallerChecks  # noqa: E402
from test_packaged_workflow import WORK, copy_release  # noqa: E402

PYTHON = ROOT / 'yinxing-dev' / '.venv' / 'bin' / 'python'
if not PYTHON.is_file():
    PYTHON = Path(sys.executable)

PACKAGE_ORDER = [
    ('1.4.1', WORK / 'release/growth-collection-patch-20261101/GinkgoGrowth-1.4.1'),
    ('1.4.2', RELEASE / 'GinkgoGrowth-1.4.2'),
    ('1.4.3', RELEASE / 'GinkgoGrowth-1.4.3'),
    ('1.4.4', RELEASE / 'GinkgoGrowth-1.4.4'),
    ('1.4.5', RELEASE / 'GinkgoGrowth-1.4.5'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

rollback.PACKAGE = PACKAGE

SUITES = (
    'test_growth.py', 'test_ai.py', 'test_workflow.py', 'test_external.py', 'test_delivery.py',
    'test_collection.py', 'test_job_intent.py', 'test_practice_intent.py',
    'test_delivery_source.py', 'test_source_dedup.py',
)


class FinalInstallerChecks(InstallerChecks):
    def setUp(self):
        super().setUp()
        manifest_path = self.m.PAYLOAD / 'external-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'] = [x for x in manifest['files'] if x['path'] != 'growth-web/external.js']
        manifest['baseline'].pop('growth-web/external.js', None)
        if 'growth-web/external.js' in self.names:
            self.names.remove('growth-web/external.js')
        for name, body in (
            ('growth_collection.py', ('old_collection=True', 'new_collection=True')),
            ('growth_acquisition.py', ('old_classifier=True', 'new_classifier=True')),
        ):
            self.names.append(name)
            (self.m.TARGET / name).write_text(body[0])
            (self.m.PAYLOAD / name).write_text(body[1])
            manifest['baseline'][name] = [sha(self.m.TARGET / name)]
            manifest['files'].append({'path': name, 'sha256': sha(self.m.PAYLOAD / name)})
        manifest_path.write_text(json.dumps(manifest))
        (self.m.TARGET / 'identity.py').write_text('existing_phone_identity_102=True')
        for protected in ('growth_ai.py', 'growth_channels.py', 'growth_playbook.json'):
            (self.m.TARGET / protected).write_text(f'protected_{protected}=True')

    def test_installs_only_payload(self):
        super().test_installs_only_payload()
        self.assertEqual((self.m.TARGET / 'growth_acquisition.py').read_text(), 'new_classifier=True')
        self.assertEqual((self.m.TARGET / 'identity.py').read_text(), 'existing_phone_identity_102=True')
        self.assertEqual((self.m.TARGET / 'growth_ai.py').read_text(), 'protected_growth_ai.py=True')

    def test_start_failure_rolls_back(self):
        super().test_start_failure_rolls_back()
        self.assertEqual((self.m.TARGET / 'growth_acquisition.py').read_text(), 'old_classifier=True')

    def test_health_failure_rolls_back(self):
        super().test_health_failure_rolls_back()
        self.assertEqual((self.m.TARGET / 'growth_acquisition.py').read_text(), 'old_classifier=True')

    def test_unrelated_identity_cannot_be_added_to_payload(self):
        path = self.m.PAYLOAD / 'external-manifest.json'
        manifest = json.loads(path.read_text())
        (self.m.PAYLOAD / 'identity.py').write_text('unexpected_identity=True')
        manifest['files'].append({'path': 'identity.py', 'sha256': sha(self.m.PAYLOAD / 'identity.py')})
        path.write_text(json.dumps(manifest))
        with self.assertRaises(RuntimeError):
            self.run_install()
        self.assertEqual(self.actions, [])
        self.assertEqual((self.m.TARGET / 'identity.py').read_text(), 'existing_phone_identity_102=True')

    def test_every_embedded_preflight_command_compiles_and_uses_runtime_assets(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location('final_preflight', PACKAGE / 'install_growth_external.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.BASE = self.m.BASE
        module.TARGET = self.m.TARGET
        commands = []

        def fake(command, **kwargs):
            self.assertIn('-c', command)
            self.assertIn(str(module.BASE), kwargs['env']['PYTHONPATH'].split(os.pathsep))
            code = command[command.index('-c') + 1]
            ast.parse(code)
            self.assertIn(repr(str(module.TARGET)), code)
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=b'isolated preflight', stderr=b'')

        original = module.subprocess.run
        try:
            module.subprocess.run = fake
            with contextlib.redirect_stdout(io.StringIO()):
                module.preflight()
        finally:
            module.subprocess.run = original
        self.assertEqual(len(commands), len(SUITES) + 1)


checks = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(FinalInstallerChecks))
assert checks.wasSuccessful(), 'Installer simulation failed'

assert sha(FROZEN) == '948e30c1825f7dba3fac13159947ccdd3b90488b31333e9c1fb7652e15a05777'

manifest = json.loads((PACKAGE / 'payload/external-manifest.json').read_text('utf-8'))
with zipfile.ZipFile(PACKAGE / 'payload/growth-web/browser-helper.zip') as z:
    assert json.loads(z.read('browser-helper/manifest.json'))['version'] == '1.4.9'

results = []
with tempfile.TemporaryDirectory(prefix='ginkgo-146-frozen-') as temporary:
    base = Path(temporary)
    for baseline in ('1.4.1', '1.4.2', '1.4.3', '1.4.5'):
        runtime = base / baseline
        runtime.mkdir()
        for version, package_dir in PACKAGE_ORDER:
            copy_release(package_dir, 'external-manifest.json', runtime)
            if version == baseline:
                break
        (runtime / 'identity.py').write_text('existing_phone_identity_102=True', encoding='utf-8')
        acq_seed = PRIOR / 'payload/growth_acquisition.py'
        if not (runtime / 'growth_acquisition.py').is_file() and acq_seed.is_file():
            shutil.copy2(acq_seed, runtime / 'growth_acquisition.py')
        for protected in ('growth_ai.py', 'growth_channels.py', 'growth_automation.py', 'growth_playbook.json'):
            src = SRC / protected
            if src.is_file():
                shutil.copy2(src, runtime / protected)
            else:
                (runtime / protected).write_text(f'protected_{protected}=True', encoding='utf-8')
        for extra in ('growth_workflow.py', 'growth_permissions.py'):
            src = SRC / extra
            if src.is_file():
                shutil.copy2(src, runtime / extra)
        web_dest = runtime / 'growth-web'
        web_dest.mkdir(parents=True, exist_ok=True)
        for item in (SRC / 'growth-web').iterdir():
            if item.is_file() and not (web_dest / item.name).is_file():
                shutil.copy2(item, web_dest / item.name)
        for name, values in manifest['baseline'].items():
            path = runtime / name
            if not path.is_file():
                continue
            assert sha(path) in values, (baseline, name)
        retained = {
            name: sha(runtime / name)
            for name in ('growth_ai.py', 'growth_channels.py', 'growth_automation.py', 'growth_playbook.json', 'identity.py')
        }
        for mode in ('overlay-preflight', 'installed-runtime'):
            if mode == 'installed-runtime':
                copy_release(PACKAGE, 'external-manifest.json', runtime)
            paths = ([PACKAGE / 'payload'] if mode == 'overlay-preflight' else []) + [PACKAGE, runtime, SRC]
            env = {
                **os.environ,
                'PYTHONIOENCODING': 'utf-8',
                'PYTHONDONTWRITEBYTECODE': '1',
                'PYTHONPATH': os.pathsep.join(map(str, paths)),
            }
            for name in SUITES:
                code = (
                    'from pathlib import Path;import growth_acquisition as m,runpy;'
                    f'm.BASE=Path({repr(str(runtime))});runpy.run_path({repr(str(PACKAGE / name))},run_name="__main__")'
                )
                proc = subprocess.run([str(PYTHON), '-c', code], capture_output=True, timeout=120, env=env, cwd=base)
                output = proc.stderr.decode('utf-8', 'replace') + proc.stdout.decode('utf-8', 'replace')
                if proc.returncode:
                    print(output[-6500:], flush=True)
                    raise AssertionError(f'{baseline}/{mode}/{name}')
                count = re.search(r'Ran (\d+) tests?', output)
                results.append({
                    'baseline': baseline,
                    'layout': mode,
                    'suite': name,
                    'tests': int(count[1]) if count else None,
                    'passed': True,
                })
            for name, value in retained.items():
                assert sha(runtime / name) == value, name
            print(f'PASS: {baseline} {mode}; suites + support retention.', flush=True)

report = {
    'passed': True,
    'package_version': 'growth-external-1.4.6',
    'installer_checks': checks.testsRun,
    'layouts': results,
    'total_test_executions': checks.testsRun + sum(x['tests'] or 0 for x in results),
    'helper_version': '1.4.9',
    'frozen_1.4.5_zip_sha256': sha(FROZEN),
    'live_api_calls': 0,
    'platform_messages': 0,
    'business_database_writes': 0,
    'live_deployment': False,
    'note': 'Repeated suites across supported baseline/layout combinations; not unique feature count.',
}
(RELEASE / 'backend-1.4.6-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
