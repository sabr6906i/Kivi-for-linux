%{!?bol_version:%global bol_version 0.1.0}
%{!?bol_release:%global bol_release 0.1.alpha1}
%global bol_appdir %{_prefix}/lib/bol-linux

Name:           bol-linux
Version:        %{bol_version}
Release:        %{bol_release}%{?dist}
Summary:        Linux voice typing and writing workspace
License:        MIT
URL:            https://github.com/sabr6906i/Kivi-for-linux
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       gtk4
Requires:       python3-tkinter
Requires:       pipewire-utils
Requires:       wl-clipboard
Requires:       libnotify
Requires:       ffmpeg-free
Recommends:     xdg-desktop-portal
Recommends:     xclip
Recommends:     xdotool
Recommends:     xprop

%description
Bol provides dictation, reviewable voice editing, text-to-speech, and optional
account preference sync. Speech engines include Sarvam, compatible APIs,
ElevenLabs through its helper, and a separately configured local whisper.cpp.
Hyprland is the primary desktop integration. Other desktops may use clipboard
output and manually assigned shortcuts; see the desktop support matrix.


%prep
%setup -q

%build
# Python source package; no native compilation.

%install
install -d %{buildroot}%{bol_appdir}/icons %{buildroot}%{bol_appdir}/themes
install -m 644 kivi_linux.py %{buildroot}%{bol_appdir}/bol.py
install -m 644 bol_*.py %{buildroot}%{bol_appdir}/
install -m 644 icons/*.svg %{buildroot}%{bol_appdir}/icons/
install -m 644 themes/*.svg %{buildroot}%{bol_appdir}/themes/
install -d %{buildroot}%{_bindir} %{buildroot}%{_datadir}/applications
printf '#!/bin/sh\nexec /usr/bin/python3 %{bol_appdir}/bol.py "$@"\n' > %{buildroot}%{_bindir}/bol
chmod 755 %{buildroot}%{_bindir}/bol
cat > %{buildroot}%{_datadir}/applications/io.github.sabr6906i.Bol.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Bol Voice Typing
Comment=Voice typing and writing workspace
Exec=bol settings
Icon=io.github.sabr6906i.Bol
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=true
DESKTOP
install -d %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -m 644 icons/brand.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.sabr6906i.Bol.svg

%files
%license LICENSE
%{_bindir}/bol
%{bol_appdir}/
%{_datadir}/applications/io.github.sabr6906i.Bol.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.sabr6906i.Bol.svg
%doc README.md ROADMAP.md docs/PACKAGES.md docs/DESKTOPS.md

%changelog
* Thu Nov 19 2026 Bol contributors - 0.1.0-0.1.alpha1
- Initial experimental Fedora package; desktop support must be validated separately.
