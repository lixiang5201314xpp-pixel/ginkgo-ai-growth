"""Real Windows ACL/DPAPI checks confined to disposable synthetic credentials."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from growth_permissions import protect_credentials
from growth_ai import Vault

class Tests(unittest.TestCase):
    def test_rejects_any_other_directory(self):
        for p in [Path('C:/Windows'),Path('C:/Temp/secrets')]:
            with self.assertRaises(RuntimeError):protect_credentials(p)

    @unittest.skipUnless(os.name=='nt','Windows ACL')
    def test_real_file_acl_preserves_ciphertext_and_allows_rotation(self):
        with tempfile.TemporaryDirectory(prefix='growth-acl-test-') as tmp:
            root=Path(tmp)/'growth-data';root.mkdir();vault=Vault(root)
            vault.put('deepseek','sk-synthetic-acl-test-only')
            cipher=(root/'secrets/deepseek.dpapi').read_bytes()
            protect_credentials(root/'secrets')
            self.assertEqual((root/'secrets/deepseek.dpapi').read_bytes(),cipher)
            self.assertEqual(vault.get('deepseek'),'sk-synthetic-acl-test-only')
            vault.put('deepseek','sk-synthetic-rotation-only')
            self.assertEqual(vault.get('deepseek'),'sk-synthetic-rotation-only')

    @unittest.skipUnless(os.name=='nt','Windows ACL')
    def test_credential_file_gets_direct_rules_without_world_access(self):
        with tempfile.TemporaryDirectory(prefix='growth-acl-test-') as tmp:
            root=Path(tmp)/'growth-data';root.mkdir();vault=Vault(root);vault.put('deepseek','sk-synthetic-acl-test-only')
            protect_credentials(root/'secrets')
            script="[IO.File]::GetAccessControl($env:GINKGO_TEST_CIPHER).GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | Select-Object @{n='sid';e={$_.IdentityReference.Value}},@{n='flags';e={[int]$_.InheritanceFlags}},IsInherited | ConvertTo-Json -Compress"
            r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,
                             env={**os.environ,'GINKGO_TEST_CIPHER':str(root/'secrets/deepseek.dpapi')},check=True)
            rows=json.loads(r.stdout)
            self.assertTrue(all(x['flags']==0 and not x['IsInherited'] for x in rows))
            sids={x['sid'] for x in rows}
            self.assertIn('S-1-5-19',sids);self.assertIn('S-1-5-32-544',sids)
            self.assertNotIn('S-1-1-0',sids);self.assertNotIn('S-1-5-32-545',sids)

    def test_native_failure_does_not_look_successful(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'growth-data/secrets';p.mkdir(parents=True)
            with patch('growth_permissions.subprocess.run') as mocked:
                mocked.return_value.returncode=1;mocked.return_value.stdout=b''
                with self.assertRaises(RuntimeError):protect_credentials(p)

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    Path(__file__).with_name('permissions-verification.json').write_text(json.dumps({'passed':r.wasSuccessful(),'tests':r.testsRun,'production_changes':False},indent=2),'utf-8')
    raise SystemExit(not r.wasSuccessful())
