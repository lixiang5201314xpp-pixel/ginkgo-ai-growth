"""Interactive server-console secret entry. Never accept the API key as a CLI argument."""
from pathlib import Path
import base64
import re
import subprocess
import sys

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'payload'))
from growth_acquisition import Store
from growth_ai import AIService,AIError
TARGET=Path(r'C:\Services\KaiqiuMatch_20260915\growth-data')


def read_key():
    """Visible entry requested by the owner; the key only crosses an anonymous pipe."""
    script=r'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$form=New-Object System.Windows.Forms.Form
$form.Text='DeepSeek API Key - secure setup'
$form.ClientSize=New-Object System.Drawing.Size(560,225)
$form.StartPosition='CenterScreen'
$form.FormBorderStyle='FixedDialog'
$form.MaximizeBox=$false
$form.MinimizeBox=$false
$form.TopMost=$true
$label=New-Object System.Windows.Forms.Label
$label.Location=New-Object System.Drawing.Point(20,18)
$label.Size=New-Object System.Drawing.Size(520,48)
$label.Text='Paste the complete DeepSeek API Key below (Ctrl+V).'+[Environment]::NewLine+'Visible input: check the complete key. Do not share a screenshot.'
$box=New-Object System.Windows.Forms.TextBox
$box.Location=New-Object System.Drawing.Point(20,76)
$box.Size=New-Object System.Drawing.Size(520,30)
$box.UseSystemPasswordChar=$false
$box.MaxLength=310
$box.ShortcutsEnabled=$true
$status=New-Object System.Windows.Forms.Label
$status.Location=New-Object System.Drawing.Point(20,115)
$status.Size=New-Object System.Drawing.Size(520,25)
$status.Text='Waiting for input...'
$box.Add_TextChanged({
    if($box.Text.Length -gt 0){$status.Text='Input received. Click Continue.'}
    else{$status.Text='Waiting for input...'}
})
$ok=New-Object System.Windows.Forms.Button
$ok.Location=New-Object System.Drawing.Point(300,164)
$ok.Size=New-Object System.Drawing.Size(115,34)
$ok.Text='Continue'
$ok.Add_Click({
    if($box.Text.Trim() -notmatch '^sk-[a-zA-Z0-9_-]{12,300}$'){
        $status.Text='Please paste the complete API Key, starting with sk-.'
        return
    }
    $form.DialogResult=[System.Windows.Forms.DialogResult]::OK
    $form.Close()
})
$cancel=New-Object System.Windows.Forms.Button
$cancel.Location=New-Object System.Drawing.Point(425,164)
$cancel.Size=New-Object System.Drawing.Size(115,34)
$cancel.Text='Cancel'
$cancel.DialogResult=[System.Windows.Forms.DialogResult]::Cancel
$form.Controls.AddRange(@($label,$box,$status,$ok,$cancel))
$form.AcceptButton=$ok
$form.CancelButton=$cancel
$form.Add_Shown({$box.Focus()})
if($form.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){
    [Console]::Write($box.Text.Trim())
}
$box.Clear()
$form.Dispose()
'''
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result=subprocess.run(['powershell.exe','-NoProfile','-STA','-EncodedCommand',encoded],
                          capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Secure input window could not open. No key was saved.')
    key=result.stdout.strip()
    if not key:return ''
    if not re.fullmatch(r'sk-[a-zA-Z0-9_-]{12,300}',key):
        raise RuntimeError('API Key format is invalid. No key was saved.')
    return key


def main():
    print('Ginkgo AI secure configuration 1.1.2 / DeepSeek / VISIBLE input window')
    print('No service restart. No generated text. A separate visible input window will open.')
    if not sys.stdin.isatty():raise RuntimeError('Run Configure-AI.cmd directly in your server Remote Desktop console.')
    if not TARGET.is_dir():raise RuntimeError('Install the existing acquisition workbench first.')
    folder=TARGET/'secrets';folder.mkdir(exist_ok=True)
    if folder.resolve().parent!=TARGET.resolve():raise RuntimeError('Unexpected secret directory')
    # Dedicated credential folder, not the application tree or business database.
    from growth_permissions import protect_credentials
    protect_credentials(folder)
    key=read_key()
    if not key:print('CANCELLED: configuration was not changed.');return
    print('API key received. The key itself is hidden.')
    print('AI generation: max 30 requests/day; public web search: max 8 requests/day.')
    print('Only redacted request text and public club data are sent to DeepSeek.')
    print('Usage may be billed by DeepSeek. Automatic scheduled running is OFF.')
    answer=input('Allow this API usage and redacted-data processing? Type YES to save: ').strip()
    if answer.upper()!='YES':print('CANCELLED: key was not saved.');return
    ai=AIService(Store(TARGET))
    ai.configure({'provider':'deepseek','model':'deepseek-flash','api_key':key,'enabled':True,
                  'search_enabled':True,'automatic':False,'daily_ai_limit':30,'daily_search_limit':8,
                  'paid_usage_authorized':True,'data_processing_authorized':True})
    key=''
    result=ai.test_connection()
    if not result['ok']:raise AIError(result['message'],result.get('code','connection'))
    print('SUCCESS: DeepSeek key encrypted and saved; credential/model connection verified.')
    print('No text generation, customer messages, registrations or business-data changes were made.')
    print('The updated workbench will read this configuration after its installation.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('CONFIGURATION NOT VERIFIED: '+str(error));sys.exit(1)
