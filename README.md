# Bol — a Linux voice workspace

An independent Sarvam-powered voice typing and writing app for **Hyprland / Wayland**. Inspired by Kivi's workflow; not affiliated with Sarvam or Kivi. Requires your own Sarvam API key.

## Features

- Global dictation with toggle or hold-to-talk shortcuts.
- Floating recording/processing indicator that does not take focus.
- English and 22 Indic languages, automatic detection, mixed-script output, Roman transliteration, English translation and verbatim modes.
- Optional AI polish: punctuation, filler removal, spoken corrections, paragraphs and lists.
- Voice editing: select text, say how to rewrite/translate/shorten/format it, then replace the selection. Without a selection, draft from your instruction.
- Global writing preferences plus exact app-class writing profiles.
- Recognition vocabulary (up to 50 terms), remembered spelling corrections, and spoken text snippets.
- Latest-result recovery, optional private local history capped at 200 entries, copy and clear controls.
- Local three-second microphone check with quiet-signal and clipping detection; the sample is never uploaded.
- Search saved history by text, app, mode or date. Export filtered history as JSON or the current result as text. New exports use owner-only permissions.
- Microphone node selection, adjustable recording limit (5–300 seconds), and automatic paste with terminal shortcuts.
- Shortcut configuration with conflict checking and an optional hold-to-talk mode.

The app is an early implementation of these workflows, not a claim of complete Kivi feature or quality parity. See the limitations below.

## Install

On Arch Linux:

```sh
sudo pacman -S python python-gobject gtk4 tk pipewire wl-clipboard libnotify ffmpeg
git clone git@github.com:sabr6906i/Kivi-for-linux.git
cd Kivi-for-linux
./install.sh
~/.local/bin/bol settings
```

