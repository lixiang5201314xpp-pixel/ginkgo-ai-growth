"""Claim only the development heartbeat; does not resume the old scan agent."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os

parser=argparse.ArgumentParser()
parser.add_argument('round_id')
parser.add_argument('phase')
args=parser.parse_args()
path=Path(__file__).resolve().parents[2]/'work/release/growth-dev-20261102/status.json'
lock=path.with_suffix('.claim.lock')
fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
try:
    os.close(fd)
    state=json.loads(path.read_text('utf-8-sig'))
    now=datetime.now(timezone.utc)
    assert not state.get('active_run'),'Another round owns these files'
    assert state['status'] not in ('已完成','用户暂停','已暂停')
    assert not state.get('next_run_at') or now>=datetime.fromisoformat(state['next_run_at'])
    state.update(status='运行中',next_run_at=None,active_run={
        'id':args.round_id,'started_at':now.isoformat(),'updated_at':now.isoformat(),'phase':args.phase})
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
    print('CLAIMED '+args.round_id)
finally:
    lock.unlink()
