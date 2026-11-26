#!/usr/bin/env bash
# Switch to a text console and back; report active CRTC modes (no root, no logout).
# Not for sampling a logout: opening the card on a text VT can briefly take DRM master.
set -eu
away=${1:-3}
read -r home </sys/class/tty/tty0/active
home=${home#tty}
vt() { timeout 5 busctl call org.freedesktop.login1 /org/freedesktop/login1/seat/seat0 org.freedesktop.login1.Seat SwitchTo u "$1"; }
mode() {
    read -r active </sys/class/tty/tty0/active
    read -r up _ </proc/uptime
    echo "$1 up=$up $active"
    timeout 3 modetest -M i915 -p 2>/dev/null | sed -n '/^CRTCs:/,/^Planes:/p' |
        awk '/^[0-9]/{crtc=$1; fb=$2} /^  #0 [0-9]/{print "  crtc=" crtc, "fb=" fb, $2, $3 "Hz", "clock=" $12}'
}
mode desktop
# Let the Enter that started this be released; otherwise it may auto-repeat across the switch.
sleep 1
trap 'vt "$home"' EXIT
vt "$away"
sleep 1.5
mode console
vt "$home"
trap - EXIT
sleep 2
mode returned
