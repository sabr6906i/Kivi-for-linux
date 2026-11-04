"""Native GTK 4 settings workspace for Bol."""
import json
import threading
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from bol_features import LANGUAGES, MODES, History
from bol_ui import parse_pairs, format_pairs, apply_shortcuts

CSS = b'''
window.bol { background: #212121; color: #ececec; font-family: 'Noto Sans', sans-serif; font-size: 13px; }
.bol headerbar { background: #212121; box-shadow: none; border-bottom: 1px solid #303030; min-height: 40px; }
.bol .sidebar { background: #181818; border-right: 1px solid #303030; }
.bol .brand { font-size: 18px; font-weight: 650; color: #f5f5f5; }
.bol .nav-heading { font-size: 11px; color: #858585; font-weight: 500; }
.bol .nav-button { background: transparent; color: #aaa; border: none; box-shadow: none; border-radius: 8px; padding: 11px 12px; font-weight: 400; }
.bol .nav-button:hover { background: #242424; color: #eee; }
.bol .nav-button.selected { background: #303030; color: #f5f5f5; }
.bol .page-title { font-size: 28px; font-weight: 650; letter-spacing: -0.6px; }
.bol .muted { color: #929292; font-size: 12px; }
.bol .section-title { color: #ddd; font-size: 13px; font-weight: 600; }
.bol .group { background: #262626; border: 1px solid #383838; border-radius: 12px; }
.bol .row-title { font-weight: 500; color: #e4e4e4; }
.bol .row-hint { font-size: 11px; color: #999; }
.bol separator { background: #373737; min-height: 1px; }
.bol entry, .bol passwordentry, .bol dropdown > button, .bol spinbutton { background: #303030; color: #eee; border: 1px solid #444; border-radius: 8px; box-shadow: none; min-height: 34px; }
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
.bol .footer { background: #212121; border-top: 1px solid #343434; }
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
    ('General','preferences-system-symbolic','Connection, language, and recording preferences.'),
    ('Writing','document-edit-symbolic','Choose how your words sound, wherever you work.'),
    ('Vocabulary','accessories-dictionary-symbolic','Names and terms that should always sound like you.'),
    ('Snippets','edit-paste-symbolic','Reusable text, just a short phrase away.'),
    ('History','document-open-recent-symbolic','Review and recover your recent results.'),
    ('Shortcuts','input-keyboard-symbolic','Make voice typing part of your everyday workflow.'),
]


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
        side.add_css_class('sidebar');side.set_size_request(218,-1);side.set_hexpand(False);layout.append(side)
        brand=Gtk.Box(spacing=10);margins(brand,22)
        icon=Gtk.Image.new_from_icon_name('audio-input-microphone-symbolic');icon.set_pixel_size(22)
        brand.append(icon);brand.append(label('Bol','brand'));side.append(brand)
        navtitle=label('Workspace','nav-heading');navtitle.set_margin_start(22);navtitle.set_margin_top(9);navtitle.set_margin_bottom(8);side.append(navtitle)
        self.nav={}
        for title,icon_name,description in PAGES:
            button=Gtk.Button();button.add_css_class('nav-button');button.set_margin_start(10);button.set_margin_end(10)
            row=Gtk.Box(spacing=11);image=Gtk.Image.new_from_icon_name(icon_name);image.set_pixel_size(16)
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
            page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20);margins(page,38);scroller.set_child(page)
            heading=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);heading.set_margin_bottom(9)
            heading.append(label(title,'page-title'));heading.append(label(description,'muted',True));page.append(heading)
            self.stack.add_named(scroller,title);self.pages[title]=page
        footer=Gtk.Box(spacing=12);footer.add_css_class('footer');margins(footer,0)
        inner=Gtk.Box(spacing=12);margins(inner,18);inner.set_hexpand(True);footer.append(inner)
        self.save_note=label('All changes saved','muted');self.save_note.set_hexpand(True);inner.append(self.save_note)
        self.status=label('Ready','status');self.status.set_ellipsize(3);self.status.set_max_width_chars(28);inner.append(self.status)
        cancel=Gtk.Button(label='Cancel recording');cancel.connect('clicked',lambda b:self.action(lambda:self.core.request('cancel')));inner.append(cancel)
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
        self.history_list=Gtk.ListBox();self.history_list.set_selection_mode(Gtk.SelectionMode.SINGLE);self.history_list.connect('row-selected',self.history_selected)
        self.empty=label('No saved results yet.','empty');self.history_list.set_placeholder(self.empty)
        scroll=Gtk.ScrolledWindow();scroll.set_min_content_height(130);scroll.set_max_content_height(190);scroll.set_child(self.history_list);margins(scroll,8);group.append(scroll)
        group=self.section(page,'Result preview','Review or edit the text before copying.')
        self.editor(group,'result','',170)
        actions=Gtk.Box(spacing=8)
        for title,callback in [('Refresh',lambda:self.refresh_history()),('Copy result',self.copy_result),('Remember correction',self.remember),('Clear history',self.clear_history)]:
            button=Gtk.Button(label=title);button.connect('clicked',lambda b,fn=callback:self.action(fn));actions.append(button)
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

    def refresh_history(self):
        while child:=self.history_list.get_first_child():self.history_list.remove(child)
        self.history_rows=History(self.core.CONFIG).list() if (self.core.CONFIG/'history.sqlite3').exists() else []
        for row in self.history_rows:
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
            preview=label(row['result'].replace('\n',' ')[:100]);preview.set_ellipsize(3);box.append(preview)
            box.append(label(f'{row["created"]} UTC · {row["app"]}','muted'));self.history_list.append(box)
        latest=self.core.request('result').get('text','')
        if latest:self.buffers['result'].set_text(latest)

    def history_selected(self,listbox,row):
        if row and row.get_index()<len(self.history_rows):self.buffers['result'].set_text(self.history_rows[row.get_index()]['result'])

    def copy_result(self):
        text=self.text('result')
        if text:self.core.copy_text(text);self.status.set_text('Copied to clipboard')

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
                try:
                    state=self.core.request('status')
                    text=state.get('error') or (f'Recording · {state["seconds"]:.0f}s' if state['state']=='Recording' else state.get('outcome') or state['state'])
                except Exception as error:text=str(error)
                GLib.idle_add(self.status_update,text)
            threading.Thread(target=worker,daemon=True).start()
        return True

    def status_update(self,text):
        self.polling=False
        if self.alive:self.status.set_text(text);self.status.set_tooltip_text(text)
        return False

    def on_close(self,*args):
        self.alive=False
        return False


def settings_window(core):
    Workspace(core).app.run([])
