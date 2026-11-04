from pathlib import Path
from datetime import datetime, timezone
import json

path = Path(__file__).resolve().parents[2] / 'work/release/growth-dev-20261102/status.json'
state = json.loads(path.read_text('utf-8-sig'))
now = datetime.now(timezone.utc)
assert not state.get('active_run'), 'An existing round owns the files'
assert state['status'] not in ('已完成', '用户暂停')
assert now >= datetime.fromisoformat(state['next_run_at'])
state.update(status='运行中', next_run_at=None, active_run={
    'id': 'round-005-kuaishou-scope', 'started_at': now.isoformat(),
    'updated_at': now.isoformat(), 'phase': '核对快手公开原帖链接与连播评论作用域'
})
temporary=path.with_suffix('.tmp')
temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
temporary.replace(path)
print('CLAIMED round-005-kuaishou-scope')
