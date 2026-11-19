import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import bol_desktop as desktop
import kivi_linux as bol


class DesktopTests(unittest.TestCase):
    def environment(self, name='GNOME', session='wayland'):
        return patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': name, 'XDG_SESSION_TYPE': session, 'HYPRLAND_INSTANCE_SIGNATURE': '', 'DISPLAY': ':1', 'WAYLAND_DISPLAY': 'wayland-0'}, clear=True)

    def test_gnome_and_kde_wayland_have_no_inferred_target_or_hypr_dependency(self):
        for name in ('GNOME', 'KDE'):
            with self.subTest(name=name), self.environment(name), patch.object(desktop.subprocess, 'run') as run:
                info = desktop.desktop_info()
                self.assertFalse(info['automatic_insertion'])
                self.assertFalse(info['selection_capture'])
                self.assertEqual(desktop.active_window(), {'address': '', 'class': ''})
                self.assertNotIn('hyprctl', desktop.recording_dependencies())
                with self.assertRaisesRegex(RuntimeError, 'Paste'):desktop.shortcut('V')
                self.assertFalse(desktop.focus_window('0x1234'))
                run.assert_not_called()

    def test_hyprland_keeps_existing_window_and_shortcut_protocol(self):
        with self.environment('Hyprland'), patch.object(desktop.subprocess, 'run') as run:
            run.return_value = Mock(stdout='{"address":"0x1","class":"Editor"}', returncode=0)
            self.assertEqual(desktop.active_window()['address'], '0x1')
            run.return_value = Mock(stdout='ok', returncode=0)
            desktop.shortcut('V', 'CTRL SHIFT')
            args = run.call_args.args[0]
            self.assertEqual(args[:2], ['hyprctl', 'dispatch'])
            self.assertIn('hl.dsp.send_shortcut', args[2])
            self.assertIn('"CTRL SHIFT"', args[2])

    def test_x11_uses_xclip_and_xdotool_without_wayland(self):
        with self.environment('GNOME', 'x11'), patch.object(desktop.subprocess, 'run') as run, patch.object(desktop.shutil, 'which', return_value=None):
            run.return_value = Mock(stdout='12345\n', returncode=0)
            self.assertEqual(desktop.active_window()['address'], '12345')
            desktop.shortcut('V', 'CTRL SHIFT')
            self.assertEqual(run.call_args.args[0], ['xdotool', 'key', '--clearmodifiers', 'ctrl+shift+V'])
            desktop.copy_text('Text with $(shell) and Unicode ਪੰਜਾਬੀ')
            self.assertEqual(run.call_args.args[0], ['xclip', '-selection', 'clipboard', '-in'])
            self.assertEqual(run.call_args.kwargs['input'], 'Text with $(shell) and Unicode ਪੰਜਾਬੀ'.encode())
            self.assertEqual(desktop.recording_dependencies(), ['pw-record', 'xclip', 'xdotool'])

    def test_clipboard_text_goes_over_stdin_not_process_arguments(self):
        with self.environment(), patch.object(desktop.subprocess, 'run') as run:
            desktop.copy_text('private transcript')
            self.assertNotIn('private transcript', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['input'], b'private transcript')

    def test_gnome_recording_starts_without_hyprctl(self):
        with tempfile.TemporaryDirectory() as folder, self.environment(), patch.object(bol, 'RUNTIME', Path(folder)), patch.object(bol, 'config', return_value={'speech_provider': 'sarvam'}), patch.object(bol, 'validate_speech'), patch.object(bol.shutil, 'which', side_effect=lambda name: None if name == 'hyprctl' else '/usr/bin/' + name), patch.object(bol.subprocess, 'Popen') as popen, patch.object(bol.threading, 'Timer'), patch.object(bol, 'notify'):
            service = bol.Service()
            self.assertEqual(service.command('start')['state'], 'Recording')
            self.assertEqual(service.target, '')
            self.assertEqual(popen.call_args.args[0][0], 'pw-record')
            service.cancel(silent=True)

    def test_portable_edit_requires_explicit_copied_source(self):
        with self.environment(), patch.object(bol, 'config', return_value={'speech_provider': 'sarvam'}), patch.object(bol, 'validate_speech'), patch.object(bol, 'notify'), patch.object(bol.subprocess, 'Popen') as popen:
            service = bol.Service()
            result = service.command('edit')
            self.assertIn('edit-clipboard', result['error'])
            popen.assert_not_called()

    def test_explicit_clipboard_edit_is_never_inserted_into_guessed_window(self):
        with tempfile.TemporaryDirectory() as folder, self.environment(), patch.object(bol, 'RUNTIME', Path(folder)), patch.object(bol, 'config', return_value={'speech_provider': 'sarvam'}), patch.object(bol, 'validate_speech'), patch.object(bol, 'read_clipboard', return_value=b'Copied source'), patch.object(bol.shutil, 'which', return_value='/usr/bin/tool'), patch.object(bol.subprocess, 'Popen'), patch.object(bol.threading, 'Timer'), patch.object(bol, 'notify'):
            service = bol.Service()
            self.assertEqual(service.command('edit-clipboard')['state'], 'Recording')
            self.assertEqual(service.selection, 'Copied source')
            self.assertEqual(service.target, '')
            service.cancel(silent=True)
        with self.environment(), patch.object(bol, 'copy_text') as copy, patch.object(bol, 'shortcut') as shortcut, patch.object(bol, 'notify'):
            service = bol.Service()
            service.commit_result(0, 'Result', 'Instruction', {}, '', 'edit', 'Copied source', '', focus=True)
            copy.assert_called_once_with('Result')
            shortcut.assert_not_called()
            self.assertEqual(service.outcome, 'Copied — paste into your app')

    def test_kde_shortcut_settings_do_not_rewrite_config(self):
        with self.environment('KDE'), patch.object(desktop.shutil, 'which', return_value='/usr/bin/systemsettings'), patch.object(desktop.subprocess, 'Popen') as popen:
            desktop.open_shortcut_settings()
            self.assertEqual(popen.call_args.args[0], ['systemsettings', 'kcm_keys'])
            with self.assertRaisesRegex(ValueError, 'System Settings'):
                desktop.apply_shortcuts({'record_key': 'F8', 'cancel_key': 'F9', 'edit_key': 'F10'})


