import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from test_workflow import ROOT, configured, row, s


def worker():
    return dict(task_id='task-1', state='completed', writer_state='closed',
                config_sha256='config', processed_count=1, prepared_count=1,
                outcomes=[dict(corporate_key='demo-key', state='prepared',
                               row_id='001', evidence='synthetic form readback')])


def lead(id='001', key='demo-key', **kw):
    v=row();v.update(row_id=id, corporate_key=key, campaign='demo', research_run_id='old',
                    shard=s.shard(key,3), state='deferred', prepared_at='2026-09-01T00:00:00Z')
    v.update(kw);return v


class LifecycleTests(unittest.TestCase):
    def test_disabled_setup_dry_run_and_final_hash(self):
        c=configured();c['enabled']=False
        self.assertIs(s.validate(c,require_enabled=False),c)
        with self.assertRaises(ValueError):s.validate(c)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','__pycache__','.shipthensell'))
            path=root/'.shipthensell/config.json';s.write_private(path,c)
            with self.assertRaises(ValueError):s.make_plan(path,root)
            disabled_hash=s.file_hash(path)
            c['enabled']=True;s.write_private(path,c);plan=s.make_plan(path,root)
            fake_settings={'config_sha256':s.file_hash(path),'enabled':True}
            self.assertEqual(plan['config_sha256'],fake_settings['config_sha256'])
            self.assertNotEqual(plan['config_sha256'],disabled_hash)
            self.assertTrue(all(t['initial_status']=='PAUSED' for t in plan['tasks']))

    def test_weekdays_and_version_migration(self):
        for days in ([],[True],[7],[-1],[0,0],['Monday']):
            c=configured();c['reply']['weekdays']=days
            with self.subTest(days=days),self.assertRaises(ValueError):s.validate(c)
        c=configured();c['reply']['weekdays']=[5,6];s.validate(c)
        c['version']=1
        with self.assertRaises(ValueError):s.validate(c)

    def test_phase_dependency_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','__pycache__','.shipthensell'))
            cfg=root/'.shipthensell/config.json';s.write_private(cfg,configured())
            before=s.make_plan(cfg,root)
            with (root/'workflows/replies.md').open('a') as f:f.write('\nReply-only change\n')
            after=s.make_plan(cfg,root)
            self.assertEqual(before['tasks'][:2],after['tasks'][:2])
            self.assertNotEqual(before['tasks'][2],after['tasks'][2])
            with (root/'workflows/copywriting.md').open('a') as f:f.write('\nCopy-only change\n')
            copy_plan=s.make_plan(cfg,root)
            self.assertNotEqual(after['tasks'][0],copy_plan['tasks'][0])
            self.assertEqual(after['tasks'][1:],copy_plan['tasks'][1:])
            (root/'workflows/common.md').unlink()
            with self.assertRaises(OSError):s.make_plan(cfg,root)

    def test_required_shared_and_phase_dependencies(self):
        for phase in ('research','outreach','replies'):
            deps=set(s.phase_dependencies(phase))
            self.assertTrue({'AGENTS.md','scripts/shipthensell.py','config/example.json',
                             'config/crm-columns.json','docs/crm.md','.shipthensell/config.json',
                             'workflows/common.md',f'workflows/{phase}.md'} <= deps)
            self.assertIn(f'.agents/skills/shipthensell-{phase}/SKILL.md',deps)
        self.assertIn('workflows/copywriting.md',s.phase_dependencies('research'))
        with self.assertRaises(ValueError):s.phase_dependencies('unknown')

    def test_stop_scopes_preserve_shared_gates(self):
        self.assertEqual(s.stop_scope('captcha'),'item')
        self.assertEqual(s.stop_scope('missing_tool'),'phase')
        for cause in ('identity_mismatch','hash_mismatch','shared_corruption','unknown'):
            self.assertEqual(s.stop_scope(cause),'campaign')

    def test_only_transient_reads_retry_with_bound(self):
        self.assertTrue(s.read_retry_allowed('read_only','timeout',1))
        self.assertTrue(s.read_retry_allowed('read_only','rate_limit',2))
        for op,reason,count in [('send','timeout',1),('write','timeout',1),('read_only','auth',1),
                               ('read_only','timeout',3),('read_only','timeout',True)]:
            self.assertFalse(s.read_retry_allowed(op,reason,count))

    def test_reconciled_under_quota_and_partial(self):
        w=worker();self.assertTrue(s.research_ready([w],['task-1'],'config',50))
        w['state']='partial';self.assertTrue(s.research_ready([w],['task-1'],'config',50))
        w['outcomes'][0].update(state='skipped');w['prepared_count']=0
        self.assertTrue(s.research_ready([w],['task-1'],'config',50))

    def test_missing_or_inconsistent_workers_block(self):
        self.assertFalse(s.research_ready([],['task-1'],'config',50))
        for field,value in [('writer_state','active'),('config_sha256','other'),('task_id','other'),
                            ('processed_count',2),('prepared_count',0),('state','running')]:
            w=worker();w[field]=value
            self.assertFalse(s.research_ready([w],['task-1'],'config',50),field)
        w=worker();w['outcomes'][0]['evidence']=''
        self.assertFalse(s.research_ready([w],['task-1'],'config',50))
        a=worker();b=worker();b['task_id']='task-2'
        self.assertFalse(s.research_ready([a,b],['task-1','task-2'],'config',50))

    def select(self, rows, date='2026-09-06', budget=1):
        return s.select_backlog(rows,{'old','new'},'demo',date,'Asia/Tokyo',3,budget)

    def test_backlog_uses_preparation_order_and_stable_tie(self):
        a=lead('z','a');b=lead('a','b',prepared_at='2026-09-02T00:00:00Z')
        self.assertEqual([x['row_id'] for x in self.select([b,a],budget=5)],['z','a'])
        b['prepared_at']=a['prepared_at']
        self.assertEqual([x['row_id'] for x in self.select([a,b],budget=5)],['a','z'])
        self.assertEqual(a['research_run_id'],'old')

    def test_all_run_attempts_and_unknown_consume_local_daily_budget(self):
        key='demo-key';assigned=s.shard(key,3)
        other=next(str(i) for i in range(100) if s.shard(str(i),3)==assigned)
        attempted=lead('old',key,submission_attempted_at='2026-09-05T15:01:00Z',state='needs_review',research_run_id='different')
        candidate=lead('new',other)
        self.assertEqual(self.select([attempted,candidate]),[])
        self.assertEqual(self.select([attempted,candidate],date='2026-09-07'),[candidate])
        same=lead('duplicate',key)
        self.assertEqual(self.select([attempted,same],date='2026-09-07'),[])

    def test_invalid_and_ineligible_backlog(self):
        a=lead(research_run_id='unreconciled')
        self.assertEqual(self.select([a]),[])
        a=lead();self.assertEqual(len(self.select([a,lead('002')])),1)
        with self.assertRaises(ValueError):self.select([a,a])
        a['shard']=(a['shard']+1)%3
        with self.assertRaises(ValueError):self.select([a])
        a=lead(prepared_at='2026-09-01')
        with self.assertRaises(ValueError):self.select([a])

    def approval(self, scope):
        return dict(decision='approved',scope_sha256=s.digest(scope),evidence='Synthetic explicit approval',
                    approved_at='2026-09-06T00:00:00Z',task_id='parent')

    def test_scoped_handoff_and_bookkeeping(self):
        a=row();scope=s.approval_scope('demo','send-1','config',[a]);approval=self.approval(scope)
        self.assertFalse(s.approval_covers(approval,scope,[a],'child'))
        self.assertTrue(s.approval_covers(approval,scope,[a],'child',True))
        a.update(state='approved',approval_json='stored')
        self.assertTrue(s.approval_covers(approval,scope,[a],'parent'))
        for field in ('body','form_url'):
            b=copy.deepcopy(a);b[field]+='changed'
            self.assertFalse(s.approval_covers(approval,scope,[b],'parent'))
        b=copy.deepcopy(a);b['field_bindings'][0]['label']='changed'
        self.assertFalse(s.approval_covers(approval,scope,[b],'parent'))
        for field in ('campaign','send_run_id','config_sha256'):
            other=copy.deepcopy(scope);other[field]='other'
            self.assertFalse(s.approval_covers(approval,other,[a],'parent'))
        for decision in ('denied','','pending'):
            approval['decision']=decision
            self.assertFalse(s.approval_covers(approval,scope,[a],'parent'))

    def test_checkpoint_requires_host_termination_and_exact_rows(self):
        a=row();scope=s.approval_scope('demo','send','config',[a])
        workers=[dict(task_id='w',writer_state='closed',host_terminal=True)]
        saved=s.approval_checkpoint(scope,[a],workers,['w'],{'0':1},0)
        s.canonical(saved)
        self.assertEqual(saved['scope_sha256'],s.digest(scope))
        workers[0]['host_terminal']=False
        with self.assertRaises(ValueError):s.approval_checkpoint(scope,[a],workers,['w'],{},0)
        workers[0]['host_terminal']=True
        with self.assertRaises(ValueError):s.approval_checkpoint(scope,[a],workers,['w','missing'],{},0)
        a['body']='changed'
        with self.assertRaises(ValueError):s.approval_checkpoint(scope,[a],workers,['w'],{},0)

    def test_review_cursor_does_not_wait_for_business_resolution(self):
        record=dict(message_id='m',classification='needs_review',reason='Ambiguous sender',
                    summary='Synthetic evidence',crm_status='completed',review_status='open')
        self.assertTrue(s.reply_record_handled(record))
        record['crm_status']='pending';self.assertFalse(s.reply_record_handled(record))
        record['crm_status']='completed';record['reason']=''
        self.assertFalse(s.reply_record_handled(record))

    def test_unicode_bindings_and_legacy_payload_rejection(self):
        a=row();self.assertEqual(s.payload(a)['payload_version'],2)
        for key in ('name','label','required'):
            b=copy.deepcopy(a);b['field_bindings'][0][key]=False if key=='required' else 'changed'
            self.assertNotEqual(s.digest(s.payload(a)),s.digest(s.payload(b)))
        b=copy.deepcopy(a);del b['field_bindings']
        with self.assertRaises(KeyError):s.payload(b)
        b=copy.deepcopy(a);b['field_bindings'].append(b['field_bindings'][0])
        with self.assertRaises(ValueError):s.payload(b)

    def test_http_is_evidence_only(self):
        a=row();a['consent_checks']=[dict(label='Privacy',urls=['http://example.com/privacy'],required=True,checked=True)]
        s.payload(a)
        for bad in ('javascript:alert(1)','/privacy','https://user:pass@example.com','https://example.com/a b'):
            a['consent_checks'][0]['urls']=[bad]
            with self.assertRaises(ValueError):s.payload(a)
        a=row();a['form_url']='http://example.com/contact'
        with self.assertRaises(ValueError):s.payload(a)

    def test_fake_partial_to_checkpoint_reply_recovery_and_resume(self):
        # In-memory CRM only: no connector or external side effects.
        source=worker();source['state']='partial'
        crm=[lead(state='pending_approval')]
        self.assertTrue(s.research_ready([source],['task-1'],'config',50))
        selected=self.select(crm)
        scope=s.approval_scope('demo','send-1','config',selected)
        checkpoint=s.approval_checkpoint(scope,selected,
            [dict(task_id='w',writer_state='closed',host_terminal=True)],['w'],{0:1},0)
        s.canonical(checkpoint)
        # A reply can update administrative fields while the send writer is closed.
        pre=copy.deepcopy(crm[0]);post=copy.deepcopy(pre);post['latest_reply_message_id']='m1'
        self.assertEqual(s.recovery_action(crm[0],pre,post,s.digest(pre),s.digest(post)),'apply_saved_post')
        crm[0]=post
        resumed=self.select(crm)
        self.assertTrue(s.approval_covers(self.approval(scope),scope,resumed,'w',True))
        # Marker survives unknown result; a second run cannot select the same company.
        crm[0]['submission_attempted_at']='2026-09-06T00:00:00Z'
        crm[0]['state']='needs_review'
        self.assertEqual(self.select(crm),[])
        self.assertEqual(self.select(crm,date='2026-09-07'),[])
