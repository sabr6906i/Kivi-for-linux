"""Native GTK 4 settings workspace for Bol."""
import json
import threading
from functools import lru_cache
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from bol_features import LANGUAGES, MODES, History, audio_level, history_date, filter_history
from bol_providers import SPEECH_PROVIDERS, WRITING_PROVIDERS, detect_whisper, validate_speech
from bol_ui import parse_pairs, format_pairs, apply_shortcuts

CSS = b'''
window.bol { background: #090909; color: #ececec; font-family: 'Noto Sans', sans-serif; font-size: 13px; }
.bol headerbar { background: #090909; box-shadow: none; border-bottom: 1px solid #242424; min-height: 40px; }
.bol .sidebar { background: #0c0c0c; border-right: 1px solid #242424; }
.bol .brand { font-size: 18px; font-weight: 650; color: #f5f5f5; }
.bol .nav-heading { font-size: 11px; color: #858585; font-weight: 500; }
.bol .nav-button { background: transparent; color: #aaa; border: none; box-shadow: none; border-radius: 7px; padding: 10px 12px; font-weight: 400; transition: background-color 120ms ease-in-out, color 120ms ease-in-out; }
.bol .nav-button:hover { background: #242424; color: #eee; }
.bol .nav-button.selected { background: #242424; color: #f5f5f5; }
.bol .page-title { font-size: 30px; font-weight: 600; letter-spacing: -0.6px; }
.bol .muted { color: #929292; font-size: 12px; }
.bol .section-title { color: #ddd; font-size: 13px; font-weight: 600; }
.bol .group { background: #141414; border: 1px solid #292929; border-radius: 10px; }
.bol .row-title { font-weight: 500; color: #e4e4e4; }
.bol .row-hint { font-size: 11px; color: #999; }
.bol separator { background: #292929; min-height: 1px; }
.bol entry, .bol passwordentry, .bol dropdown > button, .bol spinbutton { background: #191919; color: #eee; border: 1px solid #333333; border-radius: 8px; box-shadow: none; min-height: 34px; }
.bol entry:focus-within, .bol passwordentry:focus-within { border-color: #929292; outline: none; }
.bol passwordentry entry, .bol spinbutton entry { border: none; background: transparent; }
.bol button { background: #242424; color: #ddd; border: 1px solid #333; border-radius: 8px; box-shadow: none; padding: 8px 12px; transition: background-color 120ms ease-in-out, border-color 120ms ease-in-out; }
.bol button:hover { background: #303030; }
.bol button.primary { background: #ededed; color: #171717; border-color: #ededed; font-weight: 600; }
.bol button.primary:hover { background: white; }
.bol button.primary:disabled { background: #222222; color: #858585; border-color: #222222; }
.bol switch { background: #505050; border: none; min-width: 38px; min-height: 22px; }
.bol switch:checked { background: #e0e0e0; }
.bol switch slider { background: #bdbdbd; border: none; box-shadow: none; }
.bol switch:checked slider { background: #252525; }
.bol textview, .bol textview text { background: #141414; color: #e4e4e4; }
.bol textview { border-radius: 8px; padding: 12px; font-size: 13px; }
.bol .editor-frame { border: 1px solid #424242; border-radius: 9px; }
.bol .footer { background: #090909; border-top: 1px solid #252525; }
.bol .status { color: #bdbdbd; font-size: 11px; }
.bol .key { background: #292929; color: #b8b8b8; border: 1px solid #303030; border-radius: 5px; font-size: 10px; padding: 3px 6px; }
.bol .empty { color: #868686; padding: 25px; }
.bol listbox { background: transparent; }
.bol listbox row { padding: 10px; border-radius: 7px; }
.bol listbox row:selected { background: #303030; }
.bol popover contents { background: #242424; color: #eee; border: 1px solid #353535; border-radius: 10px; }
.bol .history-toolbar { background: #111111; border: 1px solid #292929; border-radius: 10px; padding: 8px; }
.bol .filter { background: transparent; border-color: transparent; color: #939393; padding: 7px 12px; }
.bol button.filter:checked label { color: #f3f3f3; }
.bol .filter:checked { background: #2a2a2a; color: #f3f3f3; border-color: #3a3a3a; }
.bol .transcript { background: #141414; border: 1px solid #292929; border-radius: 12px; padding: 19px; }
.bol .transcript:hover { border-color: #464646; background: #181818; }
.bol .transcript-text { font-size: 14px; color: #e4e4e4; line-height: 1.6; }
.bol .transcript-meta { color: #8c8c8c; font-size: 11px; }
.bol .date-heading { color: #a0a0a0; font-size: 11px; font-weight: 600; margin-top: 12px; margin-bottom: 2px; }
.bol .tag { background: #232323; border: 1px solid #333333; border-radius: 5px; padding: 3px 7px; color: #aaa; font-size: 10px; }
.bol .quiet { background: transparent; border-color: transparent; color: #a0a0a0; padding: 6px 8px; }
.bol .quiet:hover { background: #292929; border-color: #3b3b3b; color: white; }
.bol .history-empty { background: #101010; border: 1px dashed #333333; border-radius: 12px; padding: 42px; }
.bol scrollbar slider { background: #515151; min-width: 5px; border-radius: 4px; }
'''

