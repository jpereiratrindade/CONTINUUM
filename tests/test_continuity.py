"""Functional continuity: observation -> reference -> work -> restart -> revision."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

from lab.api import execute
from lab.core import Lab


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.lab=Lab(self.root/'lab.sqlite')
        self.source=self.root/'source';self.source.mkdir()
        self.file=self.source/'creative.md'
        self.file.write_text('# Continuidade criativa\n\nMemória e convergência entre documentos no processo criativo.',encoding='utf-8')
        self.call('register_source',path=str(self.source),label='Pesquisa')
        self.call('scan')
        self.node=self.call('investigate',query='Como sustentar continuidade criativa e convergência entre documentos?',request_id=str(uuid.uuid4()))['question_node']

    def tearDown(self):
        self.lab.close();self.temp.cleanup()

    def call(self,name,**args):
        return execute(self.lab,name,args,allow_writes=True)

    def test_context_is_prepared_with_immutable_evidence_and_no_self_match(self):
        ref=self.call('reference',id=self.node['id'])
        self.assertFalse(ref['stale'])
        self.assertEqual(ref['note']['revision'],0)
        package=ref['package']
        self.assertEqual(package['evidence'][0]['source_label'],'Pesquisa')
        self.assertNotIn(self.node['id'],[n['id'] for n in package['related']])
        doc=self.call('document_version',id=package['evidence'][0]['version_event_id'])
        self.assertEqual(doc['content_hash'],package['evidence'][0]['content_hash'])
        self.assertIn('Memória e convergência',doc['body'])
        self.assertTrue(all(c['state']=='candidate' for c in package['contributions']))
        self.assertLessEqual(len(package['contributions']),3)

    def test_observation_updates_context_without_overwriting_work_and_preserves_old_snapshot(self):
        before=self.call('reference',id=self.node['id'])
        self.call('save_note',id=self.node['id'],text='Meu esboço livre.\n\nPróximo movimento\nComparar argumentos antes de concluir.',revision=0)
        self.file.write_text('# Continuidade criativa\n\nConvergência e memória: novo contraponto entre documentos.',encoding='utf-8')
        self.call('scan')
        after=self.call('reference',id=self.node['id'])
        self.assertNotEqual(before['package_event_id'],after['package_event_id'])
        self.assertIn('Meu esboço',after['note']['text'])
        self.assertEqual(after['package']['next_movement'],'Comparar argumentos antes de concluir.')
        old=self.call('document_version',id=before['package']['evidence'][0]['version_event_id'])
        self.assertIn('Memória e convergência',old['body'])
        self.assertNotIn('novo contraponto',old['body'])
        self.assertTrue(self.call('verify')['ok'])

    def test_reading_and_unchanged_scans_do_not_create_history_noise(self):
        before=self.call('anchor')
        for _ in range(3):
            self.call('reference',id=self.node['id'])
            self.call('scan')
        self.assertEqual(before['seq'],self.call('anchor')['seq'])
        self.assertEqual(before['hash'],self.call('anchor')['hash'])

    def test_conflicting_clients_and_lost_response_retry(self):
        first=self.call('save_note',id=self.node['id'],text='Primeira contribuição',revision=0)
        before=self.call('anchor')
        retry=self.call('save_note',id=self.node['id'],text='Primeira contribuição',revision=0)
        self.assertEqual(first,retry)
        self.assertEqual(before['seq'],self.call('anchor')['seq'])
        second=Lab(self.lab.database)
        try:
            with self.assertRaisesRegex(ValueError,'outro ambiente'):
                execute(second,'save_note',{'id':self.node['id'],'text':'Escrita concorrente','revision':0},allow_writes=True)
        finally:
            second.close()
        self.assertEqual(self.call('reference',id=self.node['id'])['note']['text'],'Primeira contribuição')
        self.assertEqual(self.call('reference',id=self.node['id'])['note']['revision'],1)

    def test_feedback_survives_restart_and_new_version_remains_a_candidate(self):
        contribution=self.call('reference',id=self.node['id'])['package']['contributions'][0]
        self.call('review_contribution',id=self.node['id'],suggestion_id=contribution['id'],state='dismissed')
        self.lab.close();self.lab=Lab(self.root/'lab.sqlite')
        ref=self.call('reference',id=self.node['id'])
        self.assertEqual(ref['feedback'][contribution['id']],'dismissed')
        self.call('scan')
        self.assertEqual(self.call('reference',id=self.node['id'])['feedback'][contribution['id']],'dismissed')
        self.file.write_text('# Continuidade criativa\nOutra versão sobre convergência criativa e memória.',encoding='utf-8')
        self.call('scan')
        new=self.call('reference',id=self.node['id'])['package']['contributions'][0]
        self.assertNotEqual(new['id'],contribution['id'])
        self.assertEqual(new['state'],'candidate')

    def test_local_draft_survives_separate_mcp_process_and_actor_is_recorded(self):
        self.call('save_note',id=self.node['id'],text='Continuar amanhã: confrontar evidências.',revision=0)
        messages=[
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'creative-client','version':'1'}}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'reference','arguments':{'id':self.node['id']}}},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'save_note','arguments':{'id':self.node['id'],'text':'Continuar pelo contraponto recuperado.','revision':1}}},
        ]
        result=subprocess.run([sys.executable,'-m','lab','--db',str(self.lab.database),'mcp','--allow-writes'],
            input=''.join(json.dumps(m)+'\n' for m in messages),text=True,capture_output=True,timeout=10,
            cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(result.returncode,0,result.stderr)
        responses=[json.loads(line) for line in result.stdout.splitlines()]
        recovered=json.loads(responses[1]['result']['content'][0]['text'])
        self.assertIn('Continuar amanhã',recovered['note']['text'])
        events=self.lab.trajectory(self.node['id'])['events']
        edit=next(e for e in reversed(events) if e['kind']=='working_note_saved')
        self.assertEqual(edit['source_type'],'mcp_client')
        self.assertEqual(edit['source_ref'],'mcp:creative-client')
        self.assertIn('contraponto',self.call('reference',id=self.node['id'])['note']['text'])

    def test_packages_cannot_be_rewritten_and_verification_detects_projection_tampering(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute("UPDATE continuity_packages SET payload='{}'")
        self.lab.db.execute('DROP TRIGGER packages_immutable_update')
        self.lab.db.execute("UPDATE continuity_packages SET payload='{}'")
        self.assertEqual(self.call('verify')['error'],'continuity_package_mismatch')

    def test_long_intention_is_supported_and_examples_are_identified(self):
        result=self.call('investigate',query='Continuidade criativa '+('memória ' * 250),request_id=str(uuid.uuid4()))
        self.assertGreater(len(result['query']),1500)
        self.file.write_text('# Continuidade criativa\nExemplo hipotético: a convergência de documentos aumenta a criatividade.',encoding='utf-8')
        self.call('scan')
        ref=self.call('reference',id=self.node['id'])
        self.assertIn('hipotético',ref['package']['evidence'][0]['context_notice'])

    def test_initial_fragment_is_available_as_working_text_without_truncation(self):
        fragment='Um fragmento livre.\n' + ('Criar e continuar o pensamento. ' * 50)
        node=self.call('investigate',query=fragment,request_id=str(uuid.uuid4()))['question_node']
        self.assertEqual(len(node['title']),240)
        self.assertEqual(self.call('reference',id=node['id'])['note']['text'],fragment.strip())
        self.lab.close();self.lab=Lab(self.root/'lab.sqlite')
        self.assertEqual(self.call('reference',id=node['id'])['note']['text'],fragment.strip())

    def test_working_text_is_searchable_and_exportable(self):
        text='Anotação nova: transdisciplinaridade entre ferramentas.\nPróximo movimento: experimentar uma contraposição.'
        self.call('save_note',id=self.node['id'],text=text,revision=0)
        matches=self.call('ask',query='transdisciplinaridade')['nodes']
        self.assertEqual(matches[0]['id'],self.node['id'])
        export=self.call('export_reference',id=self.node['id'])['markdown']
        self.assertIn(text,export)
        self.assertIn('snapshot',export)
        self.assertEqual(self.call('reference',id=self.node['id'])['package']['next_movement'],'experimentar uma contraposição.')

    def test_no_source_is_read_without_authorization(self):
        other=self.root/'unauthorized';other.mkdir()
        (other/'secret.md').write_text('Continuidade criativa secreta')
        self.call('scan')
        evidence=self.call('reference',id=self.node['id'])['package']['evidence']
        self.assertTrue(all('secret' not in d['path'] for d in evidence))
        with self.assertRaises(PermissionError):
            execute(self.lab,'save_note',{'id':self.node['id'],'text':'X','revision':0})

    def test_transformations_and_git_versioning_workflow(self):
        # 1. Transform question into a hypothesis via transform_node
        res = self.call(
            'transform_node',
            source_id=self.node['id'],
            kind='hypothesis',
            title='A convergência emerge quando pacotes lexicais cruzam transformações versionadas em Git',
            body='Hipótese desdobrada a partir da questão central.',
            relation='evolves_into',
            reason='Desdobrar a questão em uma hipótese testável'
        )
        hyp = res['node']
        self.assertEqual(hyp['kind'], 'hypothesis')
        q_ref = self.call('reference', id=self.node['id'])
        self.assertEqual(len(q_ref['transformations']), 1)
        self.assertEqual(q_ref['transformations'][0]['direction'], 'outgoing')
        self.assertEqual(q_ref['transformations'][0]['relation'], 'evolves_into')
        self.assertEqual(q_ref['transformations'][0]['node']['id'], hyp['id'])

        h_ref = self.call('reference', id=hyp['id'])
        self.assertEqual(len(h_ref['transformations']), 1)
        self.assertEqual(h_ref['transformations'][0]['direction'], 'incoming')
        self.assertEqual(h_ref['transformations'][0]['node']['id'], self.node['id'])

        # 2. Version the question trajectory in Git (commit 1)
        g1 = self.call('git_checkpoint', id=self.node['id'])
        self.assertTrue(g1['versioned'])
        self.assertTrue(g1['committed'])
        self.assertEqual(len(g1['commits']), 1)
        # Calling git_checkpoint again without changes is idempotent (no empty commit)
        g1_repeat = self.call('git_checkpoint', id=self.node['id'])
        self.assertFalse(g1_repeat['committed'])
        self.assertEqual(len(g1_repeat['commits']), 1)

        # 3. Advance working text and record a second Git commit, inspecting diff
        self.call('save_note', id=self.node['id'], text='Desenvolvimento com hipótese vinculada.\n\nPróximo movimento: validar no Git.', revision=0)
        g2 = self.call('git_checkpoint', id=self.node['id'])
        self.assertTrue(g2['committed'])
        self.assertEqual(len(g2['commits']), 2)
        self.assertIn('+Desenvolvimento com hipótese vinculada.', g2['diff'])
        self.assertIn('evolves_into', Path(g2['path']).read_text(encoding='utf-8'))
        self.assertTrue(self.call('verify')['ok'])
