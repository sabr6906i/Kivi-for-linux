#!/usr/bin/env bash
set -euo pipefail
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/bol-linux"
bin_dir="$HOME/.local/bin"
mkdir -p "$app_dir" "$bin_dir" "${XDG_DATA_HOME:-$HOME/.local/share}/applications"
install -m 755 "$(dirname "$0")/kivi_linux.py" "$app_dir/bol.py"
install -m 644 "$(dirname "$0")/bol_features.py" "$(dirname "$0")/bol_ui.py" "$(dirname "$0")/bol_gtk.py" "$app_dir/"
cat > "$bin_dir/bol" <<EOF
#!/bin/sh
exec /usr/bin/python "$app_dir/bol.py" "\$@"
EOF
chmod 755 "$bin_dir/bol"
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
printf 'Installed Bol. Add the F8/F9/F10 Lua bindings from README.md to your Hyprland config.\nOpen settings: %s/bol settings\n' "$bin_dir"
