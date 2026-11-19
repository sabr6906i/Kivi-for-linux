# Bol — a Linux voice workspace

An independent voice typing and writing app for **Hyprland / Wayland**. Inspired by Kivi's workflow; not affiliated with Sarvam or Kivi. Supports Sarvam, local whisper.cpp, ElevenLabs through official CLI browser sign-in, and configurable compatible speech/writing APIs. Local dictation needs no API key.

## Features

- Global dictation with toggle or hold-to-talk shortcuts.
- Text to Audio: Sarvam Bulbul v3 generation with language, voice and speed selection, local playback and WAV export.
- History-first navigation with colorful SVG icons, vivid section accents and stronger active controls on a black background.
- Floating recording/processing indicator that does not take focus.
- English and 22 Indic languages, automatic detection, mixed-script output, Roman transliteration, English translation and verbatim modes.
- Optional AI polish: punctuation, filler removal, spoken corrections, paragraphs and lists.
- Reviewable voice edits: inspect or change the proposal, then approve, copy or discard it. Approval rechecks the target window and selection.
- History retention choices: 24 hours, 7 days, 30 days, or the existing 200-result limit.
- Voice editing: select text, say how to rewrite/translate/shorten/format it, then review the proposed replacement. Without a selection, draft from your instruction.
- Global writing preferences plus exact app-class writing profiles.
- Recognition vocabulary (up to 50 terms), remembered spelling corrections, and spoken text snippets.
- Latest-result recovery, optional private local history capped at 200 entries, copy and clear controls.
- Local three-second microphone check with quiet-signal and clipping detection; the sample is never uploaded.
- Date-grouped transcript cards with app labels, word counts, inline copy and a Result/Original detail view (voice edits show the spoken Instruction). Latest unsaved results are marked separately.
- Search saved history by text, app, mode or date; combine search with All / Dictation / Voice edit filters. Export filtered history as JSON or the current result as text. New exports use owner-only permissions.
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

