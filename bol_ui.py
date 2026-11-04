"""Bol settings and a small non-interactive recording indicator."""
import json
from pathlib import Path
import re
import subprocess
import threading
from bol_features import LANGUAGES, MODES, History


def parse_pairs(text):
    result = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if '=>' not in line:
            raise ValueError(f'Line {number}: use phrase => replacement')
        key, value = line.split('=>', 1)
        if not key.strip() or not value.strip():
            raise ValueError(f'Line {number}: both sides must contain text')
        result[key.strip()] = value.strip().replace('\\n', '\n')
    return result


def format_pairs(pairs):
    return '\n'.join(key + ' => ' + value.replace('\n', '\\n') for key, value in pairs.items())


def apply_shortcuts(settings):
    """Update the existing custom Hyprland file; preserve unrelated bindings."""
    for field in ['record_key', 'edit_key', 'cancel_key']:
        key = settings[field].upper()
        if not re.fullmatch(r'(?:(?:SUPER|CTRL|ALT|SHIFT)\s*\+\s*)*F(?:[1-9]|1[0-2])', key):
            raise ValueError('Use F1–F12, optionally with CTRL +, ALT +, SHIFT + or SUPER +.')
    if len({settings[key].upper().replace(' ', '') for key in ['record_key', 'edit_key', 'cancel_key']}) != 3:
        raise ValueError('Choose three different shortcuts.')
    binds = json.loads(subprocess.check_output(['hyprctl', '-j', 'binds'], text=True, timeout=3))
    mask_values = {'SUPER': 64, 'CTRL': 4, 'ALT': 8, 'SHIFT': 1}
    for field in ['record_key', 'edit_key', 'cancel_key']:
        parts = [part.strip().upper() for part in settings[field].split('+')]
        mask = sum(mask_values[part] for part in set(parts[:-1]))
        for bind in binds:
            if bind['modmask'] == mask and bind['key'].upper() == parts[-1] and not bind.get('description', '').startswith('Bol:'):
                raise ValueError(f'{settings[field]} is already used: {bind.get("description") or "another binding"}')
    path = Path.home() / '.config/hypr/custom/keybinds.lua'
    if not path.exists():
        raise ValueError('Automatic shortcuts require ~/.config/hypr/custom/keybinds.lua. See README for manual setup.')
    old = path.read_text()
    lines = [line for line in old.splitlines() if not ('hl.bind(' in line and ('Bol:' in line or 'bol toggle' in line or 'bol cancel' in line)) and line != '-- Bol voice dictation']
    def binding(key, command, description, options=''):
        return f'hl.bind({json.dumps(key)}, hl.dsp.exec_cmd("$HOME/.local/bin/bol {command}"), {{ description = "Bol: {description}"{options} }})'
    lines += ['', '-- Bol voice dictation']
    if settings.get('hold_to_talk'):
        lines += [binding(settings['record_key'], 'start', 'hold to dictate'), binding(settings['record_key'], 'stop', 'finish dictation', ', release = true')]
    else:
        lines += [binding(settings['record_key'], 'toggle', 'toggle dictation')]
    lines += [binding(settings['cancel_key'], 'cancel', 'cancel dictation', ', ignore_mods = true'), binding(settings['edit_key'], 'edit', 'voice edit')]
    path.with_suffix('.lua.bol-backup').write_text(old)
    path.write_text('\n'.join(lines) + '\n')
    result = subprocess.run(['hyprctl', 'reload'], capture_output=True, text=True, timeout=5)
    errors = subprocess.run(['hyprctl', 'configerrors'], capture_output=True, text=True, timeout=3)
    if result.returncode or errors.stdout.strip():
        path.write_text(old)
        subprocess.run(['hyprctl', 'reload'], capture_output=True, timeout=5)
        raise ValueError('Hyprland rejected the shortcuts. The previous configuration was restored.')


