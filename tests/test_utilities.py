import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave
from bol_features import History, audio_level

class UtilitiesTests(unittest.TestCase):
    def test_history_search_matches_app_and_unicode_text(self):
        with tempfile.TemporaryDirectory() as folder:
            history=History(folder)
            history.add('Editor','dictate','hello','ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ')
            history.add('Mail','edit','draft','Meeting notes')
            self.assertEqual(len(history.list('editor')),1)
            self.assertEqual(history.list('ਅਕਾਲ')[0]['app'],'Editor')
            self.assertEqual(history.list('MEETING')[0]['app'],'Mail')
            self.assertEqual(history.list('missing'),[])

    def test_local_audio_levels_detect_silence_and_clipping(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.wav'
            for amplitude,quiet,clipping in [(0,True,False),(6000,False,False),(32767,False,True)]:
                with wave.open(str(path),'wb') as out:
                    out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
                    out.writeframes(b''.join(struct.pack('<h',int(amplitude*math.sin(2*math.pi*n/40))) for n in range(1600)))
                result=audio_level(path)
                self.assertEqual(result['quiet'],quiet)
                self.assertEqual(result['clipping'],clipping)
                self.assertAlmostEqual(result['seconds'],.1)
