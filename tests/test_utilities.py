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

class HistoryPresentationTests(unittest.TestCase):
    def test_date_groups_respect_local_midnight(self):
        from datetime import datetime, timezone, timedelta
        from bol_features import history_date
        india=timezone(timedelta(hours=5,minutes=30))
        now=datetime(2026,11,16,2,0,tzinfo=india)
        self.assertEqual(history_date('2026-11-15 20:00:00',now),('Today','01:30'))
        self.assertEqual(history_date('2026-11-14 20:00:00',now)[0],'Yesterday')
        self.assertEqual(history_date('2026-11-10 12:00:00',now)[0],'10 Nov 2026')
        self.assertEqual(history_date('',now),('This session',''))

    def test_type_and_search_filters_compose(self):
        from bol_features import filter_history
        rows=[{'mode':'dictate','app':'Editor','result':'ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ'},
              {'mode':'edit','app':'Mail','result':'Project update'},
              {'mode':'edit','app':'Editor','original':'shorten','result':'Project notes'}]
        self.assertEqual(len(filter_history(rows,'project','edit')),2)
        self.assertEqual(filter_history(rows,'EDITOR','edit')[0]['result'],'Project notes')
        self.assertEqual(filter_history(rows,'ਅਕਾਲ','dictate')[0]['app'],'Editor')
        self.assertEqual(filter_history(rows,'project','dictate'),[])