LANGUAGE_NAMES = dict(zip(LANGUAGES, ['Detect automatically','English','Hindi','Punjabi','Bengali','Kannada','Malayalam','Marathi','Odia','Tamil','Telugu','Gujarati','Assamese','Urdu','Nepali','Konkani','Sanskrit','Sindhi','Kashmiri','Dogri','Bodo','Manipuri','Maithili','Santali']))
MODE_NAMES = dict(zip(MODES, ['Original language','Mixed language & script','Roman script','Translate to English','Word for word']))
PAGES = [
    ('General','general','Connection, language, and recording preferences.'),
    ('Providers','providers','Choose local models and connect speech or writing APIs.'),
    ('Writing','writing','Writing preferences and application-specific styles.'),
    ('Vocabulary','vocabulary','Recognition hints and preferred spellings.'),
    ('Snippets','snippets','Expand a spoken phrase into reusable text.'),
    ('History','history','Review and recover your recent results.'),
    ('Shortcuts','shortcuts','Keyboard shortcuts and recording controls.'),
]


ICON_DIR = Path(__file__).resolve().parent / 'icons'


@lru_cache(maxsize=48)
def icon_paintable(name, size):
    file = Gio.File.new_for_path(str(ICON_DIR / (name + '.svg')))
    return Gtk.IconPaintable.new_for_file(file, size, 1)


def svg_icon(name, size=18):
    paintable = icon_paintable(name, size)
    image = Gtk.Image.new_from_paintable(paintable)
    image.set_pixel_size(size)
    return image


def action_button(title, icon_name):
    button = Gtk.Button()
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


