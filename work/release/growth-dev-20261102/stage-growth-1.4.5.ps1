
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$parent='C:\Services\GinkgoTrainingAutoCancel'
$archive='C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.5.zip'
$packageRoot=[IO.Path]::GetFullPath((Join-Path $parent 'GinkgoGrowth-1.4.5'))
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne '948e30c1825f7dba3fac13159947ccdd3b90488b31333e9c1fb7652e15a05777') { throw 'Archive checksum mismatch' }
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
Write-Output 'STAGED: growth-external-1.4.5; all 4 payload hashes verified. Installer was NOT executed. No service or business data changed.'
