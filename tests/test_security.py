"""Security boundary regressions; no real provider credentials or user data."""
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
import urllib.request

import kivi_linux as bol
from bol_providers import open_api, read_json


class SecurityTests(unittest.TestCase):
    def test_provider_redirect_never_reaches_destination(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.send_response(302 if self.path == '/start' else 200)
                self.send_header('Location', '/capture')
                self.end_headers()
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/start',
                                             headers={'api-subscription-key': 'test-secret'})
            with self.assertRaisesRegex(RuntimeError, 'redirected'):
                open_api(request)
            self.assertEqual(received, ['/start'])
        finally:
            server.shutdown(); server.server_close(); worker.join()

    def test_response_size_enforced_before_json_parse(self):
        with self.assertRaisesRegex(RuntimeError, 'allowed size'):
            read_json(io.BytesIO(b' ' * 101), limit=100)
        self.assertEqual(read_json(io.BytesIO(b'{"ok":true}')), {'ok': True})

    def test_runtime_rejects_shared_and_symlink_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime = root / 'bol-linux'
            with patch.object(bol, 'RUNTIME', runtime), patch.dict(os.environ, {'XDG_RUNTIME_DIR': folder}):
                bol.secure_runtime()
                self.assertEqual(runtime.stat().st_mode & 0o777, 0o700)
                runtime.chmod(0o755)
                with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                    bol.secure_runtime()
                runtime.rmdir()
                runtime.symlink_to(root, target_is_directory=True)
                with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                    bol.secure_runtime()

    def test_fallback_runtime_rejects_shared_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder) / 'fallback'
            parent.mkdir(mode=0o755)
            parent.chmod(0o755)
            with patch.object(bol, 'RUNTIME', parent / 'bol-linux'), patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                    bol.secure_runtime()

    def test_history_secure_delete_on_every_connection(self):
        from bol_features import History
        with tempfile.TemporaryDirectory() as folder:
            history = History(folder)
            with history.connect() as db:
                self.assertEqual(db.execute('PRAGMA secure_delete').fetchone()[0], 1)

    def test_multiline_terminal_output_is_not_automatically_pasted(self):
        service = bol.Service()
        with patch.object(bol, 'active_window', return_value={'address': 'target'}), \
             patch.object(bol, 'copy_text'), patch.object(bol, 'notify'), \
             patch.object(bol, 'shortcut') as shortcut:
            service.commit_result(0, 'echo hello\ncommand', '', {'auto_paste': True},
                                  'kitty', 'dictate', '', 'target')
            shortcut.assert_not_called()
            self.assertIn('review', service.outcome)
