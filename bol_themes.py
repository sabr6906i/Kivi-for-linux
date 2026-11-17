"""Curated appearance palettes; existing dark/light preference IDs stay valid."""
THEMES = {
    'dark': dict(name='Midnight', family='dark', description='True black with vivid accents.', bg='#090909',sidebar='#0c0c0c',panel='#141414',field='#191919',border='#292929',fg='#ececec',muted='#a0a0a0'),
    'graphite': dict(name='Graphite', family='dark', description='Soft charcoal with a quieter contrast.', bg='#1a1c20',sidebar='#14161a',panel='#23262c',field='#1c1f24',border='#363b45',fg='#f2f3f5',muted='#aaafb9'),
    'ocean': dict(name='Deep Ocean', family='dark', description='Inky navy and cool slate surfaces.', bg='#080f18',sidebar='#0b1421',panel='#101d2d',field='#0b1726',border='#243a52',fg='#edf5ff',muted='#9db2c9'),
    'cinder': dict(name='Cinder', family='dark', description='Warm black with subtle bronze undertones.', bg='#151211',sidebar='#100e0d',panel='#201b18',field='#181411',border='#3b302a',fg='#f5eee8',muted='#b8a99c'),
    'paper': dict(name='Paper', family='light', description='Clean white with neutral grey details.', bg='#ffffff',sidebar='#f5f5f6',panel='#ffffff',field='#f6f6f7',border='#e0e0e4',fg='#202024',muted='#67676f'),
    'light': dict(name='Porcelain', family='light', description='Cool white with a hint of blue.', bg='#f7f8fb',sidebar='#eff2f7',panel='#ffffff',field='#f5f7fa',border='#dce3ed',fg='#19263b',muted='#5e6e84'),
    'ivory': dict(name='Ivory', family='light', description='Warm cream with soft, natural surfaces.', bg='#faf7f0',sidebar='#f0ebe1',panel='#fffdf8',field='#f4efe6',border='#e3dbce',fg='#322b24',muted='#74685a'),
    'sage': dict(name='Sage', family='light', description='Fresh white with muted green undertones.', bg='#f3f7f3',sidebar='#e9f0e9',panel='#ffffff',field='#f0f5f0',border='#d7e2d8',fg='#24372a',muted='#607365'),
}


def palette(theme):
    return THEMES.get(theme, THEMES['dark'])


def is_light(theme):
    return palette(theme)['family']=='light'


def overrides(theme):
    p=palette(theme)
    return f'''
window.bol, .bol headerbar, .bol .footer {{ background: {p['bg']}; color: {p['fg']}; }}
.bol .sidebar {{ background: {p['sidebar']}; border-color: {p['border']}; }}
.bol .group, .bol .transcript, .bol .history-empty, .bol .profile-menu-panel {{ background: {p['panel']}; border-color: {p['border']}; }}
.bol .transcript:hover {{ background: {p['field']}; border-color: {p['border']}; }}
.bol entry, .bol passwordentry, .bol dropdown > button, .bol spinbutton, .bol .history-toolbar {{ background: {p['field']}; color: {p['fg']}; border-color: {p['border']}; }}
.bol dropdown > button {{ background: transparent; border: 0; border-radius: 7px; padding: 6px 10px; min-height: 24px; box-shadow: none; }}
.bol dropdown > button:hover, .bol dropdown > button:checked {{ background: {p['field']}; }}
.bol dropdown > button:focus-visible {{ outline: 2px solid {'#396ed8' if is_light(theme) else '#82b8ff'}; outline-offset: 2px; }}
.bol dropdown > button label {{ font-weight: 500; color: {p['fg']}; }}
.bol dropdown > button arrow {{ color: {p['muted']}; min-width: 12px; min-height: 12px; margin-left: 16px; }}
.bol dropdown popover contents {{ background: {p['panel']}; color: {p['fg']}; border: 1px solid {p['border']}; padding: 5px; border-radius: 12px; box-shadow: 0 6px 18px alpha(#000000, 0.14); }}
.bol dropdown popover listview {{ background: transparent; color: {p['fg']}; }}
.bol dropdown popover row {{ border-radius: 6px; padding: 7px 10px; }}
.bol dropdown popover row:hover, .bol dropdown popover row:selected {{ background: {p['field']}; color: {p['fg']}; }}
.bol textview, .bol textview text {{ background: {p['panel']}; color: {p['fg']}; }}
.bol .page-title, .bol .row-title, .bol .transcript-text, .bol .profile-name {{ color: {p['fg']}; }}
.bol .muted, .bol .row-hint, .bol .transcript-meta, .bol .profile-caption, .bol .menu-item-hint, .bol .nav-heading {{ color: {p['muted']}; }}
.bol separator, .bol .footer {{ border-color: {p['border']}; }}
.bol separator {{ background: {p['border']}; }}
.bol button.profile-card {{ background: {p['field']}; }}
.bol .theme-preview {{ border: 0; padding: 9px; border-radius: 10px; background: {p['field']}; }}
.bol .theme-preview:hover {{ background: {p['border']}; }}
.bol .theme-preview.selected {{ box-shadow: inset 0 0 0 2px {'#396ed8' if is_light(theme) else '#82b8ff'}; }}
.bol .theme-preview label {{ color: {p['fg']}; font-size: 11px; font-weight: 600; }}
'''