Enter your API key from [Sarvam's dashboard](https://dashboard.sarvam.ai/) in **General**. Save settings. Writing features use the same key and require access to the `sarvam-105b` chat model. They consume additional API credits. Enable **Polish dictation** in Writing if desired; raw dictation remains the default.

The app requires Hyprland 0.55+ with the Lua configuration API. Other compositors are not currently supported. `ffmpeg` is needed for recordings longer than 25 seconds; these are split into 24-second requests and combined before writing/pasting. This is not live streaming and may have small boundary recognition errors.

## Shortcuts

Add these to a file loaded by your Hyprland Lua configuration (for example `~/.config/hypr/custom/keybinds.lua`):

```lua
hl.bind("F8", hl.dsp.exec_cmd("$HOME/.local/bin/bol toggle"), { description = "Bol: toggle dictation" })
hl.bind("F9", hl.dsp.exec_cmd("$HOME/.local/bin/bol cancel"), { description = "Bol: cancel dictation", ignore_mods = true })
hl.bind("F10", hl.dsp.exec_cmd("$HOME/.local/bin/bol edit"), { description = "Bol: voice edit" })
```

Run `hyprctl reload`. On the original development machine these bindings are already installed. The Shortcuts tab can update them if your main config loads `~/.config/hypr/custom/keybinds.lua`. Shortcut changes are checked against existing bindings, and the previous file is backed up as `keybinds.lua.bol-backup`.

- **F8:** start recording; press again to finish and transcribe. Hold mode can be enabled in settings.
- **F9:** cancel recording or discard a pending result; it does not transcribe.
- **F10:** select text, press F10, speak an editing instruction, then press F10 again. You can also finish with F8. With no selection, it drafts at the cursor.

Keep the original text box focused and leave the selection unchanged. If the app or captured selection changes, Bol copies the result for manual paste. The latest result is available in **History → Refresh** even with disk history disabled. `bol copy-last` also recovers it. Latest-result memory is cleared when the daemon exits.

## Personalize

Settings use a native GTK 4 workspace with neutral dark surfaces, a sidebar, grouped controls, and a consistent set of bundled SVG line icons. If GTK bindings are unavailable, Bol falls back to its Tk settings window. The recording indicator uses Tk.

Open **Bol Voice Typing** from your app launcher, or run `~/.local/bin/bol settings`. Use **General → Test microphone** for a local three-second level check; it does not use API credits.

- **General:** key, language, output mode, microphone node name (blank uses the PipeWire default), recording limit, paste, and local-history preference.
- **Writing:** optional polish, global rules and per-app rules. Profiles use exact app classes, e.g. `Chatgpt => Preserve code identifiers; be concise`. The app can show currently open app classes. Writing rules apply to AI polish and voice editing, not raw dictation.
- **Vocabulary:** one recognition hint per line. Add explicit corrections such as `sara vam => Sarvam`. Corrections match whole words/phrases and preserve unrelated text. Recognition hints go to the speech API.
- **Snippets:** e.g. `my signature => Regards,\nSarbjeet`. Say only the trigger phrase to expand it. Use literal `\n` for line breaks.
- **History:** search saved results, export matching history as JSON, export the current preview as text, edit/copy a result, explicitly remember a correction, or clear saved history. History saving must be enabled in General to retain new results.
- **Shortcuts:** customize keys, toggle hold-to-talk, and choose an editing key.

## Privacy and recovery

Audio goes to Sarvam for speech recognition. AI polish sends the dictated text and writing rules to Sarvam. Voice editing also sends the text explicitly copied from your selection. There is no automatic screen capture or background reading of app contents.

Settings live at `~/.config/bol-linux/settings.json`, including the API key, with owner-only file permissions. Temporary audio is deleted after processing. History is **off by default**. When enabled it stores the original transcript, final text, app class and UTC timestamp in an owner-only `history.sqlite3`, retaining the newest 200 results. Disabling history stops future storage; use Clear history to remove existing entries. Text is also placed on the clipboard and may be retained by your clipboard manager.

Cancellation prevents pending results from being pasted or added to history, and stops further chunk uploads, but cannot recall an API request already sent. If polish fails, raw dictation is recovered. If editing fails, selected text is left intact. A paste shortcut being accepted does not prove that an application's text widget accepted the text; recover the result from History or `bol copy-last` if necessary.

## Current limits compared with Kivi

[Kivi's official site](https://heykivi.ai/) advertises Mac dictation, correction memory, app-specific personas and voice text editing; it currently lists a Windows waitlist.

Bol implements the corresponding basic workflows using public APIs, with these remaining gaps:

- Corrections are remembered explicitly through the Vocabulary tab or Remember correction button. Passive learning from arbitrary edits is not implemented.
- Voice formatting produces plain text/Markdown; it cannot reliably apply rich formatting such as actual bold inside every editor.
- It uses selection capture and keyboard paste. Browser fields, unusual editors, XWayland apps and terminals can behave differently. Selection capture is intentionally skipped in terminals to avoid Ctrl+C interrupting a command; voice editing there drafts from speech.
- No screen-context reading, live streaming captions, system-tray menu, automatic updater, offline model, cloud synchronization or cross-compositor packaging yet.
- Model output quality and latency are not guaranteed to match Kivi's private prompts or services.

## Development

```sh
python -m unittest discover -s tests -v
python -m py_compile kivi_linux.py bol_features.py bol_ui.py
bash -n install.sh
```

`kivi_linux.py` provides recording, IPC and insertion. `bol_features.py` handles vocabulary/snippets, writing API and SQLite history. `bol_gtk.py` contains the native GTK settings workspace. `bol_ui.py` provides the fallback settings window, shortcut helpers, and recording indicator. The app uses Python's standard library plus Tk and system executables.

`bol doctor` checks dependencies, and `bol status` shows recording/processing state. The daemon starts on demand. After an upgrade, stop the existing daemon before starting the new version so it imports the updated modules. It handles SIGTERM by stopping its recorder and cleaning temporary audio.

## Remove

Remove the Bol bindings from your Hyprland config and reload. Stop the Bol daemon, then delete `~/.local/bin/bol`, `~/.local/share/bol-linux`, and `~/.local/share/applications/bol-linux.desktop`. Optionally remove `~/.config/bol-linux` including settings and history.
