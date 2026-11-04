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
    root.geometry('860x720')
    root.minsize(760, 640)
    style = ttk.Style(root)
    style.theme_use('clam')
    bg, panel, fg, muted, accent = '#111827', '#1f2937', '#f3f4f6', '#9ca3af', '#6ee7b7'
    root.configure(bg=bg)
    style.configure('.', background=bg, foreground=fg, font=('Sans', 10))
    style.configure('TFrame', background=bg)
    style.configure('TLabel', background=bg)
    style.configure('TButton', background=panel, padding=(12, 7))
    style.map('TButton', background=[('active', '#374151')])
    style.configure('TEntry', fieldbackground=panel, foreground=fg, insertcolor=fg)
    style.configure('TCombobox', fieldbackground=panel, foreground=fg, arrowcolor=fg)
    style.map('TCombobox', fieldbackground=[('readonly', panel)], selectbackground=[('readonly', panel)], selectforeground=[('readonly', fg)])
    style.configure('TNotebook', background=bg, borderwidth=0)
    style.configure('TNotebook.Tab', background=panel, foreground=fg, padding=(12, 9))
    style.map('TNotebook.Tab', background=[('selected', '#065f46')])
    style.configure('TCheckbutton', background=bg, foreground=fg)
    style.map('TCheckbutton', background=[('active', bg)])
    settings = core.config()
    outer = ttk.Frame(root, padding=22); outer.pack(fill='both', expand=True)
    header = ttk.Frame(outer); header.pack(fill='x')
    ttk.Label(header, text='Bol', font=('Sans', 26, 'bold'), foreground=accent).pack(side='left')
    status = tk.StringVar(value='Ready')
    ttk.Label(header, textvariable=status, foreground=muted).pack(side='right')
    ttk.Label(outer, text='Your voice, your words, in every app.', foreground=muted).pack(anchor='w', pady=(0, 14))
    notebook = ttk.Notebook(outer); notebook.pack(fill='both', expand=True)
    tabs = {}
    for title in ['General', 'Writing', 'Vocabulary', 'Snippets', 'History', 'Shortcuts']:
        frame = ttk.Frame(notebook, padding=16); notebook.add(frame, text=title); tabs[title] = frame
    variables = {}
    editors = {}
    def label(parent, text):
        ttk.Label(parent, text=text, wraplength=735).pack(anchor='w', pady=(8, 4))
    def entry(parent, key, text, choices=None, secret=False):
        label(parent, text)
        var = tk.StringVar(value=settings.get(key, '')); variables[key] = var
        widget = ttk.Combobox(parent, textvariable=var, values=choices, state='readonly') if choices else ttk.Entry(parent, textvariable=var, show='•' if secret else '')
        widget.pack(fill='x', pady=(0, 5))
        return widget
    def check(parent, key, text):
        var = tk.BooleanVar(value=settings.get(key, False)); variables[key] = var
        ttk.Checkbutton(parent, text=text, variable=var).pack(anchor='w', pady=7)
    def editor(parent, key, text, value, height=6):
        label(parent, text)
        widget = tk.Text(parent, height=height, bg=panel, fg=fg, insertbackground=accent, relief='flat', padx=10, pady=10, wrap='word', undo=True)
        widget.pack(fill='both', expand=True, pady=(0, 8)); widget.insert('1.0', value); editors[key] = widget
        return widget
    general = tabs['General']
    entry(general, 'api_key', 'Sarvam API key', secret=True)
    entry(general, 'language', 'Speech language · unknown detects automatically', LANGUAGES)
    entry(general, 'output_mode', 'Output · original, mixed script, Roman script, English translation, or verbatim', MODES)
    entry(general, 'microphone', 'Microphone · leave empty for the PipeWire default (or enter a node name)')
    entry(general, 'record_seconds', 'Maximum recording length in seconds · 5 to 300')
    check(general, 'auto_paste', 'Paste automatically into the original focused app')
    check(general, 'history_enabled', 'Keep the last 200 results on this computer')
    label(general, 'Audio goes to Sarvam and is deleted locally after processing. Writing features also send dictated/selected text and writing preferences to Sarvam. API usage may cost credits.')
    writing = tabs['Writing']
    check(writing, 'polish', 'Polish dictation with AI · remove fillers, resolve corrections, format lists')
    editor(writing, 'writing_rules', 'Writing preferences · e.g. British spelling; preserve Punjabi; keep technical terms', settings.get('writing_rules', ''), 4)
    editor(writing, 'profiles', 'Per-app rules · one exact app class => instruction per line', format_pairs(settings.get('profiles', {})), 5)
    def current_app():
        classes = sorted({item.get('class', '') for item in json.loads(subprocess.check_output(['hyprctl', '-j', 'clients'], text=True, timeout=3)) if item.get('class')})
        messagebox.showinfo('Open app classes', '\n'.join(classes) or 'No apps found')
    ttk.Button(writing, text='Show open app classes', command=current_app).pack(anchor='w')
    vocabulary = tabs['Vocabulary']
    editor(vocabulary, 'vocabulary', 'Recognition hints · one name or technical term per line (up to 50, 64 characters each)', '\n'.join(settings.get('vocabulary', [])), 5)
    editor(vocabulary, 'corrections', 'Remembered corrections · heard phrase => preferred spelling, one per line', format_pairs(settings.get('corrections', {})), 6)
    editor(tabs['Snippets'], 'snippets', 'Say a phrase to insert its full text · phrase => expansion\nUse \\n for line breaks. A snippet triggers only when it matches the entire dictation.', format_pairs(settings.get('snippets', {})), 16)
    shortcuts = tabs['Shortcuts']
    for key, text in [('record_key', 'Dictate'), ('cancel_key', 'Cancel / discard'), ('edit_key', 'Voice edit / draft')]:
        entry(shortcuts, key, text)
    check(shortcuts, 'hold_to_talk', 'Hold the dictation key to record; release to finish')
    label(shortcuts, 'Voice edit: select text, press the editing key, speak your instruction, then press it again. Without a selection, Bol drafts from your instruction. Selected text is sent to Sarvam.')
    label(shortcuts, 'Shortcut edits apply to Hyprland when you save. Use F1–F12, optionally with CTRL +, ALT +, SHIFT + or SUPER +. Existing non-Bol shortcuts are checked for conflicts.')
    history = tabs['History']
    rows = []
    history_list = tk.Listbox(history, height=5, bg=panel, fg=fg, selectbackground='#065f46', relief='flat', exportselection=False)
    history_list.pack(fill='x')
    result = editor(history, 'result', 'Latest result / selected history entry · edit here, then Copy', '', 8)
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
        latest = core.request('result').get('text', '')
        if latest:
            result.delete('1.0', 'end'); result.insert('1.0', latest)
    def copy():
        text = result.get('1.0', 'end-1c')
        if text:
            core.copy_text(text); status.set('Result copied')
    def clear():
        if messagebox.askyesno('Clear local history?', 'Delete all saved transcripts from this computer?'):
            if (core.CONFIG / 'history.sqlite3').exists():
                History(core.CONFIG).clear()
            rows.clear(); history_list.delete(0, 'end'); result.delete('1.0', 'end')
    def remember():
        old = simpledialog.askstring('Remember correction', 'What did Bol get wrong?', parent=root)
        if not old: return
        new = simpledialog.askstring('Remember correction', 'Preferred spelling:', parent=root)
        if not new: return
        data = core.config(); data.setdefault('corrections', {})[old] = new
        core.save_config(data)
        editors['corrections'].delete('1.0', 'end'); editors['corrections'].insert('1.0', format_pairs(data['corrections']))
        status.set('Correction remembered')
    buttons = ttk.Frame(history); buttons.pack(fill='x', pady=4)
    for text, command in [('Refresh', refresh), ('Copy', copy), ('Remember correction', remember), ('Clear history', clear)]:
        ttk.Button(buttons, text=text, command=command).pack(side='left', padx=(0, 6))
    footer = ttk.Frame(outer); footer.pack(fill='x', pady=(14, 0))
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
            status.set('Settings saved · ready for your next recording')
        except Exception as error:
            messagebox.showerror('Could not save', str(error))
    ttk.Button(footer, text='Save settings', command=save).pack(side='right')
    ttk.Button(footer, text='Cancel recording', command=lambda: core.request('cancel')).pack(side='left')
    last_state = [None]
    def poll():
        try:
            state = core.request('status')
            if state != last_state[0]:
                status.set(state.get('error') or (f'{state["state"]} · {state["seconds"]:.0f}s' if state['state'] == 'Recording' else state.get('outcome') or state['state']))
                last_state[0] = state
        except Exception as error:
            status.set(str(error))
        root.after(600, poll)
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
    root.configure(bg='#111827')
    width, height = 300, 48
    root.geometry(f'{width}x{height}+{(root.winfo_screenwidth()-width)//2}+40')
    label = tk.Label(root, bg='#111827', fg='#6ee7b7', font=('Sans', 12, 'bold'), padx=16, pady=12)
    label.pack(fill='both', expand=True)
    root.withdraw()
    def poll():
        try:
            state = core.request('status', start=False)
            if state['state'] in ['Recording', 'Transcribing', 'Writing']:
                text = f'● {state["mode"].title()} · {state["seconds"]:.0f}s' if state['state'] == 'Recording' else state['state'] + '…'
                label.configure(text=text)
                if root.state() == 'withdrawn': root.deiconify()
            else:
                root.withdraw()
        except Exception:
            root.destroy(); return
        root.after(250, poll)
    root.after(300, poll)
    root.mainloop()
