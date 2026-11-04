import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import kivi_linux as bol
from bol_features import expand, write, History
from bol_ui import parse_pairs

class PersonalizationTests(unittest.TestCase):
    def test_snippet_is_whole_phrase_and_preserves_expansion(self):
        settings = {'snippets': {'my signature': 'Sarbjeet\nDeveloper'}}
        self.assertEqual(expand('My signature.', settings), ('Sarbjeet\nDeveloper', True))
        self.assertEqual(expand('Here is my signature.', settings), ('Here is my signature.', False))

    def test_corrections_do_not_change_substrings_or_cascade(self):
        text, _ = expand('sara met SARVAM and concatenate cat', {'corrections': {'sara':'Sarvam','Sarvam':'Sarvam AI','cat':'dog'}})
        self.assertEqual(text, 'Sarvam met Sarvam AI and concatenate dog')

    def test_indic_corrections(self):
        self.assertEqual(expand('ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ', {'corrections': {'ਅਕਾਲ':'ਅਕਾਲ ਜੀ'}})[0], 'ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ')

    def test_pairs_with_multiline_snippet(self):
        self.assertEqual(parse_pairs('signature => hello\\nworld'), {'signature':'hello\nworld'})
        with self.assertRaises(ValueError): parse_pairs('missing delimiter')

    def test_private_history_retention_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            history = History(folder)
            for n in range(205): history.add('app','dictate','original',str(n))
            self.assertEqual(len(history.list()), 200)
            self.assertEqual(history.list()[0]['result'], '204')
            self.assertEqual(history.path.stat().st_mode & 0o777, 0o600)
            history.clear()
            self.assertEqual(history.list(), [])

    def test_writing_request_uses_selected_text_and_exact_profile(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({'choices':[{'message':{'content':'Rewritten'}}]}).encode()
        settings = {'api_key':'fake','profiles':{'Editor':'Use bullets'},'writing_rules':'Preserve Punjabi'}
        with patch('urllib.request.urlopen', return_value=response) as call:
            self.assertEqual(write('Make this shorter',settings,'Editor','Selected source',True), 'Rewritten')
        payload = json.loads(call.call_args.args[0].data)
        self.assertIn('Use bullets',payload['messages'][0]['content'])
        self.assertEqual(json.loads(payload['messages'][1]['content'])['selected_text'],'Selected source')
        self.assertNotIn('fake', payload['messages'][0]['content'])

class DeliveryTests(unittest.TestCase):
    def deliver(self, service, settings, mode='dictate', selection=''):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name)/'speech.wav'
        path.write_bytes(b'a'*101)
        service.deliver(service.generation, directory, path, 'target', (settings,'Editor',mode,selection))

    @patch.object(bol, 'notify')
    @patch.object(bol, 'copy_text')
    @patch.object(bol, 'shortcut')
    @patch.object(bol, 'active_window', return_value={'address':'other'})
    @patch.object(bol, 'transcribe', return_value='hello')
    def test_focus_change_copies_without_pasting(self, transcript, active, shortcut, copy, notify):
        service=bol.Service(); self.deliver(service, {'auto_paste':True})
        shortcut.assert_not_called(); copy.assert_called_once_with('hello')
        self.assertEqual(service.latest, 'hello')

    @patch.object(bol, 'notify')
    @patch.object(bol, 'copy_text')
    @patch.object(bol, 'shortcut')
    @patch.object(bol, 'selection_for', return_value='different selection')
    @patch.object(bol, 'active_window', return_value={'address':'target'})
    @patch.object(bol, 'write', return_value='replacement')
    @patch.object(bol, 'transcribe', return_value='shorten')
    def test_changed_selection_does_not_replace(self, transcribe, write, active, selection, shortcut, copy, notify):
        service=bol.Service(); self.deliver(service, {'auto_paste':True},'edit','old selection')
        shortcut.assert_not_called(); copy.assert_called_once_with('replacement')

    @patch.object(bol, 'notify')
    @patch.object(bol, 'copy_text')
    @patch.object(bol, 'shortcut')
    @patch.object(bol, 'active_window', return_value={'address':'target'})
    @patch.object(bol, 'write', side_effect=RuntimeError('Model unavailable'))
    @patch.object(bol, 'transcribe', return_value='recover me')
    def test_polish_failure_recovers_transcription(self, transcribe, write, active, shortcut, copy, notify):
        service=bol.Service(); self.deliver(service, {'auto_paste':True,'polish':True})
        self.assertEqual(service.latest, 'recover me')
        self.assertIn('recovered', service.error)
        copy.assert_called_once_with('recover me')

    @patch.object(bol, 'notify')
    @patch.object(bol, 'copy_text')
    @patch.object(bol, 'transcribe')
    def test_cancel_during_transcription_discards_result(self, transcribe, copy, notify):
        service=bol.Service()
        def result(*args, **kwargs):
            service.cancel(); return 'stale'
        transcribe.side_effect=result
        self.deliver(service,{})
        copy.assert_not_called(); self.assertEqual(service.latest,'')

    @patch.object(bol, 'notify')
    @patch.object(bol, 'copy_text')
    @patch.object(bol, 'shortcut')
    @patch.object(bol, 'selection_for', return_value='old selection')
    @patch.object(bol, 'active_window', return_value={'address':'target'})
    @patch.object(bol, 'write', return_value='replacement')
    @patch.object(bol, 'transcribe', return_value='shorten')
    def test_edit_replaces_verified_selection(self, transcribe, write, active, selection, shortcut, copy, notify):
        from unittest.mock import call
        service=bol.Service(); self.deliver(service, {'auto_paste':True}, 'edit','old selection')
        self.assertEqual(shortcut.call_args_list,[call('BackSpace',''),call('V','CTRL')])
        self.assertEqual(service.latest,'replacement')

    def test_long_audio_splits_into_short_requests(self):
        import wave
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'speech.wav'
            with wave.open(str(path),'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
                audio.writeframes(b'\0'*(16000*2*27))
            with patch.object(bol,'transcribe_one',side_effect=['first','second']) as transcribe:
                self.assertEqual(bol.transcribe(path,{}),'first\nsecond')
                self.assertEqual(transcribe.call_count,2)
                for call in transcribe.call_args_list:
                    with wave.open(str(call.args[0]),'rb') as chunk:
                        self.assertLess(chunk.getnframes()/chunk.getframerate(),26)

    def test_vocabulary_is_json_in_single_multipart_field(self):
        body,_=bol.multipart(b'audio','pa-IN','codemix',['Sarvam','ਸਤਿ'])
        self.assertIn(b'name="keyterms"',body)
        self.assertIn(json.dumps(['Sarvam','ਸਤਿ'],ensure_ascii=False).encode(),body)
        self.assertIn(b'codemix',body)

if __name__ == '__main__': unittest.main()
