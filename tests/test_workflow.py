import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sts',ROOT/'scripts/shipthensell.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def configured():
    c=s.read(ROOT/'config/example.json')
    c['product']={'name':'Demo','url':'https://example.com','description':'A demo product',
                  'approved_facts':[{'claim':'Exports CSV','source_url':'https://example.com/docs'}]}
    c['sender'].update(company='Demo Co',name='Test Sender',email='test@example.com')
    c['target'].update(region='Test region',industry='Test industry',queries=['test query'])
    c['connections'].update(crm_spreadsheet_id='synthetic-sheet',google_account='test@example.com',gmail_account='test@example.com')
    c['runtime']['model']='test-model';c['enabled']=True
    return c


def row():
    return {'row_id':'001','corporate_key':'demo-key','company':'Demo Co','form_url':'https://example.com/contact',
            'sender_fields':{'name':'Test Sender','email':'test@example.com'},'body':'Hello, example.'}


class WorkflowTests(unittest.TestCase):
    def test_example_cannot_activate(self):
        with self.assertRaises(ValueError):s.validate(s.read(ROOT/'config/example.json'))

    def test_valid_config(self):
        self.assertEqual(s.validate(configured())['runtime']['shards'],3)

    def test_invalid_configs(self):
        cases=[('enabled',None,False),('schedule','timezone','No/Such_Zone'),('schedule','research_time','27:00'),
               ('schedule','outreach_time','02:00'),('runtime','shards',True),('runtime','shards',4),
               ('runtime','items_per_worker',0),('product','approved_facts',[]),('sender','email','other@example.com'),
               ('reply','mode','send_everything'),('reply','mode','send_after_quality_gate')]
        for group,key,value in cases:
            c=configured()
            if key is None:c[group]=value
            else:c[group][key]=value
            with self.subTest(group=group,key=key,value=value),self.assertRaises(ValueError):s.validate(c)

    def test_extra_fields_rejected(self):
        c=configured();c['skip_approval']=True
        with self.assertRaises(ValueError):s.validate(c)

    def test_shard_known_vector(self):
        self.assertEqual(s.shard('abc',3),int('ba7816bf',16)%3)
        with self.assertRaises(ValueError):s.shard('x',0)

    def test_manifest_binds_every_field(self):
        original=row();baseline=s.manifest([original])['manifest_sha256']
        for key in s.PAYLOAD_FIELDS:
            changed=copy.deepcopy(original)
            if key=='sender_fields':changed[key]['email']='changed@example.com'
            elif key=='form_url':changed[key]='https://example.com/changed'
            else:changed[key]+=' changed'
            self.assertNotEqual(baseline,s.manifest([changed])['manifest_sha256'],key)

    def test_manifest_stable_order_and_duplicate_rejection(self):
        a=row();b=row();b.update(row_id='002',corporate_key='other')
        self.assertEqual(s.manifest([a,b]),s.manifest([b,a]))
        with self.assertRaises(ValueError):s.manifest([a,a])
        b['corporate_key']=a['corporate_key']
        with self.assertRaises(ValueError):s.manifest([a,b])

    def test_canonical_unicode_and_types(self):
        self.assertEqual(s.canonical({'z':'日本語','a':1}),'{"a":1,"z":"日本語"}'.encode())
        for value in ({'x':float('nan')},{'x':1.2},{'日本語':'value'}):
            with self.assertRaises(ValueError):s.canonical(value)

    def test_recovery_is_saved_state_only(self):
        pre={'state':'sent','latest_reply_message_id':'old'};post={'state':'reply','latest_reply_message_id':'new'}
        args=(pre,post,s.digest(pre),s.digest(post))
        self.assertEqual(s.recovery_action(pre,*args),'apply_saved_post')
        self.assertEqual(s.recovery_action(post,*args),'mark_completed')
        with self.assertRaises(ValueError):s.recovery_action({'state':'edited'},*args)
        with self.assertRaises(ValueError):s.recovery_action(pre,pre,post,'0'*64,s.digest(post))

    def test_reply_send_guards(self):
        args=dict(mode='send_after_quality_gate',authorization='User explicitly authorized this campaign.',
                  classification='positive',high_confidence=True,identity_matches=True,unchanged=True,
                  blocked=False,attempted_at=None,send_status='not_attempted')
        self.assertTrue(s.reply_send_allowed(**args))
        for key,values in {'mode':['draft_only'],'authorization':['','   '],
                           'classification':['declined','automated','bounced','deferred','needs_review'],
                           'high_confidence':[False],'identity_matches':[False],'unchanged':[False],
                           'blocked':[True],'attempted_at':['2026-01-01T00:00:00Z'],
                           'send_status':['attempted','unknown','sent','invalid']}.items():
            for v in values:
                changed=dict(args);changed[key]=v
                self.assertFalse(s.reply_send_allowed(**changed),(key,v))

    def test_plan_has_three_paused_pinned_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'clone';shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','.shipthensell','__pycache__'))
            cfg=root/'.shipthensell/config.json';s.write_private(cfg,configured())
            plan=s.make_plan(cfg,root)
            self.assertEqual([x['phase'] for x in plan['tasks']],['research','outreach','replies'])
            for task in plan['tasks']:
                self.assertEqual(task['initial_status'],'PAUSED')
                self.assertIn(s.file_hash(root/'workflows/replies.md'),task['prompt'])
                self.assertIn(s.file_hash(cfg),task['prompt'])
            self.assertEqual(plan['tasks'][0]['schedule_intent'],{'daily_at':'03:00'})
            self.assertEqual(plan['tasks'][2]['schedule_intent'],{'every_hours':3})
            self.assertEqual(cfg.stat().st_mode & 0o777,0o600)
            before=plan['tasks'][0]['prompt']
            (root/'workflows/common.md').write_text('changed')
            self.assertNotEqual(before,s.make_plan(cfg,root)['tasks'][0]['prompt'])

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"enabled":false,"enabled":true}')
            with self.assertRaises(ValueError):s.read(p)

if __name__=='__main__':unittest.main()
