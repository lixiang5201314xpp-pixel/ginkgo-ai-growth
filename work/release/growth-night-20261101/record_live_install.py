"""Record independently verified installation and visible UI milestones only."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json

ROOT=Path(__file__).resolve().parent
status=json.loads((ROOT/'status.json').read_text('utf-8'))
installed=json.loads((ROOT/'external-install-result.json').read_text('utf-8'))
assert installed['success'] and installed['version']=='growth-external-1.3.1'
status.update(backend_installed=True,owner_install_pending=False,local_extension_reload_pending=False,
    live_verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    live_version='growth-external-1.3.1',backup=installed['backup'],
    workbench_blocker='',production_leads_imported=1,production_contacts_recorded=1,
    ai_prepared_replies_live_verified=1,automatic_platform_sending_connected=False)
status['platform_blockers']['xiaohongshu']='普通内容账号已登录；已找到儿童训练询价原帖，评论提交状态待核实，不计为已联系。'
status['existing_service_health']={'/health':{'status':200},'/growth/external/health':{'status':200,'version':'growth-external-1.3.1'},'/growth/channels/health':{'status':200,'version':'growth-channels-1.0.0'},'/growth/api/external':{'status':401}}
(ROOT/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),'utf-8')
ledger=json.loads((ROOT/'contact-ledger.json').read_text('utf-8'))
ledger['verified_contacts'][0].update(backend_imported=True,backend_contact_recorded=True,duplicate_contact_block_visible=True)
(ROOT/'contact-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),'utf-8')
print('Recorded: installed 1.3.1; live AI draft and one recorded contact verified. No application or production data changed by this script.')
