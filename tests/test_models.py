import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from bol_models import download_model, SecureDownloadRedirect


class ModelDownloadTests(unittest.TestCase):
    def run_download(self, payload=b'model data', expected=b'model data', cancel=False):
        catalog={'test':{'size':len(expected),'sha256':hashlib.sha256(expected).hexdigest()}}
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'ggml-test.bin'
            destination.write_bytes(b'old model')
            response=io.BytesIO(payload)
            opener=Mock();opener.open.return_value=response
            with patch('bol_models.MODELS',catalog), patch('bol_models.urllib.request.build_opener',return_value=opener):
                if cancel or payload!=expected:
                    with self.assertRaises(ValueError):download_model('test',lambda:cancel,folder=folder)
                    self.assertEqual(destination.read_bytes(),b'old model')
                else:
                    result=download_model('test',folder=folder)
                    self.assertEqual(result.read_bytes(),expected)
                    self.assertEqual(result.stat().st_mode & 0o777,0o600)
            self.assertEqual(list(Path(folder).iterdir()),[destination])

    def test_verified_download_is_atomic_and_private(self):self.run_download()
    def test_checksum_failure_preserves_existing_model(self):self.run_download(b'evil data!')
    def test_truncated_download_is_removed(self):self.run_download(b'x')
    def test_oversized_download_is_removed(self):self.run_download(b'x'*100)
    def test_cancellation_removes_partial_file(self):self.run_download(cancel=True)
    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):download_model('../../outside')
    def test_redirect_rejects_plain_http_and_credentials(self):
        for url in ['http://example.com/file','https://user:password@example.com/file','file:///etc/passwd']:
            with self.assertRaises(ValueError):SecureDownloadRedirect().redirect_request(None,None,302,'',{},url)
