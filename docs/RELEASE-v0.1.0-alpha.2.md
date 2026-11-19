# Bol v0.1.0-alpha.2 — offline models and security updates

Updated Linux preview packages for Arch/Hyprland, Ubuntu/Debian and Fedora.

## New

- Download multilingual OpenAI Whisper Tiny (78 MB), Base (148 MB) and Small (488 MB) from Profile & settings → Connections. These whisper.cpp conversions run locally without an account or API key; a working whisper-cli executable is still required.
- Downloads show progress, support cancellation, verify pinned SHA-256 and exact size, and select only complete verified models. Click Save changes after download. No model weights are bundled in the installers or downloaded automatically.

## Security fixes

- Reject provider API redirects to avoid forwarding credentials; bound text/TTS response sizes.
- Reject unsafe runtime directories and keep the daemon running when a client disconnects during its response.
- Require manual pasting of multiline/control-character text into recognized terminals.
- Enable SQLite secure deletion on every history connection.
- Pin GitHub Actions to verified commit hashes.

See [the security review](https://github.com/sabr6906i/Kivi-for-linux/blob/v0.1.0-alpha.2/docs/SECURITY-REVIEW-2026-11-19.md) for scope and remaining risks. This release is not a security certification; local credentials remain in private plaintext files and packages are not independently signed.

## Downloads

- Arch: `bol-linux-0.1.0alpha2-1-any.pkg.tar.zst`
- Ubuntu/Debian: `bol-linux_0.1.0.alpha2_all.deb` (package metadata version `0.1.0~alpha2`)
- Fedora: `bol-linux-0.1.0-0.1.alpha2.fc45.noarch.rpm` (Fedora runner suffix may vary)
- Source archive, PKGBUILD, SRCINFO, source commit and SHA256SUMS are included.

Upgrade with your normal package manager (`pacman -U`, `apt install ./…deb`, or `dnf install ./…rpm`), then restart Bol and its background daemon when no recording is in progress. User settings are preserved. If an earlier manual installation exists, check `command -v bol`: `~/.local/bin/bol` may shadow `/usr/bin/bol`.

## Validation and limitations

105 tests passed locally, including six isolated PostgreSQL RLS checks. CI runs the suite on Ubuntu, Fedora and Arch (PostgreSQL integration tests require separate local opt-in), installs each package, and verifies that the packaged model catalog imports. Ubuntu/Fedora additionally run GTK launch and own-clipboard checks under an isolated X11 display with simulated GNOME/KDE metadata.

Hyprland remains the primary desktop. GNOME/KDE Wayland support remains clipboard-first preview. These package checks do not establish physical microphone, shortcut or cross-app insertion support on every distribution. Flatpak is not included; AUR/Flathub listings have not been submitted.
