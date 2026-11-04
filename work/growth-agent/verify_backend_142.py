"""Verify the frozen package against both actual release layouts using isolated data."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'work/ginkgo-growth-autocollect'
RELEASE = ROOT / 'work/release/growth-dev-20261102'
sys.path.insert(0, str(SRC))
import test_external_patch_package as rollback
from test_collection_package import InstallerChecks
from test_packaged_workflow import copy_release
from package_collection_patch import CHAIN, WORK, sha

PACKAGE = RELEASE / 'GinkgoGrowth-1.4.2'
rollback.PACKAGE = PACKAGE
checks = unittest.TextTestRunner(verbosity=1).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(InstallerChecks))
assert checks.wasSuccessful()
results = []
with tempfile.TemporaryDirectory(prefix='ginkgo-142-') as temporary:
    root = Path(temporary)
    runtime = root / 'runtime'
    runtime.mkdir()
    for folder, name in CHAIN + [('growth-collection-patch-20261101/GinkgoGrowth-1.4.1', 'external-manifest.json')]:
        copy_release(WORK / 'release' / folder, name, runtime)
    frozen = root / 'package'
    shutil.copytree(PACKAGE, frozen)
    manifest = json.loads((frozen / 'payload/external-manifest.json').read_text('utf-8'))
    for name, values in manifest['baseline'].items():
        assert sha(runtime / name) in values, name
    retained = {name: sha(runtime / name) for name in (
        'growth_acquisition.py', 'growth_automation.py', 'growth_ai.py', 'growth_channels.py', 'growth_playbook.json')}
    for mode in ('overlay-preflight', 'installed-runtime'):
        if mode == 'installed-runtime':
            copy_release(frozen, 'external-manifest.json', runtime)
        paths = ([frozen / 'payload'] if mode == 'overlay-preflight' else []) + [
            runtime, runtime / 'channel-vendor', WORK / 'python-deps']
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPATH': os.pathsep.join(map(str, paths))}
        for name in ('test_external.py', 'test_workflow.py', 'test_growth.py', 'test_delivery.py', 'test_collection.py'):
            command = [sys.executable, str(frozen / name)]
            if name == 'test_growth.py':
                code = 'from pathlib import Path;import growth_acquisition as m,runpy;m.BASE=Path(' + repr(str(runtime)) + ');runpy.run_path(' + repr(str(frozen / name)) + ',run_name="__main__")'
                command = [sys.executable, '-c', code]
            result = subprocess.run(command, capture_output=True, timeout=90, env=env, cwd=root)
            output = result.stderr.decode('utf-8', 'replace')
            if result.returncode:
                print(output[-6000:])
                raise AssertionError(mode + '/' + name)
            count = re.search(r'Ran (\d+) tests?', output)
            results.append({'layout': mode, 'suite': name, 'tests': int(count[1]) if count else None, 'passed': True})
        for name, value in retained.items():
            assert sha(runtime / name) == value, name
        print('PASS: ' + mode + '; WeChat reception, AI, limits and core source retained.', flush=True)
report = {'passed': True, 'installer_checks': checks.testsRun, 'layouts': results,
          'live_api_calls': 0, 'customer_messages': 0, 'business_database_writes': 0,
          'live_deployment': False}
(RELEASE / 'backend-1.4.2-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
