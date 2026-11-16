import base64
import io
import json
import unittest
import wave
from unittest.mock import Mock,patch
from bol_audio import synthesize


def clip():
    data=io.BytesIO()
    with wave.open(data,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b'\0\0'*2400)
    return data.getvalue()

class AudioTests(unittest.TestCase):
    def response(self,value):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps(value).encode();return response

    def test_request_and_wav_decoding(self):
        with patch('urllib.request.urlopen',return_value=self.response({'audios':[base64.b64encode(clip()).decode()]})) as call:
            result=synthesize('ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ','private-key','pa-IN','simran',1.2)
        payload=json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['model'],'bulbul:v3');self.assertEqual(payload['language_code'],'pa-IN');self.assertEqual(payload['pace'],1.2)
        self.assertNotIn('private-key',json.dumps(payload))
        with wave.open(io.BytesIO(result),'rb') as audio:self.assertEqual(audio.getnframes(),2400)

    def test_multiple_wav_segments_are_joined_without_extra_headers(self):
        encoded=base64.b64encode(clip()).decode()
        with patch('urllib.request.urlopen',return_value=self.response({'audios':[encoded,encoded]})):
            result=synthesize('A sample','key')
        with wave.open(io.BytesIO(result),'rb') as audio:self.assertEqual(audio.getnframes(),4800)

    def test_invalid_requests_do_not_call_api(self):
        with patch('urllib.request.urlopen') as network:
            for text,key in [('', 'key'),('x'*2501,'key'),('hello','')]:
                with self.assertRaises(ValueError):synthesize(text,key)
            network.assert_not_called()

    def test_invalid_audio_is_reported(self):
        with patch('urllib.request.urlopen',return_value=self.response({'audios':['not base64']})):
            with self.assertRaisesRegex(RuntimeError,'invalid WAV'):synthesize('hello','key')
