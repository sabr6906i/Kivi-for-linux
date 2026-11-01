# Bol — voice typing for Linux

Independent Sarvam-powered dictation prototype for Arch Linux / Hyprland Wayland. Not affiliated with Sarvam or Kivi.

## Start

Run `./install.sh`, then launch **Bol Voice Typing** from your app launcher or run `~/.local/bin/bol settings`. Enter your Sarvam API key locally and save. Audio is uploaded to Sarvam; API usage may incur charges. Get a key at https://dashboard.sarvam.ai/.

Add these bindings to your Hyprland Lua configuration (for example, `~/.config/hypr/custom/keybinds.lua` if your main config loads it):

```lua
hl.bind("F8", hl.dsp.exec_cmd("$HOME/.local/bin/bol toggle"), { description = "Bol: toggle dictation" })
hl.bind("F9", hl.dsp.exec_cmd("$HOME/.local/bin/bol cancel"), { description = "Bol: cancel dictation", ignore_mods = true })
```

Run `hyprctl reload` after saving. Shortcuts:

- **F8** starts recording; press again to finish.
- **F9** cancels recording or discards a pending result.

Keep your target app focused. Recording stops automatically at 25 seconds. Transcription is copied to the clipboard, replacing its previous contents. The app attempts Ctrl+V only if the original window remains focused. If focus changed or paste fails, paste manually. Terminals may require Ctrl+Shift+V. This version uses toggle recording, not hold-to-talk.

## Requirements

Hyprland 0.55 or newer with Lua configuration, Python 3 with Tk, PipeWire (`pw-record`), `wl-clipboard`, Hyprland and optionally `libnotify`. On Arch: `sudo pacman -S python tk pipewire wl-clipboard libnotify`.

Settings are stored at `~/.config/bol-linux/settings.json` with owner-only file permissions, including the API key. Audio lives temporarily in the runtime directory and is deleted after each request; there is no transcript history. Text remains in your clipboard and may be retained by your clipboard manager. Cancellation during upload discards the result but cannot recall audio already sent.

`bol doctor` checks dependencies; `bol status` checks service state. The service starts on demand. Restart it after updating the app. No API credentials are included in this repository.

## Validation

`python -m unittest discover -s tests -v`

Live audio upload requires your API key. Rewriting, vocabulary memory, offline recognition, hold-to-talk, tray integration and packaging are future work.

## Remove

Remove the two Bol bindings from the custom keybind file and reload Hyprland. Delete `~/.local/bin/bol`, `~/.local/share/bol-linux`, `~/.local/share/applications/bol-linux.desktop`, and optionally `~/.config/bol-linux`. Stop the Bol daemon before removing files.
