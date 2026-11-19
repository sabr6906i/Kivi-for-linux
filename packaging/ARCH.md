# Arch Linux and Hyprland prerelease

Build a native package using an explicit committed snapshot:

```sh
./scripts/build-arch.sh --version 0.1.0alpha1 --tag v0.1.0-alpha.1 --ref HEAD --output dist/arch
```

The build requires `makepkg` and the dependencies declared in the generated `PKGBUILD`. The script never installs dependencies, uses sudo, publishes, or changes the current desktop. Commit the intended release files before building: the source archive uses `git archive`, so uncommitted edits, local configuration, API keys, account sessions, and untracked files are excluded.

Artifacts include:

- `bol-linux-0.1.0alpha1-1-any.pkg.tar.zst`: the installable Arch package.
- `bol-linux-0.1.0alpha1.tar.gz`: source archive, published alongside the binary package.
- `PKGBUILD` and `.SRCINFO`: a materialized source recipe with the archive's real SHA-256 digest.
- `SHA256SUMS` and `SOURCE_COMMIT`: integrity checks and the exact source revision.

The recipe's source URL points to the corresponding GitHub Release source **asset**, rather than GitHub's automatically generated tag archive. Upload the exact generated archive without recompressing it, or its SHA-256 digest will no longer match. SHA-256 checks detect corruption, not publisher identity; signing releases is a separate future step.

Install the built package using pacman:

```sh
sudo pacman -U ./dist/arch/bol-linux-0.1.0alpha1-1-any.pkg.tar.zst
/usr/bin/bol settings
/usr/bin/bol doctor
```

The package installs a desktop launcher and uses `/usr/bin/bol`; its Python modules and SVG assets live under `/usr/lib/bol-linux`. Per-user settings, account sessions and transcript history remain under the existing user configuration directory. It does not copy development-machine API keys, recordings, history, model files, the ElevenLabs CLI, or a Python virtual environment.

If an older manual install is present, `~/.local/bin/bol` may take precedence over `/usr/bin/bol` on `PATH`. Check `command -v bol` and remove the old manual launcher only after confirming that the native package works. The package does not delete or overwrite per-user files.

Configure global shortcuts explicitly in Hyprland; no package install hook edits the user's desktop configuration. Use the packaged `bol` launcher on `PATH`. The daemon starts on demand when a dictation command is sent.

## Release boundaries

This is prerelease packaging. A successful package build and file inspection do not replace a fresh Arch+Hyprland runtime test covering microphone capture, F8/F9/F10, text insertion and cancellation. GNOME/KDE support must be tested separately; a package is not evidence of desktop compatibility.

The package declares MIT and installs the repository's `LICENSE` under `/usr/share/licenses/bol-linux/`. No AUR package has been submitted by this script. Review the [Arch package guidelines](https://wiki.archlinux.org/title/Arch_package_guidelines) and [AUR submission requirements](https://wiki.archlinux.org/title/AUR_submission_guidelines) before submitting the generated recipe.
