import json
from pathlib import Path

release = Path(__file__).resolve().parents[1] / 'release/growth-collection-20261101'
path = release / 'status.json'
data = json.loads(path.read_text(encoding='utf-8'))
data.update({
    'automatic_intake_enabled_live_verified': True,
    'continuous_browser_round_live_verified': True,
    'live_browser': 'Chrome profile 您的 Chrome; connected browser id 3',
    'first_automatic_round': {
        'platform': 'douyin',
        'receipt_times_cst': ['2026-11-01 14:12:56', '2026-11-01 14:13:57',
                              '2026-11-01 14:14:58', '2026-11-01 14:15:59',
                              '2026-11-01 14:18:35'],
        'receipts': 5,
        'added_valid': 0,
        'pending_review_added': 2,
        'sent': 0,
        'bookings': 0,
        'review_outcome': 'Both pending records were older content, reviewed and recoverably archived. No new qualified customer was found in this round.',
    },
    'human_review': [
        {'source': 'https://www.douyin.com/video/7679679918087250107',
         'published_original_ui_cst': '2026-08-30 12:40', 'stage_ui_verified': 'archived',
         'reason': 'Older third-party request; not a recent customer request.'},
        {'source': 'https://www.douyin.com/video/7539834374747032889',
         'published_original_ui_cst': '2025-08-18 16:08', 'stage_ui_verified': 'archived',
         'reason': 'Older instructional discussion; not an expressed current personal need.'},
    ],
    'production_leads_last_ui_verified': 5,
    'production_leads_eligible_or_contacted': 3,
    'production_leads_archived': 2,
    'production_contacts_last_ui_verified': 1,
    'production_bookings_last_ui_verified': 0,
    'local_helper_version': '1.4.1',
    'local_helper_files_updated_and_verified': True,
    'local_extension_reload_pending': True,
    'helper_fix': 'Open the actual canonical Douyin detail page before intake, retain the parent search when starting inside a modal, and refresh phase/count/next-run status while popup remains open.',
    'helper_fix_tests': '10 isolated scheduler/state-flow checks passed, including two-title canonical navigation. Existing capture logic unchanged.',
    'helper_1_4_1_live_cycle_verified': False,
    'browser_blocker': 'Chrome website control connected; browser URL policy prohibits opening extension management. Owner must reload the pre-existing helper.',
    'next': ['Owner reloads helper 1.4.1 and starts once from the public search page.',
             'Verify corrected original publication times, receipt totals and subsequent round before claiming completion.'],
    'proof': 'work/release/growth-collection-20261101/live-five-capture-receipts.png',
})
assert data['codex_recurring_agent_status'] == 'PAUSED'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS: first real five-post collection round recorded without treating pending records as customers; helper 1.4.1 reload remains pending.')
