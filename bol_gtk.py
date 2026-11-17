"""Native GTK 4 settings workspace for Bol."""
import json
import threading
import re
import colorsys
from functools import lru_cache
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from bol_features import LANGUAGES, MODES, History, audio_level, history_date, filter_history
from bol_providers import SPEECH_PROVIDERS, WRITING_PROVIDERS, detect_whisper, validate_speech
from bol_audio import synthesize, suggest_delivery, STYLE_PRESETS, TTS_LANGUAGES, TTS_VOICES
from bol_themes import THEMES, is_light, overrides, light_accents
from bol_ui import parse_pairs, format_pairs, apply_shortcuts

CSS = b'''
window.bol  { background: #090909; color: #ececec; font-family: 'Noto Sans', sans-serif; font-size: 13px; }
.bol headerbar  { background: #090909; box-shadow: none; border-bottom: 1px solid #242424; min-height: 40px; }
.bol .sidebar  { background: #0c0c0c; border-right: 1px solid #242424; }
.bol .brand  { font-size: 18px; font-weight: 700; color: #8cf3c2; }
.bol .nav-heading  { font-size: 11px; color: #858585; font-weight: 500; }
.bol .nav-button  { background: transparent; color: #aaa; border: none; box-shadow: none; border-radius: 7px; padding: 10px 12px; font-weight: 550; transition: background-color 120ms ease-in-out, color 120ms ease-in-out; }
.bol .nav-button:hover  { background: #242424; color: #eee; }
.bol .nav-button.selected  { border: 0; background: #242424; color: #f5f5f5; }
.bol .page-title  { font-size: 30px; font-weight: 700; letter-spacing: -0.6px; }
.bol .muted  { color: #929292; font-size: 12px; }
.bol .section-title  { color: #ddd; font-size: 13px; font-weight: 600; }
.bol .group  { background: #141414; border: 1px solid #292929; border-radius: 10px; }
.bol .row-title  { font-weight: 500; color: #e4e4e4; }
.bol .row-hint  { font-size: 11px; color: #999; }
.bol separator  { background: #292929; min-height: 1px; }
.bol entry, .bol passwordentry, .bol dropdown > button, .bol spinbutton  { background: #191919; color: #eee; border: 1px solid #333333; border-radius: 8px; box-shadow: none; min-height: 34px; }
.bol entry:focus-within, .bol passwordentry:focus-within  { border-color: #4da3ff; outline: none; }
.bol passwordentry entry, .bol spinbutton entry  { border: none; background: transparent; }
.bol button  { background: #242424; color: #ddd; border: 1px solid #333; border-radius: 8px; box-shadow: none; padding: 8px 12px; transition: background-color 120ms ease-in-out, border-color 120ms ease-in-out; }
.bol button:hover  { background: #303030; }
.bol button.primary  { border: 0; background: #65b0ff; color: #101823;  font-weight: 600; }
.bol button.primary:hover  { border: 0; background: #91c7ff;  }
.bol button.primary:disabled  { border: 0; background: #222222; color: #858585;  }
.bol switch  { background: #505050; border: none; min-width: 38px; min-height: 22px; }
.bol switch:checked  { background: #4da3ff; }
.bol switch slider  { background: #bdbdbd; border: none; box-shadow: none; }
.bol switch:checked slider  { background: #142039; }
.bol textview, .bol textview text  { background: #141414; color: #e4e4e4; }
.bol textview  { border-radius: 8px; padding: 12px; font-size: 13px; }
.bol .editor-frame  { border: 1px solid #424242; border-radius: 9px; }
.bol .footer  { background: #090909; border-top: 1px solid #252525; }
.bol .status  { color: #bdbdbd; font-size: 11px; }
.bol .key  { border: 0; background: #292929; color: #b8b8b8;  border-radius: 5px; font-size: 10px; padding: 3px 6px; }
.bol .empty  { color: #868686; padding: 25px; }
.bol listbox  { background: transparent; }
.bol listbox row  { padding: 10px; border-radius: 7px; }
.bol listbox row:selected  { background: #303030; }
.bol popover contents  { background: #242424; color: #eee; border: 1px solid #353535; border-radius: 10px; }
.bol .history-toolbar  { background: #111111; border: 1px solid #292929; border-radius: 10px; padding: 8px; }
.bol .filter  { background: transparent; border-color: transparent; color: #939393; padding: 7px 12px; }
.bol button.filter:checked label  { border: 0; color: #f3f3f3; }
.bol .filter:checked  { border: 0; background: #182b43; color: #b6d5ff;  }
.bol .transcript  { background: #141414; border: 1px solid #292929; border-radius: 12px; padding: 19px; }
.bol .transcript:hover  { border-color: #464646; background: #181818; }
.bol .transcript-text  { font-size: 14px; color: #e4e4e4; line-height: 1.6; }
.bol .transcript-meta  { color: #8c8c8c; font-size: 11px; }
.bol .date-heading  { color: #a0a0a0; font-size: 11px; font-weight: 600; margin-top: 12px; margin-bottom: 2px; }
.bol .tag  { border: 0; background: #232323;  border-radius: 5px; padding: 3px 7px; color: #aaa; font-size: 10px; }
.bol .quiet  { background: transparent; border-color: transparent; color: #a0a0a0; padding: 6px 8px; }
.bol .quiet:hover  { background: #292929; border-color: #3b3b3b; color: white; }
.bol .history-empty  { background: #101010; border: 1px dashed #333333; border-radius: 12px; padding: 42px; }
.bol .nav-button.nav-general.selected  { border: 0; background: #152235;  color: #4da3ff; }
.bol .nav-button.nav-general.selected label  { border: 0; color: #4da3ff; }
.bol .nav-button.nav-providers.selected  { border: 0; background: #251b36;  color: #ad78ff; }
.bol .nav-button.nav-providers.selected label  { border: 0; color: #ad78ff; }
.bol .nav-button.nav-writing.selected  { border: 0; background: #2d2317;  color: #ffb53f; }
.bol .nav-button.nav-writing.selected label  { border: 0; color: #ffb53f; }
.bol .nav-button.nav-vocabulary.selected  { border: 0; background: #152a21;  color: #43e3a1; }
.bol .nav-button.nav-vocabulary.selected label  { border: 0; color: #43e3a1; }
.bol .nav-button.nav-snippets.selected  { border: 0; background: #2d1b29;  color: #ff72c2; }
.bol .nav-button.nav-snippets.selected label  { border: 0; color: #ff72c2; }
.bol .nav-button.nav-history.selected  { border: 0; background: #15292d;  color: #39dcea; }
.bol .nav-button.nav-history.selected label  { border: 0; color: #39dcea; }
.bol .nav-button.nav-shortcuts.selected  { border: 0; background: #222235;  color: #9b92ff; }
.bol .nav-button.nav-shortcuts.selected label  { border: 0; color: #9b92ff; }
.bol .tag-dictation  { border: 0; background: #142b23; color: #65efaf;  }
.bol .tag-edit  { border: 0; background: #261d35; color: #c29aff;  }
.bol .tag-unsaved  { border: 0; background: #302417; color: #ffd071;  }
.bol .saving-on  { border: 0; background: #142b23; color: #65efaf;  }
.bol .saving-off  { border: 0; background: #302417; color: #ffd071;  }
.bol .destructive  { color: #f0a0ae; }
.bol .destructive:hover  { border: 0; background: #351b23;  }
.bol .nav-button.nav-general.selected  { border: 0; background-image: linear-gradient(to bottom, #163352, #15151a);  box-shadow: none; }
.bol .page-general .section-title  { color: #4da3ff; }
.bol .nav-button.nav-providers.selected  { border: 0; background-image: linear-gradient(to bottom, #34204b, #15151a);  box-shadow: none; }
.bol .page-providers .section-title  { color: #ad78ff; }
.bol .nav-button.nav-writing.selected  { border: 0; background-image: linear-gradient(to bottom, #3b2c13, #15151a);  box-shadow: none; }
.bol .page-writing .section-title  { color: #ffb53f; }
.bol .nav-button.nav-vocabulary.selected  { border: 0; background-image: linear-gradient(to bottom, #103c2b, #15151a);  box-shadow: none; }
.bol .page-vocabulary .section-title  { color: #43e3a1; }
.bol .nav-button.nav-snippets.selected  { border: 0; background-image: linear-gradient(to bottom, #3d1d32, #15151a);  box-shadow: none; }
.bol .page-snippets .section-title  { color: #ff72c2; }
.bol .nav-button.nav-history.selected  { border: 0; background-image: linear-gradient(to bottom, #10383e, #15151a);  box-shadow: none; }
.bol .page-history .section-title  { color: #39dcea; }
.bol .nav-button.nav-shortcuts.selected  { border: 0; background-image: linear-gradient(to bottom, #2b2748, #15151a);  box-shadow: none; }
.bol .page-shortcuts .section-title  { color: #9b92ff; }
.bol button.primary  { border: 0; background-image: linear-gradient(to bottom, #8dc5ff, #4a99f5); font-weight: 700; box-shadow: 0 2px 8px alpha(#388cff, 0.18); }
.bol button.primary:disabled  { border: 0; background-image: none; box-shadow: none; }
.bol .filter:checked  { border: 0;  background-image: linear-gradient(to bottom, #1d426c, #152a44); }
.bol .tag  { border: 0; font-weight: 600; }
.bol .key  { border: 0; color: #b6acff; background: #231e39;  font-weight: 600; }
.bol .transcript:hover  { border-color: #296771; }
.bol .history-toolbar:focus-within  { border-color: #2a8d9b; }
.bol .copy-action  { border: 0; color: #65efaf; background: #102b21;  }
.bol .copy-action:hover  { border: 0; background: #184333;  }
.bol .export-action  { border: 0; color: #77e5f0; background: #10272c;  }
.bol .export-action:hover  { border: 0; background: #163943;  }
.bol .memory-action  { border: 0; color: #ffd071; background: #302415;  }
.bol .memory-action:hover  { border: 0; background: #48351c;  }
.bol .status  { color: #94c6ff; }
.bol .date-heading  { color: #7edce5; }
.bol .nav-button.nav-text-to-audio.selected  { border: 0; background: linear-gradient(to bottom, #422113, #17100c);  color: #ffbd88; }
.bol .nav-button.nav-text-to-audio.selected label, .bol .page-text-to-audio .section-title  { border: 0; color: #ffbd88; }
.bol .profile-avatar { background: #183827; color: #8cf3c2; border-radius: 9px; padding: 10px; font-weight: 700; }
.bol .nav-button.nav-profile.selected { background: #19352a; color: #8cf3c2; border: 0; }
.bol .page-profile .section-title { color: #8cf3c2; }
.bol button.profile-card { background: linear-gradient(to bottom, #191d1d, #131616); border: 0; border-radius: 13px; padding: 0; box-shadow: none; }
.bol button.profile-card:hover { background: linear-gradient(to bottom, #252d2b, #1a211f); }
.bol button.profile-card:checked { background: #202b27; }
.bol .profile-avatar { background: linear-gradient(145deg, #24664a, #123c2e); color: #a7ffd1; border: 0; border-radius: 11px; padding: 0; font-size: 14px; font-weight: 700; }
.bol .profile-name { color: #f2f4f3; font-size: 13px; font-weight: 600; }
.bol .profile-caption { color: #8f9a95; font-size: 11px; font-weight: 400; }
.bol .profile-menu contents { background: #141717; border: 0; border-radius: 15px; padding: 3px; box-shadow: 0 12px 35px alpha(black, 0.55); }
.bol .profile-menu .menu-group { color: #77847e; font-size: 10px; font-weight: 600; }
.bol .profile-menu .nav-button.settings-item { background: transparent; background-image: none; border: 0; padding: 9px 10px; border-radius: 9px; box-shadow: none; }
.bol .profile-menu .nav-button.settings-item:hover { background: #232a27; }
.bol .profile-menu .nav-button.settings-item.selected { background: #26332d; background-image: none; border: 0; box-shadow: none; }
.bol .profile-menu .nav-button.settings-item .menu-item-title { color: #e5ece8; font-size: 12px; font-weight: 500; }
.bol .profile-menu .menu-item-hint { color: #89958e; font-size: 10px; font-weight: 400; }
.bol .profile-menu .menu-icon { padding: 7px; border-radius: 8px; background: #232c27; }
.bol .profile-menu .well-general { background: #172b42; }
.bol .profile-menu .well-providers { background: #2b2040; }
.bol .profile-menu .well-writing { background: #362b17; }
.bol .profile-menu .well-vocabulary { background: #17342a; }
.bol .profile-menu .well-snippets { background: #362035; }
.bol .profile-menu .well-shortcuts { background: #282540; }
.bol .profile-menu .menu-setup { background: transparent; border: 0; padding: 14px 17px; border-radius: 9px; margin: 4px; color: #a3d9be; }
.bol .profile-menu .menu-setup:hover { background: #222c26; }
.bol .profile-menu-panel { background: #141717; border: 0; border-radius: 15px; padding: 3px; box-shadow: 0 6px 20px alpha(black, 0.35); }
.bol scrollbar.vertical, .bol scrollbar.vertical contents, .bol scrollbar.vertical trough { min-width: 4px; background: transparent; border: 0; padding: 0; margin: 0; }
.bol scrollbar.vertical slider { min-width: 4px; min-height: 30px; background: #454b48; border: 0; margin: 0; border-radius: 3px; }
.bol scrollbar.vertical:hover slider { background: #74867b; min-width: 5px; }
.bol .window-control { min-width: 28px; min-height: 28px; padding: 2px; border: 0; border-radius: 8px; background: transparent; box-shadow: none; }
.bol .window-control.minimize-control:hover { background: #272727; }
.bol .window-control.hide-control:hover { background: #272727; }
.bol .window-control.close-control:hover { background: #303030; }
.bol scrollbar slider  { background: #515151; min-width: 5px; border-radius: 4px; }
'''

