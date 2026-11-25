#!/usr/bin/env bash
# Read-only probe; start outside the desktop session to survive logout.
set -eu
state=/sys/kernel/debug/dri/0000:00:02.0/state
[[ -r $state ]]
end=$((SECONDS + 120))
last=
while ((SECONDS < end)); do
    read -r uptime _ </proc/uptime
    read -r vt </sys/class/tty/tty0/active
    read -r enabled </sys/class/drm/card1-DP-1/enabled
    summary=$(awk '
        /^crtc\[/ { block=$0; sub(/^.*: /, "", block); kind="pipe"; next }
        /^connector\[/ { kind=($NF=="DP-1" ? "dp" : ""); next }
        kind=="dp" && /^[[:space:]]+crtc=/ { pipe=$0; sub(/^.*crtc=/, "", pipe) }
        kind=="pipe" && /^[[:space:]]+(enable|active)=/ { data[block]=data[block] " " $1 }
        kind=="pipe" && /^[[:space:]]+mode:/ { data[block]=data[block] " " $2 " " $3 "Hz clock=" $4; kind="" }
        END { print "pipe=" pipe data[pipe] }
    ' "$state")
    row="$vt connector=$enabled $summary"
    if [[ $row != "$last" ]]; then
        printf '%s %s\n' "$uptime" "$row"
        last=$row
    fi
    sleep .05
done
