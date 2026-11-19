# Debian/Ubuntu and Fedora packages

These package builders produce native installers without modifying the build host or the user's home directory. They package the GTK workspace, Python modules, SVG icons, themes, launcher, desktop entry, and documentation. The optional ElevenLabs CLI and whisper.cpp binaries/models are not bundled; configure them separately after installation.

A package's existence is not evidence of full desktop compatibility. Hyprland is the primary integration. Consult the desktop support matrix before relying on global shortcuts or automatic insertion under GNOME/KDE. On other desktops, use the available clipboard workflow and assign supported shortcuts manually.

## Debian and Ubuntu

Build using Python 3.10+; root and Debian tools are not needed:

```sh
SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)" \
  python3 scripts/build-deb.py --version '0.1.0~alpha1' --output dist
```

The result is `dist/bol-linux_0.1.0~alpha1_all.deb`. Its architecture is `all` because it ships Python source rather than native binaries. Debian prerequisites are declared in the package, including GTK4/PyGObject, PipeWire tools, wl-clipboard, notifications, and ffmpeg.

Install on a Debian/Ubuntu machine with a graphical user session:

```sh
sudo apt install ./bol-linux_0.1.0~alpha1_all.deb
bol settings
```

`apt` resolves dependencies; `dpkg -i` alone may leave missing dependencies. The package requires a distribution version that provides GTK4 and Python 3.10 or newer. Removal with `sudo apt remove bol-linux` removes system files and leaves private settings/history in the user's configuration directory.

Inspect without installing:

```sh
dpkg-deb --info dist/bol-linux_0.1.0~alpha1_all.deb
dpkg-deb --contents dist/bol-linux_0.1.0~alpha1_all.deb
```

On a non-Debian build host, `ar t package.deb` and `ar p package.deb data.tar.gz | tar -tzf -` inspect the same archive. The builder includes deterministic gzip/tar/ar metadata and a `md5sums` control member. Use the same `SOURCE_DATE_EPOCH` and source tree for reproducible artifacts.

## Fedora RPM

`rpmbuild` must already be present. The build script deliberately refuses to install it. In a disposable Fedora CI container, provision the build tools:

```sh
dnf install -y rpm-build python3
SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)" \
  python3 scripts/build-rpm.py --version 0.1.0 --release 0.1.alpha1 --output dist
rpm -qip dist/bol-linux-*.noarch.rpm
rpm -qlp dist/bol-linux-*.noarch.rpm
```

The script creates an isolated temporary rpmbuild tree, constructs a source archive containing only app assets and documentation, runs `rpmbuild -bb`, and copies the resulting noarch RPM to `dist`. Fedora may append its distribution suffix (`.fcNN`) to the filename. Fedora dependencies use Fedora package names (`python3-gobject`, `python3-tkinter`, `pipewire-utils`, `ffmpeg-free`, and others); they are not copied from Debian names.

Install on Fedora:

```sh
sudo dnf install ./bol-linux-*.noarch.rpm
bol settings
```

No package script runs the application as root, enables a system daemon, edits a user's Hyprland configuration, or installs speech API credentials. Users launch the app in their own session and assign supported shortcuts. Distribution packages do not bundle Python or GTK; their package managers supply those runtime dependencies.

## Release checks

Build public artifacts from a clean checkout of the release tag, not a development tree containing uncommitted user changes. The prerelease tag `v0.1.0-alpha.1` maps to Debian version `0.1.0~alpha1`, RPM version/release `0.1.0-0.1.alpha1`, and an Arch prerelease version. Debian's tilde and RPM's `0.` release prefix ensure the later `0.1.0` stable release upgrades normally.

Before claiming support, install and launch each artifact in a disposable target-distribution session. Verify microphone recording, history, provider connection, shortcuts, text insertion or documented clipboard fallback, and uninstall behavior. Archive inspection and mocked desktop tests alone are insufficient for GNOME/KDE release certification. RPM signatures and a maintained apt/dnf update repository are separate release tasks; a GitHub download does not create either.

## Automated prereleases

`.github/workflows/linux-release.yml` builds on clean Ubuntu, Fedora and Arch runners. A manual workflow dispatch with `publish=false` only creates workflow artifacts. With `publish=true`, the final job publishes an explicitly labelled GitHub prerelease **only after all three build/test jobs pass**. Use tag `v0.1.0-alpha.1` for this initial preview. Native GNOME/KDE compositor support remains preview even when the Xvfb GTK checks pass.

The source snapshot is the workflow's checked-out commit. Local uncommitted edits, account sessions and provider keys do not enter release assets. All uploaded assets receive a fresh SHA-256 manifest; no signing key is configured in this version.
