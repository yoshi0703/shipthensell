#!/usr/bin/env python3
"""Offline configuration and integrity helpers. Never connects or sends."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.shipthensell'
PAYLOAD_FIELDS = ('row_id', 'corporate_key', 'company', 'form_url', 'sender_fields', 'field_bindings', 'body', 'consent_checks')


def canonical(value):
    def check(v):
        if v is None or type(v) in (str, int, bool):
            return
        if isinstance(v, list):
            for item in v:
                check(item)
            return
        if isinstance(v, dict) and all(isinstance(k, str) and k.isascii() for k in v):
            for item in v.values():
                check(item)
            return
        raise ValueError('Canonical data requires ASCII keys and no floats/unsupported types')
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('Refusing symlink output')
    with path.open('w', encoding='utf-8') as handle:
        path.chmod(0o600)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and not value.startswith(('YOUR_', 'REPLACE_'))


def https(value):
    if not isinstance(value, str):
        return False
    u = urlsplit(value)
    return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password


def evidence_url(value):
    # Evidence only: this does not authorize navigation or HTTP form submission.
    if not isinstance(value, str) or any(ch.isspace() for ch in value):
        return False
    try:
        u = urlsplit(value)
        return u.scheme in ('http', 'https') and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False


def validate(c, *, require_enabled=True):
    if not isinstance(c, dict):
        raise ValueError('Config must be an object')
    template = read(ROOT / 'config/example.json')
    def shape(v, t, at='config'):
        if isinstance(t, dict):
            if not isinstance(v, dict) or set(v) != set(t):
                raise ValueError(at + ': missing or unknown fields')
            for k in t:
                shape(v[k], t[k], at + '.' + k)
        elif type(v) is not type(t):
            raise ValueError(at + ': wrong type')
    shape(c, template)
    if c['version'] != 2 or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', c['campaign']):
        raise ValueError('Invalid version or campaign slug')
    for group, keys in {'product': ['name','url','description'], 'sender':['company','name','email'],
                        'target':['region','industry','language'], 'connections':['crm_spreadsheet_id','google_account','gmail_account','calendar_id'],
                        'runtime':['model','reasoning_effort']}.items():
        if any(not nonempty(c[group][k]) for k in keys):
            raise ValueError('Missing configuration in ' + group)
    if not https(c['product']['url']):
        raise ValueError('Product URL must be HTTPS')
    for email in (c['sender']['email'], c['connections']['google_account'], c['connections']['gmail_account']):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Invalid email')
    if c['sender']['email'] != c['connections']['gmail_account']:
        raise ValueError('Sender must match configured Gmail account; aliases are unsupported in v1')
    if not c['target']['queries'] or not all(nonempty(x) for x in c['target']['queries']):
        raise ValueError('At least one target query is required')
    if not c['product']['approved_facts']:
        raise ValueError('Evidence-backed product facts are required')
    for fact in c['product']['approved_facts']:
        if not isinstance(fact, dict) or set(fact) != {'claim', 'source_url'} or not nonempty(fact['claim']) or not https(fact['source_url']):
            raise ValueError('Each fact needs claim and HTTPS source_url')
    try:
        ZoneInfo(c['schedule']['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Unknown IANA timezone') from None
    for t in (c['schedule']['research_time'], c['schedule']['outreach_time'], c['reply']['business_start'], c['reply']['business_end']):
        if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', t):
            raise ValueError('Times must be HH:MM')
    if c['schedule']['research_time'] >= c['schedule']['outreach_time']:
        raise ValueError('Outreach must follow research on the same local date')
    if c['reply']['business_start'] >= c['reply']['business_end']:
        raise ValueError('Invalid business hours')
    bounds = [('schedule','reply_interval_hours',1,24), ('runtime','shards',1,3), ('runtime','waves',1,2),
              ('runtime','items_per_worker',1,50), ('runtime','send_attempts_per_shard',1,100),
              ('runtime','cooldown_days',1,3650), ('reply','duration_minutes',1,240), ('reply','candidate_count',1,10)]
    for g,k,lo,hi in bounds:
        if not lo <= c[g][k] <= hi:
            raise ValueError(f'{g}.{k} must be {lo}..{hi}')
    if c['runtime']['reasoning_effort'] not in ('low','medium','high','xhigh','max','ultra','minimal','none'):
        raise ValueError('Unknown reasoning effort')
    if c['reply']['mode'] not in ('draft_only','send_after_quality_gate'):
        raise ValueError('Unknown reply mode')
    if c['reply']['mode'] == 'send_after_quality_gate' and not nonempty(c['reply']['auto_send_authorization']):
        raise ValueError('Auto replies require explicit user authorization recorded during setup')
    weekdays = c['reply']['weekdays']
    if (not weekdays or any(type(day) is not int or not 0 <= day <= 6 for day in weekdays)
            or len(set(weekdays)) != len(weekdays)):
        raise ValueError('weekdays must contain unique integers: Monday=0 through Sunday=6')
    if require_enabled and c['enabled'] is not True:
        raise ValueError('Campaign disabled; complete connection checks before enabling')
    return c


def shard(key, count):
    if not nonempty(key) or type(count) is not int or count < 1:
        raise ValueError('Nonempty corporate key and positive shard count required')
    return int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:4], 'big') % count


def payload(row):
    p = {k: row[k] for k in PAYLOAD_FIELDS}
    p['payload_version'] = 2
    if any(not nonempty(p[k]) for k in PAYLOAD_FIELDS if k not in ('sender_fields', 'field_bindings', 'consent_checks')) or not https(p['form_url']):
        raise ValueError('Incomplete approval payload')
    if not isinstance(p['sender_fields'], dict) or not p['sender_fields'] or not all(nonempty(v) for v in p['sender_fields'].values()):
        raise ValueError('Sender fields must contain all exact field values')
    bindings = p['field_bindings']
    if not isinstance(bindings, list) or not bindings:
        raise ValueError('Exact field bindings are required')
    keys = []
    for binding in bindings:
        if (not isinstance(binding, dict) or set(binding) != {'key', 'name', 'label', 'required'}
                or not nonempty(binding['key']) or not binding['key'].isascii()
                or not isinstance(binding['name'], str) or not isinstance(binding['label'], str)
                or not (nonempty(binding['name']) or nonempty(binding['label']))
                or type(binding['required']) is not bool):
            raise ValueError('Invalid field binding')
        keys.append(binding['key'])
    if len(set(keys)) != len(keys) or set(keys) != set(p['sender_fields']):
        raise ValueError('Every sender field needs exactly one binding')
    if not isinstance(p['consent_checks'], list):
        raise ValueError('consent_checks must be an explicit list, empty if none')
    for consent in p['consent_checks']:
        if (not isinstance(consent, dict)
                or set(consent) != {'label', 'urls', 'required', 'checked'}
                or not nonempty(consent['label'])
                or not isinstance(consent['urls'], list)
                or not all(evidence_url(url) for url in consent['urls'])
                or type(consent['required']) is not bool
                or consent['checked'] is not True):
            raise ValueError('Consent requires exact label, absolute HTTP/HTTPS evidence URLs, required flag and checked=true')
    canonical(p)
    return p


def manifest(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Nonempty row list required')
    items = sorted((payload(x) for x in rows), key=lambda x: x['row_id'])
    for key in ('row_id','corporate_key'):
        if len({x[key] for x in items}) != len(items):
            raise ValueError('Duplicate ' + key)
    entries = [dict(x, payload_sha256=digest(x)) for x in items]
    return {'count': len(entries), 'entries': entries, 'manifest_sha256': digest(entries)}


def recovery_action(current, pre, post, pre_hash, post_hash):
    if digest(pre) != pre_hash or digest(post) != post_hash:
        raise ValueError('WRITE_STATE_MISMATCH: snapshot hash')
    if current == post:
        return 'mark_completed'
    if current == pre:
        return 'apply_saved_post'
    raise ValueError('WRITE_STATE_MISMATCH: current record')


def reply_send_allowed(mode, authorization, classification, high_confidence, identity_matches, unchanged, blocked, attempted_at, send_status):
    return (mode == 'send_after_quality_gate' and nonempty(authorization)
            and classification in ('positive','question','scheduling')
            and high_confidence is True and identity_matches is True and unchanged is True
            and blocked is False and attempted_at is None and send_status == 'not_attempted')


def phase_dependencies(phase):
    if phase not in ('research', 'outreach', 'replies'):
        raise ValueError('Unknown phase')
    shared = ['AGENTS.md', 'scripts/shipthensell.py', 'config/example.json',
              'config/crm-columns.json', 'docs/crm.md', '.shipthensell/config.json',
              'workflows/common.md']
    return shared + [f'workflows/{phase}.md',
                     f'.agents/skills/shipthensell-{phase}/SKILL.md',
                     f'.agents/skills/shipthensell-{phase}/agents/openai.yaml'] + (
                         ['workflows/copywriting.md'] if phase == 'research' else [])


def stop_scope(reason):
    if reason in ('captcha', 'form_login', 'personal_consent', 'missing_recipient_fact',
                  'form_changed', 'page_injection', 'browser_approval'):
        return 'item'
    if reason in ('missing_tool', 'phase_auth'):
        return 'phase'
    # Unknown shared failures fail closed until their scope is established.
    return 'campaign'


def read_retry_allowed(operation, reason, attempts):
    return (operation == 'read_only' and reason in ('timeout', 'rate_limit', 'temporary_unavailable')
            and type(attempts) is int and 1 <= attempts < 3)


def research_ready(workers, expected_task_ids, config_hash, limit):
    """Verify durable dispatched-worker records, independent of the target quota."""
    if not expected_task_ids or len(set(expected_task_ids)) != len(expected_task_ids):
        return False
    if len(workers) != len(expected_task_ids) or {w['task_id'] for w in workers} != set(expected_task_ids):
        return False
    keys = set()
    for w in workers:
        outcomes = w['outcomes']
        if (w['state'] not in ('completed', 'partial', 'failed') or w['writer_state'] != 'closed'
                or w['config_sha256'] != config_hash or not isinstance(outcomes, list)
                or type(w['processed_count']) is not int or not 0 <= w['processed_count'] <= limit
                or w['processed_count'] != len(outcomes)):
            return False
        for outcome in outcomes:
            key = outcome['corporate_key']
            if (not nonempty(key) or key in keys or outcome['state'] not in ('prepared', 'skipped', 'needs_review')
                    or not nonempty(outcome['evidence'])
                    or (outcome['state'] == 'prepared' and not nonempty(outcome.get('row_id')))):
                return False
            keys.add(key)
        if w['prepared_count'] != sum(o['state'] == 'prepared' for o in outcomes):
            return False
    return True


def utc_timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp required')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt.astimezone(timezone.utc)


def select_backlog(rows, eligible_run_ids, campaign, local_date, tz, shard_count, per_shard_limit):
    """Select only unattempted rows; budgets include every run on this local date.

    Caller first reconciles all source runs, CRM identities, cooldown and blocklist.
    This selection is not permission to input or send.
    """
    zone = ZoneInfo(tz)
    if (type(shard_count) is not int or not 1 <= shard_count <= 3
            or type(per_shard_limit) is not int or not 1 <= per_shard_limit <= 100):
        raise ValueError('Invalid shard count or daily budget')
    if datetime.strptime(local_date, '%Y-%m-%d').date().isoformat() != local_date:
        raise ValueError('Invalid local date')
    remaining = {i: per_shard_limit for i in range(shard_count)}
    candidates = []
    seen = set()
    for row in rows:
        if row['campaign'] != campaign:
            continue
        if row['row_id'] in seen:
            raise ValueError('Duplicate CRM row_id')
        seen.add(row['row_id'])
        assigned = shard(row['corporate_key'], shard_count)
        if row['shard'] != assigned:
            raise ValueError('Shard mismatch; migrate deliberately')
        attempted = row.get('submission_attempted_at')
        if attempted:
            if utc_timestamp(attempted).astimezone(zone).date().isoformat() == local_date:
                remaining[assigned] -= 1
        elif (row['research_run_id'] in eligible_run_ids
              and row['state'] in ('pending_approval', 'approved', 'deferred')):
            candidates.append(row)
    attempted_keys = {r['corporate_key'] for r in rows if r.get('submission_attempted_at')}
    selected = []
    selected_keys = set()
    for row in sorted(candidates, key=lambda r: (utc_timestamp(r['prepared_at']), r['row_id'])):
        key = row['corporate_key']; assigned = row['shard']
        if key in attempted_keys or key in selected_keys or remaining[assigned] <= 0:
            continue
        selected.append(row); selected_keys.add(key); remaining[assigned] -= 1
    return selected


def approval_scope(campaign, run_id, config_hash, rows):
    return {'campaign': campaign, 'send_run_id': run_id, 'config_sha256': config_hash,
            'manifest': manifest(rows)}


def approval_covers(approval, scope, rows, task_id, host_allows_handoff=False):
    if (approval.get('decision') != 'approved' or not nonempty(approval.get('evidence'))
            or not nonempty(approval.get('approved_at'))
            or not nonempty(approval.get('task_id'))
            or approval.get('scope_sha256') != digest(scope)):
        return False
    if approval['task_id'] != task_id and host_allows_handoff is not True:
        return False
    allowed = {entry['row_id']: entry['payload_sha256'] for entry in scope['manifest']['entries']}
    return bool(rows) and all(allowed.get(r['row_id']) == digest(payload(r)) for r in rows)


def approval_checkpoint(scope, pending_rows, workers, expected_task_ids, remaining, resume_position):
    if (not expected_task_ids or len(set(expected_task_ids)) != len(expected_task_ids)
            or len(workers) != len(expected_task_ids)
            or {w['task_id'] for w in workers} != set(expected_task_ids)
            or any(w['writer_state'] != 'closed' or w['host_terminal'] is not True for w in workers)):
        raise ValueError('All dispatched workers must be durably closed and host-confirmed terminal')
    entries = {e['row_id']: e['payload_sha256'] for e in scope['manifest']['entries']}
    if not pending_rows or any(entries.get(r['row_id']) != digest(payload(r)) for r in pending_rows):
        raise ValueError('Checkpoint rows differ from manifest')
    return {'scope': scope, 'scope_sha256': digest(scope),
            'pending_row_ids': [r['row_id'] for r in pending_rows],
            'workers': workers, 'remaining_budget': {str(k): v for k, v in remaining.items()},
            'resume_position': resume_position}


def reply_record_handled(record):
    # Review is durably classified, not business-complete or permission to send.
    return (nonempty(record.get('message_id')) and record.get('crm_status') == 'completed'
            and (record.get('classification') != 'needs_review'
                 or (nonempty(record.get('reason')) and nonempty(record.get('summary')))))


def make_plan(config_path, root=ROOT):
    root = Path(root).resolve()
    config_path = Path(config_path).resolve()
    if config_path != (root / '.shipthensell/config.json').resolve():
        raise ValueError('Plan requires this clone\'s private config')
    c = validate(read(config_path))
    prefix = f'ShipThenSell [{c["campaign"]}]'
    schedules = {'research': {'daily_at': c['schedule']['research_time']},
                 'outreach': {'daily_at': c['schedule']['outreach_time']},
                 'replies': {'every_hours': c['schedule']['reply_interval_hours']}}
    tasks = []
    for phase, intent in schedules.items():
        pins = {path: file_hash(root / path) for path in phase_dependencies(phase)}
        prompt = (f'{prefix} phase={phase}. Work only in {root.resolve()}.\n'
                  'Before any external tools, compute SHA-256 for every following relative file and compare to these literal pins. '
                  'Missing/unreadable/mismatched files: stop without external actions; never regenerate the pins.\n'
                  + json.dumps(pins, indent=2) + '\n'
                  + f'Read AGENTS.md, .shipthensell/config.json, docs/crm.md, config/crm-columns.json, workflows/common.md and workflows/{phase}.md completely. '
                  'Follow that phase; verify enabled config, CRM Settings hash and actual connector identities. '
                  'This installed standalone schedule authorizes creating the bounded standalone workers described by research/outreach; workers may not spawn more tasks. '
                  'It never substitutes for the required form batch approval. Reply send authorization comes only from explicit user setup authorization, limited by config. '
                  'No input on absent approval, no consent/CAPTCHA bypass, no retry of unknown sends. '
                  'Stay quiet on unchanged/non-actionable reply checks; notify completion, meaningful changes, failure or required user action.')
        tasks.append({'phase':phase,'name':prefix+' '+phase,'kind':'cron','execution_environment':'local',
                      'timezone':c['schedule']['timezone'],'schedule_intent':intent,'model':c['runtime']['model'],
                      'reasoning_effort':c['runtime']['reasoning_effort'],'initial_status':'PAUSED','prompt':prompt})
    return {'version':1,'campaign':c['campaign'],'config_sha256':file_hash(config_path),
            'registration':'Use the live Codex automation tool schema and resolve project ID; this is not an API request.',
            'tasks':tasks}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    sub.add_parser('init');sub.add_parser('validate');sub.add_parser('plan')
    s=sub.add_parser('shard');s.add_argument('key');s.add_argument('--count',type=int,default=3)
    s=sub.add_parser('manifest');s.add_argument('rows',type=Path)
    s=sub.add_parser('hash-json');s.add_argument('path',type=Path)
    a=p.parse_args()
    try:
        if a.command=='init':
            dest=PRIVATE/'config.json'
            if dest.exists():
                print('Existing config preserved')
            else:
                write_private(dest,read(ROOT/'config/example.json'));print('Created .shipthensell/config.json (disabled)')
        elif a.command=='validate':
            validate(read(PRIVATE/'config.json'), require_enabled=False);print('Config structurally valid; connections still require live checks')
        elif a.command=='plan':
            plan=make_plan(PRIVATE/'config.json');write_private(PRIVATE/'plan.json',plan);print('Wrote .shipthensell/plan.json; no schedules installed')
        elif a.command=='shard':print(shard(a.key,a.count))
        elif a.command=='manifest':print(json.dumps(manifest(read(a.rows)),ensure_ascii=False,indent=2))
        elif a.command=='hash-json':print(digest(read(a.path)))
    except (ValueError,KeyError,TypeError,OSError) as e:
        p.exit(1,f'Error: {e}\n')

if __name__=='__main__':
    main()
