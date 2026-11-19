#!/usr/bin/env python3
"""Headless GTK launch smoke; desktop labels are simulated, not native session tests."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock

parser=argparse.ArgumentParser()
parser.add_argument('--desktop',choices=['GNOME','KDE','Hyprland'],default='GNOME')
parser.add_argument('--clipboard-roundtrip',action='store_true',help='Use only under an isolated test display; replaces that display’s clipboard')
args=parser.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['XDG_CURRENT_DESKTOP']=args.desktop
os.environ['XDG_SESSION_TYPE']='wayland'
if args.desktop!='Hyprland':os.environ.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
from bol_features import DEFAULTS
from bol_gtk import Workspace, Gtk, GLib, Gdk
from bol_desktop import desktop_info
with tempfile.TemporaryDirectory(prefix='bol-gtk-smoke-') as folder:
    settings=deepcopy(DEFAULTS)
    core=Mock();core.CONFIG=Path(folder)
    core.config.side_effect=lambda:deepcopy(settings)
    core.save_config.side_effect=lambda value:settings.update(deepcopy(value))
    core.request.return_value={'state':'Ready','seconds':0,'error':'','outcome':''}
    app=Workspace(core,single_instance=False);app.app.register(None);app.activate(app.app)
    context=GLib.MainContext.default()
    until=time.monotonic()+.3
    while time.monotonic()<until:
        while context.pending():context.iteration(False)
        time.sleep(.005)
    assert app.window.get_visible()
    assert not app.account_project_setup.get_visible()
    welcome=next(w for w in Gtk.Window.list_toplevels() if w.get_title()=='Welcome to Bol')
    assert welcome.get_visible()
    app.select('General');assert app.stack.get_visible_child_name()=='General'
    if args.desktop in ['GNOME','KDE']:
        assert desktop_info()['automatic_insertion'] is False
    if args.clipboard_roundtrip:
        app.copy_text('Bol GTK clipboard smoke')
        copied=[]
        clipboard=Gdk.Display.get_default().get_clipboard()
        def received(clipboard,result):copied.append(clipboard.read_text_finish(result))
        clipboard.read_text_async(None,received)
        until=time.monotonic()+3
        while not copied and time.monotonic()<until:
            while context.pending():context.iteration(False)
            time.sleep(.005)
        assert copied==['Bol GTK clipboard smoke'], copied
    welcome.close();app.window.close()
print('GTK startup passed for simulated '+args.desktop+' metadata. No native desktop/input/audio behavior was tested.')