LANGUAGE_NAMES = dict(zip(LANGUAGES, ['Detect automatically','English','Hindi','Punjabi','Bengali','Kannada','Malayalam','Marathi','Odia','Tamil','Telugu','Gujarati','Assamese','Urdu','Nepali','Konkani','Sanskrit','Sindhi','Kashmiri','Dogri','Bodo','Manipuri','Maithili','Santali']))
MODE_NAMES = dict(zip(MODES, ['Original language','Mixed language & script','Roman script','Translate to English','Word for word']))
PAGES = [
    ('History','history','Review and recover your recent results.'),
    ('Text to Audio','audio','Turn your words into natural speech.'),
    ('General','general','Connection, language, and recording preferences.'),
    ('Providers','providers','Choose local models and connect speech or writing APIs.'),
    ('Writing','writing','Writing preferences and application-specific styles.'),
    ('Vocabulary','vocabulary','Recognition hints and preferred spellings.'),
    ('Snippets','snippets','Expand a spoken phrase into reusable text.'),
    ('Shortcuts','shortcuts','Keyboard shortcuts and recording controls.'),
    ('Profile','profile','Your local workspace and personal preferences.'),
]


ICON_DIR = Path(__file__).resolve().parent / 'icons'


ICON_THEME='dark'
ICON_IMAGES={}


def light_color(color):
    value=color.lstrip('#')
    if len(value)==3:value=''.join(c*2 for c in value)
    explicit={'090909':'#f7f8fb','0c0c0c':'#eff2f7','141414':'#ffffff','191919':'#f5f7fa',
              '242424':'#e8edf4','292929':'#dce3ed','333333':'#cbd5e2','ececec':'#19263b',
              'e4e4e4':'#26354a','929292':'#5e6e84','999999':'#627187','858585':'#69788c'}
    if value.lower() in explicit:return explicit[value.lower()]
    r,g,b=[int(value[index:index+2],16)/255 for index in (0,2,4)]
    hue,lum,sat=colorsys.rgb_to_hls(r,g,b)
    if sat<.15:
        return '#edf1f6' if lum<.15 else '#ced7e3' if lum<.45 else '#607087' if lum<.7 else '#1d2b40'
    rgb=colorsys.hls_to_rgb(hue,.90 if lum<.35 else .39,min(1.0,sat*1.18))
    return '#'+''.join(f'{round(channel*255):02x}' for channel in rgb)


