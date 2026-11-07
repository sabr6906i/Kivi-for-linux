"""Native GTK 4 settings workspace for Bol."""
import json
import threading
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from bol_features import LANGUAGES, MODES, History, audio_level
from bol_ui import parse_pairs, format_pairs, apply_shortcuts

CSS = b'''
window.bol { background: #202022; color: #ececec; font-family: 'Noto Sans', sans-serif; font-size: 13px; }
.bol headerbar { background: #202022; box-shadow: none; border-bottom: 1px solid #303030; min-height: 40px; }
.bol .sidebar { background: #18181a; border-right: 1px solid #303030; }
.bol .brand { font-size: 18px; font-weight: 650; color: #f5f5f5; }
.bol .nav-heading { font-size: 11px; color: #858585; font-weight: 500; }
.bol .nav-button { background: transparent; color: #aaa; border: none; box-shadow: none; border-radius: 7px; padding: 10px 12px; font-weight: 400; }
.bol .nav-button:hover { background: #242424; color: #eee; }
.bol .nav-button.selected { background: #303030; color: #f5f5f5; }
.bol .page-title { font-size: 30px; font-weight: 600; letter-spacing: -0.6px; }
.bol .muted { color: #929292; font-size: 12px; }
.bol .section-title { color: #ddd; font-size: 13px; font-weight: 600; }
.bol .group { background: #262626; border: 1px solid #353537; border-radius: 10px; }
.bol .row-title { font-weight: 500; color: #e4e4e4; }
.bol .row-hint { font-size: 11px; color: #999; }
.bol separator { background: #373737; min-height: 1px; }
.bol entry, .bol passwordentry, .bol dropdown > button, .bol spinbutton { background: #2b2b2e; color: #eee; border: 1px solid #414144; border-radius: 8px; box-shadow: none; min-height: 34px; }
.bol entry:focus-within, .bol passwordentry:focus-within { border-color: #929292; outline: none; }
.bol passwordentry entry, .bol spinbutton entry { border: none; background: transparent; }
.bol button { background: #303030; color: #ddd; border: 1px solid #444; border-radius: 8px; box-shadow: none; padding: 8px 12px; }
.bol button:hover { background: #3a3a3a; }
.bol button.primary { background: #ededed; color: #171717; border-color: #ededed; font-weight: 600; }
.bol button.primary:hover { background: white; }
.bol button.primary:disabled { background: #393939; color: #858585; border-color: #393939; }
.bol switch { background: #505050; border: none; min-width: 38px; min-height: 22px; }
.bol switch:checked { background: #e0e0e0; }
.bol switch slider { background: #bdbdbd; border: none; box-shadow: none; }
.bol switch:checked slider { background: #252525; }
.bol textview, .bol textview text { background: #262626; color: #e4e4e4; }
.bol textview { border-radius: 8px; padding: 12px; font-size: 13px; }
.bol .editor-frame { border: 1px solid #424242; border-radius: 9px; }
.bol .footer { background: #202022; border-top: 1px solid #343434; }
.bol .status { color: #bdbdbd; font-size: 11px; }
.bol .key { background: #292929; color: #b8b8b8; border: 1px solid #3b3b3b; border-radius: 5px; font-size: 10px; padding: 3px 6px; }
.bol .empty { color: #868686; padding: 25px; }
.bol listbox { background: transparent; }
.bol listbox row { padding: 10px; border-radius: 7px; }
.bol listbox row:selected { background: #3b3b3b; }
.bol popover contents { background: #303030; color: #eee; border: 1px solid #484848; border-radius: 10px; }
.bol scrollbar slider { background: #515151; min-width: 5px; border-radius: 4px; }
'''

LANGUAGE_NAMES = dict(zip(LANGUAGES, ['Detect automatically','English','Hindi','Punjabi','Bengali','Kannada','Malayalam','Marathi','Odia','Tamil','Telugu','Gujarati','Assamese','Urdu','Nepali','Konkani','Sanskrit','Sindhi','Kashmiri','Dogri','Bodo','Manipuri','Maithili','Santali']))
MODE_NAMES = dict(zip(MODES, ['Original language','Mixed language & script','Roman script','Translate to English','Word for word']))
PAGES = [
    ('General','general','Connection, language, and recording preferences.'),
    ('Writing','writing','Writing preferences and application-specific styles.'),
    ('Vocabulary','vocabulary','Recognition hints and preferred spellings.'),
    ('Snippets','snippets','Expand a spoken phrase into reusable text.'),
    ('History','history','Review and recover your recent results.'),
    ('Shortcuts','shortcuts','Keyboard shortcuts and recording controls.'),
]


ICON_DIR = Path(__file__).resolve().parent / 'icons'


