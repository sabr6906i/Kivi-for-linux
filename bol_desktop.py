"""Desktop capabilities and explicit fallbacks; no privileged input emulation.

Hyprland retains focus-checked insertion. X11 uses optional xdotool/xclip.
GNOME/KDE Wayland deliberately use clipboard delivery because focus inspection
and arbitrary keyboard injection are not public compositor APIs.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def _backend():
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    session = os.environ.get('XDG_SESSION_TYPE', '').lower()
    if not session:
        session = 'wayland' if os.environ.get('WAYLAND_DISPLAY') else 'x11' if os.environ.get('DISPLAY') else 'wayland'
    if session == 'wayland' and ('hyprland' in desktop or (not desktop and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'))):
        return 'hyprland', session, 'Hyprland'
    name = 'GNOME' if 'gnome' in desktop else 'KDE Plasma' if 'kde' in desktop or 'plasma' in desktop else 'Linux desktop'
    return ('x11' if session == 'x11' else 'wayland'), session, name


def desktop_info():
    backend, session, name = _backend()
    insertion = backend in ('hyprland', 'x11')
    return {'name': name, 'session': session, 'backend': backend,
            'automatic_insertion': insertion, 'selection_capture': insertion,
            'shortcut_setup': 'hyprland' if backend == 'hyprland' else 'gnome' if name == 'GNOME' else 'manual',
            'summary': 'Focus-checked automatic insertion is supported.' if insertion else
                'Clipboard mode: dictate, then paste into your app. To voice-edit existing text, copy it first and run bol edit-clipboard.'}


def recording_dependencies():
    backend = _backend()[0]
    return ['pw-record'] + (['wl-copy', 'wl-paste', 'hyprctl'] if backend == 'hyprland' else
                            ['xclip', 'xdotool'] if backend == 'x11' else [])


def active_window():
    backend = _backend()[0]
    if backend == 'hyprland':
        result = subprocess.run(['hyprctl', '-j', 'activewindow'], capture_output=True, text=True, check=True, timeout=3)
        return json.loads(result.stdout)
    if backend == 'x11':
        result = subprocess.run(['xdotool', 'getactivewindow'], capture_output=True, text=True, check=True, timeout=3)
        address = result.stdout.strip()
        if not address.isdecimal():
            raise RuntimeError('X11 did not return a valid focused window.')
        app = ''
        if shutil.which('xprop'):
            result = subprocess.run(['xprop', '-id', address, 'WM_CLASS'], capture_output=True, text=True, timeout=3)
            classes = re.findall(r'"([^"\n]*)"', result.stdout)
            if classes:app = classes[-1]
        return {'address': address, 'class': app}
    # Never manufacture an address: an empty target prevents input injection.
    return {'address': '', 'class': ''}


def shortcut(key, mods='CTRL'):
    if key not in ('C', 'V', 'BackSpace') or mods not in ('', 'CTRL', 'CTRL SHIFT'):
        raise ValueError('Unsupported desktop shortcut.')
    backend = _backend()[0]
    if backend == 'hyprland':
        code = 'hl.dsp.send_shortcut({ mods = ' + json.dumps(mods) + ', key = ' + json.dumps(key) + ' })'
        result = subprocess.run(['hyprctl', 'dispatch', code], capture_output=True, text=True, timeout=3)
        if result.returncode or result.stdout.strip() != 'ok':
            raise RuntimeError('Hyprland rejected the keyboard shortcut.')
        return
    if backend == 'x11':
        combo = '+'.join([part.lower() for part in mods.split()] + [key])
        subprocess.run(['xdotool', 'key', '--clearmodifiers', combo], check=True, capture_output=True, timeout=3)
        return
    raise RuntimeError('This Wayland desktop uses clipboard delivery. Paste the result manually.')


def focus_window(target):
    backend = _backend()[0]
    if backend == 'hyprland':
        clients = json.loads(subprocess.check_output(['hyprctl', '-j', 'clients'], text=True, timeout=3))
        if any(client.get('address') == target for client in clients):
            code = 'hl.dsp.focus({ window = ' + json.dumps('address:' + target) + ' })'
            subprocess.run(['hyprctl', 'dispatch', code], check=True, capture_output=True, timeout=3)
            return True
        return False
    if backend == 'x11':
        if not str(target).isdecimal():return False
        subprocess.run(['xdotool', 'windowactivate', '--sync', str(target)], check=True, capture_output=True, timeout=3)
        return True
    return False


def copy_text(text):
    command = ['xclip', '-selection', 'clipboard', '-in'] if _backend()[0] == 'x11' else ['wl-copy'] if isinstance(text, bytes) else ['wl-copy', '--type', 'text/plain;charset=utf-8']
    payload = text if isinstance(text, bytes) else text.encode('utf-8')
    subprocess.run(command, input=payload, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)


def read_clipboard():
    command = ['xclip', '-selection', 'clipboard', '-out'] if _backend()[0] == 'x11' else ['wl-paste', '--no-newline']
    try:result = subprocess.run(command, capture_output=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Background clipboard access is unavailable. Use Bol’s explicit clipboard action or paste the source text into Bol.') from None
    if result.returncode:
        raise ValueError('No text is available on the clipboard. Copy the source text first.')
    return result.stdout


def open_app_classes():
    if _backend()[0] == 'hyprland':
        clients = json.loads(subprocess.check_output(['hyprctl', '-j', 'clients'], text=True, timeout=3))
        return sorted({item.get('class', '') for item in clients if item.get('class')})
    if _backend()[0] == 'x11':
        app = active_window().get('class', '')
        return [app] if app else []
    raise ValueError('This Wayland desktop does not expose other apps’ window classes. Global writing rules still work.')


def _shortcut_values(settings):
    values = {}
    for field in ('record_key', 'edit_key', 'cancel_key'):
        key = settings.get(field, '').upper().replace(' ', '')
        if not re.fullmatch(r'(?:(?:SUPER|CTRL|ALT|SHIFT)\+)*F(?:[1-9]|1[0-2])', key):
            raise ValueError('Use F1–F12, optionally with CTRL +, ALT +, SHIFT + or SUPER +.')
        parts = key.split('+')
        if len(set(parts[:-1])) != len(parts[:-1]):raise ValueError('Do not repeat shortcut modifiers.')
        accel = ''.join('<' + {'CTRL': 'Control', 'ALT': 'Alt', 'SHIFT': 'Shift', 'SUPER': 'Super'}[part] + '>' for part in sorted(parts[:-1])) + parts[-1]
        values[field] = accel
    if len(set(values.values())) != 3:raise ValueError('Choose three different shortcuts.')
    return values


def _canonical_accelerator(value):
    value = value.replace('<Primary>', '<Control>').replace('<Ctrl>', '<Control>')
    return tuple(sorted(part.lower() for part in re.findall(r'<([^>]+)>', value))), re.sub(r'<[^>]+>', '', value).lower()


def install_gnome_shortcuts(settings, gio=None):
    """Install only Bol's custom shortcuts; preserve other bindings and roll back errors."""
    if settings.get('hold_to_talk'):
        raise ValueError('GNOME custom shortcuts support toggle recording, not hold-to-talk. Disable hold-to-talk first.')
    values = _shortcut_values(settings)
    if gio is None:
        try:
            from gi.repository import Gio
            gio = Gio
        except ImportError:
            raise ValueError('GNOME shortcut setup needs PyGObject (python3-gi / python-gobject).') from None
    source = gio.SettingsSchemaSource.get_default()
    root_schema = 'org.gnome.settings-daemon.plugins.media-keys'
    custom_schema = root_schema + '.custom-keybinding'
    if not source or not source.lookup(root_schema, True) or not source.lookup(custom_schema, True):
        raise ValueError('GNOME keyboard settings are unavailable. Add the Bol commands manually in desktop Keyboard settings.')
    root = gio.Settings.new(root_schema)
    if not root.is_writable('custom-keybindings'):raise ValueError('Your administrator has locked GNOME custom shortcuts.')
    paths = list(root.get_strv('custom-keybindings'))
    own = {field: '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/bol-' + field.replace('_', '-') + '/' for field in values}
    desired = {_canonical_accelerator(value) for value in values.values()}
    # Refuse collisions with existing custom bindings, never steal another app's key.
    for path in paths:
        if path in own.values():continue
        existing = gio.Settings.new_with_path(custom_schema, path)
        if _canonical_accelerator(existing.get_string('binding')) in desired:
            raise ValueError('A selected shortcut is already assigned to ' + (existing.get_string('name') or 'another app') + '.')
    for schema_name in ('org.gnome.desktop.wm.keybindings', root_schema, root_schema + '.static', 'org.gnome.mutter.keybindings', 'org.gnome.mutter.wayland.keybindings'):
        schema = source.lookup(schema_name, True)
        if not schema:continue
        existing = gio.Settings.new(schema_name)
        for key in schema.list_keys():
            if key == 'custom-keybindings':continue
            variant = existing.get_value(key)
            if variant.get_type_string() == 'as':bindings = variant.unpack()
            elif variant.get_type_string() == 's':bindings = [variant.unpack()]
            else:continue
            if any(_canonical_accelerator(binding) in desired for binding in bindings if binding):
                raise ValueError('A selected shortcut is already used by GNOME: ' + key)
    launcher = shutil.which('bol') or str(Path.home() / '.local/bin/bol')
    import shlex
    commands = {'record_key': ('Dictate', 'toggle'), 'cancel_key': ('Cancel dictation', 'cancel'), 'edit_key': ('Voice edit copied text', 'edit-clipboard')}
    snapshots = []
    try:
        for field, path in own.items():
            entry = gio.Settings.new_with_path(custom_schema, path)
            old = {key: entry.get_user_value(key) for key in ('name', 'command', 'binding')}
            snapshots.append((entry, old))
            name, command = commands[field]
            for key, value in {'name': 'Bol: ' + name, 'command': shlex.quote(launcher) + ' ' + command, 'binding': values[field]}.items():
                if not entry.is_writable(key) or not entry.set_string(key, value):raise ValueError('Could not write the GNOME shortcut settings.')
        if not root.set_strv('custom-keybindings', paths + [path for path in own.values() if path not in paths]):
            raise ValueError('Could not enable the GNOME shortcuts.')
        gio.Settings.sync()
    except Exception:
        root.set_strv('custom-keybindings', paths)
        for entry, old in snapshots:
            for key, value in old.items():
                if value is None:entry.reset(key)
                else:entry.set_value(key, value)
        gio.Settings.sync()
        raise


def apply_shortcuts(settings):
    info = desktop_info()
    if info['backend'] == 'hyprland':
        from bol_ui import apply_shortcuts as apply_hyprland_shortcuts
        return apply_hyprland_shortcuts(settings)
    if info['name'] == 'GNOME':return install_gnome_shortcuts(settings)
    _shortcut_values(settings)
    raise ValueError('Automatic shortcut registration is not available on this desktop. Add bol toggle, bol cancel, and bol edit-clipboard in System Settings → Shortcuts. Hold-to-talk is unavailable; use toggle recording.')


def open_shortcut_settings():
    info = desktop_info()
    if info['name'] == 'GNOME':command = ['gnome-control-center', 'keyboard']
    elif info['name'] == 'KDE Plasma':command = ['systemsettings', 'kcm_keys']
    else:raise ValueError('Add the commands bol toggle, bol cancel, and bol edit-clipboard in your desktop’s shortcut settings.')
    if not shutil.which(command[0]):raise ValueError('Desktop shortcut settings are not installed. Configure the Bol commands manually.')
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
