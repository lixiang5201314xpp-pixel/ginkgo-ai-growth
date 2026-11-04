"""Transfer a verified archive to the permitted staging directory, never install it."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
RELEASE=ROOT/'work/release/growth-dev-20261102'
report_path=RELEASE/'backend-package-1.4.3.json'
proof=json.loads((RELEASE/'backend-1.4.3-verification.json').read_text('utf-8'))
assert proof['passed'] and proof['live_api_calls']==0
meta=json.loads(report_path.read_text('utf-8'))
archive=RELEASE/'GinkgoGrowth-1.4.3.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==meta['sha256']
remote=r'C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.3.zip'
copied=subprocess.run([sys.executable,str(ROOT/'work/tools/push_remote_file.py'),str(archive),remote],
                      capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
if copied.returncode:
    print(copied.stdout[-2000:]);print(copied.stderr[-2000:]);raise RuntimeError('Staging transfer failed')
print(copied.stdout.strip())
script=r'''
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$parent='C:\Services\GinkgoTrainingAutoCancel'
$archive='C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.3.zip'
$packageRoot=[IO.Path]::GetFullPath((Join-Path $parent 'GinkgoGrowth-1.4.3'))
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ARCHIVE_HASH') { throw 'Archive checksum mismatch' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($archive)
try {
  foreach ($entry in $zip.Entries) {
    $resolved=[IO.Path]::GetFullPath((Join-Path $parent $entry.FullName))
    if ($resolved -ne $packageRoot -and -not $resolved.StartsWith($packageRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Archive entry leaves intended staging package' }
  }
} finally { $zip.Dispose() }
if (Test-Path -LiteralPath (Join-Path $packageRoot 'external-install-result.json')) { throw 'Installation result exists; do not overwrite this staging package' }
Expand-Archive -LiteralPath $archive -DestinationPath $parent -Force
$manifest=Get-Content -LiteralPath (Join-Path $packageRoot 'payload\external-manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files) {
  $target=[IO.Path]::GetFullPath((Join-Path (Join-Path $packageRoot 'payload') $entry.path))
  if (-not $target.StartsWith($packageRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Payload path leaves staging' }
  if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw 'Staged payload checksum mismatch' }
}
if (-not (Test-Path -LiteralPath (Join-Path $packageRoot 'Install-Growth-External.cmd'))) { throw 'Installer launcher missing' }
Write-Output 'STAGED: growth-external-1.4.3; all 4 payload hashes verified. Installer was NOT executed. No service or business data changed.'
'''.replace('ARCHIVE_HASH',meta['sha256'])
script_path=RELEASE/'stage-growth-1.4.3.ps1'
script_path.write_text(script,encoding='utf-8')
script_remote=r'C:\Services\GinkgoTrainingAutoCancel\Stage-Growth-1.4.3.ps1'
stager=subprocess.run([sys.executable,str(ROOT/'work/tools/push_remote_file.py'),str(script_path),script_remote],
                      capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
if stager.returncode:
    print(stager.stdout[-2000:]);print(stager.stderr[-2000:]);raise RuntimeError('Staging-script transfer failed')
command='powershell -NoProfile -NonInteractive -File '+script_remote
expanded=subprocess.run([sys.executable,str(ROOT/'work/tools/remote_command.py'),command],
                        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
log=copied.stdout+stager.stdout+expanded.stdout+expanded.stderr
(RELEASE/'backend-1.4.3-staging.txt').write_text(log,encoding='utf-8')
if expanded.returncode or 'STAGED: growth-external-1.4.3' not in expanded.stdout:
    print(expanded.stdout[-3000:]);print(expanded.stderr[-2000:]);raise RuntimeError('Staged extraction/verification failed')
meta.update(staged_on_server=True,staging_directory=r'C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.3',installer_executed=False)
report_path.write_text(json.dumps(meta,indent=2),encoding='utf-8')
print('STAGED and hash verified. Installer not executed; live service version unchanged.')