class Workspace:
    def __init__(self, core):
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
        self.app=Gtk.Application(application_id='io.github.bol.Workspace', flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.app.connect('activate', self.activate)

    def changed(self,*args):
        if not self.loading:
            self.save_note.set_text('Unsaved changes')
            self.save_button.set_sensitive(True)

    def activate(self,app):
        provider=Gtk.CssProvider(); provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.window=Gtk.ApplicationWindow(application=app,title='Bol')
        self.window.add_css_class('bol'); self.window.set_default_size(1120,800)
        self.window.set_size_request(900,620)
        self.window.connect('close-request',self.on_close)
        header=Gtk.HeaderBar();header.set_title_widget(label('Bol','section-title'));self.window.set_titlebar(header)
        layout=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.window.set_child(layout)
        side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
        side.add_css_class('sidebar');side.set_size_request(224,-1);side.set_hexpand(False);layout.append(side)
        brand=Gtk.Box(spacing=10);margins(brand,22)
        icon=svg_icon('brand',24)
        brand.append(icon);brand.append(label('Bol','brand'));side.append(brand)
        navtitle=label('Workspace','nav-heading');navtitle.set_margin_start(22);navtitle.set_margin_top(9);navtitle.set_margin_bottom(8);side.append(navtitle)
        self.nav={}
        for title,icon_name,description in PAGES:
            button=Gtk.Button();button.add_css_class('nav-button');button.set_margin_start(10);button.set_margin_end(10)
            row=Gtk.Box(spacing=12);image=svg_icon(icon_name,18)
            row.append(image);row.append(label(title));button.set_child(row)
            button.connect('clicked',lambda b,name=title:self.select(name));side.append(button);self.nav[title]=button
        spacer=Gtk.Box();spacer.set_vexpand(True);side.append(spacer)
        quick=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);margins(quick,22)
        quick.append(label('Quick access','nav-heading'));self.key_labels={}
        for key,title in [('record_key','Dictate'),('edit_key','Voice edit'),('cancel_key','Cancel')]:
            row=Gtk.Box();name=label(title,'muted');name.set_hexpand(True);row.append(name)
            value=label(self.settings.get(key,''),'key');row.append(value);self.key_labels[key]=value;quick.append(row)
        side.append(quick)
        powered=label('Voice workspace for Linux','muted');margins(powered,22);side.append(powered)
        main=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);main.set_hexpand(True);layout.append(main)
        self.stack=Gtk.Stack();self.stack.set_vexpand(True);self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE);self.stack.set_transition_duration(120);main.append(self.stack)
        self.pages={}
        for title,icon_name,description in PAGES:
            scroller=Gtk.ScrolledWindow();scroller.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
            page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20);margins(page,42);scroller.set_child(page)
            heading=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);heading.set_margin_bottom(9)
            heading.append(label(title,'page-title'));heading.append(label(description,'muted',True));page.append(heading)
            self.stack.add_named(scroller,title);self.pages[title]=page
        footer=Gtk.Box(spacing=12);footer.add_css_class('footer');margins(footer,0)
        inner=Gtk.Box(spacing=12);margins(inner,18);inner.set_hexpand(True);footer.append(inner)
        self.save_note=label('All changes saved','muted');self.save_note.set_hexpand(True);inner.append(self.save_note)
        self.status=label('Ready','status');self.status.set_ellipsize(3);self.status.set_max_width_chars(28);inner.append(self.status)
        self.review_button=Gtk.Button(label='Review edit');self.review_button.add_css_class('primary');self.review_button.set_visible(False);self.review_button.connect('clicked',self.review_pending);inner.append(self.review_button)
        self.cancel_button=action_button('Cancel recording','cancel');cancel=self.cancel_button;cancel.set_visible(False);cancel.connect('clicked',self.cancel_recording);inner.append(cancel)
        self.save_button=Gtk.Button(label='Save changes');self.save_button.add_css_class('primary');self.save_button.set_sensitive(False);self.save_button.connect('clicked',self.save);inner.append(self.save_button)
        main.append(footer)
        self.build_general();self.build_providers();self.build_writing();self.build_vocabulary();self.build_snippets();self.build_history();self.build_shortcuts()
        self.update_provider_sections();self.loading=False;self.select('General');self.window.present()
        GLib.timeout_add(800,self.poll)

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
        widget=Gtk.DropDown.new_from_strings([names.get(v,v) for v in values]);widget.set_size_request(245,-1)
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
        if key!='result':buffer.connect('changed',self.changed)
        self.buffers[key]=buffer;scroller.set_child(view);group.append(scroller);return buffer

    def build_general(self):
        page=self.pages['General'];group=self.section(page,'Speech recognition')
        self.choice(group,'speech_provider','Speech engine','Configure keys and model paths in Providers.',SPEECH_PROVIDERS,{'sarvam':'Sarvam cloud','whispercpp':'Local whisper.cpp','compatible':'Compatible speech API'})
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
        for name,visible in {'sarvam':speech=='sarvam' or writing=='sarvam','local':speech=='whispercpp','speech_api':speech=='compatible','writing_api':writing=='compatible'}.items():
            self.provider_sections[name].set_visible(visible)

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
        clear=Gtk.Button(label='Clear saved history');clear.add_css_class('quiet');clear.connect('clicked',lambda b:self.clear_history());bottom.append(clear);page.append(bottom)

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
        self.history_saving.set_text('Saving on' if self.core.config().get('history_enabled') else 'Saving off')
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
        top.append(label({'edit':'Voice edit','dictate':'Dictation'}.get(row.get('mode'),'Session result'),'tag'))
        if memory:top.append(label('Not saved','tag'))
        _,clock=history_date(row.get('created',''))
        if clock:top.append(label(clock,'transcript-meta'))
        card.append(top)
        text=label(row['result'],'transcript-text',True);text.set_lines(5);text.set_ellipsize(3);text.set_max_width_chars(80);card.append(text)
        bottom=Gtk.Box(spacing=8)
        count=label(f'{len(row["result"].split())} words','transcript-meta');count.set_hexpand(True);bottom.append(count)
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
        self.stack.set_visible_child_name(title)
        for name,button in self.nav.items():
            if name==title:button.add_css_class('selected')
            else:button.remove_css_class('selected')
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
        process=getattr(self,'mic_test_process',None)
        if process and process.poll() is None:process.terminate()
        return False


def settings_window(core):
    Workspace(core).app.run([])
