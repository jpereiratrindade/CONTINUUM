import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

from lab.api import catalog, execute
from lab.core import Lab, provenance


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'lab.sqlite'
        self.lab = Lab(self.path)
        self.node = self.call('create_node', kind='idea', title='Criação contínua', body='Meu esboço.')['id']

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def call(self, name, **args):
        return execute(self.lab, name, args, allow_writes=True)

    def proposal(self):
        with provenance('mcp_client', 'mcp:codex-teste'):
            return self.call('propose_note', id=self.node, text='Uma possibilidade aberta.', revision=0, request_id=str(uuid.uuid4()))

    def test_proposal_preserves_text_origin_and_retry_survives_restart(self):
        p = self.proposal()
        ref = self.call('reference', id=self.node)
        self.assertEqual(ref['note']['text'], 'Meu esboço.')
        self.assertEqual(ref['note']['revision'], 0)
        self.assertEqual(ref['proposals'][0]['source_ref'], 'mcp:codex-teste')
        self.assertEqual(ref['authorship']['edits'], 0)
        anchor = self.call('anchor')
        self.lab.close(); self.lab = Lab(self.path)
        retry = self.call('propose_note', id=self.node, text=p['text'], revision=0, request_id=p['id'])
        self.assertEqual(retry, p)
        self.assertEqual(anchor, self.call('anchor'))
        with self.assertRaisesRegex(ValueError, 'request_id'):
            self.call('propose_note', id=self.node, text='Outro texto', revision=0, request_id=p['id'])

    def test_incorporation_is_atomic_idempotent_and_keeps_both_origins(self):
        p = self.proposal()
        with provenance('user', 'browser-or-http-client'):
            args = dict(id=self.node, proposal_id=p['id'], state='incorporated', revision=0)
            self.call('review_proposal', **args)
            self.call('review_proposal', **args)
        ref = self.call('reference', id=self.node)
        self.assertEqual(ref['note']['text'], 'Meu esboço.\n\nUma possibilidade aberta.')
        self.assertEqual(ref['note']['revision'], 1)
        self.assertEqual(ref['authorship']['last_edit']['source_ref'], 'browser-or-http-client')
        self.assertEqual(ref['authorship']['proposal']['source_ref'], 'mcp:codex-teste')
        self.assertEqual(ref['authorship']['edits'], 1)
        event = next(e for e in self.lab.trajectory(self.node)['events'] if e['kind'] == 'working_note_saved')
        self.assertEqual(event['payload']['before']['text'], 'Meu esboço.')
        self.assertEqual(event['payload']['proposal']['event_id'], p['event_id'])
        self.assertTrue(self.call('verify')['ok'])

    def test_concurrent_edit_rejects_old_preview_then_uses_new_revision(self):
        p = self.proposal()
        other = Lab(self.path)
        try:
            execute(other, 'save_note', dict(id=self.node, text='Nova edição humana.', revision=0), allow_writes=True)
        finally:
            other.close()
        with self.assertRaisesRegex(ValueError, 'outro ambiente'):
            self.call('review_proposal', id=self.node, proposal_id=p['id'], state='incorporated', revision=0)
        self.assertEqual(self.call('reference', id=self.node)['proposals'][0]['state'], 'pending')
        self.call('review_proposal', id=self.node, proposal_id=p['id'], state='incorporated', revision=1)
        self.assertEqual(self.call('reference', id=self.node)['note']['text'], 'Nova edição humana.\n\n'+p['text'])

    def test_dismissal_is_durable_and_cannot_be_incorporated_later(self):
        p = self.proposal()
        self.call('review_proposal', id=self.node, proposal_id=p['id'], state='dismissed', revision=0)
        self.lab.close(); self.lab = Lab(self.path)
        retry = self.call('propose_note', id=self.node, text=p['text'], revision=0, request_id=p['id'])
        self.assertEqual(retry['state'], 'dismissed')
        self.assertEqual(self.call('reference', id=self.node)['note']['text'], 'Meu esboço.')
        with self.assertRaisesRegex(ValueError, 'já foi examinada'):
            self.call('review_proposal', id=self.node, proposal_id=p['id'], state='incorporated', revision=0)

    def test_mcp_cannot_review_its_own_proposal(self):
        p = self.proposal()
        self.assertNotIn('review_proposal', [t['name'] for t in catalog(True)])
        with provenance('mcp_client', 'mcp:codex-teste'), self.assertRaises(PermissionError):
            self.call('review_proposal', id=self.node, proposal_id=p['id'], state='incorporated', revision=0)
        with self.assertRaises(PermissionError):
            execute(self.lab, 'propose_note', dict(id=self.node, text='Teste', revision=0, request_id=str(uuid.uuid4())))

    def test_real_mcp_subprocess_delivers_pending_proposal(self):
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'external-assistant'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'propose_note', 'arguments': {'id': self.node, 'text': 'Contraponto via MCP.', 'revision': 0, 'request_id': str(uuid.uuid4())}}},
        ]
        result = subprocess.run([sys.executable, '-m', 'lab', '--db', str(self.path), 'mcp', '--allow-writes'],
                                input=''.join(json.dumps(m)+'\n' for m in messages), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout.splitlines()[-1])['result']
        self.assertFalse(response['isError'])
        ref = self.call('reference', id=self.node)
        self.assertEqual(ref['proposals'][0]['source_ref'], 'mcp:external-assistant')
        self.assertEqual(ref['note']['text'], 'Meu esboço.')

    def test_invalid_proposal_or_oversized_incorporation_changes_nothing(self):
        with self.assertRaises(ValueError):
            self.call('propose_note', id=self.node, text='Teste', revision=0, request_id='x'*36)
        p = self.proposal()
        self.call('save_note', id=self.node, text='x'*20000, revision=0)
        with self.assertRaisesRegex(ValueError, 'limite'):
            self.call('review_proposal', id=self.node, proposal_id=p['id'], state='incorporated', revision=1)
        ref = self.call('reference', id=self.node)
        self.assertEqual(ref['note']['revision'], 1)
        self.assertEqual(ref['proposals'][0]['state'], 'pending')

    def test_verification_detects_proposal_state_tampering(self):
        p = self.proposal()
        self.lab.db.execute("UPDATE note_proposals SET state='incorporated' WHERE id=?", (p['id'],))
        self.assertEqual(self.call('verify')['error'], 'note_proposal_mismatch')
