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
        /^plane\[/ {
            plane=$0; sub(/:.*$/, "", plane); s="plane"; next
        }
        s=="plane" && /^[[:space:]]+crtc=/ { target[plane]=substr($1,6) }
        s=="plane" && /^[[:space:]]+fb=/ { fb[plane]=substr($1,4) }
        /^connector\[/ { s=($NF=="DP-3" ? "dp" : ""); next }
        s=="crtc" && /^[[:space:]]+(enable|active)=/ { a[p]=a[p] " " $1 }
        s=="crtc" && /^[[:space:]]+mode:/ {
            sub(/^[[:space:]]+/, ""); m[p]=$0
        }
        s=="dp" && /^[[:space:]]+crtc=/ { c=$0; sub(/^.*crtc=/,"",c) }
        s=="dp" && /^[[:space:]]+(link-status|self_refresh_aware)=/ { l=l " " $1 }
        END {
            printf "crtc=%s%s %s%s", c, a[c], m[c], l
            for (p in fb)
                if (target[p]==c && c!="" && c!="(null)" && fb[p]+0>0)
                    printf " %s.fb=%s", p, fb[p]
        }
    ' "$state")
    dp=/sys/class/drm/card2-DP-3
    row="$vt $row dpms=$(<"$dp/dpms") en=$(<"$dp/enabled")"
    if [[ $row != "$last" ]]; then
        owners=unknown
        if [[ -r ${state%/*}/framebuffer ]]; then
            owners=$(awk -v row="$row" '
                BEGIN {
                    n=split(row, fields)
                    for(i=1; i<=n; i++) if(fields[i] ~ /^plane\[[0-9]+\]\.fb=/) {
                        split(fields[i], kv, "="); want[kv[2]]=1
                    }
                }
                /^framebuffer\[/ { id=$0; sub(/^framebuffer\[/,"",id); sub(/\].*$/,"",id) }
                /allocated by = / && id in want {
                    sub(/^.*allocated by = /,""); printf " fb%s=%s", id, $0
                }
            ' "${state%/*}/framebuffer") || owners=unknown
        fi
        read -r end_up _ </proc/uptime
        printf '%s..%s %s allocators:%s\n' "$up" "$end_up" "$row" "${owners:-unknown}"
        last=$row
    fi
    sleep .02
done
