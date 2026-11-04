import json
from pathlib import Path

root=Path(__file__).resolve().parents[2]
release=root/'work/release/growth-collection-20261101'
path=release/'status.json'
data=json.loads(path.read_text(encoding='utf-8'))
data.update({
    'local_helper_version':'1.4.3','local_extension_reload_pending':True,
    'helper_1_4_2_owner_restarted_from_search':True,
    'helper_1_4_2_last_observed_pause':{
        'observed_cst':'2026-11-01 18:18:33',
        'reason':'原帖未能打开，已停止本轮，避免把搜索页当原文',
        'rounds_completed_this_attempt':0,'new_valid_leads':0,
    },
    'navigation_evidence':{
        'tab_metadata_url':'https://www.douyin.com/search/成都 乒乓球 找教练',
        'actual_document_url':'https://www.douyin.com/video/7669322400018301029',
        'actual_document_h1':'怎么才能找到适合自己的乒乓球教练？',
        'fix':'Use actual inspected document URL; canonicalize displayed modal links before navigation; wait up to three inspections for transitional documents; never double click or count partial navigation as a completed empty round.',
    },
    'helper_1_4_3_live_cycle_verified':False,
    'helper_1_4_3_tests':{'state_flow':18,'browser_capture':16,'read_only_status_bridge':5},
    'server_patch_version':'growth-external-1.4.1',
    'server_patch_staged_hashes_verified':True,'server_patch_owner_install_pending':True,
    'server_patch_archive_sha256':'09b1cc74738bb18224d5d51b2f3a90bebc18397bf89a17ab82d6e1b0238eb8ce',
    'server_patch_scope':'Four acquisition files only. Skip known older-than-30-day sources, normalize formatting-only post titles on the same original URL, show skipped counts, update helper download. No schema changes or existing-record repair.',
    'server_patch_tests':{'collection_suite_including_inherited_checks':44,'installer_rollback':8,'frozen_layouts':2},
    'next':['Owner installs staged server patch 1.4.1 from its new fixed directory.',
            'Owner reloads local helper 1.4.3 once and starts on the public search results.',
            'Verify one actual complete round and its automatic cooldown without relying only on a started label.'],
})
assert data['codex_recurring_agent_status']=='PAUSED'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('continuous-verification.json','capture-browser-verification.json','status-bridge-verification.json','collection-patch-package-verification.json'):
    source=Path(__file__).parent/name
    (root/'work/release/growth-collection-patch-20261101'/name).write_bytes(source.read_bytes())
print('PASS: final helper/server patch evidence recorded. Actual new-version installation and complete live cycle remain pending.')