def settings_window(core):
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
    root = tk.Tk(className='BolSettings')
    root.title('Bol · Voice workspace')
    root.geometry('1120x820')
    root.minsize(960, 680)
    bg, panel, fg, muted, accent = '#09090c', '#131318', '#f1f0f7', '#9493a6', '#9b87ff'
    line, field, sidebar = '#292831', '#0c0c11', '#0d0d12'
    root.configure(bg=bg)
    root.option_add('*background', panel)
    root.option_add('*foreground', fg)
    root.option_add('*Entry.insertBackground', fg)
    root.option_add('*Button.activeBackground', '#292332')
    root.option_add('*Button.activeForeground', fg)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=bg, foreground=fg, font=('Sans', 10))
    style.configure('TFrame', background=bg)
    style.configure('Card.TFrame', background=panel)
    style.configure('TLabel', background=bg, foreground=fg)
    style.configure('Card.TLabel', background=panel, foreground=fg)
    style.configure('Muted.TLabel', background=panel, foreground=muted, font=('Sans', 9))
    style.configure('TButton', background=panel, foreground=fg, bordercolor=line,
                    focuscolor=accent, padding=(14, 9), relief='flat')
    style.map('TButton', background=[('active', '#26232f')], bordercolor=[('active', '#4b4266')])
    style.configure('Primary.TButton', background=accent, foreground='#100b21', bordercolor=accent,
                    padding=(22, 10), font=('Sans', 10, 'bold'))
    style.map('Primary.TButton', background=[('disabled', '#393044'), ('active', '#b7a8ff')], foreground=[('disabled', '#8f839f')])
    style.configure('TEntry', fieldbackground=field, foreground=fg, bordercolor=line,
                    lightcolor=line, darkcolor=line, padding=9, insertcolor=fg)
    style.map('TEntry', bordercolor=[('focus', accent)], lightcolor=[('focus', accent)], darkcolor=[('focus', accent)])
    style.configure('TCombobox', fieldbackground=field, foreground=fg, arrowcolor=muted,
                    bordercolor=line, padding=8, arrowsize=13)
    style.map('TCombobox', fieldbackground=[('readonly', field)], selectbackground=[('readonly', field)], selectforeground=[('readonly', fg)], bordercolor=[('focus', accent)])
    root.option_add('*TCombobox*Listbox.background', '#191820')
    root.option_add('*TCombobox*Listbox.foreground', fg)
    root.option_add('*TCombobox*Listbox.selectBackground', '#3d305b')
    root.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
    style.configure('TCheckbutton', background=panel, foreground=fg, padding=(0, 6))
    style.map('TCheckbutton', background=[('active', panel)])
    style.configure('Vertical.TScrollbar', background='#35323f', troughcolor=bg, borderwidth=0, arrowsize=10)
    settings = core.config()
    side = tk.Frame(root, bg=sidebar, width=218)
    side.pack(side='left', fill='y'); side.pack_propagate(False)
    brand = tk.Frame(side, bg=sidebar); brand.pack(fill='x', padx=24, pady=(30, 6))
    logo = tk.Canvas(brand, width=42, height=42, bg=sidebar, highlightthickness=0)
    logo.pack(side='left', padx=(0, 9))
    logo.create_oval(1, 1, 41, 41, fill='#241c38', outline='#403255')
    for x, height in [(12, 10), (18, 21), (24, 28), (30, 15)]:
        logo.create_line(x, 21-height/2, x, 21+height/2, fill='#c6b6ff', width=3, capstyle='round')
    tk.Label(brand, text='bol', font=('Sans', 25, 'bold'), bg=sidebar, fg='#f5f3ff').pack(side='left')
    tk.Label(side, text='VOICE WORKSPACE', font=('Sans', 8, 'bold'), bg=sidebar, fg='#747184').pack(anchor='w', padx=25, pady=(8, 28))
    nav = tk.Frame(side, bg=sidebar); nav.pack(fill='x', padx=12)
    side_bottom = tk.Frame(side, bg=sidebar); side_bottom.pack(side='bottom', fill='x', padx=20, pady=22)
    tk.Label(side_bottom, text='●  Powered by Sarvam', font=('Sans', 9), bg=sidebar, fg='#878397').pack(anchor='w')
    tk.Label(side_bottom, text='Your voice. Your workflow.', font=('Sans', 8), bg=sidebar, fg='#625e70').pack(anchor='w', pady=(7, 0))
    quick = tk.Frame(side, bg='#141219', highlightbackground='#29232f', highlightthickness=1, padx=13, pady=14)
    quick.pack(side='bottom', fill='x', padx=16, pady=(0, 8))
    tk.Label(quick, text='QUICK ACCESS', bg='#141219', fg='#797184', font=('Sans', 8, 'bold')).pack(anchor='w', pady=(0, 11))
    for key, description in [('record_key', 'Dictate'), ('edit_key', 'Voice edit'), ('cancel_key', 'Cancel')]:
        row = tk.Frame(quick, bg='#141219'); row.pack(fill='x', pady=4)
        tk.Label(row, text=description, bg='#141219', fg='#b2aaba', font=('Sans', 9)).pack(side='left')
        tk.Label(row, text=settings.get(key, ''), bg='#25202e', fg='#d8c9ef', font=('Sans', 8), padx=6, pady=3).pack(side='right')
    tk.Frame(root, bg='#25222d', width=1).pack(side='left', fill='y')
    outer = ttk.Frame(root); outer.pack(side='left', fill='both', expand=True)
    header = ttk.Frame(outer, padding=(32, 27, 32, 21)); header.pack(fill='x')
    ttk.Label(header, text='PERSONAL SPACE  /  SETTINGS', foreground=muted, font=('Sans', 8, 'bold')).pack(anchor='w')
    heading = ttk.Frame(header); heading.pack(fill='x', pady=(12, 7))
    page_title = tk.StringVar(value='General')
    ttk.Label(heading, textvariable=page_title, font=('Sans', 25, 'bold')).pack(side='left')
    status = tk.StringVar(value='Ready')
    status_label = tk.Label(heading, textvariable=status, bg='#15231e', fg='#8bd1ad', font=('Sans', 9), padx=12, pady=6, wraplength=280, justify='left')
    status_label.pack(side='right')
    page_description = tk.StringVar()
    ttk.Label(header, textvariable=page_description, foreground=muted, wraplength=650).pack(anchor='w')
    tk.Frame(outer, bg=line, height=1).pack(fill='x')
    # The footer stays visible while each page scrolls independently.
    footer_shell = tk.Frame(outer, bg=panel)
    footer_shell.pack(side='bottom', fill='x')
    tk.Frame(footer_shell, bg=line, height=1).pack(fill='x')
    footer = tk.Frame(footer_shell, bg=panel, padx=30, pady=16)
    footer.pack(fill='x')
    save_message = tk.StringVar(value='All changes saved')
    tk.Label(footer, textvariable=save_message, bg=panel, fg=muted, font=('Sans', 9)).pack(side='left')
    page_area = ttk.Frame(outer); page_area.pack(fill='both', expand=True)
    page_area.rowconfigure(0, weight=1); page_area.columnconfigure(0, weight=1)
    tabs, canvases, nav_buttons, scroll_canvases = {}, {}, {}, {}
    descriptions = {
        'General': 'Set up your connection, language, and recording preferences.',
        'Writing': 'Make every result sound like you. Choose your voice and app preferences.',
        'Vocabulary': 'Teach Bol the names, phrases, and technical terms you use every day.',
        'Snippets': 'Turn a short spoken phrase into the text you write most often.',
        'History': 'Find, review, and recover your recent dictation results.',
        'Shortcuts': 'A few keys are all you need. Make them feel natural.',
    }
    icons = {'General':'◉', 'Writing':'✎', 'Vocabulary':'Aa', 'Snippets':'≡', 'History':'◷', 'Shortcuts':'⌘'}
    history_refresh = [lambda: None]
    def select_page(title):
        page_title.set(title); page_description.set(descriptions[title])
        for name, container in canvases.items():
            if name == title: container.tkraise()
        for name, button in nav_buttons.items():
            button.configure(bg='#272034' if name == title else sidebar,
                             fg='#d8c9ff' if name == title else '#8d879c')
        if title == 'History':
            try: history_refresh[0]()
            except Exception as error: status.set(str(error))
    for title in descriptions:
        page = ttk.Frame(page_area); page.grid(row=0, column=0, sticky='nsew')
        canvas = tk.Canvas(page, bg=bg, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        frame = ttk.Frame(canvas, padding=(30, 24, 24, 24))
        window = canvas.create_window((0, 0), window=frame, anchor='nw')
        frame.bind('<Configure>', lambda e, c=canvas: c.configure(scrollregion=c.bbox('all')))
        canvas.bind('<Configure>', lambda e, c=canvas, w=window: c.itemconfigure(w, width=e.width))
        tabs[title], canvases[title], scroll_canvases[title] = frame, page, canvas
        button = tk.Button(nav, text=f'{icons[title]:<3}  {title}', command=lambda t=title: select_page(t),
                           anchor='w', bg=sidebar, fg='#8d879c', activebackground='#211b2b',
                           activeforeground='white', relief='flat', bd=0, padx=16, pady=13,
                           font=('Sans', 11), cursor='hand2', highlightthickness=0)
        button.pack(fill='x', pady=3); nav_buttons[title] = button
        button.bind('<Enter>', lambda e, t=title, b=button: b.configure(bg='#211b2b') if page_title.get() != t else None)
        button.bind('<Leave>', lambda e, t=title, b=button: b.configure(bg=sidebar) if page_title.get() != t else None)
    def wheel(event):
        if event.widget.winfo_class() not in ['Text', 'Listbox', 'TCombobox']:
            scroll_canvases[page_title.get()].yview_scroll(-3 if event.num == 4 else 3, 'units')
    root.bind_all('<Button-4>', wheel)
    root.bind_all('<Button-5>', wheel)
    variables, editors = {}, {}
    def dirty(*args):
        save_message.set('You have unsaved changes')
    def rounded(canvas, width, height, fill, outline, radius=16):
        r = radius
        points = [r, 1, width-r, 1, width-1, 1, width-1, r, width-1, height-r,
                  width-1, height-1, width-r, height-1, r, height-1, 1, height-1,
                  1, height-r, 1, r, 1, 1]
        return canvas.create_polygon(points, smooth=True, splinesteps=24, fill=fill, outline=outline)
    def card(parent, title, description=''):
        surface = tk.Canvas(parent, bg=bg, bd=0, highlightthickness=0, height=160)
        surface.pack(fill='x', pady=(0, 18))
        shape = rounded(surface, 650, 160, panel, line)
        body = ttk.Frame(surface, style='Card.TFrame', padding=(22, 10, 22, 10))
        embedded = surface.create_window(2, 14, anchor='nw', window=body)
        def resize(event=None):
            width = max(100, surface.winfo_width())
            surface.itemconfigure(embedded, width=width-4)
            height = body.winfo_reqheight() + 28
            surface.configure(height=height)
            surface.delete('outline')
            surface.delete(shape)
            outline = rounded(surface, width, height, panel, line)
            surface.itemconfigure(outline, tags=('outline',))
            surface.tag_lower(outline)
        body.bind('<Configure>', resize)
        surface.bind('<Configure>', resize)
        head = ttk.Frame(body, style='Card.TFrame'); head.pack(fill='x', pady=(0, 2))
        ttk.Label(head, text=title, style='Card.TLabel', font=('Sans', 12, 'bold')).pack(side='left')
        if title in ['Connection', 'AI writing', 'Your vocabulary', 'Keyboard shortcuts']:
            tag = {'Connection':'ACCOUNT', 'AI writing':'PERSONALIZE', 'Your vocabulary':'MEMORY', 'Keyboard shortcuts':'CONTROLS'}[title]
            tk.Label(head, text=tag, bg='#241e30', fg='#b39bd9', font=('Sans', 7, 'bold'), padx=8, pady=4).pack(side='right')
        if description:
            ttk.Label(body, text=description, style='Muted.TLabel', wraplength=620).pack(anchor='w', pady=(6, 12))
        else:
            ttk.Frame(body, style='Card.TFrame', height=8).pack()
        return body
    def label(parent, text):
        title, _, hint = text.partition(' · ')
        ttk.Label(parent, text=title, style='Card.TLabel', font=('Sans', 10, 'bold'), wraplength=620).pack(anchor='w', pady=(10, 5))
        if hint:
            ttk.Label(parent, text=hint, style='Muted.TLabel', wraplength=620).pack(anchor='w', pady=(0, 7))
    language_names = {'unknown':'Detect automatically', 'en-IN':'English', 'hi-IN':'Hindi', 'pa-IN':'Punjabi', 'bn-IN':'Bengali', 'kn-IN':'Kannada', 'ml-IN':'Malayalam', 'mr-IN':'Marathi', 'od-IN':'Odia', 'ta-IN':'Tamil', 'te-IN':'Telugu', 'gu-IN':'Gujarati', 'as-IN':'Assamese', 'ur-IN':'Urdu', 'ne-IN':'Nepali', 'kok-IN':'Konkani', 'sa-IN':'Sanskrit', 'sd-IN':'Sindhi', 'ks-IN':'Kashmiri', 'doi-IN':'Dogri', 'brx-IN':'Bodo', 'mni-IN':'Manipuri', 'mai-IN':'Maithili', 'sat-IN':'Santali'}
    mode_names = {'transcribe':'Original language', 'codemix':'Mixed language & script', 'translit':'Roman script', 'translate':'Translate to English', 'verbatim':'Word for word'}
    def entry(parent, key, text, choices=None, secret=False):
        label(parent, text)
        var = tk.StringVar(value=settings.get(key, '')); variables[key] = var
        var.trace_add('write', dirty)
        row = ttk.Frame(parent, style='Card.TFrame'); row.pack(fill='x', pady=(0, 8))
        if choices:
            names = language_names if key == 'language' else mode_names if key == 'output_mode' else {}
            display = tk.StringVar(value=names.get(var.get(), var.get()))
            widget = ttk.Combobox(row, textvariable=display, values=[names.get(v, v) for v in choices], state='readonly')
            reverse = {names.get(v, v):v for v in choices}
            display.trace_add('write', lambda *args: var.set(reverse.get(display.get(), display.get())))
        else:
            widget = ttk.Entry(row, textvariable=var, show='•' if secret else '')
        widget.pack(side='left', fill='x', expand=True)
        if secret:
            revealed = [False]
            def reveal():
                revealed[0] = not revealed[0]
                widget.configure(show='' if revealed[0] else '•')
                reveal_button.configure(text='Hide' if revealed[0] else 'Show')
            reveal_button = ttk.Button(row, text='Show', command=reveal)
            reveal_button.pack(side='right', padx=(8, 0))
        return widget
    def check(parent, key, text):
        var = tk.BooleanVar(value=settings.get(key, False)); variables[key] = var
        var.trace_add('write', dirty)
        title, _, hint = text.partition(' · ')
        row = ttk.Frame(parent, style='Card.TFrame'); row.pack(fill='x', pady=10)
        words = ttk.Frame(row, style='Card.TFrame'); words.pack(side='left', fill='x', expand=True)
        ttk.Label(words, text=title, style='Card.TLabel', wraplength=530).pack(anchor='w')
        if hint: ttk.Label(words, text=hint, style='Muted.TLabel', wraplength=500).pack(anchor='w', pady=(5, 0))
        switch = tk.Canvas(row, width=42, height=24, bg=panel, highlightthickness=0, cursor='hand2', takefocus=True)
        switch.pack(side='right', padx=(12, 0))
        def draw(*args):
            switch.delete('all')
            rounded(switch, 42, 24, accent if var.get() else '#34303f', accent if var.get() else '#4a4256', 12)
            x = 30 if var.get() else 12
            switch.create_oval(x-8, 4, x+8, 20, fill='#100b21' if var.get() else '#c1b9cd', outline='')
            if switch.focus_get() == switch:
                switch.create_rectangle(0, 0, 41, 23, outline='#c9baff', dash=(2, 2))
        def toggle(event=None):
            var.set(not var.get()); return 'break'
        switch.bind('<Button-1>', toggle); switch.bind('<space>', toggle); switch.bind('<Return>', toggle)
        switch.bind('<FocusIn>', draw); switch.bind('<FocusOut>', draw)
        var.trace_add('write', draw); draw()
    def editor(parent, key, text, value, height=6):
        label(parent, text)
        border = tk.Frame(parent, bg=line, padx=1, pady=1); border.pack(fill='both', expand=True, pady=(0, 8))
        widget = tk.Text(border, height=height, bg=field, fg=fg, insertbackground=accent, relief='flat',
                         padx=12, pady=12, wrap='word', undo=True, font=('Sans', 10), spacing1=3, spacing3=3,
                         selectbackground='#403355', selectforeground=fg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(border, orient='vertical', command=widget.yview)
        scrollbar.pack(side='right', fill='y'); widget.pack(side='left', fill='both', expand=True)
        widget.configure(yscrollcommand=scrollbar.set)
        widget.insert('1.0', value); widget.edit_modified(False)
        def modified(event):
            if widget.edit_modified():
                if key != 'result': dirty()
                widget.edit_modified(False)
        widget.bind('<<Modified>>', modified)
        editors[key] = widget
        return widget
    general = card(tabs['General'], 'Connection', 'Connect your Sarvam account to start speaking.')
    entry(general, 'api_key', 'API key', secret=True)
    ttk.Label(general, text='Stored privately on this computer.', style='Muted.TLabel').pack(anchor='w')
    general = card(tabs['General'], 'Speech & recording', 'Choose how Bol listens and writes.')
    entry(general, 'language', 'Speech language', LANGUAGES)
    entry(general, 'output_mode', 'Output style', MODES)
    entry(general, 'microphone', 'Microphone · leave empty for the PipeWire default (or enter a node name)')
    entry(general, 'record_seconds', 'Maximum recording length in seconds · 5 to 300')
    general = card(tabs['General'], 'Workflow & privacy')
    check(general, 'auto_paste', 'Paste automatically into the original focused app')
    check(general, 'history_enabled', 'Keep the last 200 results on this computer')
    label(general, 'Audio goes to Sarvam and is deleted locally after processing. Writing features also send dictated/selected text and writing preferences to Sarvam. API usage may cost credits.')
    writing = card(tabs['Writing'], 'AI writing', 'Polish your speech without changing what you mean.')
    check(writing, 'polish', 'Polish dictation with AI · remove fillers, resolve corrections, format lists')
    editor(writing, 'writing_rules', 'Writing preferences · e.g. British spelling; preserve Punjabi; keep technical terms', settings.get('writing_rules', ''), 4)
    writing = card(tabs['Writing'], 'App preferences', 'Give your editor, email, and chat apps their own writing style.')
    editor(writing, 'profiles', 'Per-app rules · one exact app class => instruction per line', format_pairs(settings.get('profiles', {})), 5)
    def current_app():
        classes = sorted({item.get('class', '') for item in json.loads(subprocess.check_output(['hyprctl', '-j', 'clients'], text=True, timeout=3)) if item.get('class')})
        messagebox.showinfo('Open app classes', '\n'.join(classes) or 'No apps found')
    ttk.Button(writing, text='Show open app classes', command=current_app).pack(anchor='w')
    vocabulary = card(tabs['Vocabulary'], 'Your vocabulary', 'Help recognition get your names and terminology right.')
    editor(vocabulary, 'vocabulary', 'Recognition hints · one name or technical term per line (up to 50, 64 characters each)', '\n'.join(settings.get('vocabulary', [])), 5)
    vocabulary = card(tabs['Vocabulary'], 'Remembered corrections', 'Replace recurring mistakes with the spelling you prefer.')
    editor(vocabulary, 'corrections', 'Remembered corrections · heard phrase => preferred spelling, one per line', format_pairs(settings.get('corrections', {})), 6)
    snippets = card(tabs['Snippets'], 'Say less. Write more.', 'Create reusable signatures, replies, and frequently used text.')
    editor(snippets, 'snippets', 'Say a phrase to insert its full text · phrase => expansion\nUse \\n for line breaks. A snippet triggers only when it matches the entire dictation.', format_pairs(settings.get('snippets', {})), 16)
    shortcuts = card(tabs['Shortcuts'], 'Keyboard shortcuts', 'Your voice workspace, one key away.')
    for key, text in [('record_key', 'Dictate'), ('cancel_key', 'Cancel / discard'), ('edit_key', 'Voice edit / draft')]:
        entry(shortcuts, key, text)
    shortcuts = card(tabs['Shortcuts'], 'Recording behavior')
    check(shortcuts, 'hold_to_talk', 'Hold the dictation key to record; release to finish')
    label(shortcuts, 'Voice edit: select text, press the editing key, speak your instruction, then press it again. Without a selection, Bol drafts from your instruction. Selected text is sent to Sarvam.')
    label(shortcuts, 'Shortcut edits apply to Hyprland when you save. Use F1–F12, optionally with CTRL +, ALT +, SHIFT + or SUPER +. Existing non-Bol shortcuts are checked for conflicts.')
    history = card(tabs['History'], 'Recent results', 'History stays on this computer. Enable saving in General to keep up to 200 results.')
    rows = []
    history_list = tk.Listbox(history, height=5, bg=field, fg=fg, selectbackground='#403355', selectforeground=fg, relief='flat', exportselection=False, font=('Sans', 10), highlightthickness=1, highlightbackground=line, activestyle='none')
    empty_history = ttk.Label(history, text='No saved results yet. Your latest result will appear when you refresh.', style='Muted.TLabel', wraplength=600)
    empty_history.pack(anchor='w', pady=(6, 10))
    history_list.pack(fill='x')
    result = editor(history, 'result', 'Result preview · Review or edit the text, then copy it to any app.', '', 8)
    def show_result(event=None):
        if history_list.curselection():
            row = rows[history_list.curselection()[0]]
            result.delete('1.0', 'end'); result.insert('1.0', row['result'])
    history_list.bind('<<ListboxSelect>>', show_result)
    def refresh():
        rows.clear(); history_list.delete(0, 'end')
        if (core.CONFIG / 'history.sqlite3').exists():
            rows.extend(History(core.CONFIG).list())
            for row in rows:
                history_list.insert('end', f'{row["created"]} · {row["app"]} · {row["result"][:65].replace(chr(10), " ")}')
        empty_history.configure(text=f'{len(rows)} saved results · newest first' if rows else 'No saved results yet. Your latest result is still available below after dictation.')
        latest = core.request('result').get('text', '')
        if latest:
            result.delete('1.0', 'end'); result.insert('1.0', latest)
    history_refresh[0] = refresh
    def copy():
        text = result.get('1.0', 'end-1c')
        if text:
            core.copy_text(text); status.set('Result copied')
    def clear():
        if messagebox.askyesno('Clear local history?', 'Delete all saved transcripts from this computer?'):
            if (core.CONFIG / 'history.sqlite3').exists():
                History(core.CONFIG).clear()
            rows.clear(); history_list.delete(0, 'end'); result.delete('1.0', 'end')
            empty_history.configure(text='Your saved history has been cleared.')
    def remember():
        old = simpledialog.askstring('Remember correction', 'What did Bol get wrong?', parent=root)
        if not old: return
        new = simpledialog.askstring('Remember correction', 'Preferred spelling:', parent=root)
        if not new: return
        data = core.config(); data.setdefault('corrections', {})[old] = new
        core.save_config(data)
        editors['corrections'].delete('1.0', 'end'); editors['corrections'].insert('1.0', format_pairs(data['corrections']))
        status.set('Correction remembered')
    buttons = ttk.Frame(history, style='Card.TFrame'); buttons.pack(fill='x', pady=4)
    for text, command in [('Refresh', refresh), ('Copy', copy), ('Remember correction', remember), ('Clear history', clear)]:
        ttk.Button(buttons, text=text, command=command).pack(side='left', padx=(0, 6))
    def save():
        try:
            data = core.config()
            data.update({key: value.get().strip() if isinstance(value, tk.StringVar) else value.get() for key, value in variables.items()})
            terms = [line.strip() for line in editors['vocabulary'].get('1.0', 'end-1c').splitlines() if line.strip()]
            if len(terms) > 50 or any(len(term) > 64 for term in terms):
                raise ValueError('Vocabulary supports up to 50 terms, each at most 64 characters.')
            data['record_seconds'] = int(data['record_seconds'])
            if not 5 <= data['record_seconds'] <= 300:
                raise ValueError('Recording length must be between 5 and 300 seconds.')
            data['vocabulary'] = terms
            data['writing_rules'] = editors['writing_rules'].get('1.0', 'end-1c').strip()
            for key in ['profiles', 'corrections', 'snippets']:
                data[key] = parse_pairs(editors[key].get('1.0', 'end-1c'))
            changed = any(data.get(key) != settings.get(key) for key in ['record_key', 'edit_key', 'cancel_key', 'hold_to_talk'])
            if changed:
                apply_shortcuts(data)
            core.save_config(data); settings.update(data)
            save_message.set('All changes saved')
            status.set('Settings saved')
        except Exception as error:
            messagebox.showerror('Could not save', str(error))
    ttk.Button(footer, text='Save changes', style='Primary.TButton', command=save).pack(side='right')
    ttk.Button(footer, text='Stop recording', command=lambda: core.request('cancel')).pack(side='right', padx=(0, 10))
    last_state = [None]
    def poll():
        try:
            state = core.request('status')
            if state != last_state[0]:
                status.set(state.get('error') or (f'{state["state"]} · {state["seconds"]:.0f}s' if state['state'] == 'Recording' else state.get('outcome') or state['state']))
                busy = state['state'] in ['Recording', 'Transcribing', 'Writing']
                status_label.configure(bg='#30251a' if busy else '#301a22' if state.get('error') else '#15231e', fg='#edc58c' if busy else '#ef9cac' if state.get('error') else '#8bd1ad')
                last_state[0] = state
        except Exception as error:
            status.set(str(error))
        root.after(600, poll)
    select_page('General')
    root.after(100, poll)
    root.mainloop()


def recording_indicator(core):
    import tkinter as tk
    root = tk.Tk(className='BolIndicator')
    root.title('Bol Recording Indicator')
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    try:
        root.attributes('-type', 'notification')
    except tk.TclError:
        pass
    root.configure(bg='#101015')
    width, height = 340, 66
    root.geometry(f'{width}x{height}+{(root.winfo_screenwidth()-width)//2}+40')
    body = tk.Frame(root, bg='#101015', padx=18, pady=10); body.pack(fill='both', expand=True)
    dot = tk.Label(body, text='●', bg='#101015', fg='#f87171', font=('Sans', 17)); dot.pack(side='left', padx=(0, 12))
    words = tk.Frame(body, bg='#101015'); words.pack(side='left', fill='both', expand=True)
    label = tk.Label(words, bg='#101015', fg='#f3f4f6', font=('Sans', 11, 'bold'), anchor='w')
    label.pack(fill='x')
    hint = tk.Label(words, text=f"{core.config().get('cancel_key', 'F9')} to cancel", bg='#101015', fg='#8f859f', font=('Sans', 8), anchor='w'); hint.pack(fill='x', pady=(3, 0))
    root.withdraw()
    def poll():
        try:
            state = core.request('status', start=False)
            if state['state'] in ['Recording', 'Transcribing', 'Writing']:
                text = f'● {state["mode"].title()} · {state["seconds"]:.0f}s' if state['state'] == 'Recording' else state['state'] + '…'
                label.configure(text=text.replace('● ', ''))
                dot.configure(fg='#f87171' if state['state'] == 'Recording' else '#a5a0ff')
                if root.state() == 'withdrawn': root.deiconify()
            else:
                root.withdraw()
        except Exception:
            root.destroy(); return
        root.after(250, poll)
    root.after(300, poll)
    root.mainloop()
