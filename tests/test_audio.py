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
        with patch('bol_audio.open_api',return_value=self.response({'audios':[base64.b64encode(clip()).decode()]})) as call:
            result=synthesize('ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ','private-key','pa-IN','simran',1.2)
        payload=json.loads(call.call_args.args[0].data)
        self.assertEqual(payload['model'],'bulbul:v3');self.assertEqual(payload['language_code'],'pa-IN');self.assertEqual(payload['pace'],1.2)
        self.assertNotIn('private-key',json.dumps(payload))
        with wave.open(io.BytesIO(result),'rb') as audio:self.assertEqual(audio.getnframes(),2400)

    def test_multiple_wav_segments_are_joined_without_extra_headers(self):
        encoded=base64.b64encode(clip()).decode()
        with patch('bol_audio.open_api',return_value=self.response({'audios':[encoded,encoded]})):
            result=synthesize('A sample','key')
        with wave.open(io.BytesIO(result),'rb') as audio:self.assertEqual(audio.getnframes(),4800)

    def test_invalid_requests_do_not_call_api(self):
        with patch('bol_audio.open_api') as network:
            for text,key in [('', 'key'),('x'*2501,'key'),('hello','')]:
                with self.assertRaises(ValueError):synthesize(text,key)
            network.assert_not_called()

    def test_invalid_audio_is_reported(self):
        with patch('bol_audio.open_api',return_value=self.response({'audios':['not base64']})):
            with self.assertRaisesRegex(RuntimeError,'invalid WAV'):synthesize('hello','key')

class DeliveryStyleTests(unittest.TestCase):
    def response(self,content):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps({'choices':[{'message':{'content':content}}]}).encode()
        return response

    def test_instructions_choose_controls_not_script(self):
        from bol_audio import suggest_delivery
        with patch('bol_audio.open_api',return_value=self.response('{"voice":"roopa","pace":0.85,"temperature":0.4}')) as network:
            plan=suggest_delivery('Warm and soothing, a little slower',{'api_key':'secret'},'pa-IN')
        self.assertEqual(plan['voice'],'roopa')
        payload=json.loads(network.call_args.args[0].data)
        self.assertIsNone(payload['reasoning_effort'])
        self.assertEqual(payload['response_format'],{'type':'json_object'})
        self.assertGreaterEqual(payload['max_tokens'],1024)
        user=json.loads(payload['messages'][1]['content'])
        self.assertEqual(user['language'],'pa-IN');self.assertIn('soothing',user['instructions'])
        self.assertNotIn('text',user);self.assertNotIn('secret',json.dumps(payload))

    def test_invalid_suggestions_are_rejected(self):
        from bol_audio import suggest_delivery
        for content in ['{"voice":"invented","pace":1,"temperature":0.6}', '{"voice":"roopa","pace":8,"temperature":0.6}', '{"voice":"roopa","pace":1,"temperature":2}', 'Not JSON']:
            with patch('bol_audio.open_api',return_value=self.response(content)):
                with self.assertRaisesRegex(RuntimeError,'invalid style'):suggest_delivery('Calm',{'api_key':'secret'})

    def test_all_presets_use_supported_controls(self):
        from bol_audio import STYLE_PRESETS,TTS_VOICES
        for plan in STYLE_PRESETS.values():
            if plan:
                self.assertIn(plan['voice'],TTS_VOICES)
                self.assertTrue(.5<=plan['pace']<=2)
                self.assertTrue(.01<=plan['temperature']<=1)

    def test_compatible_writing_provider_can_interpret_instructions(self):
        from bol_audio import suggest_delivery
        reply={'choices':[{'message':{'content':'{"voice":"ritu","pace":1.1,"temperature":0.7}'}}]}
        with patch('bol_providers.chat_api',return_value=reply) as chat:
            plan=suggest_delivery('Energetic',{'writing_provider':'compatible'})
        self.assertEqual(plan['voice'],'ritu');chat.assert_called_once()
