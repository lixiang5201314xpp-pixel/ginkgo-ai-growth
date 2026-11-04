import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
release = ROOT / 'work/release/growth-collection-20261101'
record = {
    'version': 'growth-external-1.4.0',
    'recorded_at': datetime.now().astimezone().isoformat(),
    'server_staged_and_payload_hashes_verified': True,
    'owner_reported_install_success': True,
    'owner_install_backup': r'C:\Services\GinkgoTrainingAutoCancel\GinkgoGrowth-1.4.0\backups\external-20261101-135835',
    'service_owner_reported': 'KaiqiuMatchCenter RUNNING',
    'local_helper_files_updated_and_verified': True,
    'local_helper_version': '1.4.0',
    'local_extension_reload_pending': True,
    'automatic_intake_enabled_live_verified': False,
    'continuous_browser_round_live_verified': False,
    'external_automatic_sending_connected': False,
    'channels_browser_collection_connected': False,
    'production_leads_last_ui_verified': 3,
    'production_contacts_last_ui_verified': 1,
    'production_bookings_last_ui_verified': 0,
    'new_xhs_training_lead': {
        'source': 'https://www.xiaohongshu.com/explore/6ae233c7000000003501eedb',
        'original_ui_date': '3天前 四川',
        'source_and_image_reviewed': True,
        'ai_draft_prepared_live_verified': True,
        'contacted': False,
    },
    'codex_recurring_agent_status': 'PAUSED',
    'browser_blocker': 'Windows browser control stopped because the current Chrome URL could not be determined reliably. Do not retry UI control in the blocked turn.',
    'next': [
        'Owner reloads the pre-existing Chrome helper; verify version 1.4.0.',
        'Refresh production workbench; enable Automatic Intake and AI Preparation.',
        'Start helper from a logged-in public search page and verify a real collection receipt, not merely a draft or an enabled switch.',
    ],
    'verification_files': [
        'work/ginkgo-growth-autocollect/capture-browser-verification.json',
        'work/ginkgo-growth-autocollect/continuous-verification.json',
        'work/ginkgo-growth-autocollect/collection-package-verification.json',
    ],
}
(release / 'status.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
old = ROOT / 'work/release/growth-night-20261101/status.json'
data = json.loads(old.read_text(encoding='utf-8'))
data.update(production_leads_imported=3, production_contacts_recorded=1,
            registrations_verified=0, ai_prepared_replies_live_verified=3,
            latest_product_handoff='work/release/growth-collection-20261101/status.json',
            latest_owner_reported_product_version='growth-external-1.4.0')
assert data['status'] == '已暂停' and data['active_round'] is None
old.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS: installation receipt and next verification steps saved; Codex recurring Agent remains paused.')
