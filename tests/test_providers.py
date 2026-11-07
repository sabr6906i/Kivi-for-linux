import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from bol_providers import transcribe_local,transcribe_api,chat_api,validate_speech,api_endpoint

class ProviderTests(unittest.TestCase):
    def fixture(self,folder,script):
        binary=Path(folder)/'whisper-cli'
        binary.write_text('#!'+sys.executable+'\n'+script)
        binary.chmod(0o700)
        model=Path(folder)/'ggml-small.en.bin';model.write_bytes(b'model')
        audio=Path(folder)/'speech.wav';audio.write_bytes(b'RIFF audio')
        settings={'speech_provider':'whispercpp','whisper_binary':str(binary),'whisper_model':str(model),'language':'en-IN'}
        return audio,settings

    def test_local_transcription_needs_no_key_or_network(self):
        with tempfile.TemporaryDirectory() as folder:
            audio,settings=self.fixture(folder,"import sys\nfrom pathlib import Path\na=sys.argv\nPath(a[a.index('-of')+1]+'.txt').write_text('Local transcript')\n")
            self.assertEqual(transcribe_local(audio,settings),'Local transcript')

    def test_local_cancellation_terminates_child(self):
        with tempfile.TemporaryDirectory() as folder:
            audio,settings=self.fixture(folder,'import time\ntime.sleep(30)\n')
            start=time.monotonic()
            with self.assertRaisesRegex(RuntimeError,'Cancelled'):
                transcribe_local(audio,settings,lambda:time.monotonic()-start>.1)
            self.assertLess(time.monotonic()-start,2)

    def test_english_model_rejects_punjabi(self):
        with tempfile.TemporaryDirectory() as folder:
            _,settings=self.fixture(folder,'pass')
            settings['language']='pa-IN'
            with self.assertRaisesRegex(ValueError,'English-only'):validate_speech(settings)

    def test_endpoint_validation(self):
        self.assertEqual(api_endpoint('http://localhost:8080/v1/chat/completions'),'http://localhost:8080/v1/chat/completions')
        for url in ['http://external.example/api','https://user:password@example.com/api','https://example.com/api?key=secret']:
            with self.assertRaises(ValueError):api_endpoint(url)

    def test_compatible_speech_and_chat_use_separate_keys(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=self.rfile.read(int(self.headers['Content-Length']))
                received.append((self.path,self.headers.get('Authorization'),body))
                reply={'text':'API transcript'} if self.path=='/audio/transcriptions' else {'choices':[{'message':{'content':'Edited text'}}]}
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(reply).encode())
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            base='http://127.0.0.1:'+str(server.server_port)
            with tempfile.TemporaryDirectory() as folder:
                audio=Path(folder)/'sample.wav';audio.write_bytes(b'RIFF test')
                settings={'speech_provider':'compatible','speech_api_url':base+'/audio/transcriptions','speech_api_model':'whisper-test','speech_api_key':'speech-secret','writing_api_url':base+'/chat/completions','writing_api_model':'writer-test','writing_api_key':'writer-secret','api_key':'sarvam-secret'}
                self.assertEqual(transcribe_api(audio,settings),'API transcript')
                self.assertEqual(chat_api({'messages':[]},settings)['choices'][0]['message']['content'],'Edited text')
            self.assertEqual(received[0][1],'Bearer speech-secret')
            self.assertEqual(received[1][1],'Bearer writer-secret')
            self.assertIn(b'whisper-test',received[0][2])
            self.assertEqual(json.loads(received[1][2])['model'],'writer-test')
            self.assertTrue(all(b'sarvam-secret' not in body for _,_,body in received))
        finally:server.shutdown();server.server_close();worker.join()
