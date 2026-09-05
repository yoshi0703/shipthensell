#!/usr/bin/env python3
"""Offline configuration and integrity helpers. Never connects or sends."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.shipthensell'
PAYLOAD_FIELDS = ('row_id', 'corporate_key', 'company', 'form_url', 'sender_fields', 'body', 'consent_checks')


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


def validate(c):
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
    if c['version'] != 1 or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', c['campaign']):
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
    if c['enabled'] is not True:
        raise ValueError('Campaign disabled; complete connection checks before enabling')
    return c


def shard(key, count):
    if not nonempty(key) or type(count) is not int or count < 1:
        raise ValueError('Nonempty corporate key and positive shard count required')
    return int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:4], 'big') % count


def payload(row):
    p = {k: row[k] for k in PAYLOAD_FIELDS}
    if any(not nonempty(p[k]) for k in PAYLOAD_FIELDS if k not in ('sender_fields', 'consent_checks')) or not https(p['form_url']):
        raise ValueError('Incomplete approval payload')
    if not isinstance(p['sender_fields'], dict) or not p['sender_fields'] or not all(nonempty(v) for v in p['sender_fields'].values()):
        raise ValueError('Sender fields must contain all exact field values')
    if not isinstance(p['consent_checks'], list):
        raise ValueError('consent_checks must be an explicit list, empty if none')
    for consent in p['consent_checks']:
        if (not isinstance(consent, dict)
                or set(consent) != {'label', 'urls', 'required', 'checked'}
                or not nonempty(consent['label'])
                or not isinstance(consent['urls'], list)
                or not all(https(url) for url in consent['urls'])
                or type(consent['required']) is not bool
                or consent['checked'] is not True):
            raise ValueError('Consent requires exact label, HTTPS URLs, required flag and checked=true')
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


def make_plan(config_path, root=ROOT):
    root = Path(root).resolve()
    config_path = Path(config_path).resolve()
    if config_path != (root / '.shipthensell/config.json').resolve():
        raise ValueError('Plan requires this clone\'s private config')
    c = validate(read(config_path))
    paths = [root / 'AGENTS.md', root / 'scripts/shipthensell.py', root / 'config/example.json', root / 'config/crm-columns.json', root / 'docs/crm.md', config_path]
    paths += sorted((root / 'workflows').glob('*.md'))
    paths += sorted((root / '.agents/skills').glob('**/SKILL.md'))
    paths += sorted((root / '.agents/skills').glob('**/openai.yaml'))
    pins = {str(p.relative_to(root)): file_hash(p) for p in paths}
    prefix = f'ShipThenSell [{c["campaign"]}]'
    schedules = {'research': {'daily_at': c['schedule']['research_time']},
                 'outreach': {'daily_at': c['schedule']['outreach_time']},
                 'replies': {'every_hours': c['schedule']['reply_interval_hours']}}
    tasks = []
    for phase, intent in schedules.items():
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
            validate(read(PRIVATE/'config.json'));print('Config structurally valid; connections still require live checks')
        elif a.command=='plan':
            plan=make_plan(PRIVATE/'config.json');write_private(PRIVATE/'plan.json',plan);print('Wrote .shipthensell/plan.json; no schedules installed')
        elif a.command=='shard':print(shard(a.key,a.count))
        elif a.command=='manifest':print(json.dumps(manifest(read(a.rows)),ensure_ascii=False,indent=2))
        elif a.command=='hash-json':print(digest(read(a.path)))
    except (ValueError,KeyError,TypeError,OSError) as e:
        p.exit(1,f'Error: {e}\n')

if __name__=='__main__':
    main()
