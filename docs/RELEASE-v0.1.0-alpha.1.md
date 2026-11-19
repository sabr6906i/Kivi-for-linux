Bol's first native Linux package preview, distributed under the MIT license.

## Downloads

- Arch Linux / Hyprland: `bol-linux-0.1.0alpha1-1-any.pkg.tar.zst`; install with `sudo pacman -U ./bol-linux-0.1.0alpha1-1-any.pkg.tar.zst`.
- Ubuntu / Debian: `bol-linux_0.1.0.alpha1_all.deb`; install with `sudo apt install './bol-linux_0.1.0.alpha1_all.deb'`.
- Fedora: the `.noarch.rpm` asset; install with `sudo dnf install ./bol-linux-0.1.0-0.1.alpha1*.noarch.rpm`.
- Source archive, checksummed `PKGBUILD`, `bol-linux.SRCINFO`, exact `SOURCE_COMMIT`, and `SHA256SUMS` are provided alongside the packages.

Download the checksum file and run `sha256sum -c SHA256SUMS --ignore-missing` from the download directory. Packages and checksum files are not GPG-signed in this preview.

If a previous manual installation exists, `~/.local/bin/bol` may shadow `/usr/bin/bol`. Check `command -v bol`, and use `/usr/bin/bol settings` to test the native package before removing the old launcher. User settings/accounts/history are preserved; private user files are never included in a package.

## Desktop support

Hyprland retains focus-checked insertion and selection-based voice editing. GNOME/KDE Wayland use a preview clipboard-first path: dictate, open History and Copy when necessary, and paste into the target app. GTK Copy uses the toolkit clipboard; background command-line clipboard transfer can be unavailable on some Wayland desktops. GNOME custom shortcuts can be set up from Bol; KDE uses System Settings. Voice editing copied text is available through Writing or `bol edit-clipboard` where clipboard reading is supported. X11 has an optional xdotool/xclip adapter.

The pipeline builds native packages, installs Debian/Fedora packages in clean runner environments, runs unit tests, and launches GTK under Xvfb with simulated GNOME/KDE environment metadata. The package pipeline's Xvfb checks do not certify a native desktop session. Separate real nested Wayland checks have also passed for [GNOME Shell 46.0](https://github.com/sabr6906i/Kivi-for-linux/actions/runs/44554729029/job/135667604117) and [KWin 5.27.11](https://github.com/sabr6906i/Kivi-for-linux/actions/runs/44554104055/job/135665386726): Bol connected through `GdkWaylandDisplay` and passed welcome-screen/GTK own-clipboard tests. Physical microphone use, global shortcuts, cross-app clipboard ownership, and end-to-end paste workflows still require full desktop testing. No GNOME/KDE automatic insertion claim is made.

## Included

- First-launch welcome and optional Bol account sign-in.
- Automatic account preference sync, reviewable conflicts, private device-local API keys/history.
- Multiple dark/light themes and SVG icons.
- Speech providers, local Whisper integration, voice editing, history, and text-to-audio features.
- Desktop capability reporting and `bol doctor` diagnostics.
- Flatpak permission investigation and a read-only portal probe. A runnable Flatpak and Flathub listing are **not included**.

Cloud speech and writing require each user's own provider access/credits; a Bol account does not provide paid API usage. Local Whisper requires a separately installed compatible binary and model. ElevenLabs sign-in requires its optional helper. See README and docs/DESKTOPS.md for setup and limitations.
