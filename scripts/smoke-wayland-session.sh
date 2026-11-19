#!/usr/bin/env bash
# Real, isolated Wayland compositor smoke, not just XDG_CURRENT_DESKTOP labels.
# Never use the user's session bus, display socket, settings or audio devices.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
desktop=${1:-}
output_dir=${2:-"$repo_root/dist/desktop-preview"}
case "$desktop" in GNOME|KDE) ;; *) echo 'Usage: scripts/smoke-wayland-session.sh GNOME|KDE [LOG_DIRECTORY]' >&2; exit 2;; esac
mkdir -p -- "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
if [[ ${BOL_COMPOSITOR_TEST_INSIDE:-} != 1 ]]; then
    for tool in dbus-run-session python3 wayland-info; do
        command -v "$tool" >/dev/null || { echo "Missing test dependency: $tool" >&2; exit 2; }
    done
    isolated=$(mktemp -d /tmp/bol-wayland-test.XXXXXXXX)
    trap 'rm -rf -- "$isolated"' EXIT
    mkdir -m700 "$isolated/runtime" "$isolated/config" "$isolated/cache" "$isolated/data"
    env -u DISPLAY -u WAYLAND_DISPLAY -u DBUS_SESSION_BUS_ADDRESS -u HYPRLAND_INSTANCE_SIGNATURE \
        BOL_COMPOSITOR_TEST_INSIDE=1 \
        XDG_RUNTIME_DIR="$isolated/runtime" XDG_CONFIG_HOME="$isolated/config" \
        XDG_CACHE_HOME="$isolated/cache" XDG_DATA_HOME="$isolated/data" \
        dbus-run-session -- "$0" "$desktop" "$output_dir"
    exit $?
fi

compositor_pid=''
xvfb_pid=''
cleanup() {
    [[ -z $compositor_pid ]] || kill "$compositor_pid" 2>/dev/null || true
    [[ -z $xvfb_pid ]] || kill "$xvfb_pid" 2>/dev/null || true
    [[ -z $compositor_pid ]] || wait "$compositor_pid" 2>/dev/null || true
    [[ -z $xvfb_pid ]] || wait "$xvfb_pid" 2>/dev/null || true
}
trap cleanup EXIT
export XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP="$desktop"
export LIBGL_ALWAYS_SOFTWARE=1 GDK_BACKEND=wayland GTK_A11Y=none
socket_name=bol-test-wayland
if [[ $desktop == GNOME ]]; then
    command -v gnome-shell >/dev/null || { echo 'gnome-shell is not installed.' >&2; exit 2; }
    command -v Xvfb >/dev/null || { echo 'Xvfb is needed for an isolated nested Mutter display.' >&2; exit 2; }
    # -displayfd allocates its own X display; it never replaces the user's display.
    Xvfb -displayfd 3 -screen 0 1280x800x24 -nolisten tcp 3>"$output_dir/gnome-x-display" >"$output_dir/gnome-xvfb.log" 2>&1 &
    xvfb_pid=$!
    for attempt in $(seq 1 100); do
        [[ ! -s "$output_dir/gnome-x-display" ]] || break
        kill -0 "$xvfb_pid" 2>/dev/null || { cat "$output_dir/gnome-xvfb.log" >&2; exit 1; }
        sleep .1
    done
    [[ -s "$output_dir/gnome-x-display" ]] || { echo 'Xvfb did not become ready.' >&2; exit 1; }
    export DISPLAY=":$(cat "$output_dir/gnome-x-display")"
    gnome-shell --version >"$output_dir/gnome-version.txt" 2>&1 || true
    MUTTER_DEBUG_DUMMY_MODE_SPECS=1280x800 gnome-shell --nested --wayland --no-x11 --wayland-display="$socket_name" >"$output_dir/gnome-compositor.log" 2>&1 &
    compositor_pid=$!
else
    command -v kwin_wayland >/dev/null || { echo 'kwin_wayland is not installed.' >&2; exit 2; }
    kwin_wayland --version >"$output_dir/kde-version.txt" 2>&1 || true
    kwin_wayland --virtual --width 1280 --height 800 --socket "$socket_name" --no-lockscreen --no-global-shortcuts >"$output_dir/kde-compositor.log" 2>&1 &
    compositor_pid=$!
fi
export WAYLAND_DISPLAY="$socket_name"
compositor_log="$output_dir/$(printf '%s' "$desktop" | tr '[:upper:]' '[:lower:]')-compositor.log"
for attempt in $(seq 1 200); do
    [[ ! -S "$XDG_RUNTIME_DIR/$socket_name" ]] || break
    kill -0 "$compositor_pid" 2>/dev/null || { cat "$compositor_log" >&2; exit 1; }
    sleep .1
 done
[[ -S "$XDG_RUNTIME_DIR/$socket_name" ]] || { cat "$compositor_log" >&2; echo 'Compositor did not create a Wayland socket.' >&2; exit 1; }
# A socket existing is not sufficient: verify protocol globals and GTK's real backend.
timeout 15 wayland-info >"$output_dir/$desktop-wayland-info.txt" 2>&1
python3 - <<'PY' >"$output_dir/$desktop-gdk-backend.txt"
import gi
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk
display = Gdk.Display.open(None)
assert display is not None, 'GTK could not connect to the isolated compositor'
name = display.__gtype__.name
assert 'Wayland' in name, name
print('Real GDK backend:', name)
PY
# This is a real compositor connection with simulated application service responses.
# It does not create users, contact speech providers, record audio, or inject input.
python3 "$repo_root/scripts/smoke-gtk.py" --desktop "$desktop" --clipboard-roundtrip >"$output_dir/$desktop-gtk-smoke.txt" 2>&1
cat "$output_dir/$desktop-gdk-backend.txt" "$output_dir/$desktop-gtk-smoke.txt"
printf '%s\n' "Real $desktop Wayland compositor startup and GTK own-clipboard smoke passed." \
    'This does not certify physical audio, global shortcuts, cross-app clipboard, automatic insertion, or a full desktop login session.'
# Flag references (upstream source):
# https://github.com/GNOME/mutter/blob/gnome-46/src/core/meta-context-main.c
# https://github.com/KDE/kwin/blob/Plasma/6.0/src/main_wayland.cpp
