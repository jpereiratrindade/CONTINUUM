import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lab.api import execute
from lab.core import Lab
from lab.mcp import MCPServer, serve


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lab = Lab(Path(self.temp.name) / 'lab.sqlite')
        self.server = MCPServer(self.lab)

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def call(self, method, params=None, server=None):
        return (server or self.server).handle({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})

    def initialize(self, server=None):
        server = server or self.server
        response = self.call('initialize', {'protocolVersion': '2025-11-25', 'clientInfo': {'name': 'test', 'version': '1'}, 'capabilities': {}}, server)
        self.assertEqual(response['result']['protocolVersion'], '2025-11-25')
        self.assertIsNone(server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))

    def test_lifecycle_and_readonly_enforced(self):
        self.assertEqual(self.call('tools/list')['error']['code'], -32000)
        self.initialize()
        tools = self.call('tools/list')['result']['tools']
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in tools))
        self.assertNotIn('create_node', [t['name'] for t in tools])
        response = self.call('tools/call', {'name': 'create_node', 'arguments': {'kind': 'question', 'title': 'X'}})
        self.assertTrue(response['result']['isError'])
        self.assertEqual(self.lab.nodes(), [])

    def test_writes_history_and_integrity(self):
        server = MCPServer(self.lab, True)
        self.initialize(server)
        def invoke(name, args):
            result = self.call('tools/call', {'name': name, 'arguments': args}, server)['result']
            self.assertFalse(result['isError'])
            return json.loads(result['content'][0]['text'])
        node = invoke('create_node', {'kind': 'question', 'title': 'Questão inicial'})
        invoke('revise_node', {'id': node['id'], 'title': 'Questão revista', 'reason': 'Precisar contexto'})
        history = invoke('trajectory', {'id': node['id']})
        self.assertEqual(len(history['events']), 2)
        self.assertTrue(invoke('verify', {})['ok'])

    def test_invalid_arguments_and_unknown_methods(self):
        self.initialize()
        for args in ({'limit': -1}, {'limit': True}, {'limit': 501}, {'extra': 'x'}, [], {'offset': 2**63}):
            response = self.call('tools/call', {'name': 'nodes', 'arguments': args})
            self.assertEqual(response['error']['code'], -32602)
        self.assertEqual(self.call('tools/call', {'name': 'missing'})['error']['code'], -32602)
        self.assertEqual(self.call('missing')['error']['code'], -32601)
        self.assertEqual(self.server.handle([])['error']['code'], -32600)
        self.assertIsNone(self.server.handle({'jsonrpc': '2.0', 'method': 'unknown_notification'}))

    def test_tool_failure_is_not_protocol_error(self):
        self.initialize()
        result = self.call('tools/call', {'name': 'node', 'arguments': {'id': 'missing'}})
        self.assertTrue(result['result']['isError'])

    def test_pagination_no_overlap_and_stream_filter(self):
        nodes = [self.lab.create_node('idea', f'Idea {i}') for i in range(3)]
        first = execute(self.lab, 'nodes', {'limit': 2})
        second = execute(self.lab, 'nodes', {'offset': first['next_offset'], 'limit': 2})
        self.assertEqual(len({n['id'] for n in first['nodes'] + second['nodes']}), 3)
        events = execute(self.lab, 'events', {'limit': 2})
        rest = execute(self.lab, 'events', {'after': events['next_after']})
        self.assertEqual(len(events['events'] + rest['events']), 3)
        filtered = execute(self.lab, 'events', {'stream_id': nodes[0]['id']})
        self.assertEqual(len(filtered['events']), 1)

    def test_document_reads_observed_snapshot(self):
        folder = Path(self.temp.name) / 'source'
        folder.mkdir()
        file = folder / 'research.md'
        file.write_text('# Pesquisa\nEvidência original', encoding='utf-8')
        source = self.lab.register_source(str(folder), 'Research')
        self.lab.scan()
        docs = execute(self.lab, 'documents', {'source_id': source['id']})['documents']
        file.write_text('Alteração ainda não observada', encoding='utf-8')
        doc = execute(self.lab, 'document', {'id': docs[0]['id']})
        self.assertIn('Evidência original', doc['body'])
        self.assertNotIn('body', docs[0])
        self.assertEqual(execute(self.lab, 'documents', {'source_id': 'missing'})['documents'], [])

    def test_stdio_parse_error_recovery(self):
        output = io.StringIO()
        serve(self.lab, stdin=io.StringIO('broken\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n'), stdout=output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]['error']['code'], -32700)
        self.assertEqual(responses[1]['result'], {})

    def test_real_cli_process_stdout_is_only_jsonrpc(self):
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'create_node', 'arguments': {'kind': 'idea', 'title': 'Via subprocesso'}}},
        ]
        result = subprocess.run([sys.executable, '-m', 'lab', '--db', str(self.lab.database), 'mcp', '--allow-writes'],
                                input=''.join(json.dumps(m) + '\n' for m in messages), text=True,
                                capture_output=True, timeout=10, cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r['id'] for r in responses], [1, 2, 3])
        self.assertFalse(responses[-1]['result']['isError'])
        self.assertEqual(self.lab.nodes()[0]['title'], 'Via subprocesso')
        self.assertTrue(self.lab.verify()['ok'])
