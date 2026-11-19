# Flatpak feasibility and permission investigation

Status: **investigated, not a shipped Flatpak**. Native packages are the supported release route for now. No blanket host/session-bus permissions have been added to make a sandbox appear to work.

## Proposed permissions and missing implementations

| Feature | Suitable approach | Current Bol gap |
|---|---|---|
| GTK windows | `--socket=wayland`, `--socket=fallback-x11`, `--device=dri` | Straightforward, but needs runtime-build validation. |
| Accounts, STT/TTS and writing APIs | `--share=network` | Standard HTTPS calls work in principle; test certificates and offline mode in the runtime. |
| Microphone + playback | `--socket=pulseaudio` with a PulseAudio-compatible recorder/player | Current `pw-record` / `pw-play` use the native PipeWire socket. Granting the PulseAudio socket alone does **not** make those commands work. Implement a PulseAudio-compatible backend and bundle the required tools, or separately validate a permission-scoped PipeWire approach. A screen-capture PipeWire stream is not a microphone backend. |
| Local Whisper | FileChooser/document portal; bundle a compatible whisper binary | Existing absolute host binary paths cannot run inside the sandbox. Models must be selected/imported and a sandbox-compatible executable shipped. |
| Global shortcuts | `org.freedesktop.portal.GlobalShortcuts` | Need create/bind/activate/deactivate portal sessions; capabilities differ by desktop/backend. Native GSettings/KDE shortcuts are not a sandbox substitute. |
| Copy Bol’s own result | GTK/GDK clipboard after an explicit user action | Prefer the toolkit clipboard instead of invoking host `wl-copy`. Copying Bol’s own text does not itself require a RemoteDesktop session. |
| Read text from another app | User copies the selection first; a compatible clipboard portal session if background access is required | There is no general selected-text reading portal. The Clipboard portal shares clipboard contents, not arbitrary selections, and depends on another portal session. `wl-paste` needs protocols not generally exposed to sandbox clients. |
| Automatic typing/paste into another app | User-approved RemoteDesktop portal session / supported input transport | Current Hyprland IPC is host-specific; no portable Wayland input backend exists in this release. The portal must be available and user-approved. |
| Account session/preferences/history | App-private XDG directories | Fits normal Flatpak storage. File permissions remain private. Must test migration from native paths. |
| Import/export | GTK native file chooser with portal integration | Verify selected-document access for exports and WAV playback. No blanket home permission is needed. |
| Notifications/browser auth | Notification/OpenURI portals | Test with the chosen runtime; the optional ElevenLabs host CLI is not available automatically inside the sandbox. |

Use the stable app ID `io.github.sabr6906i.Bol` for a future manifest, metadata, desktop file, and portal identity. Native GTK and package desktop files now use this ID; a future sandbox manifest must use it as well. MIT licensing is now provided in the repository.

## Actual host probe

Run:

```sh
python scripts/probe-flatpak-portals.py
```

On the development Hyprland/Wayland host on 2026-11-19:

- PipeWire socket present.
- GlobalShortcuts portal interface advertised.
- RemoteDesktop and Clipboard portal interfaces **not advertised**.
- `flatpak` and `flatpak-builder` not installed.

An advertised interface is not proof of permission or correct behavior. The probe performs introspection only: it does not record audio, request input access, install anything, or create portal sessions. Native GNOME/KDE desktop testing and a sandbox build are still required.

## Release gates

1. Implement and test audio recording/playback in the sandbox. Treat microphone access as a sensitive capability; do not imply an individual recording prompt is guaranteed by `--socket=pulseaudio`.
2. Bundle local Whisper support or disable it with an accurate explanation.
3. Implement the GlobalShortcuts portal and graceful unsupported-backend handling.
4. Implement a user-approved input/clipboard portal path, or explicitly ship clipboard-only dictation with user-triggered Copy actions.
5. Remove dependencies on host Hyprland sockets, GSettings writes, host executables, and host home paths.
6. Add a pinned runtime manifest, AppStream metadata, icons, license, and integration tests.
7. Test microphone capture, stopping/canceling, sign-in/sync, file export, and clipboard/input behavior on actual GNOME and KDE sessions.
8. Submit to Flathub only after a real sandbox build and runtime checks pass.

## Primary references

- [Flatpak sandbox permissions](https://docs.flatpak.org/en/latest/sandbox-permissions.html): PulseAudio includes microphone access; Wayland/X11/network permissions and restrictions.
- [GlobalShortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html).
- [Clipboard portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Clipboard.html): extends compatible RemoteDesktop/InputCapture sessions, not a standalone clipboard permission.
- [RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html).
- [Flathub submission requirements](https://docs.flathub.org/docs/for-app-authors/requirements).
