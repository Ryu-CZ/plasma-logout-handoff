#!/usr/bin/env bash
# Read-only logout capture. HOLD=1 also keeps /dev/dri/card2 open (no master, no ioctls)
# to test whether the blackout is the driver's last-close fbdev restore.
set -eu
[[ $(hostname) == loki ]]
if [[ ${HOLD:-0} == 1 ]]; then exec 9</dev/dri/card2; echo "holder: card2 open"; fi
state=/sys/kernel/debug/dri/0000:01:00.0/state
[[ -r $state ]] || state=/sys/kernel/debug/dri/2/state
[[ -r $state ]] || { echo "no debugfs state"; exit 1; }
last=; end=$((SECONDS + 290))
while ((SECONDS < end)); do
    read -r up _ </proc/uptime
    read -r vt </sys/class/tty/tty0/active
    row=$(awk '
        /^crtc\[/ { p=$0; sub(/^.*: /,"",p); s="crtc"; next }
        /^plane\[/ { s=""; next }
        /^connector\[/ { s=($NF=="DP-3" ? "dp" : ""); next }
        s=="crtc" && /^[[:space:]]+(enable|active)=/ { a[p]=a[p] " " $1 }
        s=="crtc" && /^[[:space:]]+mode:/ { m[p]=$3 "Hz" }
        s=="dp" && /^[[:space:]]+crtc=/ { c=$0; sub(/^.*crtc=/,"",c) }
        s=="dp" && /^[[:space:]]+(link-status|self_refresh_aware)=/ { l=l " " $1 }
        END { printf "crtc=%s%s %s%s", c, a[c], m[c], l }
    ' "$state")
    row="$vt $row dpms=$(cat /sys/class/drm/card2-DP-3/dpms) en=$(cat /sys/class/drm/card2-DP-3/enabled)"
    [[ $row == "$last" ]] || { printf '%s %s\n' "$up" "$row"; last=$row; }
    sleep .02
done
