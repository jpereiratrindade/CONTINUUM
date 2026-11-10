"""CLI errors should explain how to recover without a traceback."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def test_busy_port_reports_actionable_message(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as folder, socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            env = {**os.environ, 'LAB_DB': str(Path(folder) / 'lab.sqlite'),
                   'LAB_WORKSPACE': str(Path(folder) / 'workspace')}
            commands = [
                [sys.executable, '-m', 'lab', '--db', env['LAB_DB'], 'serve', '--port', str(port)],
                [str(root / 'run.sh'), '--port', str(port)],
            ]
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(command, cwd=root, env=env, text=True,
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(f'A porta {port} já está em uso', result.stderr)
                    self.assertIn(f'http://127.0.0.1:{port}', result.stderr)
                    self.assertIn('--port', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertEqual(result.stdout, '')
