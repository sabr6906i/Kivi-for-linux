import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bol', Path(__file__).parents[1] / 'kivi_linux.py')
bol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bol)

class Tests(unittest.TestCase):
    def test_multipart_keeps_audio_and_language(self):
        body, boundary = bol.multipart(b'RIFF\x00audio', 'pa-IN')
        self.assertIn(b'RIFF\x00audio', body)
        self.assertIn(b'pa-IN', body)
        self.assertTrue(body.endswith(f'--{boundary}--\r\n'.encode()))

    def test_settings_private_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bol, 'CONFIG', Path(directory)):
            bol.save_config({'api_key': 'test-secret', 'language': 'unknown'})
            self.assertEqual(bol.config()['api_key'], 'test-secret')
            self.assertEqual((Path(directory) / 'settings.json').stat().st_mode & 0o777, 0o600)

    def test_cancel_stops_recorder_and_cleans_audio(self):
        import subprocess
        service = bol.Service()
        directory = tempfile.TemporaryDirectory()
        folder = Path(directory.name)
        service.directory = directory
        service.recorder = subprocess.Popen(['sleep', '30'])
        recorder = service.recorder
        service.state = 'Recording'
        with patch.object(bol, 'notify') as notification:
            result = service.command('cancel')
        self.assertIsNotNone(recorder.poll())
        self.assertFalse(folder.exists())
        self.assertEqual(result['state'], 'Ready')
        self.assertEqual(result['error'], '')
        notification.assert_called_once_with('Cancelled. Microphone stopped.')

    def test_cancel_discards_pending_result_without_upload(self):
        service = bol.Service()
        service.state = 'Transcribing'
        before = service.generation
        with patch.object(bol, 'notify'):
            self.assertEqual(service.command('cancel')['state'], 'Ready')
        self.assertGreater(service.generation, before)

if __name__ == '__main__':
    unittest.main()