class FakeVariant:
    def __init__(self, value):self.value = value
    def get_type_string(self):return 'as' if isinstance(self.value, list) else 's'
    def unpack(self):return self.value


class FakeSettings:
    def __init__(self, values=None):self.values = dict(values or {});self.fail_key = None
    def is_writable(self, key):return True
    def get_strv(self, key):return self.values.get(key, [])
    def get_string(self, key):return self.values.get(key, '')
    def get_user_value(self, key):return FakeVariant(self.values[key]) if key in self.values else None
    def get_value(self, key):return FakeVariant(self.values.get(key, []))
    def set_string(self, key, value):
        if self.fail_key == key:return False
        self.values[key] = value;return True
    def set_strv(self, key, value):self.values[key] = list(value);return True
    def set_value(self, key, value):self.values[key] = value.unpack();return True
    def reset(self, key):self.values.pop(key, None)


class GnomeShortcutTests(unittest.TestCase):
    def fake_gio(self):
        base = 'org.gnome.settings-daemon.plugins.media-keys'
        root = FakeSettings({'custom-keybindings': ['/unrelated/']})
        entries = {'/unrelated/': FakeSettings({'binding': '<Control>F7', 'name': 'Another app', 'command': 'other'})}
        source = Mock();source.lookup.side_effect = lambda name, recursive: Mock(list_keys=lambda: ['custom-keybindings']) if name == base else Mock(list_keys=lambda: []) if name == base + '.custom-keybinding' else None
        gio = Mock();gio.SettingsSchemaSource.get_default.return_value = source
        gio.Settings.new.return_value = root
        def entry(schema, path):return entries.setdefault(path, FakeSettings())
        gio.Settings.new_with_path.side_effect = entry
        return gio, root, entries

    def test_installs_bol_bindings_and_preserves_unrelated_paths(self):
        gio, root, entries = self.fake_gio()
        settings = {'record_key': 'F8', 'cancel_key': 'F9', 'edit_key': 'F10'}
        with patch.object(desktop.shutil, 'which', return_value='/usr/bin/bol'):
            desktop.install_gnome_shortcuts(settings, gio)
        self.assertIn('/unrelated/', root.values['custom-keybindings'])
        self.assertEqual(entries['/unrelated/'].values['command'], 'other')
        self.assertEqual(len(root.values['custom-keybindings']), 4)
        commands = {item.values.get('command') for path, item in entries.items() if path != '/unrelated/'}
        self.assertEqual(commands, {'/usr/bin/bol toggle', '/usr/bin/bol cancel', '/usr/bin/bol edit-clipboard'})

    def test_existing_custom_shortcut_conflict_is_not_overwritten(self):
        gio, root, entries = self.fake_gio()
        with self.assertRaisesRegex(ValueError, 'Another app'):
            desktop.install_gnome_shortcuts({'record_key': 'CTRL + F7', 'cancel_key': 'F9', 'edit_key': 'F10'}, gio)
        self.assertEqual(root.values['custom-keybindings'], ['/unrelated/'])

    def test_failed_write_restores_original_values(self):
        gio, root, entries = self.fake_gio()
        own_path = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/bol-edit-key/'
        entries[own_path] = FakeSettings({'name': 'Old name', 'command': 'old', 'binding': 'F6'})
        entries[own_path].fail_key = 'binding'
        with self.assertRaisesRegex(ValueError, 'Could not write'):
            desktop.install_gnome_shortcuts({'record_key': 'F8', 'cancel_key': 'F9', 'edit_key': 'F10'}, gio)
        self.assertEqual(entries[own_path].values, {'name': 'Old name', 'command': 'old', 'binding': 'F6'})
        self.assertEqual(root.values['custom-keybindings'], ['/unrelated/'])

    def test_hold_to_talk_and_duplicate_chords_rejected_before_mutation(self):
        gio, root, entries = self.fake_gio()
        for settings in ({'hold_to_talk': True}, {'record_key': 'CTRL + ALT + F8', 'cancel_key': 'ALT + CTRL + F8', 'edit_key': 'F10'}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):desktop.install_gnome_shortcuts(settings, gio)
        self.assertEqual(root.values['custom-keybindings'], ['/unrelated/'])

