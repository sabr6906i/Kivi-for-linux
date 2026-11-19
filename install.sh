#!/usr/bin/env bash
set -euo pipefail
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/bol-linux"
bin_dir="$HOME/.local/bin"
mkdir -p "$app_dir" "$bin_dir" "${XDG_DATA_HOME:-$HOME/.local/share}/applications"
install -m 755 "$(dirname "$0")/kivi_linux.py" "$app_dir/bol.py"
install -m 644 "$(dirname "$0")/bol_features.py" "$(dirname "$0")/bol_ui.py" "$(dirname "$0")/bol_gtk.py" "$(dirname "$0")/bol_providers.py" "$(dirname "$0")/bol_audio.py" "$(dirname "$0")/bol_elevenlabs.py" "$(dirname "$0")/bol_themes.py" "$(dirname "$0")/bol_accounts.py" "$(dirname "$0")/bol_models.py" "$(dirname "$0")/bol_desktop.py" "$app_dir/"
cat > "$bin_dir/bol" <<EOF
#!/bin/sh
exec /usr/bin/python3 "$app_dir/bol.py" "\$@"
EOF
chmod 755 "$bin_dir/bol"
mkdir -p "$app_dir/icons" "$app_dir/themes"
install -m 644 "$(dirname "$0")"/themes/*.svg "$app_dir/themes/"
install -m 644 "$(dirname "$0")"/icons/*.svg "$app_dir/icons/"
cat > "${XDG_DATA_HOME:-$HOME/.local/share}/applications/bol-linux.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Bol Voice Typing
Comment=Voice dictation for Linux using Sarvam
Exec="$bin_dir/bol" settings
Icon=audio-input-microphone
Terminal=false
Categories=Utility;Accessibility;
EOF
printf 'Installed Bol. Open Preferences for desktop shortcut setup; see docs/DESKTOPS.md.\nOpen settings: %s/bol settings\n' "$bin_dir"
