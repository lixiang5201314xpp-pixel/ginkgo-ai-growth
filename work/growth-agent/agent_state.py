"""Durable, fail-closed round gate for the existing Codex heartbeat.

No network, customer messages, AI calls or business database access.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timedelta, timezone
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'work/release/growth-night-20261101/status.json'

def now():
    return datetime.now(timezone.utc)

def stamp(value):
    return value.isoformat()

def save(path, state):
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(state, out, ensure_ascii=False, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

@contextlib.contextmanager
def locked(path):
    lock = path.with_suffix(path.suffix + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()

def transition(state, action, *, clock=None, round_id=None, count=0, reason='', report=None):
    clock = clock or now()
    current = state.get('status', '待运行')
    empty = state.get('consecutive_empty_rounds', 0)
    if type(empty) is not int or empty < 0:
        raise ValueError('Invalid empty-round counter; inspect state before running')
    # Completion is sticky, including when an old round finishes after an owner stop.
    if current == '已完成':
        return {'action': 'stop', 'pause_automation': True, 'reason': '已完成'}
    if action == 'cancel':
        active = state.get('active_round')
        if active:
            entry = {**active, 'completed_at': stamp(clock), 'outcome': '用户中止',
                     'new_valid_leads': None, 'reason': reason or '用户要求先停止旧轮次'}
            state['round_history'] = (state.get('round_history', []) + [entry])[-100:]
        state.update(status='已暂停', active_round=None, next_run_at=None,
                     pause_reason=reason or '用户要求先停止旧轮次')
        return {'action': 'cancelled', 'pause_automation': True,
                'consecutive_empty_rounds': empty}
    if action == 'resume':
        if state.get('active_round'):
            raise ValueError('An active round must be resolved before manual resume')
        state.update(status='待运行', consecutive_empty_rounds=0, next_run_at=None,
                     pause_reason=None, resumed_at=stamp(clock))
        return {'action': 'ready', 'manual_resume': True}
    if current == '已暂停' or empty >= 3:
        state.update(status='已暂停', next_run_at=None)
        return {'action': 'pause', 'pause_automation': True,
                'reason': state.get('pause_reason') or '连续3轮无有效新线索'}
    if action == 'check':
        if state.get('active_round'):
            return {'action': 'skip', 'reason': '已有轮次运行'}
        due = state.get('next_run_at')
        if due and datetime.fromisoformat(due) > clock:
            return {'action': 'wait', 'next_run_at': due}
        return {'action': 'ready'}
    if action == 'start':
        gate = transition(state, 'check', clock=clock)
        if gate['action'] != 'ready':
            return gate
        rid = uuid.uuid4().hex
        state.update(status='运行中', active_round={'round_id': rid, 'started_at': stamp(clock)},
                     consecutive_empty_rounds=empty, next_run_at=None,
                     agent_automation_id='agent', round_cooldown_minutes=8)
        return {'action': 'scan', 'round_id': rid}
    if action != 'finish':
        raise ValueError('Unknown action')
    active = state.get('active_round') or {}
    history = state.get('round_history', [])
    if not active and any(x.get('round_id') == round_id for x in history):
        return {'action': 'already_recorded', 'pause_automation': False}
    if not round_id or active.get('round_id') != round_id:
        raise ValueError('Round identity mismatch; no state changed')
    if type(count) is not int or count < 0:
        raise ValueError('New valid lead count must be a nonnegative integer')
    if not report:
        raise ValueError('A saved scan report is required, including for zero new leads')
    evidence = json.loads(Path(report).read_text(encoding='utf-8'))
    if evidence.get('round_id') != round_id:
        raise ValueError('Scan report belongs to another round')
    leads = evidence.get('new_valid_leads', [])
    if not isinstance(leads, list) or len(leads) != count:
        raise ValueError('Count must match the report new_valid_leads list')
    keys = set(state.get('agent_recorded_lead_keys', []))
    incoming = []
    for lead in leads:
        required = ['key', 'source_url', 'published_at', 'source_text', 'city_evidence', 'backend_record_id']
        if not isinstance(lead, dict) or any(not lead.get(k) for k in required):
            raise ValueError('New lead lacks verified source/import evidence')
        key = lead['key']
        if key in keys or key in incoming:
            raise ValueError('Previously recorded or repeated lead cannot count as new')
        incoming.append(key)
    entry = {**active, 'completed_at': stamp(clock), 'new_valid_leads': count,
             'report': str(Path(report).resolve()), 'blocked_reason': reason or None}
    state.update(active_round=None, last_round=entry,
                 round_history=(history + [entry])[-100:])
    if reason:
        state.update(status='已暂停', next_run_at=None, pause_reason=reason)
        return {'action': 'pause', 'pause_automation': True, 'reason': reason}
    if evidence.get('scan_completed') is not True:
        raise ValueError('Unfinished scan must be marked blocked, not an empty round')
    empty = 0 if count else empty + 1
    state.update(consecutive_empty_rounds=empty, agent_recorded_lead_keys=sorted(keys | set(incoming)))
    if empty >= 3:
        state.update(status='已暂停', next_run_at=None, pause_reason='连续3轮无有效新线索')
        return {'action': 'pause', 'pause_automation': True, 'reason': state['pause_reason']}
    due = clock + timedelta(minutes=8)
    state.update(status='待运行', next_run_at=stamp(due), pause_reason=None)
    return {'action': 'wait', 'next_run_at': stamp(due), 'consecutive_empty_rounds': empty}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['check', 'start', 'finish', 'resume', 'cancel'])
    p.add_argument('--state', type=Path, default=DEFAULT)
    p.add_argument('--round-id')
    p.add_argument('--new-valid-leads', type=int, default=0)
    p.add_argument('--blocked', default='')
    p.add_argument('--report')
    a = p.parse_args()
    with locked(a.state):
        state = json.loads(a.state.read_text(encoding='utf-8-sig'))
        result = transition(state, a.action, round_id=a.round_id, count=a.new_valid_leads,
                            reason=a.blocked, report=a.report)
        save(a.state, state)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