class HyprlandLauncherTests(unittest.TestCase):
    def test_native_package_shortcuts_use_discovered_launcher(self):
        from bol_ui import apply_shortcuts
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder);config = home / '.config/hypr/custom/keybinds.lua';config.parent.mkdir(parents=True);config.write_text('-- user bindings remain\n')
            settings = {'record_key': 'F8', 'cancel_key': 'F9', 'edit_key': 'F10'}
            with patch('bol_ui.Path.home', return_value=home), patch('bol_ui.shutil.which', return_value='/usr/bin/bol'), patch('bol_ui.subprocess.check_output', return_value='[]'), patch('bol_ui.subprocess.run', return_value=Mock(returncode=0, stdout='')):
                apply_shortcuts(settings)
            text = config.read_text()
            self.assertIn('-- user bindings remain', text)
            self.assertIn('hl.dsp.exec_cmd("/usr/bin/bol toggle")', text)
            self.assertNotIn('$HOME/.local/bin/bol', text)

class ClipboardRecoveryTests(unittest.TestCase):
    def test_missing_background_transport_keeps_result_ready_in_app(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME', 'XDG_SESSION_TYPE': 'wayland'}, clear=True), patch.object(bol, 'copy_text', side_effect=FileNotFoundError('wl-copy')), patch.object(bol, 'shortcut') as shortcut, patch.object(bol, 'notify'):
            service = bol.Service()
            service.commit_result(0, 'Recovered text', 'Original', {}, '', 'dictate', '', '')
            self.assertEqual(service.status()['state'], 'Ready')
            self.assertEqual(service.command('result')['text'], 'Recovered text')
            self.assertIn('History', service.status()['error'])
            shortcut.assert_not_called()

    def test_clipboard_process_has_no_inherited_output_pipes(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME', 'XDG_SESSION_TYPE': 'x11'}, clear=True), patch.object(desktop.subprocess, 'run') as run:
            desktop.copy_text('Text')
            self.assertEqual(run.call_args.kwargs['stdout'], desktop.subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['stderr'], desktop.subprocess.DEVNULL)

    def test_gui_can_supply_explicit_source_without_background_clipboard(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME', 'XDG_SESSION_TYPE': 'wayland'}, clear=True), patch.object(bol, 'RUNTIME', Path(folder)), patch.object(bol, 'config', return_value={'speech_provider': 'sarvam'}), patch.object(bol, 'validate_speech'), patch.object(bol, 'read_clipboard') as read, patch.object(bol.shutil, 'which', side_effect=lambda name: '/usr/bin/pw-record' if name == 'pw-record' else None), patch.object(bol.subprocess, 'Popen'), patch.object(bol.threading, 'Timer'), patch.object(bol, 'notify'):
            service = bol.Service()
            service.command({'command': 'edit-clipboard', 'source': '    indented source\n'})
            self.assertEqual(service.state, 'Recording')
            self.assertEqual(service.selection, '    indented source\n')
            self.assertEqual(service.target, '')
            read.assert_not_called()
            service.cancel(silent=True)
