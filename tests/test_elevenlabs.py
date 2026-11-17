import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import bol_elevenlabs as el

class ElevenLabsTests(unittest.TestCase):
    def helper(self,folder):
        path=Path(folder)/'elevenlabs'
        path.write_text('#!'+sys.executable+'\nimport json,sys\nif sys.argv[1:3]==["auth","status"]: print(json.dumps({"schemes":[{"logged_in":True}]}))\nelse: print(json.dumps({"text":"Browser-connected transcript"}))\n')
        path.chmod(0o700);return str(path)

    def test_cli_auth_status_is_not_dashboard_sign_in(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(el,'workdir',return_value=Path(folder)):
            with patch.object(el,'cli_path',return_value=self.helper(folder)):
                self.assertEqual(el.status(),{'installed':True,'logged_in':True})

    def test_speech_uses_official_cli_without_copying_credentials(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(el,'workdir',return_value=Path(folder)):
            path=Path(folder)/'speech.wav';path.write_bytes(b'audio')
            with patch.object(el,'cli_path',return_value=self.helper(folder)):
                self.assertEqual(el.transcribe(path,{'language':'en-IN'}),'Browser-connected transcript')

    def test_missing_helper_is_reported(self):
        with patch.object(el,'cli_path',return_value=''):
            self.assertEqual(el.status(),{'installed':False,'logged_in':False})
            with self.assertRaisesRegex(RuntimeError,'Install and connect'):el.transcribe(Path('missing'),{})
