import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import kivi_linux as bol
from bol_features import History

class ReviewTests(unittest.TestCase):
    def pending(self):
        service=bol.Service()
        folder=tempfile.TemporaryDirectory();path=Path(folder.name)/'speech.wav';path.write_bytes(b'a'*101)
        with patch.object(bol,'transcribe',return_value='Make it shorter'),patch.object(bol,'write',return_value='Short result'),patch.object(bol,'copy_text') as copy,patch.object(bol,'shortcut') as shortcut,patch.object(bol,'notify'),patch.object(bol,'History') as history:
            service.deliver(0,folder,path,'target',({'review_edits':True,'history_enabled':True},'Editor','edit','Selected original'))
            copy.assert_not_called();shortcut.assert_not_called();history.assert_not_called()
        return service

    def test_edit_waits_without_copy_paste_or_history(self):
        service=self.pending()
        self.assertEqual(service.state,'Review')
        self.assertTrue(service.status()['has_pending_edit'])
        self.assertEqual(service.command('review')['text'],'Short result')

    def test_cancel_invalidates_approval(self):
        service=self.pending();draft=service.command('review')
        with patch.object(bol,'notify'),patch.object(bol,'copy_text') as copy:
            service.command('cancel')
            result=service.command({'command':'accept-edit','generation':draft['generation'],'text':'Old result'})
            self.assertIn('no longer',result['error']);copy.assert_not_called()

    def test_approval_uses_reviewed_text_and_rechecks_selection(self):
        service=self.pending();draft=service.command('review')
        with patch.object(bol.subprocess,'check_output',return_value=json.dumps([{'address':'target'}])),patch.object(bol.subprocess,'run'),patch.object(bol.time,'sleep'),patch.object(bol,'active_window',return_value={'address':'target'}),patch.object(bol,'selection_for',return_value='Different selection'),patch.object(bol,'copy_text') as copy,patch.object(bol,'shortcut') as shortcut,patch.object(bol,'History') as history,patch.object(bol,'notify'):
            result=service.command({'command':'accept-edit','generation':draft['generation'],'text':'Reviewed wording'})
            copy.assert_called_once_with('Reviewed wording');shortcut.assert_not_called()
            history.return_value.add.assert_called_once_with('Editor','edit','Make it shorter','Reviewed wording')
            self.assertEqual(result['state'],'Ready');self.assertFalse(result['has_pending_edit'])

    def test_duplicate_approval_is_rejected(self):
        service=self.pending()
        packet={'command':'accept-edit','generation':0,'text':'Confirmed'}
        with patch.object(service,'commit_result'):
            service.command(packet)
            self.assertIn('error',service.command(packet))

    def test_focus_failure_preserves_reviewed_result(self):
        service=self.pending()
        with patch.object(bol.subprocess,'check_output',side_effect=RuntimeError('Focus unavailable')):
            result=service.command({'command':'accept-edit','generation':0,'text':'Recover this'})
        self.assertEqual(service.latest,'Recover this');self.assertIn('Focus unavailable',result['error'])

class RetentionTests(unittest.TestCase):
    def test_retention_expires_old_entries_only(self):
        with tempfile.TemporaryDirectory() as folder:
            history=History(folder);history.add('old','dictate','old','Old');history.add('new','dictate','new','New')
            with history.connect() as db:db.execute("UPDATE history SET created=datetime('now','-2 days') WHERE app='old'")
            self.assertEqual(len(History(folder,0).list()),2)
            self.assertEqual([row['app'] for row in History(folder,1).list()],['new'])

    def test_unsupported_retention_does_not_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            history=History(folder);history.add('app','dictate','text','Result')
            with self.assertRaises(ValueError):History(folder,-1)
            self.assertEqual(len(history.list()),1)
