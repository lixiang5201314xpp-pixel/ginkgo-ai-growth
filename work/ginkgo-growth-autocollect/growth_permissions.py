"""Owner-run ACL repair confined to the dedicated encrypted-credential directory."""
import base64
import os
from pathlib import Path
import subprocess

def protect_credentials(folder):
    folder=Path(folder)
    if folder.name!='secrets' or folder.parent.name!='growth-data':
        raise RuntimeError('Unexpected credential directory; permissions unchanged')
    if folder.is_symlink() or folder.is_junction() or folder.parent.is_symlink() or folder.parent.is_junction():
        raise RuntimeError('Credential directory must not redirect to another path')
    for name in ('deepseek.dpapi','openai.dpapi'):
        if (folder/name).is_symlink() or (folder/name).is_junction():
            raise RuntimeError('Credential files must not redirect to another path')
    folder=folder.resolve()
    # Set folder inheritance rules and DIRECT file rules separately. No recursive
    # inheritance flags on .dpapi files; no Everyone/Users or code-tree grants.
    script=r'''
$ErrorActionPreference='Stop'
$folder=$env:GINKGO_CREDENTIAL_DIR
$operator=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$system='S-1-5-18';$admins='S-1-5-32-544';$service='S-1-5-19'
if(-not [IO.Directory]::Exists($folder)){[void][IO.Directory]::CreateDirectory($folder)}
$inherit=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
$none=[Security.AccessControl.PropagationFlags]::None
$allow=[Security.AccessControl.AccessControlType]::Allow
$dirAcl=New-Object Security.AccessControl.DirectorySecurity
$dirAcl.SetAccessRuleProtection($true,$false)
foreach($sid in @($system,$admins,$operator)){
 $identity=New-Object Security.Principal.SecurityIdentifier($sid)
 $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl',$inherit,$none,$allow)
 $dirAcl.AddAccessRule($rule)
}
$identity=New-Object Security.Principal.SecurityIdentifier($service)
$dirAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'Modify',$inherit,$none,$allow)))
[IO.Directory]::SetAccessControl($folder,$dirAcl)
foreach($name in @('deepseek.dpapi','openai.dpapi')){
 $file=[IO.Path]::Combine($folder,$name)
 if(-not [IO.File]::Exists($file)){continue}
 $fileAcl=New-Object Security.AccessControl.FileSecurity
 $fileAcl.SetAccessRuleProtection($true,$false)
 foreach($sid in @($system,$admins,$operator)){
  $identity=New-Object Security.Principal.SecurityIdentifier($sid)
  $fileAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl',$allow)))
 }
 $identity=New-Object Security.Principal.SecurityIdentifier($service)
 $fileAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'Modify',$allow)))
 [IO.File]::SetAccessControl($file,$fileAcl)
}
[Console]::Write('CREDENTIAL_ACL_PASS')
'''
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                     capture_output=True,timeout=25,env={**os.environ,'GINKGO_CREDENTIAL_DIR':str(folder)})
    if r.returncode or b'CREDENTIAL_ACL_PASS' not in r.stdout:
        raise RuntimeError('Encrypted-key permission repair failed. No key was changed and no service was restarted.')
