# Desktop compatibility and verification

Bol distinguishes the Linux distribution (Arch, Ubuntu, Fedora) from the desktop/session (Hyprland, GNOME, Plasma, X11). An installer does not grant another compositor permission to inspect windows or synthesize keyboard input.

## Support matrix

| Session | Recording, providers, history, audio UI | Text delivery | Voice editing | Shortcuts |
|---|---|---|---|---|
| Hyprland / Wayland | Implemented | Focus-checked automatic paste | Captures selection and rechecks it before replacement; review supported | Existing Hyprland Lua setup, toggle or hold-to-talk |
| GNOME / Wayland | Implemented, desktop integration preview | Best-effort background clipboard; explicit Bol Copy fallback | Explicit copied source through `bol edit-clipboard`; reviewed output copied | Installs custom keyboard shortcuts through GSettings, toggle only |
| KDE Plasma / Wayland | Implemented, desktop integration preview | Best-effort background clipboard; explicit Bol Copy fallback | Explicit copied source through `bol edit-clipboard`; reviewed output copied | User adds commands in System Settings → Shortcuts, toggle only |
| GNOME / Plasma / other X11 | Implemented adapter, preview | Focus-checked paste through optional `xdotool`; clipboard through `xclip` | Selection capture/recheck through Ctrl+C | GNOME custom shortcuts or desktop-specific manual commands |

GNOME/Plasma Wayland do not expose an arbitrary other application's focused text field to ordinary desktop apps. Bol does not install a privileged input daemon, change `/dev/uinput` permissions, load a Shell extension, invoke GNOME Shell Eval, or send synthetic keystrokes to a guessed target. No cross-compositor automatic insertion claim is made.

## GNOME and KDE Wayland usage

1. Install Bol and the platform packages for GTK4, PyGObject, Tk (indicator), PipeWire tools, `wl-clipboard`, notifications and FFmpeg.
2. Configure a provider or your local whisper.cpp model.
3. Add a keyboard shortcut for `bol toggle` (record/finish) and `bol cancel`. GNOME can save these through Bol's Shortcuts page; Plasma opens its own shortcut settings.
4. Dictate, then paste the result with Ctrl+V (Ctrl+Shift+V in most terminals). If background clipboard access is unavailable, the latest text remains in Bol History even when saved history is disabled; use its explicit **Copy** action, then paste. Recording on portable Wayland does not require the optional `wl-copy` / `wl-paste` commands.
5. To edit existing text, **copy the intended source first**, then invoke `bol edit-clipboard`, speak the instruction, and invoke it again to finish. Review in Bol, approve/copy the result, and paste it over the intended source yourself. `bol edit` explains that automatic selection capture is unavailable on these sessions.

The GTK UI may supply text through its explicit clipboard action instead of the background helper. `bol edit-clipboard` from the command line intentionally uses the current clipboard because this is an explicit copy-first command; it cannot infer whether an old clipboard item is your intended source. It never automatically replaces a guessed selection or refocuses another window. It accepts at most 24,000 characters.

GNOME custom bindings are scoped to Bol-owned paths, preserve unrelated custom shortcuts, check standard/custom collisions, and restore previous settings on a failed write. They use whichever `bol` launcher is installed, including `/usr/bin/bol` from a native package. KDE configuration files are not rewritten behind System Settings. Hold-to-talk requires key-release integration and is not supported by the GNOME custom-command or Plasma manual-command paths.

## Background clipboard limits on GNOME/Plasma Wayland

`wl-clipboard` works directly with compositors exposing its data-control protocol. Otherwise it may briefly create a popup surface to obtain clipboard access; this can flash, change focus, or fail when the compositor will not focus it. In particular, GNOME background clipboard access must not be assumed to work merely because `wl-copy` is installed. The helper commands have bounded timeouts and no inherited output pipes; failures return the service to Ready and preserve the latest transcript for explicit GTK Copy. Desktop-specific end-to-end clipboard behavior is still a release-test requirement. See the [upstream wl-clipboard manual, BUGS section](https://github.com/bugaevc/wl-clipboard/blob/master/data/wl-clipboard.1).

## X11 prerequisites

`xclip` and `xdotool` are required for the X11 adapter. `xprop` is optional for app-class writing rules. Pure Wayland apps on GNOME/Plasma are **not** treated as X11 just because an XWayland `DISPLAY` exists: `XDG_SESSION_TYPE=wayland` retains clipboard mode. X11 fallback still records through PipeWire; it is not a PulseAudio-only adapter.

## What has been tested

- Existing full unit suite plus desktop adapter tests pass on the development Hyprland host.
- Live, read-only Hyprland checks: session detection, required command discovery, and a valid active-window response.
- Mocked GNOME/Plasma Wayland contracts: no Hyprland dependency, recording startup without clipboard helpers, no inferred focus/injection, copied-source edit mode, clipboard stdin transport, recoverability after transport failure. The full unit suite also passes with a simulated GNOME Wayland environment; that is not a live GNOME session test.
- Mocked X11 contracts: window IDs, xclip stdin, xdotool key/focus commands.
- Mocked GNOME settings contracts: independent Bol paths, conflict detection, rollback, launcher discovery, rejection of unsupported hold-to-talk.

A real GNOME/Plasma or X11 desktop session is not available on the development host. Microphone permissions, indicator behavior, compositor key conflicts, clipboard ownership, and end-to-end recording/paste still require tests on those actual sessions. These targets are **preview**, not a certified live-tested release.

Run `bol doctor` to inspect the detected session and its dependencies. It does not send audio or reveal API keys.

## Portals and Flatpak

The GlobalShortcuts portal can authorize shortcut sessions on supporting desktops. It does not itself grant clipboard access, window inspection, selection capture, or arbitrary input injection. Portal availability and host-app identity differ by desktop/version. This release uses GNOME custom shortcuts and KDE manual shortcuts for native packages; a persistent GlobalShortcuts/RemoteDesktop permission/session implementation is not claimed. Flatpak-specific permission and command-boundary assessment is separate from native package compatibility.

References: [GNOME custom shortcuts](https://help.gnome.org/gnome-help/keyboard-shortcuts-set), [GlobalShortcuts portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html).
