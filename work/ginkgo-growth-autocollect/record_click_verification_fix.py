import json
from pathlib import Path

release=Path(__file__).resolve().parents[1]/'release/growth-collection-20261101'
path=release/'status.json'
data=json.loads(path.read_text(encoding='utf-8'))
data.update({
    'local_helper_version':'1.4.2',
    'local_helper_files_updated_and_verified':True,
    'local_extension_reload_pending':True,
    'helper_1_4_1_owner_started':True,
    'helper_1_4_1_observed_pause_reason':'搜索结果未能打开，停止本轮',
    'helper_1_4_2_live_cycle_verified':False,
    'click_fix':{
        'real_ui_check':'The exact search title opened modal_id=7630255064422560869 after a short page transition. No platform message was sent.',
        'behavior':'Return a scheduled-click acknowledgement before the click can change its document; verify the actual detail URL on the next step. Missing return is not classified as failure, and no double click is performed.',
        'read_only_monitor':'Shows helper version, phase, pause reason, completed and empty rounds, added-valid count, and next-run time in the existing workbench.',
        'permissions_changed':False,
        'server_restart_required':False,
        'tests':{'scheduler_state_flow':12,'browser_capture':16,'read_only_status_bridge':5},
    },
    'next':['Owner reloads existing Chrome helper 1.4.2 and starts the current public search once.',
            'Read the local-helper status card and server receipts. Verify actual detail opening and date capture before claiming the new fix complete.'],
})
assert data['codex_recurring_agent_status']=='PAUSED'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: helper 1.4.2 fix and test evidence saved; real-cycle verification remains explicitly pending owner reload.')
