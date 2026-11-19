"""Explicit GTK clipboard actions must not depend on host clipboard commands."""
import threading
import unittest
from unittest.mock import Mock, patch
try:
    from bol_gtk import Workspace
except (ImportError, ValueError):
    Workspace=None


@unittest.skipIf(Workspace is None, 'GTK introspection not installed')
class GtkClipboardTests(unittest.TestCase):
    def test_copy_uses_toolkit_clipboard_without_core_cli(self):
        workspace=Workspace.__new__(Workspace);workspace.core=Mock()
        display=Mock()
        with patch('bol_gtk.Gdk.Display.get_default',return_value=display):
            workspace.copy_text('Text from Bol')
        display.get_clipboard().set.assert_called_once_with('Text from Bol')
        workspace.core.copy_text.assert_not_called()

    def test_copied_source_uses_explicit_local_socket_payload(self):
        workspace=Workspace.__new__(Workspace);workspace.core=Mock();workspace.status=Mock();workspace.alive=True
        finished=threading.Event()
        workspace.core.request.side_effect=lambda data:(finished.set() or {'state':'Recording'})
        clipboard=Mock();clipboard.read_text_finish.return_value='  keep indentation\n'
        clipboard.read_text_async.side_effect=lambda cancellable,callback:callback(clipboard,Mock())
        display=Mock();display.get_clipboard.return_value=clipboard
        with patch('bol_gtk.Gdk.Display.get_default',return_value=display), patch('bol_gtk.GLib.idle_add',side_effect=lambda callback,*args:callback(*args)):
            workspace.voice_edit_clipboard()
            self.assertTrue(finished.wait(1))
        workspace.core.request.assert_called_once_with({'command':'edit-clipboard','source':'  keep indentation\n'})