def theme_css(theme):
    if not is_light(theme):return CSS+overrides(theme).encode()
    css=CSS.decode()
    css=re.sub(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b',lambda match:light_color(match[0]),css)
    css+='\n.bol button.primary, .bol button.primary label { color: white; }\n.bol button.primary:disabled, .bol button.primary:disabled label { color: #8793a4; }\n.bol .window-control { background: transparent; }\n'
    css+=overrides(theme)+light_accents(theme)
    if theme=='ivory':
        # Catch inherited GTK/base accents as well as our semantic colors.
        def warm_accent(match):
            color=match[0];rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            hue,lum,sat=colorsys.rgb_to_hls(*rgb)
            if .48<hue<.72 and sat>.12:
                rgb=colorsys.hls_to_rgb(.10,lum,min(sat,.65))
                return '#'+''.join(f'{round(c*255):02x}' for c in rgb)
            return color
        css=re.sub(r'#[0-9a-fA-F]{6}\b',warm_accent,css)
    return css.encode()


@lru_cache(maxsize=384)
def cached_icon(name,size,theme):
    path=ICON_DIR/(name+'-'+theme+'.svg') if is_light(theme) else ICON_DIR/(name+'.svg')
    if is_light(theme) and not path.exists():path=ICON_DIR/(name+'-light.svg')
    if not path.exists():path=ICON_DIR/(name+'.svg')
    return Gtk.IconPaintable.new_for_file(Gio.File.new_for_path(str(path)),size,1)


def icon_paintable(name,size):
    return cached_icon(name,size,ICON_THEME)


def svg_icon(name, size=18):
    image=Gtk.Image.new_from_paintable(icon_paintable(name,size));image.set_pixel_size(size)
    ICON_IMAGES[image]=(name,size)
    return image


def action_button(title, icon_name):
    button = Gtk.Button()
    if icon_name in ['copy','export','memory']:button.add_css_class(icon_name+'-action')
    content = Gtk.Box(spacing=8)
    content.set_halign(Gtk.Align.CENTER)
    content.append(svg_icon(icon_name,16))
    content.append(label(title))
    button.set_child(content)
    return button


def margins(widget, value):
    for side in ['top','bottom','start','end']:
        getattr(widget, 'set_margin_'+side)(value)
    return widget


def label(text, css=None, wrap=False):
    widget=Gtk.Label(label=text, xalign=0)
    if css: widget.add_css_class(css)
    widget.set_wrap(wrap)
    return widget


class SettingsPanel(Gtk.Revealer):
    def __init__(self):
        super().__init__()
        self.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.set_transition_duration(100)
        self.set_halign(Gtk.Align.START);self.set_valign(Gtk.Align.END)
        self.set_margin_start(12);self.set_margin_bottom(88)
        self.add_css_class('profile-menu');self.set_visible(False)

    def popup(self):
        self.set_visible(True);self.set_reveal_child(True)

    def popdown(self):
        self.set_reveal_child(False);self.set_visible(False)


class Workspace:
    def __init__(self, core, single_instance=True):
        self.core=core
        self.settings=core.config()
        self.widgets={}
        self.buffers={}
        self.choices={}
        self.loading=True
        self.alive=True
        self.history_rows=[]
        self.history_request=0
        self.history_kind='all'
        self.history_latest={}
        self.history_all=[]
        self.audio_generation=0
        self.audio_path=None
        self.audio_directory=None
        self.audio_player=None
        self.audio_style_generation=0
        self.app=Gtk.Application(application_id='io.github.bol.Workspace', flags=Gio.ApplicationFlags.DEFAULT_FLAGS if single_instance else Gio.ApplicationFlags.NON_UNIQUE)
        self.app.connect('activate', self.activate)

    def changed(self,*args):
        if not self.loading:
            self.save_note.set_text('Unsaved changes')
            self.save_button.set_sensitive(True)

    def activate(self,app):
        if hasattr(self,'window') and self.alive:
            self.window.present();return
        global ICON_THEME
        ICON_THEME=self.settings.get('theme','dark')
        provider=Gtk.CssProvider();self.theme_provider=provider;provider.load_from_data(theme_css(ICON_THEME))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.window=Gtk.ApplicationWindow(application=app,title='Bol')
        self.window.add_css_class('bol'); self.window.set_default_size(1120,800)
        self.window.set_size_request(900,620)
        self.window.connect('close-request',self.on_close)
        header=Gtk.HeaderBar();header.set_show_title_buttons(False);header.set_title_widget(label('Bol','section-title'))
        controls=Gtk.Box(spacing=5)
        for title,icon,callback,css in [('Minimize','minimize',self.minimize_window,'minimize-control'),('Hide · open Bol again to restore','hide',self.hide_window,'hide-control'),('Close window','close',lambda:self.window.close(),'close-control')]:
            button=Gtk.Button();button.set_child(svg_icon(icon,16));button.add_css_class('window-control');button.add_css_class(css);button.set_tooltip_text(title);button.connect('clicked',lambda b,fn=callback:fn());controls.append(button)
        header.pack_end(controls);self.window.set_titlebar(header)
        layout=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        overlay=Gtk.Overlay();self.window.set_child(overlay);overlay.set_child(layout);self.window_overlay=overlay
        side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
        side.add_css_class('sidebar');side.set_size_request(224,-1);side.set_hexpand(False);layout.append(side)
        brand=Gtk.Box(spacing=10);margins(brand,22)
        icon=svg_icon('brand',24)
        brand.append(icon);brand.append(label('Bol','brand'));side.append(brand)
        navtitle=label('Workspace','nav-heading');navtitle.set_margin_start(22);navtitle.set_margin_top(9);navtitle.set_margin_bottom(8);side.append(navtitle)
        self.nav={}
        profile_popover=SettingsPanel();overlay.add_overlay(profile_popover)
        profile_menu=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0);profile_menu.add_css_class('profile-menu-panel');profile_menu.set_size_request(296,-1);profile_popover.set_child(profile_menu)
        self.profile_popover=profile_popover
        menu_identity=Gtk.Box(spacing=12);margins(menu_identity,15)
        self.profile_menu_avatar=label('B','profile-avatar');self.profile_menu_avatar.set_xalign(.5);self.profile_menu_avatar.set_size_request(40,40);menu_identity.append(self.profile_menu_avatar)
        menu_identity_text=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);menu_identity_text.set_hexpand(True)
        self.profile_menu_name=label('Your workspace','profile-name');self.profile_menu_name.set_ellipsize(3);self.profile_menu_name.set_max_width_chars(24);menu_identity_text.append(self.profile_menu_name)
        menu_identity_text.append(label('Local profile · on this device','profile-caption'));menu_identity.append(menu_identity_text);profile_menu.append(menu_identity)
        profile_menu.append(Gtk.Separator())
        for title,icon_name,description in PAGES:
            button=Gtk.Button();button.add_css_class('nav-button');button.add_css_class('nav-'+title.lower().replace(' ','-'));button.set_margin_start(10);button.set_margin_end(10)
            row=Gtk.Box(spacing=12);image=svg_icon(icon_name,18)
            row.append(image);row.append(label('Connections' if title=='Providers' else title));button.set_child(row)
            button.connect('clicked',lambda b,name=title:self.select(name))
            if title in ['History','Text to Audio']:side.append(button)
            self.nav[title]=button
        descriptions={
            'Profile':('Your profile','Name and workspace preferences','profile'),
            'General':('Preferences','Language, recording, and privacy','general'),
            'Providers':('Connections','Speech and writing services','providers'),
            'Writing':('Writing style','Tone and app-specific rules','writing'),
            'Vocabulary':('Vocabulary','Names and preferred spellings','vocabulary'),
            'Snippets':('Snippets','Reusable spoken shortcuts','snippets'),
            'Shortcuts':('Keyboard shortcuts','Dictation and editing controls','shortcuts'),
        }
        menu_scroll=Gtk.ScrolledWindow();self.settings_menu_scroll=menu_scroll;menu_scroll.set_overlay_scrolling(True);menu_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);menu_scroll.set_propagate_natural_height(True);menu_scroll.set_max_content_height(460)
        menu_items=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2);margins(menu_items,7);menu_scroll.set_child(menu_items);profile_menu.append(menu_scroll)
        for group,items in [('Workspace',['Profile','General','Providers']),('Personalization',['Writing','Vocabulary','Snippets']),('Controls',['Shortcuts'])]:
            group_title=label(group,'menu-group');group_title.set_margin_start(10);group_title.set_margin_top(10);group_title.set_margin_bottom(5);menu_items.append(group_title)
            for key in items:
                title,hint,icon_name=descriptions[key]
                button=self.nav[key];button.add_css_class('settings-item');button.set_margin_start(0);button.set_margin_end(0)
                row=Gtk.Box(spacing=11)
                image=svg_icon(icon_name,17);image.add_css_class('menu-icon');image.add_css_class('well-'+icon_name);row.append(image)
                words=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);words.set_hexpand(True);words.append(label(title,'menu-item-title'));words.append(label(hint,'menu-item-hint'));row.append(words)
                button.set_child(row);menu_items.append(button)
        profile_menu.append(Gtk.Separator())
        setup=Gtk.Button();setup.add_css_class('menu-setup');setup_row=Gtk.Box(spacing=10);setup_row.append(svg_icon('brand',16));setup_row.append(label('Setup assistant'));setup.set_child(setup_row)
        setup.connect('clicked',lambda b:(self.profile_popover.popdown(),self.show_setup()));profile_menu.append(setup)
        spacer=Gtk.Box();spacer.set_vexpand(True);side.append(spacer)
        quick=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);margins(quick,22)
        quick.append(label('Quick access','nav-heading'));self.key_labels={}
        for key,title in [('record_key','Dictate'),('edit_key','Voice edit'),('cancel_key','Cancel')]:
            row=Gtk.Box();name=label(title,'muted');name.set_hexpand(True);row.append(name)
            value=label(self.settings.get(key,''),'key');row.append(value);self.key_labels[key]=value;quick.append(row)
        side.append(quick)
        profile_button=Gtk.Button();self.profile_button=profile_button;profile_button.add_css_class('profile-card');profile_button.connect('clicked',self.toggle_settings_menu);profile_button.set_margin_start(12);profile_button.set_margin_end(12);profile_button.set_margin_top(14);profile_button.set_margin_bottom(18)
        identity=Gtk.Box(spacing=11);margins(identity,10)
        self.profile_avatar=label('B','profile-avatar');self.profile_avatar.set_xalign(.5);self.profile_avatar.set_size_request(36,36);identity.append(self.profile_avatar)
        identity_text=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);identity_text.set_hexpand(True)
        self.profile_title=label(self.settings.get('profile_name') or 'Your workspace','profile-name');self.profile_title.set_ellipsize(3);self.profile_title.set_max_width_chars(16);identity_text.append(self.profile_title)
        identity_text.append(label('Profile & settings','profile-caption'));identity.append(identity_text)
        identity.append(svg_icon('chevrons',14));profile_button.set_child(identity);side.append(profile_button)
        keys=Gtk.EventControllerKey();keys.connect('key-pressed',self.window_key);self.window.add_controller(keys)
        click=Gtk.GestureClick();click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE);click.connect('pressed',self.outside_settings_click);self.window.add_controller(click)
        main=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);main.set_hexpand(True);layout.append(main)
        self.stack=Gtk.Stack();self.stack.set_vexpand(True);self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE);self.stack.set_transition_duration(120);main.append(self.stack)
        self.pages={}
        for title,icon_name,description in PAGES:
            scroller=Gtk.ScrolledWindow();scroller.set_overlay_scrolling(True);scroller.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
            page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20);page.add_css_class('page-'+title.lower().replace(' ','-'));margins(page,42);scroller.set_child(page)
            heading=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);heading.set_margin_bottom(9)
            heading.append(label('Connections' if title=='Providers' else title,'page-title'));heading.append(label(description,'muted',True));page.append(heading)
            self.stack.add_named(scroller,title);self.pages[title]=page
        footer=Gtk.Box(spacing=12);footer.add_css_class('footer');margins(footer,0)
        inner=Gtk.Box(spacing=12);margins(inner,18);inner.set_hexpand(True);footer.append(inner)
        self.save_note=label('All changes saved','muted');self.save_note.set_hexpand(True);inner.append(self.save_note)
        self.status=label('Ready','status');self.status.set_ellipsize(3);self.status.set_max_width_chars(28);inner.append(self.status)
        self.review_button=Gtk.Button(label='Review edit');self.review_button.add_css_class('primary');self.review_button.set_visible(False);self.review_button.connect('clicked',self.review_pending);inner.append(self.review_button)
        self.cancel_button=action_button('Cancel recording','cancel');cancel=self.cancel_button;cancel.set_visible(False);cancel.connect('clicked',self.cancel_recording);inner.append(cancel)
        self.save_button=Gtk.Button(label='Save changes');self.save_button.add_css_class('primary');self.save_button.set_sensitive(False);self.save_button.connect('clicked',self.save);inner.append(self.save_button)
        main.append(footer)
        self.build_audio();self.build_general();self.build_providers();self.build_writing();self.build_vocabulary();self.build_snippets();self.build_history();self.build_shortcuts();self.build_profile()
        self.update_provider_sections();self.loading=False;self.update_profile_identity();self.select(self.settings.get('start_page','History'));self.window.present()
        configured=bool(self.settings.get('api_key') or self.settings.get('speech_api_key') or self.settings.get('speech_provider') in ['whispercpp','elevenlabs'])
        if not self.settings.get('setup_completed') and not configured:GLib.idle_add(self.show_setup)
        GLib.timeout_add(800,self.poll)

    def minimize_window(self):
        import os
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            # Hyprland has no conventional minimize operation; hide preserves the window.
            self.hide_window()
        else:self.window.minimize()

    def hide_window(self):
        self.profile_popover.popdown();self.window.set_visible(False)
        self.core.notify('Bol is hidden. Open Bol again to restore this window. Dictation shortcuts still work.')

    def toggle_settings_menu(self,*args):
        if self.profile_popover.get_visible():self.profile_popover.popdown()
        else:
            self.settings_menu_scroll.set_max_content_height(max(150,min(460,self.window.get_height()-330)))
            self.profile_popover.popup()

    def window_key(self,controller,keyval,keycode,state):
        if keyval==Gdk.KEY_Escape and self.profile_popover.get_visible():
            self.profile_popover.popdown();return True
        return False

    def outside_settings_click(self,gesture,presses,x,y):
        if not self.profile_popover.get_visible():return
        widget=self.window.pick(x,y,Gtk.PickFlags.DEFAULT)
        while widget:
            if widget in [self.profile_popover,self.profile_button]:return
            widget=widget.get_parent()
        self.profile_popover.popdown()

    def section(self,page,title,description=None):
        section=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        section.append(label(title,'section-title'))
        if description:section.append(label(description,'muted',True))
        group=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);group.add_css_class('group');section.append(group);page.append(section)
        return group

    def row(self,group,title,hint,control):
        if group.get_first_child():group.append(Gtk.Separator())
        row=Gtk.Box(spacing=22);margins(row,16)
        words=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);words.set_hexpand(True)
        words.append(label(title,'row-title'))
        if hint:
            sub=label(hint,'row-hint',True);sub.set_max_width_chars(40);words.append(sub)
        row.append(words);control.set_valign(Gtk.Align.CENTER);row.append(control);group.append(row)
        return row

    def entry(self,group,key,title,hint='',password=False):
        widget=Gtk.PasswordEntry(show_peek_icon=True) if password else Gtk.Entry()
        widget.set_text(str(self.settings.get(key,'')));widget.set_size_request(260,-1)
        widget.connect('changed',self.changed);self.widgets[key]=widget
        self.row(group,title,hint,widget);return widget

    def choice(self,group,key,title,hint,values,names):
        widget=Gtk.DropDown.new_from_strings([names.get(v,v) for v in values]);widget.set_size_request(190,-1)
        value=self.settings.get(key,values[0]);widget.set_selected(values.index(value) if value in values else 0)
        widget.connect('notify::selected',self.changed);self.widgets[key]=widget;self.choices[key]=values
        self.row(group,title,hint,widget)

    def toggle(self,group,key,title,hint):
        widget=Gtk.Switch();widget.set_active(self.settings.get(key,False));widget.connect('notify::active',self.changed);self.widgets[key]=widget
        self.row(group,title,hint,widget)

    def editor(self,group,key,text,height=130):
        scroller=Gtk.ScrolledWindow();scroller.set_min_content_height(height);scroller.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroller.add_css_class('editor-frame');margins(scroller,14)
        view=Gtk.TextView();view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR);view.set_top_margin(12);view.set_bottom_margin(12);view.set_left_margin(12);view.set_right_margin(12)
        buffer=view.get_buffer();buffer.set_text(text)
        if key not in ['result','tts_text','tts_instructions']:buffer.connect('changed',self.changed)
        self.buffers[key]=buffer;scroller.set_child(view);group.append(scroller);return buffer

    def build_audio(self):
        page=self.pages['Text to Audio']
        group=self.section(page,'Text to speak','Powered by Sarvam Bulbul v3. Text is sent only when you choose Generate audio; API credits may be used.')
        self.editor(group,'tts_text','',210)
        self.audio_characters=label('0 / 2,500 characters','muted');page.append(self.audio_characters)
        self.buffers['tts_text'].connect('changed',lambda b:self.audio_characters.set_text(f'{len(self.text("tts_text")):,} / 2,500 characters'))
        group=self.section(page,'Voice settings')
        self.audio_language=Gtk.DropDown.new_from_strings([LANGUAGE_NAMES.get(v,LANGUAGE_NAMES.get(v.split('-')[0],v)) for v in TTS_LANGUAGES]);self.audio_language.set_size_request(190,-1)
        self.row(group,'Language','The language of the text you want spoken.',self.audio_language)
        self.audio_voice=Gtk.DropDown.new_from_strings([v.capitalize() for v in TTS_VOICES]);self.audio_voice.set_size_request(190,-1)
        self.row(group,'Voice','Choose the speaker used for generation.',self.audio_voice)
        self.audio_pace=Gtk.SpinButton.new_with_range(.5,2,.1);self.audio_pace.set_digits(1);self.audio_pace.set_value(1)
        self.row(group,'Speaking speed','1.0 is the natural speaking pace.',self.audio_pace)
        self.audio_expression=Gtk.SpinButton.new_with_range(.01,1,.05);self.audio_expression.set_digits(2);self.audio_expression.set_value(.6)
        self.row(group,'Expressiveness','Higher values add variation; they do not guarantee a specific emotion.',self.audio_expression)
        group=self.section(page,'Delivery style','Choose a preset or describe the feeling you want. Your script stays unchanged.')
        self.audio_styles=list(STYLE_PRESETS)
        self.audio_style=Gtk.DropDown.new_from_strings(self.audio_styles);self.audio_style.set_size_request(190,-1)
        self.audio_style.connect('notify::selected',self.apply_audio_preset)
        self.row(group,'Style preset','Applies a stock voice, pace and expressiveness.',self.audio_style)
        self.editor(group,'tts_instructions','',90)
        self.audio_apply_style=Gtk.Button(label='Apply instructions');self.audio_apply_style.connect('clicked',self.apply_audio_instructions)
        self.row(group,'Describe the delivery','For example: warm and reassuring, a little slower, with a professional tone. Uses your writing API; may consume credits.',self.audio_apply_style)
        self.audio_style_note=label('Click Apply instructions before generating. Instructions choose voice, speed and variation; exact emotions or effects are not guaranteed.','muted',True);margins(self.audio_style_note,16);group.append(self.audio_style_note)

        actions=Gtk.FlowBox();actions.set_selection_mode(Gtk.SelectionMode.NONE);actions.set_homogeneous(False);actions.set_column_spacing(8);actions.set_row_spacing(8);actions.set_max_children_per_line(3)
        self.audio_generate=Gtk.Button(label='Generate audio');self.audio_generate.add_css_class('primary');self.audio_generate.connect('clicked',self.generate_audio);actions.insert(self.audio_generate,-1)
        self.audio_cancel=Gtk.Button(label='Cancel generation');self.audio_cancel.set_sensitive(False);self.audio_cancel.connect('clicked',self.cancel_audio);actions.insert(self.audio_cancel,-1)
        reuse=Gtk.Button(label='Use latest transcript');reuse.connect('clicked',self.audio_from_latest);actions.insert(reuse,-1);page.append(actions)
        group=self.section(page,'Generated audio')
        self.audio_note=label('Generate a clip to play it here or save it as a WAV file.','muted',True);margins(self.audio_note,16);group.append(self.audio_note)
        player=Gtk.Box(spacing=8);margins(player,16)
        self.audio_play=action_button('Play','play');self.audio_play.set_sensitive(False);self.audio_play.connect('clicked',self.play_audio);player.append(self.audio_play)
        stop=action_button('Stop','cancel');stop.connect('clicked',lambda b:self.stop_audio());player.append(stop)
        self.audio_save=action_button('Save WAV','export');self.audio_save.set_sensitive(False);self.audio_save.connect('clicked',self.save_audio);player.append(self.audio_save);group.append(player)
        self.audio_voice.connect('notify::selected',self.audio_controls_changed)
        self.audio_language.connect('notify::selected',self.audio_controls_changed)
        self.audio_pace.connect('value-changed',self.audio_controls_changed)
        self.audio_expression.connect('value-changed',self.audio_controls_changed)
        self.buffers['tts_instructions'].connect('changed',self.audio_instructions_changed)
        page.append(label('Generated audio is temporary until you save it. Closing Bol deletes the temporary clip. Audio is not played automatically.','muted',True))

    def audio_controls_changed(self,*args):
        if getattr(self,'applying_audio_plan',False):return
        self.audio_style_generation+=1;self.audio_apply_style.set_sensitive(True)
        self.audio_style_note.set_text('Manual settings updated. Generate audio to use the selected voice, speed and expressiveness.')

    def audio_instructions_changed(self,*args):
        self.audio_style_generation+=1;self.audio_apply_style.set_sensitive(True)
        self.audio_style_note.set_text('Instructions changed. Click Apply instructions to turn them into delivery settings.')

    def apply_audio_plan(self,plan):
        self.applying_audio_plan=True
        try:
            self.audio_voice.set_selected(TTS_VOICES.index(plan['voice']))
            self.audio_pace.set_value(plan['pace']);self.audio_expression.set_value(plan['temperature'])
        finally:self.applying_audio_plan=False
        self.audio_style_note.set_text(f"Applied: {plan['voice'].capitalize()} voice, {plan['pace']:.2f}× speed, {plan['temperature']:.2f} expressiveness. You can adjust these before generating.")

    def apply_audio_preset(self,*args):
        self.audio_style_generation+=1
        self.audio_apply_style.set_sensitive(True)
        plan=STYLE_PRESETS[self.audio_styles[self.audio_style.get_selected()]]
        if plan:self.apply_audio_plan(plan)
        else:self.audio_style_note.set_text('Manual settings: choose your voice, speed and expressiveness above.')

    def apply_audio_instructions(self,*args):
        instructions=self.text('tts_instructions')
        if not instructions.strip() or len(instructions.strip())>1500:self.dialog('Delivery instructions','Enter 1–1500 characters describing the vocal delivery.');return
        settings=self.core.config();language=TTS_LANGUAGES[self.audio_language.get_selected()]
        self.audio_style_generation+=1;token=self.audio_style_generation
        self.audio_apply_style.set_sensitive(False);self.audio_style_note.set_text('Choosing delivery settings… Your script will not be changed.')
        def worker():
            try:plan=suggest_delivery(instructions,settings,language);error=None
            except Exception as exc:plan=None;error=str(exc)
            GLib.idle_add(self.audio_style_suggested,token,plan,error)
        threading.Thread(target=worker,daemon=True).start()

    def audio_style_suggested(self,token,plan,error):
        if not self.alive or token!=self.audio_style_generation:return False
        self.audio_apply_style.set_sensitive(True)
        if error:self.audio_style_note.set_text(error)
        else:self.apply_audio_plan(plan)
        return False

    def generate_audio(self,*args):
        if not self.audio_apply_style.get_sensitive():self.dialog('Style suggestion in progress','Wait for the delivery settings, or choose a preset to cancel the suggestion.');return
        text=self.text('tts_text')
        if not text.strip() or len(text.strip())>2500:self.dialog('Check your text','Enter between 1 and 2500 characters.');return
        key=self.core.config().get('api_key','')
        if not key:self.show_setup();return
        language=TTS_LANGUAGES[self.audio_language.get_selected()];voice=TTS_VOICES[self.audio_voice.get_selected()];pace=self.audio_pace.get_value();expression=self.audio_expression.get_value()
        self.audio_generation+=1;generation=self.audio_generation
        self.audio_generate.set_sensitive(False);self.audio_cancel.set_sensitive(True);self.audio_note.set_text('Generating audio… You can continue using Bol.')
        def worker():
            try:data=synthesize(text,key,language,voice,pace,expression);error=None
            except Exception as exc:data=None;error=str(exc)
            GLib.idle_add(self.audio_generated,generation,data,error)
        threading.Thread(target=worker,daemon=True).start()

    def audio_generated(self,generation,data,error):
        if not self.alive or generation!=self.audio_generation:return False
        self.audio_generate.set_sensitive(True);self.audio_cancel.set_sensitive(False)
        if error:self.audio_note.set_text(error);return False
        import tempfile,os,io,wave
        self.stop_audio()
        if self.audio_directory is None:self.audio_directory=tempfile.TemporaryDirectory(prefix='bol-audio-')
        self.audio_path=Path(self.audio_directory.name)/'generated.wav';self.audio_path.write_bytes(data);os.chmod(self.audio_path,0o600)
        with wave.open(io.BytesIO(data),'rb') as clip:duration=clip.getnframes()/clip.getframerate()
        self.audio_note.set_text(f'Audio ready · {duration:.1f} seconds · WAV, 24 kHz');self.audio_play.set_sensitive(True);self.audio_save.set_sensitive(True)
        return False

    def cancel_audio(self,*args):
        self.audio_generation+=1;self.audio_generate.set_sensitive(True);self.audio_cancel.set_sensitive(False)
        self.audio_note.set_text('Generation cancelled. A request already sent to Sarvam may still complete and use credits.')

    def text_to_audio(self,text):
        self.buffers['tts_text'].set_text(text)
        self.select('Text to Audio')

    def audio_from_latest(self,*args):
        def worker():
            try:result=self.core.request('result');text=result.get('text','')
            except Exception:text=''
            GLib.idle_add(self.set_audio_text,text)
        threading.Thread(target=worker,daemon=True).start()

    def set_audio_text(self,text):
        if self.alive:
            if text:self.buffers['tts_text'].set_text(text)
            else:self.audio_note.set_text('No latest transcript is available yet.')
        return False

    def stop_audio(self):
        if self.audio_player and self.audio_player.poll() is None:self.audio_player.terminate()
        if self.audio_player:
            try:self.audio_player.wait(timeout=1)
            except Exception:self.audio_player.kill();self.audio_player.wait()
        self.audio_player=None

    def play_audio(self,*args):
        if not self.audio_path:return
        import subprocess,shutil
        if not shutil.which('pw-play'):self.dialog('Playback unavailable','Install PipeWire tools to use audio playback.');return
        self.stop_audio();self.audio_player=subprocess.Popen(['pw-play',str(self.audio_path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def save_audio(self,*args):
        if not self.audio_path or not self.audio_path.exists():return
        # Capture this clip now, so generating a new one cannot change the export.
        data=self.audio_path.read_bytes()
        chooser=Gtk.FileChooserNative.new('Save generated audio',self.window,Gtk.FileChooserAction.SAVE,'Save','Cancel');chooser.set_current_name('bol-audio.wav')
        file_filter=Gtk.FileFilter();file_filter.set_name('WAV audio');file_filter.add_pattern('*.wav');chooser.add_filter(file_filter)
        def response(dialog,result):
            if result==Gtk.ResponseType.ACCEPT:
                path=dialog.get_file().get_path()
                try:
                    if not path:raise ValueError('Choose a local folder.')
                    import os
                    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                    with os.fdopen(fd,'wb') as output:output.write(data)
                    self.audio_note.set_text('WAV file saved.')
                except Exception as error:self.dialog('Could not save audio',str(error))
            dialog.destroy()
        chooser.connect('response',response);chooser.show()

    def preview_theme(self,*args):
        global ICON_THEME
        ICON_THEME=self.choices['theme'][self.widgets['theme'].get_selected()]
        self.theme_provider.load_from_data(theme_css(ICON_THEME))
        for image,(name,size) in list(ICON_IMAGES.items()):image.set_from_paintable(icon_paintable(name,size))
        if hasattr(self,'history_search'):self.history_search.set_icon_from_paintable(Gtk.EntryIconPosition.PRIMARY,icon_paintable('search',16))
        if hasattr(self,'theme_description'):self.theme_description.set_text(THEMES[ICON_THEME]['description'])
        for key,button in getattr(self,'theme_buttons',{}).items():
            if key==ICON_THEME:button.add_css_class('selected')
            else:button.remove_css_class('selected')

    def update_profile_identity(self):
        name=(self.settings.get('profile_name') or 'Your workspace').strip()
        self.profile_title.set_text(name)
        initials=''.join(part[0] for part in name.split()[:2]).upper() or 'B'
        self.profile_avatar.set_text(initials);self.profile_menu_avatar.set_text(initials);self.profile_menu_name.set_text(name)

    def build_profile(self):
        page=self.pages['Profile']
        group=self.section(page,'Your profile','This profile lives on this computer. It is not a cloud account or a Sarvam sign-in.')
        self.entry(group,'profile_name','Display name','How Bol labels your workspace.').set_placeholder_text('Your name')
        self.widgets['profile_name'].set_max_length(80)
        group=self.section(page,'Appearance','Choose a palette to preview it immediately. Save changes to keep it.')
        self.choice(group,'theme','Theme','Four light and four dark variations.',list(THEMES),{key:value['name'] for key,value in THEMES.items()})
        self.theme_description=label(THEMES.get(self.settings.get('theme'),THEMES['dark'])['description'],'muted',True);margins(self.theme_description,14);group.append(self.theme_description)
        self.theme_buttons={}
        for family,title in [('dark','Dark palettes'),('light','Light palettes')]:
            title_label=label(title,'muted');title_label.set_margin_start(14);title_label.set_margin_top(10);group.append(title_label)
            gallery=Gtk.FlowBox();gallery.set_selection_mode(Gtk.SelectionMode.NONE);gallery.set_homogeneous(True);gallery.set_min_children_per_line(1);gallery.set_max_children_per_line(2);gallery.set_column_spacing(8);gallery.set_row_spacing(8);margins(gallery,10)
            for key,value in THEMES.items():
                if value['family']!=family:continue
                button=Gtk.Button();button.add_css_class('theme-preview')
                content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
                picture=Gtk.Picture.new_for_filename(str(Path(__file__).resolve().parent/'themes'/(key+'.svg')));picture.set_can_shrink(True);picture.set_size_request(170,88)
                content.append(picture);content.append(label(value['name']));button.set_child(content);button.set_tooltip_text(value['description'])
                button.connect('clicked',lambda b,theme=key:self.widgets['theme'].set_selected(self.choices['theme'].index(theme)))
                gallery.insert(button,-1);self.theme_buttons[key]=button
            group.append(gallery)
        self.widgets['theme'].connect('notify::selected',self.preview_theme)
        current=self.settings.get('theme','dark')
        if current in self.theme_buttons:self.theme_buttons[current].add_css_class('selected')
        group=self.section(page,'Workspace preferences')
        self.choice(group,'start_page','Open Bol to','Choose your default workspace.',['History','Text to Audio'],{})
        self.toggle(group,'show_advanced','Expand advanced connections','Show provider URLs, keys, and model paths when opening Connections.')
        group=self.section(page,'Setup')
        setup=Gtk.Button(label='Open setup assistant');setup.connect('clicked',lambda b:self.show_setup());self.row(group,'Speech setup','Connect a cloud service or choose local Whisper.',setup)
        page.append(label('Your existing history, vocabulary, snippets, providers, and writing preferences are shared by this local workspace. There is no account synchronization yet.','muted',True))

    def show_setup(self,*args):
        dialog=Gtk.Window(title='Welcome to Bol',transient_for=self.window,modal=True);dialog.add_css_class('bol');dialog.set_default_size(680,660)
        scroller=Gtk.ScrolledWindow();scroller.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);dialog.set_child(scroller)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18);margins(box,28);scroller.set_child(box)
        box.append(label('Make Bol yours','page-title'));box.append(label('A few simple choices, then you are ready to speak.','muted',True))
        name=Gtk.Entry();name.set_max_length(80);name.set_placeholder_text('Your name (optional)');name.set_text(self.settings.get('profile_name',''));box.append(name)
        options=Gtk.DropDown.new_from_strings(['Sarvam cloud · multilingual speech','Local Whisper · on this device'])
        options.set_selected(1 if self.settings.get('speech_provider') in ['whispercpp','elevenlabs'] else 0);box.append(options)
        language=Gtk.DropDown.new_from_strings([LANGUAGE_NAMES.get(value,value) for value in LANGUAGES]);language.set_selected(LANGUAGES.index(self.settings.get('language','unknown')) if self.settings.get('language') in LANGUAGES else 0)
        box.append(label('Language','section-title'));box.append(language)
        cloud=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        cloud.append(label('Connect Sarvam','section-title'))
        cloud.append(label('1. Open Sarvam in your browser and sign in.\n2. Create a key in API Keys.\n3. Copy it once and paste it below. Bol remembers it.','muted',True))
        browser=Gtk.Button(label='Open Sarvam sign-in');browser.connect('clicked',lambda b:self.open_sarvam_dashboard());cloud.append(browser)
        key=Gtk.PasswordEntry(show_peek_icon=True);key.set_text(self.settings.get('api_key',''));cloud.append(key)
        paste=Gtk.Button(label='Paste copied key')
        def paste_key(button):
            clipboard=Gdk.Display.get_default().get_clipboard()
            def pasted(clipboard,result):
                try:
                    text=clipboard.read_text_finish(result)
                    if text and len(text.strip())<=4096:key.set_text(text.strip())
                    else:note.set_text('Copy the connection key on the Sarvam page, then try again.')
                except Exception as error:note.set_text(str(error))
            clipboard.read_text_async(None,pasted)
        paste.connect('clicked',paste_key);cloud.append(paste)
        cloud.append(label('Sarvam currently requires a connection key for third-party apps. Your website login is not copied into Bol. Cloud usage may consume credits.','muted',True));box.append(cloud)
        local=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        binary,model=detect_whisper()
        local.append(label('Use local Whisper','section-title'))
        local.append(label('No browser account or connection key is needed for local dictation. Audio stays on this device. AI writing and Text to Audio are separate cloud features.','muted',True))
        local.append(label('Whisper installation found.' if binary and model else 'No complete Whisper installation found. Choose model paths later in Profile → Providers → Advanced settings.','muted',True))
        if '.en.' in model:local.append(label('The detected model is English-only. Select English or automatic detection, or install a multilingual model for other languages.','muted',True))
        box.append(local)
        note=label('Your settings are stored on this computer.','muted',True);box.append(note)
        buttons=Gtk.Box(spacing=10);later=Gtk.Button(label='Set up later');later.connect('clicked',lambda b:dialog.close());buttons.append(later)
        gap=Gtk.Box();gap.set_hexpand(True);buttons.append(gap)
        finish=Gtk.Button(label='Finish setup');finish.add_css_class('primary');buttons.append(finish);box.append(buttons)
        def route(*args):cloud.set_visible(options.get_selected()==0);local.set_visible(options.get_selected()==1)
        options.connect('notify::selected',route);route()
        def complete(button):
            try:
                data=self.core.config();data.update({'profile_name':name.get_text().strip(),'language':LANGUAGES[language.get_selected()],'setup_completed':True})
                if options.get_selected()==0:
                    if not key.get_text().strip():raise ValueError('Paste your Sarvam key to finish, or choose local Whisper.')
                    data['speech_provider']='sarvam';data['api_key']=key.get_text().strip()
                else:
                    data['speech_provider']='whispercpp'
                    if not data.get('whisper_binary'):data['whisper_binary']=binary
                    if not data.get('whisper_model'):data['whisper_model']=model
                    validate_speech(data)
                dirty=self.save_button.get_sensitive();self.core.save_config(data);self.sync_controls(data,only=['profile_name','language','speech_provider','api_key','whisper_binary','whisper_model'],preserve_dirty=dirty);dialog.close();self.select(data.get('start_page','History'));self.status.set_text('Setup complete')
            except Exception as error:note.set_text(str(error))
        finish.connect('clicked',complete);dialog.present();return False

    def sync_controls(self,data,only=None,preserve_dirty=False):
        self.loading=True
        try:
            for key,widget in self.widgets.items():
                if only is not None and key not in only:continue
                value=data.get(key)
                if key in self.choices:
                    choices=self.choices[key]
                    if value in choices:widget.set_selected(choices.index(value))
                elif isinstance(widget,Gtk.Switch):widget.set_active(bool(value))
                elif isinstance(widget,Gtk.SpinButton):widget.set_value(value or 0)
                elif value is not None:widget.set_text(str(value))
            self.settings=data;self.update_profile_identity();self.update_provider_sections()
            self.save_note.set_text('Connection saved. Other changes are unsaved.' if preserve_dirty else 'All changes saved');self.save_button.set_sensitive(preserve_dirty)
        finally:self.loading=False

    def open_sarvam_dashboard(self):
        try:Gio.AppInfo.launch_default_for_uri('https://dashboard.sarvam.ai/key-management',None)
        except Exception as error:self.dialog('Could not open browser',str(error))

    def build_general(self):
        page=self.pages['General'];group=self.section(page,'Speech recognition')
        self.choice(group,'speech_provider','Speech engine','Configure keys and model paths in Providers.',SPEECH_PROVIDERS,{'sarvam':'Sarvam cloud','whispercpp':'Local whisper.cpp','compatible':'Compatible speech API','elevenlabs':'ElevenLabs · browser sign-in'})
        self.widgets['speech_provider'].connect('notify::selected',lambda *args:self.update_provider_sections())
        group=self.section(page,'Speech')
        self.choice(group,'language','Language','Choose a language or let Bol detect it.',LANGUAGES,LANGUAGE_NAMES)
        self.choice(group,'output_mode','Output style','How your speech appears as text.',MODES,MODE_NAMES)
        self.entry(group,'microphone','Microphone','Leave empty to use your system default.').set_placeholder_text('System default')
        self.mic_test_button=action_button('Test microphone','microphone')
        self.mic_test_button.connect('clicked',self.test_microphone)
        self.row(group,'Microphone check','Record a three-second sample locally. No upload.',self.mic_test_button)
        duration=Gtk.SpinButton.new_with_range(5,300,5);duration.set_value(self.settings.get('record_seconds',120));duration.connect('value-changed',self.changed);self.widgets['record_seconds']=duration
        self.row(group,'Recording limit','Maximum seconds before Bol finishes automatically.',duration)
        group=self.section(page,'Workflow')
        self.toggle(group,'auto_paste','Automatic paste','Insert the result into your original focused app.')
        self.toggle(group,'history_enabled','Save history','Keep up to 200 results locally on this computer.')
        self.choice(group,'history_retention_days','Keep saved history','Expired results are deleted when history is read or written.',[0,1,7,30],{0:'Up to 200 results',1:'24 hours',7:'7 days',30:'30 days'})
        page.append(label('Local Whisper keeps audio on your computer. Cloud engines send audio to the selected provider. AI writing sends text and preferences to its configured endpoint.','muted',True))

    def build_providers(self):
        page=self.pages['Providers'];self.provider_sections={}
        group=self.section(page,'Connect your speech service','Use the setup assistant to connect Sarvam or get started with local Whisper. Browser sign-in is handled on the provider website.')
        connect=Gtk.Button(label='Open setup assistant');connect.add_css_class('primary');connect.connect('clicked',lambda b:self.show_setup());self.row(group,'Guided connection','For everyday setup, you do not need to edit endpoint URLs.',connect)
        group=self.section(page,'ElevenLabs','Browser sign-in through the official ElevenLabs CLI. Credentials are managed by that helper, not copied into Bol settings.')
        self.eleven_status_label=label('Use Check connection to see whether you are signed in.','muted',True);margins(self.eleven_status_label,16);group.append(self.eleven_status_label)
        buttons=Gtk.FlowBox();buttons.set_selection_mode(Gtk.SelectionMode.NONE);buttons.set_max_children_per_line(2);buttons.set_column_spacing(8);buttons.set_row_spacing(8);margins(buttons,12)
        self.eleven_buttons=[]
        for title,action in [('Sign in with ElevenLabs','login'),('Check connection','status'),('Install sign-in helper','install'),('Disconnect ElevenLabs','logout')]:
            button=Gtk.Button(label=title);button.connect('clicked',lambda b,a=action:self.eleven_action(a));buttons.insert(button,-1);self.eleven_buttons.append(button)
        group.append(buttons)
        advanced=Gtk.Expander(label='Advanced provider settings');self.connection_details=advanced;advanced.set_expanded(self.settings.get('show_advanced',False));page.append(advanced)
        details=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18);details.set_margin_top(18);advanced.set_child(details);page=details
        group=self.section(page,'Sarvam credentials','Used for Sarvam speech recognition and Sarvam AI writing.')
        self.entry(group,'api_key','Sarvam API key','Your existing key is preserved.',True)
        self.provider_sections['sarvam']=group.get_parent()
        group=self.section(page,'Local whisper.cpp','Use an existing whisper-cli build and downloaded GGML model. No model downloads happen automatically.')
        self.entry(group,'whisper_binary','Whisper executable','Leave blank to auto-detect your existing installation.')
        self.entry(group,'whisper_model','Model file','The detected small.en model is English-only. Punjabi requires a multilingual model.')
        button=Gtk.Button(label='Detect installed Whisper');button.connect('clicked',self.detect_local)
        self.row(group,'Find local installation','Fill the paths from your existing Whisper setup.',button)
        self.provider_sections['local']=group.get_parent()
        group=self.section(page,'Compatible speech API','A multipart audio/transcriptions endpoint returning a JSON text field. Keys stay separate from Sarvam.')
        self.entry(group,'speech_api_url','Endpoint URL','For example: https://api.groq.com/openai/v1/audio/transcriptions')
        self.entry(group,'speech_api_model','Speech model','For example: whisper-large-v3-turbo')
        self.entry(group,'speech_api_key','API key','Leave blank only for a server that does not require authentication.',True)
        self.provider_sections['speech_api']=group.get_parent()
        group=self.section(page,'ElevenLabs speech model')
        self.entry(group,'elevenlabs_model','Model ID','Default: scribe_v2. Your ElevenLabs account must have speech-to-text access.')
        self.provider_sections['elevenlabs']=group.get_parent()
        group=self.section(page,'AI writing provider','Used for polish and voice editing, independently of speech recognition.')
        self.choice(group,'writing_provider','Writing engine','Select the API that should receive writing requests.',WRITING_PROVIDERS,{'sarvam':'Sarvam','compatible':'Compatible chat API'})
        self.widgets['writing_provider'].connect('notify::selected',lambda *args:self.update_provider_sections())
        group=self.section(page,'Compatible writing API','A JSON chat/completions endpoint. Use your cloud provider or a local compatible server.')
        self.entry(group,'writing_api_url','Endpoint URL','Enter the complete chat/completions URL. Localhost HTTP is supported.')
        self.entry(group,'writing_api_model','Writing model','Enter the model ID served by your endpoint.')
        self.entry(group,'writing_api_key','API key','Optional for a local server without authentication.',True)
        self.provider_sections['writing_api']=group.get_parent()
        group=self.section(page,'Local speech privacy')
        self.toggle(group,'local_speech_writing','AI writing with local speech','Allows local Whisper text to reach the chosen writing endpoint. Off keeps local dictation offline.')

    def update_provider_sections(self):
        if not hasattr(self,'provider_sections') or 'writing_provider' not in self.widgets:return
        speech=SPEECH_PROVIDERS[self.widgets['speech_provider'].get_selected()]
        writing=WRITING_PROVIDERS[self.widgets['writing_provider'].get_selected()]
        for name,visible in {'sarvam':speech=='sarvam' or writing=='sarvam','local':speech=='whispercpp','speech_api':speech=='compatible','writing_api':writing=='compatible','elevenlabs':speech=='elevenlabs'}.items():
            self.provider_sections[name].set_visible(visible)

    def eleven_action(self,action):
        from bol_elevenlabs import status,account_action
        for button in self.eleven_buttons:button.set_sensitive(False)
        self.eleven_status_label.set_text('Opening browser sign-in…' if action=='login' else 'Updating connection…')
        def process(value):self.eleven_login_process=value
        def worker():
            try:result=status() if action=='status' else account_action(action,process);error=None
            except Exception as exc:result=None;error=str(exc)
            GLib.idle_add(self.eleven_finished,result,error)
        threading.Thread(target=worker,daemon=True).start()

    def eleven_finished(self,result,error):
        if not self.alive:return False
        for button in self.eleven_buttons:button.set_sensitive(True)
        if error:self.eleven_status_label.set_text(error)
        elif result.get('logged_in'):self.eleven_status_label.set_text('Signed in. Choose ElevenLabs as the speech engine in Preferences, then save.')
        elif result.get('installed'):self.eleven_status_label.set_text('The helper is installed. Sign in with ElevenLabs to connect your account.')
        else:self.eleven_status_label.set_text('Install the official sign-in helper, then sign in with ElevenLabs.')
        return False

    def detect_local(self,*args):
        binary,model=detect_whisper()
        self.widgets['whisper_binary'].set_text(binary);self.widgets['whisper_model'].set_text(model)
        if not binary or not model:self.dialog('Whisper detection','Choose your whisper-cli and GGML model paths manually.')
        elif '.en.' in model:self.dialog('English model detected','Your model supports English only. Select English or automatic detection in General. Use a multilingual model for Punjabi.')

    def build_writing(self):
        page=self.pages['Writing'];group=self.section(page,'Dictation')
        self.toggle(group,'polish','Polish with AI','Remove fillers, resolve corrections, and format your words.')
        self.toggle(group,'review_edits','Review voice edits before inserting','Read or change the proposed edit, then approve or discard it.')
        group=self.section(page,'Your writing style','For example: British spelling, concise sentences, and preserve Punjabi.')
        self.editor(group,'writing_rules',self.settings.get('writing_rules',''))
        group=self.section(page,'App preferences','One exact app class => instruction per line. Example: Chatgpt => Preserve code identifiers.')
        self.editor(group,'profiles',format_pairs(self.settings.get('profiles',{})))
        button=Gtk.Button(label='Show open app classes');button.set_halign(Gtk.Align.START);button.connect('clicked',self.show_apps);page.append(button)

    def build_vocabulary(self):
        page=self.pages['Vocabulary'];group=self.section(page,'Recognition hints','One name or term per line. Up to 50 terms, 64 characters each.')
        self.editor(group,'vocabulary','\n'.join(self.settings.get('vocabulary',[])),150)
        group=self.section(page,'Remembered corrections','One heard phrase => preferred spelling per line.')
        self.editor(group,'corrections',format_pairs(self.settings.get('corrections',{})),150)

    def build_snippets(self):
        page=self.pages['Snippets'];group=self.section(page,'Spoken shortcuts','Say a trigger phrase on its own to insert its expansion. Use \\n for line breaks.')
        self.editor(group,'snippets',format_pairs(self.settings.get('snippets',{})),240)
        page.append(label('Example: my signature => Regards,\\nSarbjeet','muted',True))

    def build_history(self):
        page=self.pages['History']
        overview=Gtk.Box(spacing=12)
        self.history_summary=label('Your words, ready to use again.','muted');self.history_summary.set_hexpand(True);overview.append(self.history_summary)
        self.history_saving=label('','tag');overview.append(self.history_saving)
        settings_button=Gtk.Button(label='History settings');settings_button.add_css_class('quiet');settings_button.connect('clicked',lambda b:self.select('General'));overview.append(settings_button)
        page.append(overview)
        toolbar=Gtk.Box(spacing=8);toolbar.add_css_class('history-toolbar')
        self.history_search=Gtk.Entry();self.history_search.set_placeholder_text('Search your transcripts');self.history_search.set_hexpand(True)
        self.history_search.set_icon_from_paintable(Gtk.EntryIconPosition.PRIMARY,icon_paintable('search',16))
        self.history_search.set_icon_activatable(Gtk.EntryIconPosition.PRIMARY,False)
        self.history_search.connect('changed',self.history_search_changed);toolbar.append(self.history_search)
        for text,icon,callback in [('Refresh','refresh',lambda:self.refresh_history()),('Export matching history','export',lambda:self.export_results(True))]:
            button=Gtk.Button();button.set_child(svg_icon(icon,17));button.set_tooltip_text(text);button.add_css_class('quiet');button.connect('clicked',lambda b,fn=callback:self.action(fn));toolbar.append(button)
        page.append(toolbar)
        filters=Gtk.Box(spacing=5);first=None
        for title,kind in [('All','all'),('Dictation','dictate'),('Voice edit','edit')]:
            button=Gtk.ToggleButton(label=title);button.add_css_class('filter')
            if first:button.set_group(first)
            else:first=button;button.set_active(True)
            button.connect('toggled',lambda b,k=kind:self.history_filter_changed(k) if b.get_active() else None);filters.append(button)
        self.history_count=label('','muted');self.history_count.set_hexpand(True);self.history_count.set_xalign(1);filters.append(self.history_count);page.append(filters)
        self.history_feed=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);page.append(self.history_feed)
        self.history_empty=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);self.history_empty.add_css_class('history-empty');self.history_empty.set_halign(Gtk.Align.FILL)
        self.history_empty.append(svg_icon('history',28))
        self.history_empty_title=label('Your next idea starts here.','section-title');self.history_empty_title.set_halign(Gtk.Align.CENTER);self.history_empty.append(self.history_empty_title)
        self.history_empty_hint=label('Press your dictation shortcut to begin. Your latest result appears here even when saving is off.','muted',True);self.history_empty_hint.set_max_width_chars(48);self.history_empty_hint.set_justify(Gtk.Justification.CENTER);self.history_empty_hint.set_halign(Gtk.Align.CENTER);self.history_empty.append(self.history_empty_hint)
        page.append(self.history_empty)
        # Keep the existing editable preview buffer for export/correction workflows.
        scratch=Gtk.TextBuffer();self.buffers['result']=scratch
        bottom=Gtk.Box(spacing=8)
        self.history_privacy=label('Stored on this device. Audio is not retained.','muted',True);self.history_privacy.set_hexpand(True);bottom.append(self.history_privacy)
        clear=Gtk.Button(label='Clear saved history');clear.add_css_class('quiet');clear.add_css_class('destructive');clear.connect('clicked',lambda b:self.clear_history());bottom.append(clear);page.append(bottom)

    def history_search_changed(self,*args):
        source=getattr(self,'history_search_timer',None)
        if source:GLib.source_remove(source)
        def search():
            self.history_search_timer=None
            if self.alive:self.refresh_history(False)
            return False
        self.history_search_timer=GLib.timeout_add(180,search)

    def history_filter_changed(self,kind):
        self.history_kind=kind
        self.render_history()

    def render_history(self):
        if not hasattr(self,'history_feed'):return
        while child:=self.history_feed.get_first_child():self.history_feed.remove(child)
        query=self.history_search.get_text()
        self.history_rows=filter_history(self.history_all,query,self.history_kind)
        saved=len(self.history_all);words=sum(len(row['result'].split()) for row in self.history_all)
        self.history_summary.set_text(f'{saved:,} saved transcripts  ·  {words:,} words')
        saving=bool(self.core.config().get('history_enabled'))
        self.history_saving.set_text('Saving on' if saving else 'Saving off')
        self.history_saving.remove_css_class('saving-off' if saving else 'saving-on')
        self.history_saving.add_css_class('saving-on' if saving else 'saving-off')
        self.history_count.set_text(f'{len(self.history_rows)} result'+('' if len(self.history_rows)==1 else 's'))
        latest=self.history_latest
        memory_row=None
        if latest.get('text'):
            is_saved=any(row['result']==latest['text'] and (not latest.get('app') or row.get('app','')==latest.get('app','')) for row in self.history_all[:1])
            if not is_saved:
                memory_row={'id':None,'result':latest['text'],'original':latest.get('original',''),'app':latest.get('app') or 'This session','mode':latest.get('mode','session'),'created':latest.get('created','')}
                if not filter_history([memory_row],query,self.history_kind):memory_row=None
        count=len(self.history_rows)+int(memory_row is not None)
        self.history_count.set_text(f'{count} result'+('' if count==1 else 's'))
        if memory_row:
            self.history_feed.append(label('Latest result','date-heading'));self.history_feed.append(self.transcript_card(memory_row,True))
        previous_day=None
        for row in self.history_rows:
            day,_=history_date(row['created'])
            if day!=previous_day:self.history_feed.append(label(day,'date-heading'));previous_day=day
            self.history_feed.append(self.transcript_card(row))
        empty=not self.history_rows and memory_row is None
        self.history_empty.set_visible(empty)
        self.history_empty_title.set_text('No matching transcripts' if query.strip() or self.history_kind!='all' else 'Your next idea starts here.')
        self.history_empty_hint.set_text('Try a different search or select All.' if query.strip() or self.history_kind!='all' else 'Press your dictation shortcut to begin. Your latest result appears here even when saving is off.')

    def transcript_card(self,row,memory=False):
        card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);card.add_css_class('transcript')
        top=Gtk.Box(spacing=9)
        app=label(row.get('app') or 'Unknown app','transcript-meta');app.set_ellipsize(3);app.set_hexpand(True);top.append(app)
        kind=label({'edit':'Voice edit','dictate':'Dictation'}.get(row.get('mode'),'Session result'),'tag')
        kind.add_css_class('tag-edit' if row.get('mode')=='edit' else 'tag-dictation');top.append(kind)
        if memory:
            unsaved=label('Not saved','tag');unsaved.add_css_class('tag-unsaved');top.append(unsaved)
        _,clock=history_date(row.get('created',''))
        if clock:top.append(label(clock,'transcript-meta'))
        card.append(top)
        text=label(row['result'],'transcript-text',True);text.set_lines(5);text.set_ellipsize(3);text.set_max_width_chars(80);card.append(text)
        bottom=Gtk.Box(spacing=8)
        count=label(f'{len(row["result"].split())} words','transcript-meta');count.set_hexpand(True);bottom.append(count)
        speak=action_button('To audio','audio');speak.add_css_class('quiet');speak.connect('clicked',lambda b:self.text_to_audio(row['result']));bottom.append(speak)
        details=Gtk.Button(label='View transcript');details.add_css_class('quiet');details.connect('clicked',lambda b:self.transcript_details(row));bottom.append(details)
        copy=action_button('Copy','copy');copy.add_css_class('quiet');copy.connect('clicked',lambda b:self.copy_history_row(row));bottom.append(copy)
        card.append(bottom);return card

    def copy_history_row(self,row):
        self.core.copy_text(row['result']);self.status.set_text('Transcript copied')

    def transcript_details(self,row):
        dialog=Gtk.Window(title='Transcript',transient_for=self.window,modal=True);dialog.add_css_class('bol');dialog.set_default_size(660,610)
        layout=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18);margins(layout,24);dialog.set_child(layout)
        heading=Gtk.Box(spacing=12);title=label('Transcript','section-title');title.set_hexpand(True);heading.append(title)
        close=Gtk.Button(label='Close');close.connect('clicked',lambda b:dialog.close());heading.append(close);layout.append(heading)
        day,clock=history_date(row.get('created',''))
        layout.append(label(f'{row.get("app") or "This session"}  ·  {day} {clock}','muted'))
        switcher=Gtk.Box(spacing=5);final=Gtk.ToggleButton(label='Result');final.set_active(True);original=Gtk.ToggleButton(label='Instruction' if row.get('mode')=='edit' else 'Original');original.set_group(final)
        for button in [final,original]:button.add_css_class('filter');switcher.append(button)
        layout.append(switcher)
        scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);scroll.add_css_class('editor-frame')
        view=Gtk.TextView();view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        for side in ['top','bottom','left','right']:getattr(view,'set_'+side+'_margin')(16)
        buffer=view.get_buffer();buffer.set_text(row['result']);scroll.set_child(view);layout.append(scroll)
        def version(button):
            if button.get_active():buffer.set_text(row.get('original','') if button==original else row['result'])
        final.connect('toggled',version);original.connect('toggled',version)
        actions=Gtk.Box(spacing=8)
        def copy_preview(button):
            text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True);self.core.copy_text(text);self.status.set_text('Transcript copied')
        def export_preview(button):
            self.buffers['result'].set_text(buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True));self.export_results(False,dialog)
        copy=action_button('Copy text','copy');copy.add_css_class('primary');copy.connect('clicked',copy_preview);actions.append(copy)
        export=action_button('Export text','export');export.connect('clicked',export_preview);actions.append(export)
        remember=Gtk.Button(label='Remember correction');remember.connect('clicked',lambda b:self.remember(dialog));actions.append(remember)
        layout.append(actions);layout.append(label('Edits here affect copying and export, not the saved transcript.','muted',True))
        dialog.present()

    def build_shortcuts(self):
        page=self.pages['Shortcuts'];group=self.section(page,'Keyboard')
        for key,title,hint in [('record_key','Dictate','Start and finish recording.'),('edit_key','Voice edit','Rewrite selected text or draft from an instruction.'),('cancel_key','Cancel','Stop recording and discard the pending result.')]:
            self.entry(group,key,title,hint)
        group=self.section(page,'Behavior')
        self.toggle(group,'hold_to_talk','Hold to talk','Hold the dictation key to record. Release it to finish.')
        page.append(label('Use F1–F12, optionally with CTRL +, ALT +, SHIFT + or SUPER +. Saving checks for conflicts and applies shortcuts to Hyprland.','muted',True))
        page.append(label('Voice edit: select text, press your edit key, speak an instruction, then press it again. Keep the same app focused while Bol processes it.','muted',True))

    def text(self,key):
        buffer=self.buffers[key];return buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)

    def select(self,title):
        if title not in self.pages:title='History'
        self.stack.set_visible_child_name(title)
        for name,button in self.nav.items():
            if name==title:button.add_css_class('selected')
            else:button.remove_css_class('selected')
        self.profile_popover.popdown()
        if title=='Providers':self.connection_details.set_expanded(self.settings.get('show_advanced',False))
        if title=='History':self.action(self.refresh_history)

    def save(self,*args):
        try:
            data=self.core.config()
            for key,widget in self.widgets.items():
                if key in self.choices:data[key]=self.choices[key][widget.get_selected()]
                elif isinstance(widget,Gtk.Switch):data[key]=widget.get_active()
                elif isinstance(widget,Gtk.SpinButton):data[key]=widget.get_value_as_int()
                else:data[key]=widget.get_text().strip()
            terms=[v.strip() for v in self.text('vocabulary').splitlines() if v.strip()]
            if len(terms)>50 or any(len(v)>64 for v in terms):raise ValueError('Use up to 50 vocabulary terms, each at most 64 characters.')
            if data.get('speech_provider') in ['whispercpp','compatible']:validate_speech(data)
            data['vocabulary']=terms;data['writing_rules']=self.text('writing_rules').strip()
            for key in ['profiles','corrections','snippets']:data[key]=parse_pairs(self.text(key))
            if any(data.get(k)!=self.settings.get(k) for k in ['record_key','cancel_key','edit_key','hold_to_talk']):apply_shortcuts(data)
            self.core.save_config(data);self.settings=data
            self.update_profile_identity()
            for key,widget in self.key_labels.items():widget.set_text(data[key])
            self.save_note.set_text('All changes saved');self.save_button.set_sensitive(False)
        except Exception as error:self.dialog('Could not save',str(error))

    def refresh_history(self, load_latest=True):
        self.history_request+=1
        token=self.history_request
        def worker():
            try:
                rows=History(self.core.CONFIG,self.core.config().get('history_retention_days',0)).list() if (self.core.CONFIG/'history.sqlite3').exists() else []
                latest=self.core.request('result') if load_latest else None
                GLib.idle_add(self.history_loaded,token,rows,latest,None)
            except Exception as error:GLib.idle_add(self.history_loaded,token,[],None,str(error))
        threading.Thread(target=worker,daemon=True).start()

    def history_loaded(self,token,rows,latest,error):
        if not self.alive or token!=self.history_request:return False
        if error:self.status.set_text(error);return False
        self.history_all=rows
        if latest is not None:self.history_latest=latest
        self.render_history()
        return False

    def cancel_recording(self,*args):
        self.cancel_button.set_sensitive(False)
        def worker():
            try:
                self.core.request('cancel');message='Recording cancelled'
            except Exception as error:message=str(error)
            GLib.idle_add(self.cancel_finished,message)
        threading.Thread(target=worker,daemon=True).start()

    def cancel_finished(self,message):
        if self.alive:
            self.cancel_button.set_sensitive(True);self.status.set_text(message)
        return False

    def export_results(self, history=False, parent=None):
        if history:
            data=filter_history(History(self.core.CONFIG,self.core.config().get('history_retention_days',0)).list(),self.history_search.get_text(),self.history_kind) if (self.core.CONFIG/'history.sqlite3').exists() else []
            if not data:
                self.dialog('Nothing to export','No saved history matches the current search.');return
            payload=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
        else:
            payload=self.text('result')
            if not payload.strip():
                self.dialog('Nothing to export','Dictate something or select a saved result first.');return
        chooser=Gtk.FileChooserNative.new('Export history' if history else 'Export text',parent or self.window,Gtk.FileChooserAction.SAVE,'Export','Cancel')
        chooser.set_current_name('bol-history.json' if history else 'bol-result.txt')
        file_filter=Gtk.FileFilter();file_filter.set_name('JSON' if history else 'Text');file_filter.add_pattern('*.json' if history else '*.txt');chooser.add_filter(file_filter)
        def response(dialog,result):
            if result==Gtk.ResponseType.ACCEPT:
                file=dialog.get_file();path=file.get_path() if file else None
                if not path:self.dialog('Export unavailable','Choose a local folder.')
                else:
                    try:
                        # Saved transcripts can contain personal text: create exports privately.
                        import os
                        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                        with os.fdopen(fd,'w') as output:output.write(payload)
                        self.status.set_text('Export saved')
                    except Exception as error:self.dialog('Could not export',str(error))
            dialog.destroy()
        chooser.connect('response',response);chooser.show()

    def test_microphone(self,*args):
        import subprocess
        import signal
        import tempfile
        if self.core.request('status').get('state')!='Ready':
            self.dialog('Microphone is busy','Finish or cancel your current recording first.');return
        target=self.widgets['microphone'].get_text().strip()
        self.mic_test_button.set_sensitive(False);self.status.set_text('Microphone check: speak for three seconds')
        def worker():
            process=None
            try:
                with tempfile.TemporaryDirectory(prefix='bol-mic-') as folder:
                    path=Path(folder)/'test.wav'
                    command=['pw-record','--rate=16000','--channels=1','--format=s16']
                    if target:command+=['--target',target]
                    process=subprocess.Popen(command+[str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    self.mic_test_process=process
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.send_signal(signal.SIGINT)
                        try:process.wait(timeout=2)
                        except subprocess.TimeoutExpired:process.kill();process.wait()
                    result=audio_level(path)
                    verdict='The signal is clipping. Reduce your microphone gain.' if result['clipping'] else 'The signal is very quiet. Move closer or raise your microphone gain.' if result['quiet'] else 'Your microphone is receiving audio at a usable level.'
                    message=f"{verdict}\n\nPeak: {result['peak_db']} dBFS\nAverage: {result['rms_db']} dBFS\n\nThe sample was deleted. Nothing was uploaded."
            except Exception as error:message='Could not test the microphone: '+str(error)
            finally:
                if process and process.poll() is None:process.kill();process.wait()
                self.mic_test_process=None
            GLib.idle_add(self.mic_test_finished,message)
        threading.Thread(target=worker,daemon=True).start()

    def mic_test_finished(self,message):
        if self.alive:
            self.mic_test_button.set_sensitive(True);self.status.set_text('Microphone check finished')
            self.dialog('Microphone check',message)
        return False

    def dialog(self,title,message):
        dialog=Gtk.MessageDialog(transient_for=self.window,modal=True,text=title,secondary_text=message,buttons=Gtk.ButtonsType.CLOSE)
        dialog.connect('response',lambda d,r:d.destroy());dialog.present()

    def clear_history(self):
        dialog=Gtk.MessageDialog(transient_for=self.window,modal=True,text='Clear saved history?',secondary_text='Saved transcripts will be deleted from this computer.',buttons=Gtk.ButtonsType.CANCEL)
        dialog.add_button('Clear history',Gtk.ResponseType.ACCEPT)
        def response(d,value):
            if value==Gtk.ResponseType.ACCEPT:
                if (self.core.CONFIG/'history.sqlite3').exists():History(self.core.CONFIG,self.core.config().get('history_retention_days',0)).clear()
                self.refresh_history()
            d.destroy()
        dialog.connect('response',response);dialog.present()

    def remember(self,parent=None):
        dialog=Gtk.Dialog(title='Remember correction',transient_for=parent or self.window,modal=True)
        dialog.add_button('Cancel',Gtk.ResponseType.CANCEL);dialog.add_button('Remember',Gtk.ResponseType.ACCEPT)
        box=dialog.get_content_area();box.set_spacing(10);margins(box,22)
        box.append(label('Heard phrase'));old=Gtk.Entry();box.append(old)
        box.append(label('Preferred spelling'));new=Gtk.Entry();box.append(new)
        def response(d,value):
            if value==Gtk.ResponseType.ACCEPT and old.get_text().strip() and new.get_text().strip():
                pairs=parse_pairs(self.text('corrections'));pairs[old.get_text().strip()]=new.get_text().strip()
                self.buffers['corrections'].set_text(format_pairs(pairs));self.save_note.set_text('Correction added — save changes to remember it')
            d.destroy()
        dialog.connect('response',response);dialog.present()

    def show_apps(self,*args):
        import subprocess
        try:
            classes=sorted({c.get('class','') for c in json.loads(subprocess.check_output(['hyprctl','-j','clients'],text=True,timeout=3)) if c.get('class')})
            self.dialog('Open app classes','\n'.join(classes) or 'No apps found')
        except Exception as error:self.dialog('Could not list apps',str(error))

    def action(self,fn):
        try:fn()
        except Exception as error:self.dialog('Bol',str(error))

    def poll(self):
        if not self.alive:return False
        # Keep socket I/O out of GTK's UI thread.
        if not getattr(self,'polling',False):
            self.polling=True
            def worker():
                busy=False;review=False
                try:
                    state=self.core.request('status')
                    busy=state.get('state') in ['Recording','Transcribing','Writing','Review']
                    review=bool(state.get('has_pending_edit'))
                    text=state.get('error') or (f'Recording · {state["seconds"]:.0f}s' if state['state']=='Recording' else state.get('outcome') or state['state'])
                except Exception as error:text=str(error)
                GLib.idle_add(self.status_update,text,busy,review)
            threading.Thread(target=worker,daemon=True).start()
        return True

    def status_update(self,text,busy=False,review=False):
        self.polling=False
        if self.alive:
            if self.status.get_text()!=text:
                self.status.set_text(text);self.status.set_tooltip_text(text)
            if self.cancel_button.get_visible()!=busy:self.cancel_button.set_visible(busy)
            if self.review_button.get_visible()!=review:self.review_button.set_visible(review)
        return False

    def review_pending(self,*args):
        self.review_button.set_sensitive(False)
        def worker():
            try:result=self.core.request('review')
            except Exception as error:result={'error':str(error)}
            GLib.idle_add(self.show_edit_review,result)
        threading.Thread(target=worker,daemon=True).start()

    def show_edit_review(self,result):
        if not self.alive:return False
        self.review_button.set_sensitive(True)
        if result.get('error'):self.dialog('Review unavailable',result['error']);return False
        dialog=Gtk.Window(title='Review voice edit',transient_for=self.window,modal=True);dialog.add_css_class('bol');dialog.set_default_size(700,650)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);margins(box,24);dialog.set_child(box)
        box.append(label('Review your edit','page-title'))
        box.append(label('Nothing is inserted until you approve. Closing this window keeps the edit pending.','muted',True))
        instruction=label('Instruction: '+result.get('original',''),'muted',True);instruction.set_max_width_chars(75);instruction.set_lines(3);instruction.set_ellipsize(3);box.append(instruction)
        if result.get('selection'):
            original=Gtk.Expander(label='Selected text')
            scroll=Gtk.ScrolledWindow();scroll.set_min_content_height(100);scroll.set_max_content_height(130)
            source=Gtk.TextView();source.set_editable(False);source.set_cursor_visible(False);source.set_wrap_mode(Gtk.WrapMode.WORD_CHAR);source.get_buffer().set_text(result['selection']);scroll.set_child(source);original.set_child(scroll);box.append(original)
        box.append(label('Proposed result','section-title'))
        scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);scroll.set_min_content_height(220);scroll.add_css_class('editor-frame')
        proposal=Gtk.TextView();proposal.set_wrap_mode(Gtk.WrapMode.WORD_CHAR);proposal.get_buffer().set_text(result['text']);scroll.set_child(proposal);box.append(scroll)
        controls=Gtk.Box(spacing=10)
        discard=Gtk.Button(label='Discard');controls.append(discard)
        copy=action_button('Copy only','copy');controls.append(copy)
        space=Gtk.Box();space.set_hexpand(True);controls.append(space)
        approve=Gtk.Button(label='Approve and insert');approve.add_css_class('primary');controls.append(approve)
        def submit(command):
            text=proposal.get_buffer().get_text(proposal.get_buffer().get_start_iter(),proposal.get_buffer().get_end_iter(),True)
            if command=='copy':self.core.copy_text(text);self.status.set_text('Edit copied');return
            approve.set_sensitive(False);discard.set_sensitive(False)
            payload={'command':'accept-edit','generation':result['generation'],'text':text} if command=='approve' else 'cancel'
            # Close before asking the daemon to focus the original target window.
            dialog.close()
            def worker():
                try:
                    response=self.core.request(payload)
                    message=response.get('error') or response.get('outcome') or 'Edit discarded'
                except Exception as error:message=str(error)
                GLib.idle_add(self.cancel_finished,message)
            threading.Thread(target=worker,daemon=True).start()
        discard.connect('clicked',lambda b:submit('discard'));copy.connect('clicked',lambda b:self.action(lambda:submit('copy')));approve.connect('clicked',lambda b:submit('approve'))
        box.append(controls);dialog.present();return False

    def on_close(self,*args):
        self.alive=False
        ICON_IMAGES.clear()
        self.audio_generation+=1;self.audio_style_generation+=1;self.stop_audio()
        if self.audio_directory:self.audio_directory.cleanup()
        login=getattr(self,'eleven_login_process',None)
        if login and login.poll() is None:login.terminate()
        process=getattr(self,'mic_test_process',None)
        if process and process.poll() is None:process.terminate()
        return False


def settings_window(core):
    Workspace(core).app.run([])
