import json
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'release/growth-collection-20261101/status.json'
data=json.loads(path.read_text(encoding='utf-8'))
data['last_helper_status_ui_verified']={
    'version':'1.4.2','status':'paused','completed_rounds':1,'empty_rounds':1,
    'new_valid_leads':0,'observed_cst':'2026-11-01 18:21:14',
    'reason':'当前原帖采集完成；请从搜索结果页启动以连续扫描新作品',
}
data['latest_owner_action_pending']={
    'server':r'C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.1\Install-Growth-External.cmd',
    'server_archive_sha256':'09b1cc74738bb18224d5d51b2f3a90bebc18397bf89a17ab82d6e1b0238eb8ce',
    'local_helper_files_version':'1.4.3',
    'extension_reload_required':True,
    'start_from':'Logged-in public search results, not a single canonical video or the recommendation homepage.',
}
assert data['server_patch_owner_install_pending'] is True
assert data['codex_recurring_agent_status']=='PAUSED'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved verified paused state and exact pending installation steps. No automation was restarted.')