For Sarvam, enter your API key from [Sarvam's dashboard](https://dashboard.sarvam.ai/) in **Profile & settings → Connections**. Save settings. Writing features use the same key and require access to the `sarvam-105b` chat model. They consume additional API credits. Enable **Polish dictation** in Writing if desired; raw dictation remains the default.

The app requires Hyprland 0.55+ with the Lua configuration API. Other compositors are not currently supported. `ffmpeg` is needed for recordings longer than 25 seconds; these are split into 24-second requests and combined before writing/pasting. This is not live streaming and may have small boundary recognition errors.

## Profile and guided setup

The main sidebar contains **History** and **Text to Audio**. Click the **Profile & settings** button at the bottom to open Profile, General, Connections, Writing, Vocabulary, Snippets or Shortcuts. Technical provider details are collapsed under **Connections → Advanced provider settings**.

**Profile** contains eight saved appearance choices with live preview: Midnight, Graphite, Deep Ocean, and Cinder (dark); Paper, Porcelain, Ivory, and Sage (light). Each light palette has matching accents and SVG icons: cobalt/violet for Paper, sapphire/plum for Porcelain, bronze/burgundy for Ivory, and emerald/teal for Sage. Open **Profile & settings → Your profile → Appearance** to compare palette previews and save your choice. Profile also contains a local display name, the default opening page, and whether advanced connection fields should be expanded. The local workspace can optionally connect to a Bol account using Supabase email-code sign-in and manual preference sync. Signing in does not isolate local workspaces or sign in to speech providers. See [Supabase account setup](supabase/README.md).

For a first installation without configured speech access, Bol opens a setup assistant. You can also open it later from **Profile → Open setup assistant** or **Connections → Open setup assistant**.

- **Sarvam cloud:** the assistant opens Sarvam's key-management page in your default browser. Sign in there, create/copy a connection key once, then paste it into Bol (or click Paste copied key). Bol saves the key privately. The assistant does not read browser cookies, scrape keys, or automatically create credentials. Saving a key is not a live API-authentication test.
- **Local Whisper:** the assistant detects your existing installation and model and validates their paths. No browser account or API key is required for local dictation. An English-only model requires English/auto language selection.

Sarvam's [public authentication documentation](https://docs.sarvam.ai/api-reference/authentication) requires manually generated subscription keys; it does not document delegated consumer OAuth for this use case. A browser session alone cannot authorize Bol API calls. Fully keyless Bol sign-in would require a separately hosted Bol account/backend or an official provider authorization flow; the optional Supabase Bol account syncs preferences but does not proxy or pay for Sarvam API usage. Sarvam OAuth is not implemented here. ElevenLabs separately supports browser sign-in through its official CLI, as described below.

## Speech and writing providers

Select the speech engine in **General**. Open **Profile & settings → Connections** to configure credentials, local paths, and the writing engine. Speech and writing providers are independent, and their API keys are stored separately in your private settings file.

- **Sarvam:** existing default. Your saved key and preferences are preserved. Enter the Sarvam key in Providers.
- **Local whisper.cpp:** choose your `whisper-cli` executable and GGML model, or use **Detect installed Whisper**. The app detects an existing `~/.local/share/whisper-dictation` setup or `whisper-cli` on PATH. It runs the whole recording locally and stops inference on cancellation. No model is downloaded automatically.
- **Compatible speech API:** enter the full multipart transcription endpoint URL, model ID, and its own key. The response must contain a JSON `text` field. For example, [Groq's speech endpoint](https://console.groq.com/docs/speech-to-text) is `https://api.groq.com/openai/v1/audio/transcriptions`, with model `whisper-large-v3-turbo`.
- **Compatible writing API:** enter the full `chat/completions` URL, model ID, and its own key. The server must accept `model`, `messages`, `temperature`, and `max_tokens`, and return `choices[0].message.content`. HTTPS is required for remote APIs; unauthenticated HTTP endpoints on localhost are supported for local servers.

Local Whisper's `.en` models are English-only. Select **English** or **Detect automatically** for `ggml-small.en.bin`. To dictate Punjabi or other languages, choose a multilingual Whisper model instead. Local Whisper supports original-language transcription and English translation; mixed-script and Roman transliteration remain Sarvam features. Compatible speech endpoints currently use transcription only.

With local speech, **AI writing with local speech** is **off by default**, even if Polish was previously enabled. This keeps ordinary local dictation offline. Enable it explicitly in Providers to use polish or voice editing with your chosen writing endpoint. This may send text off-device if that endpoint is remote. Local corrections, snippets, clipboard insertion and history continue to work without network access.

The compatible APIs have been tested against a local protocol fixture; individual cloud providers may differ in supported models and options. There is no silent fallback from local to cloud.

## ElevenLabs browser sign-in

Bol can use the [official ElevenLabs CLI browser authorization flow](https://elevenlabs.io/docs/eleven-agents/operate/cli). This does not scrape the provider website or copy credentials into Bol settings.

1. Open **Profile & settings → Connections**.
2. Choose **Install sign-in helper** if needed (requires Node.js/npm; installs pinned `@elevenlabs/cli@1.12.1` in Bol's local tools directory). The helper is already installed on the development machine.
3. Click **Sign in with ElevenLabs** and complete authorization in your browser.
4. Use **Check connection**, then choose **ElevenLabs** as the speech engine in **Preferences** and save.

The helper manages its own credential storage, using an OS keyring when available or its documented private-file fallback. **Disconnect ElevenLabs** runs the helper's logout operation; it does not close your provider account. Environment-supplied ElevenLabs credentials can still be used by the helper independently of its saved login.

The default speech model is `scribe_v2`, configurable under Advanced provider settings. Original-language transcription is supported; billing and credits belong to your ElevenLabs account. OAuth login itself has not been performed for you, and live account transcription must be verified after your authorization. Tests cover helper invocation/status, output handling and request construction.

## Window controls

The title bar has **Minimize**, **Hide**, and **Close** controls. Their icons are white in dark palettes and dark ink in light palettes for contrast. Hide keeps the window and unsaved state in memory; reopening Bol from its launcher restores the same window. Hyprland does not implement conventional minimization, so Minimize uses Hide there. Close closes settings and stops its preview playback, while the separate dictation daemon remains available.

The settings menu is rendered inside the app overlay rather than as an unconstrained desktop popup, and uses a slim overlay scrollbar when needed.

## Text to Audio

Open **Text to Audio** from the sidebar. Type or paste text, choose a language, voice and speed, then click **Generate audio**. You can also use **Use latest transcript** or **To audio** on a History card. These shortcuts only fill the editor; generation always requires a click.

This uses [Sarvam Bulbul v3](https://docs.sarvam.ai/api-reference/text-to-speech/convert) with the existing Sarvam API key from Providers. Text is sent to Sarvam and generation may use API credits, even if local Whisper is selected for dictation. Supports English, Hindi, Punjabi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati and Odia, with up to 2500 characters per request. Speaking speed ranges from 0.5 to 2.0.

For the audio's delivery, choose a **Style preset** (calm, warm, professional, energetic promo, storytelling or dramatic narration). Presets select a stock voice, pace and variation setting without an extra API request.

You can also describe the delivery in the instruction field, then click **Apply instructions**. For example: “Warm and reassuring, slightly slower, with a professional tone.” This uses your selected writing API to suggest valid voice, pace and expressiveness settings. You can inspect and adjust them before **Generate audio**. Instructions are not read aloud, and the script is never sent to the style-planning model or rewritten. Editing the controls or instructions invalidates a pending suggestion so late responses cannot overwrite your changes.

This maps your request to Bulbul v3's supported controls; it is not a free-form emotion engine. Exact emotions, whispering, sound effects, music and arbitrary acting directions are not guaranteed. Expressiveness controls variation, not a precise emotional intensity. Style planning can consume additional writing-API credits.

After generation, click **Play**, **Stop**, or **Save WAV**. Playback uses `pw-play`. Generated audio is not played automatically. Temporary clips are private and removed when the settings window closes; use Save WAV to keep a copy. Cancelling generation discards a late result but cannot recall a request already sent to the API. This first integration uses stock voices, not voice cloning.

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
- **F10:** select text, press F10, speak an editing instruction, then press F10 again. You can also finish with F8. With review enabled (the default), open Bol and click **Review edit** to inspect or change the proposal. **Approve and insert** explicitly focuses the original window and rechecks its selection; if it changed, the result is copied for manual paste. **Copy only** copies the proposal but leaves it pending; discard it when finished. Closing the review window also leaves it pending. F9 discards it. With no selection, Bol drafts from your instruction.

Keep the original text box focused and leave the selection unchanged. If the app or captured selection changes, Bol copies the result for manual paste. The latest result is available in **History → Refresh** even with disk history disabled. `bol copy-last` also recovers it. Latest-result memory is cleared when the daemon exits.

## Personalize

Settings use a native GTK 4 workspace with neutral dark surfaces, a sidebar, grouped controls, and a consistent set of bundled SVG line icons. If GTK bindings are unavailable, Bol falls back to its Tk settings window. The recording indicator uses Tk.

Open **Bol Voice Typing** from your app launcher, or run `~/.local/bin/bol settings`. Settings are now inside the profile menu at the bottom of the sidebar. Use **General → Test microphone** for a local three-second level check; it does not use API credits.

- **General:** speech engine, language, output mode, microphone node name (blank uses the PipeWire default), recording limit, paste, and local-history preference.
- **Providers:** Sarvam key, local Whisper paths, compatible API endpoints and separate keys, and the local-speech writing opt-in.
- **Writing:** review-before-insert (on by default), optional polish, global rules and per-app rules. Profiles use exact app classes, e.g. `Chatgpt => Preserve code identifiers; be concise`. The app can show currently open app classes. Writing rules apply to AI polish and voice editing, not raw dictation.
- **Vocabulary:** one recognition hint per line. Add explicit corrections such as `sara vam => Sarvam`. Corrections match whole words/phrases and preserve unrelated text. Recognition hints go to the speech API.
- **Snippets:** e.g. `my signature => Regards,\nSarbjeet`. Say only the trigger phrase to expand it. Use literal `\n` for line breaks.
- **History:** browse cards grouped by local date, search and filter by interaction type, copy a card, or open View transcript to compare the final result with the original speech. In voice-edit entries, Instruction is what you asked Bol to do. The detail view supports temporary edits, copying, text export and remembered corrections; preview edits do not alter saved history. Export history respects both search and type filters. History saving must be enabled in General to retain new results; unsaved session results are clearly marked.
- **Shortcuts:** customize keys, toggle hold-to-talk, and choose an editing key.

## Privacy and recovery

Audio goes to the selected speech API for cloud recognition. With local whisper.cpp, audio stays on your computer. AI polish sends the dictated text and writing rules to Sarvam. Voice editing also sends the text explicitly copied from your selection. There is no automatic screen capture or background reading of app contents.

Settings live at `~/.config/bol-linux/settings.json`, including the API key, with owner-only file permissions. Temporary audio is deleted after processing. History is **off by default**. When enabled it stores the original transcript, final text, app class and UTC timestamp in an owner-only `history.sqlite3`, retaining the newest 200 results. Disabling history stops future storage; use Clear history to remove existing entries. Retention can be limited to 24 hours, 7 days or 30 days in General. Expiration runs when history is read or written; no background deletion runs while Bol is closed. Pending, unapproved voice edits are kept only in memory and are not added to history. Text is also placed on the clipboard and may be retained by your clipboard manager.

Cancellation prevents pending results from being pasted or added to history, and stops further chunk uploads, but cannot recall an API request already sent. If polish fails, raw dictation is recovered. If editing fails, selected text is left intact. A paste shortcut being accepted does not prove that an application's text widget accepted the text; recover the result from History or `bol copy-last` if necessary.

## Current limits compared with Kivi

[Kivi's official site](https://heykivi.ai/) advertises Mac dictation, correction memory, app-specific personas and voice text editing; it currently lists a Windows waitlist.

Bol implements the corresponding basic workflows using public APIs, with these remaining gaps:

- Corrections are remembered explicitly through the Vocabulary tab or Remember correction button. Passive learning from arbitrary edits is not implemented.
- Voice formatting produces plain text/Markdown; it cannot reliably apply rich formatting such as actual bold inside every editor.
- It uses selection capture and keyboard paste. Browser fields, unusual editors, XWayland apps and terminals can behave differently. Selection capture is intentionally skipped in terminals to avoid Ctrl+C interrupting a command; voice editing there drafts from speech.
- No screen-context reading, live streaming captions, system-tray menu, automatic updater, offline model, automatic cloud synchronization or cross-compositor packaging yet. Manual preference sync is available after configuring Supabase.
- Model output quality and latency are not guaranteed to match Kivi's private prompts or services.

## Development

```sh
python -m unittest discover -s tests -v
python -m py_compile kivi_linux.py bol_features.py bol_ui.py
bash -n install.sh
```

`kivi_linux.py` provides recording, IPC and insertion. `bol_features.py` handles vocabulary/snippets, writing API and SQLite history. `bol_providers.py` implements local whisper.cpp and compatible API adapters. `bol_gtk.py` contains the native GTK settings workspace. `bol_ui.py` provides the fallback settings window, shortcut helpers, and recording indicator. The app uses Python's standard library plus Tk and system executables.

`bol doctor` checks dependencies, and `bol status` shows recording/processing state. The daemon starts on demand. After an upgrade, stop the existing daemon before starting the new version so it imports the updated modules. It handles SIGTERM by stopping its recorder and cleaning temporary audio.

## Remove

Remove the Bol bindings from your Hyprland config and reload. Stop the Bol daemon, then delete `~/.local/bin/bol`, `~/.local/share/bol-linux`, and `~/.local/share/applications/bol-linux.desktop`. Optionally remove `~/.config/bol-linux` including settings and history.

See [ROADMAP.md](ROADMAP.md) for the next development milestones and their completion criteria.
