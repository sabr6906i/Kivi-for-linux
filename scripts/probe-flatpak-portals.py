#!/usr/bin/env python3
"""Read-only portal inventory; it never requests microphone/input permissions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

result = {'desktop': os.environ.get('XDG_CURRENT_DESKTOP', ''),
          'session': os.environ.get('XDG_SESSION_TYPE', ''),
          'flatpak_installed': bool(shutil.which('flatpak')),
          'flatpak_builder_installed': bool(shutil.which('flatpak-builder')),
          'pipewire_socket_present': (Path(os.environ.get('XDG_RUNTIME_DIR', '/nonexistent')) / 'pipewire-0').exists(),
          'portal_interfaces': [], 'portal_error': None, 'introspection_only': True}
try:
    xml = subprocess.check_output(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.portal.Desktop',
                                   '--object-path', '/org/freedesktop/portal/desktop',
                                   '--method', 'org.freedesktop.DBus.Introspectable.Introspect'], text=True, timeout=8)
    # gdbus returns a Python-compatible repr of a tuple containing the XML string.
    import ast
    reply = ast.literal_eval(xml)
    if not isinstance(reply, tuple) or len(reply) != 1 or not isinstance(reply[0], str):
        raise ValueError('Unexpected introspection reply')
    root = ET.fromstring(reply[0])
    result['portal_interfaces'] = sorted(node.attrib['name'] for node in root.findall('interface') if node.attrib.get('name', '').startswith('org.freedesktop.portal.'))
except (OSError, subprocess.SubprocessError, ValueError, SyntaxError, ET.ParseError):
    result['portal_error'] = 'Could not inspect the session portal service.'
result['global_shortcuts_available'] = 'org.freedesktop.portal.GlobalShortcuts' in result['portal_interfaces']
result['remote_desktop_available'] = 'org.freedesktop.portal.RemoteDesktop' in result['portal_interfaces']
result['clipboard_portal_available'] = 'org.freedesktop.portal.Clipboard' in result['portal_interfaces']
print(json.dumps(result, indent=2))