def svg_icon(name, size=18):
    file = Gio.File.new_for_path(str(ICON_DIR / (name + '.svg')))
    paintable = Gtk.IconPaintable.new_for_file(file, size, 1)
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
        powered=label('Powered by Sarvam','muted');margins(powered,22);side.append(powered)
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
        self.cancel_button=action_button('Cancel recording','cancel');cancel=self.cancel_button;cancel.set_visible(False);cancel.connect('clicked',lambda b:self.action(lambda:self.core.request('cancel')));inner.append(cancel)
        self.save_button=Gtk.Button(label='Save changes');self.save_button.add_css_class('primary');self.save_button.set_sensitive(False);self.save_button.connect('clicked',self.save);inner.append(self.save_button)
        main.append(footer)
        self.build_general();self.build_writing();self.build_vocabulary();self.build_snippets();self.build_history();self.build_shortcuts()
        self.loading=False;self.select('General');self.window.present()
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
        page=self.pages['General'];group=self.section(page,'Account')
        self.entry(group,'api_key','Sarvam API key','Stored privately on this computer.',True)
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
        page.append(label('Audio is processed by Sarvam. Writing features also send your text and preferences. Your API usage may consume credits.','muted',True))

    def build_writing(self):
        page=self.pages['Writing'];group=self.section(page,'Dictation')
        self.toggle(group,'polish','Polish with AI','Remove fillers, resolve corrections, and format your words.')
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
        page=self.pages['History'];group=self.section(page,'Recent results','History is optional. Your latest result remains available until Bol restarts.')
        toolbar=Gtk.Box(spacing=10);margins(toolbar,12)
        self.history_search=Gtk.SearchEntry();self.history_search.set_placeholder_text('Search text, app, or date');self.history_search.set_hexpand(True)
        self.history_search.connect('search-changed',lambda e:self.action(lambda:self.refresh_history(False)))
        toolbar.append(self.history_search)
        export=action_button('Export history','export');export.connect('clicked',lambda b:self.export_results(True));toolbar.append(export);group.append(toolbar)
        self.history_list=Gtk.ListBox();self.history_list.set_selection_mode(Gtk.SelectionMode.SINGLE);self.history_list.connect('row-selected',self.history_selected)
        self.empty=label('No saved results yet.','empty');self.history_list.set_placeholder(self.empty)
        scroll=Gtk.ScrolledWindow();scroll.set_min_content_height(130);scroll.set_max_content_height(190);scroll.set_child(self.history_list);margins(scroll,8);group.append(scroll)
        group=self.section(page,'Result preview','Review or edit the text before copying.')
        self.editor(group,'result','',170)
        actions=Gtk.FlowBox();actions.set_selection_mode(Gtk.SelectionMode.NONE);actions.set_homogeneous(False);actions.set_max_children_per_line(3);actions.set_column_spacing(8);actions.set_row_spacing(8)
        for title,callback in [('Export text',lambda:self.export_results(False)),('Refresh',lambda:self.refresh_history()),('Copy result',self.copy_result),('Remember correction',self.remember),('Clear history',self.clear_history)]:
            button=action_button(title,{'Export text':'export','Refresh':'refresh','Copy result':'copy','Remember correction':'memory','Clear history':'trash'}[title]);button.connect('clicked',lambda b,fn=callback:self.action(fn));actions.insert(button,-1)
        page.append(actions)

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
            data['vocabulary']=terms;data['writing_rules']=self.text('writing_rules').strip()
            for key in ['profiles','corrections','snippets']:data[key]=parse_pairs(self.text(key))
            if any(data.get(k)!=self.settings.get(k) for k in ['record_key','cancel_key','edit_key','hold_to_talk']):apply_shortcuts(data)
            self.core.save_config(data);self.settings=data
            for key,widget in self.key_labels.items():widget.set_text(data[key])
            self.save_note.set_text('All changes saved');self.save_button.set_sensitive(False)
        except Exception as error:self.dialog('Could not save',str(error))

    def refresh_history(self, load_latest=True):
        while child:=self.history_list.get_first_child():self.history_list.remove(child)
        self.history_rows=History(self.core.CONFIG).list(self.history_search.get_text()) if (self.core.CONFIG/'history.sqlite3').exists() else []
        for row in self.history_rows:
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
            preview=label(row['result'].replace('\n',' ')[:100]);preview.set_ellipsize(3);box.append(preview)
            box.append(label(f'{row["created"]} UTC · {row["app"]}','muted'));self.history_list.append(box)
        self.empty.set_text('No results match your search.' if self.history_search.get_text().strip() else 'No saved results yet.')
        if load_latest:
            latest=self.core.request('result').get('text','')
            if latest:self.buffers['result'].set_text(latest)

    def history_selected(self,listbox,row):
        if row and row.get_index()<len(self.history_rows):self.buffers['result'].set_text(self.history_rows[row.get_index()]['result'])

    def copy_result(self):
        text=self.text('result')
        if text:self.core.copy_text(text);self.status.set_text('Copied to clipboard')

    def export_results(self, history=False):
        if history:
            data=History(self.core.CONFIG).list(self.history_search.get_text()) if (self.core.CONFIG/'history.sqlite3').exists() else []
            if not data:
                self.dialog('Nothing to export','No saved history matches the current search.');return
            payload=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
        else:
            payload=self.text('result')
            if not payload.strip():
                self.dialog('Nothing to export','Dictate something or select a saved result first.');return
        chooser=Gtk.FileChooserNative.new('Export history' if history else 'Export text',self.window,Gtk.FileChooserAction.SAVE,'Export','Cancel')
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
                if (self.core.CONFIG/'history.sqlite3').exists():History(self.core.CONFIG).clear()
                self.refresh_history()
            d.destroy()
        dialog.connect('response',response);dialog.present()

    def remember(self):
        dialog=Gtk.Dialog(title='Remember correction',transient_for=self.window,modal=True)
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
                busy=False
                try:
                    state=self.core.request('status')
                    busy=state.get('state') in ['Recording','Transcribing','Writing']
                    text=state.get('error') or (f'Recording · {state["seconds"]:.0f}s' if state['state']=='Recording' else state.get('outcome') or state['state'])
                except Exception as error:text=str(error)
                GLib.idle_add(self.status_update,text,busy)
            threading.Thread(target=worker,daemon=True).start()
        return True

    def status_update(self,text,busy=False):
        self.polling=False
        if self.alive:
            self.status.set_text(text);self.status.set_tooltip_text(text)
            self.cancel_button.set_visible(busy)
        return False

    def on_close(self,*args):
        self.alive=False
        process=getattr(self,'mic_test_process',None)
        if process and process.poll() is None:process.terminate()
        return False


def settings_window(core):
    Workspace(core).app.run([])
