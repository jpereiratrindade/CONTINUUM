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
        self.assertEqual([e['kind'] for e in history['events']], ['node_created', 'continuity_prepared', 'node_revised', 'continuity_prepared'])
        self.assertEqual(history['events'][0]['source_type'], 'mcp_client')
        self.assertEqual(history['events'][0]['source_ref'], 'mcp:test')
        self.assertEqual(history['events'][1]['source_type'], 'automation')
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

    def test_streamable_http_mcp_endpoint_and_auth(self):
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        from lab.server import create_handler

        node = self.lab.create_node('question', 'Continuidade entre ambientes', 'Histórico preservado')
        http_srv = ThreadingHTTPServer(('127.0.0.1', 0), create_handler(self.lab, mcp_token='secret-token'))
        port = http_srv.server_port
        thread = threading.Thread(target=http_srv.serve_forever, daemon=True)
        thread.start()
        try:
            def post_mcp(payload, token='secret-token', session_id=None, host=f'127.0.0.1:{port}', origin=None):
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                headers = {'Host': host, 'Content-Type': 'application/json'}
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                if session_id:
                    headers['Mcp-Session-Id'] = session_id
                if origin:
                    headers['Origin'] = origin
                conn.request('POST', '/mcp', json.dumps(payload).encode('utf-8'), headers=headers)
                resp = conn.getresponse()
                body = resp.read()
                sid = resp.getheader('Mcp-Session-Id')
                status = resp.status
                conn.close()
                return status, (json.loads(body) if body else None), sid

            # Reject external Origin even with valid Bearer token (MCP spec Origin validation)
            status, _, _ = post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, origin='https://evil.example')
            self.assertEqual(status, 403)

            # Reject missing or wrong token
            status, _, _ = post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token='wrong')
            self.assertEqual(status, 401)

            # Do not claim 2024-11-05 (legacy HTTP+SSE); respond with server's supported Streamable HTTP version
            status, legacy_res, _ = post_mcp(
                {'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                 'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'legacy', 'version': '1'}}}
            )
            self.assertEqual(status, 200)
            self.assertEqual(legacy_res['result']['protocolVersion'], '2025-11-25')

            # Initialize over Streamable HTTP (even via external tunnel Host when Bearer token is valid)
            status, init_res, sid = post_mcp(
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                 'params': {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'chatgpt', 'version': '1'}}},
                host='continuum.example.org'
            )
            self.assertEqual(status, 200)
            self.assertTrue(sid)
            self.assertEqual(init_res['result']['protocolVersion'], '2025-03-26')

            # Notification returns 202 Accepted
            status, notif_res, _ = post_mcp({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, session_id=sid)
            self.assertEqual(status, 202)
            self.assertIsNone(notif_res)

            # Read node and trajectory over HTTP /mcp
            status, call_res, _ = post_mcp(
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                 'params': {'name': 'trajectory', 'arguments': {'id': node['id']}}},
                session_id=sid
            )
            self.assertEqual(status, 200)
            self.assertFalse(call_res['result']['isError'])
            traj = json.loads(call_res['result']['content'][0]['text'])
            self.assertEqual(traj['node']['id'], node['id'])
        finally:
            http_srv.shutdown()
            thread.join(timeout=3)
            http_srv.server_close()

    def test_e2e_001_cross_environment_continuity_protocol(self):
        """E2E-001: Cross-environment continuity between Web HTTP and independent MCP client process."""
        import http.client
        import threading
        import uuid
        from http.server import ThreadingHTTPServer
        from lab.server import create_handler

        # Prepare an authorized document source so lexical recovery and snapshots are exercised
        docs_dir = Path(self.temp.name) / 'authorized_docs'
        docs_dir.mkdir()
        (docs_dir / 'protocolo.md').write_text(
            '# Continuidade Intelectual\nPreservação de proveniência, temporalidade e hipóteses entre ambientes.',
            encoding='utf-8'
        )
        db_path = Path(self.temp.name) / 'lab.sqlite'
        ws_path = Path(self.temp.name) / 'workspace'

        def start_web(lab_instance):
            srv = ThreadingHTTPServer(('127.0.0.1', 0), create_handler(lab_instance))
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            return srv, t

        def http_call(port, method, path, data=None):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            headers = {'Host': f'127.0.0.1:{port}'}
            body = None
            if data is not None:
                body = json.dumps(data).encode('utf-8')
                headers.update({'Content-Type': 'application/json', 'X-Lab-Intent': 'user'})
            conn.request(method, path, body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            status = resp.status
            conn.close()
            return status, json.loads(raw)

        def mcp_subprocess(messages, allow_writes=False):
            cmd = [sys.executable, '-m', 'lab', '--db', str(db_path), '--workspace', str(ws_path), 'mcp']
            if allow_writes:
                cmd.append('--allow-writes')
            res = subprocess.run(
                cmd,
                input=''.join(json.dumps(m) + '\n' for m in messages),
                text=True, capture_output=True, timeout=10,
                cwd=Path(__file__).resolve().parent.parent
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            return [json.loads(line) for line in res.stdout.splitlines()]

        # 1. Start investigation in Web UI (and authorize + scan source)
        srv, thread = start_web(self.lab)
        try:
            port = srv.server_port
            status, _ = http_call(port, 'POST', '/api/sources', {'path': str(docs_dir), 'label': 'Protocolo'})
            self.assertEqual(status, 200)
            status, _ = http_call(port, 'POST', '/api/scan', {})
            self.assertEqual(status, 200)

            inv_req_id = str(uuid.uuid4())
            inv_query = 'Como sustentar continuidade intelectual e proveniência entre ambientes?'
            status, inv = http_call(port, 'POST', '/api/investigations', {'query': inv_query, 'request_id': inv_req_id})
            self.assertEqual(status, 200)
            q_id = inv['question_node']['id']

            # 2 & 3. Recover the same investigation from an independent read-only MCP client process
            mcp_read_msgs = [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'audit-reader', 'version': '1.0'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'reference', 'arguments': {'id': q_id}}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'trajectory', 'arguments': {'id': q_id}}},
            ]
            read_out = mcp_subprocess(mcp_read_msgs, allow_writes=False)
            ref_data = json.loads(read_out[1]['result']['content'][0]['text'])
            traj_data = json.loads(read_out[2]['result']['content'][0]['text'])
            self.assertEqual(ref_data['node']['id'], q_id)
            self.assertEqual(ref_data['node']['body'], inv_query)
            self.assertTrue(len(ref_data['package']['evidence']) >= 1)
            self.assertEqual(traj_data['events'][0]['source_type'], 'user')
            self.assertEqual(traj_data['events'][0]['source_ref'], 'browser-or-http-client')

            # 4. Register a new hypothesis and propose a note via authorized MCP client (--allow-writes)
            prop_req_id = str(uuid.uuid4())
            mcp_write_msgs = [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'chatgpt-tunnel', 'version': '1.0'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                 'params': {'name': 'create_node', 'arguments': {
                     'kind': 'hypothesis',
                     'title': 'Continuidade exige eventos imutáveis e revisão humana de propostas',
                     'body': 'Hipótese registrada via MCP sem promoção automática a fato.'
                 }}},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                 'params': {'name': 'propose_note', 'arguments': {
                     'id': q_id,
                     'text': 'Trecho proposto pelo assistente via MCP para avaliação humana.',
                     'revision': 0,
                     'request_id': prop_req_id
                 }}},
            ]
            write_out = mcp_subprocess(mcp_write_msgs, allow_writes=True)
            hyp_node = json.loads(write_out[1]['result']['content'][0]['text'])
            prop_data = json.loads(write_out[2]['result']['content'][0]['text'])
            self.assertEqual(hyp_node['kind'], 'hypothesis')
            self.assertEqual(prop_data['state'], 'pending')

            # Link candidate relation via MCP
            mcp_link_msgs = [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'chatgpt-tunnel', 'version': '1.0'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                 'params': {'name': 'add_link', 'arguments': {
                     'source_id': hyp_node['id'], 'target_id': q_id,
                     'relation': 'relates_to', 'reason': 'Hipótese responde à questão inicial', 'state': 'candidate'
                 }}},
            ]
            link_out = mcp_subprocess(mcp_link_msgs, allow_writes=True)
            link_data = json.loads(link_out[1]['result']['content'][0]['text'])
            self.assertEqual(link_data['state'], 'candidate')

            # 5. Verify in Web UI: original text is untouched while proposal is pending; then incorporate preserving history
            status, web_ref_before = http_call(port, 'GET', f'/api/reference?id={q_id}')
            self.assertEqual(status, 200)
            self.assertEqual(web_ref_before['note']['text'], inv_query)
            self.assertEqual(web_ref_before['note']['revision'], 0)
            pending_props = [p for p in web_ref_before['proposals'] if p['state'] == 'pending']
            self.assertEqual(len(pending_props), 1)
            self.assertEqual(pending_props[0]['source_ref'], 'mcp:chatgpt-tunnel')

            status, review_res = http_call(port, 'POST', '/api/reference/proposal/review', {
                'id': q_id, 'proposal_id': prop_data['id'], 'state': 'incorporated', 'revision': 0
            })
            self.assertEqual(status, 200)
            self.assertEqual(review_res['state'], 'incorporated')
            status, web_ref_after = http_call(port, 'GET', f'/api/reference?id={q_id}')
            self.assertEqual(status, 200)
            self.assertEqual(web_ref_after['note']['revision'], 1)
            self.assertIn(inv_query, web_ref_after['note']['text'])
            self.assertIn('Trecho proposto pelo assistente via MCP', web_ref_after['note']['text'])

            # 6. Repeat operations (idempotence)
            status, inv_retry = http_call(port, 'POST', '/api/investigations', {'query': inv_query, 'request_id': inv_req_id})
            self.assertEqual(status, 200)
            self.assertEqual(inv_retry['question_node']['id'], q_id)
        finally:
            srv.shutdown()
            thread.join(timeout=3)
            srv.server_close()

        # Simulate full service restart: close Lab, reopen from disk, verify persistence, provenance and anchor
        anchor_before_restart = self.lab.anchor()
        self.lab.close()
        self.lab = Lab(db_path, ws_path)
        srv2, thread2 = start_web(self.lab)
        try:
            port2 = srv2.server_port
            status, verify_res = http_call(port2, 'GET', '/api/verify')
            self.assertEqual(status, 200)
            self.assertTrue(verify_res['ok'])
            self.assertTrue(self.lab.verify(anchor_before_restart)['ok'])

            status, traj_after = http_call(port2, 'GET', f'/api/trajectory?id={q_id}')
            self.assertEqual(status, 200)
            event_kinds = [e['kind'] for e in traj_after['events']]
            self.assertIn('node_created', event_kinds)
            self.assertIn('note_proposed', event_kinds)
            self.assertIn('note_proposal_reviewed', event_kinds)
            self.assertIn('working_note_saved', event_kinds)
        finally:
            srv2.shutdown()
            thread2.join(timeout=3)
            srv2.server_close()
