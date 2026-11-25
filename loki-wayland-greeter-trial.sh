#!/usr/bin/env bash
# One-logout trial of the SDDM Wayland (kwin) greeter on loki, with automatic rollback.
# SDDM reloads its config each time it creates a display, so the drop-in applies to the
# next logout without restarting sddm. If the Wayland greeter fails, SDDM itself falls
# back to x11-user. Rollback removes the drop-in after 10 minutes or via "rollback".
set -eu
conf=/etc/sddm.conf.d/zz-logout-wayland-trial.conf
if [[ ${1:-} == rollback ]]; then
    sudo rm -f "$conf"; sudo systemctl stop loki-wayland-trial-rollback.timer 2>/dev/null || :
    test ! -e "$conf" && echo "rolled back: X11 greeter on next logout"; exit
fi
sudo -v
printf '%s\n' '[General]' 'DisplayServer=wayland' '[Wayland]' \
    'CompositorCommand=/usr/bin/kwin_wayland --no-lockscreen --no-global-shortcuts --no-kactivities --locale1' |
    sudo tee "$conf" >/dev/null
sudo systemd-run --unit=loki-wayland-trial-rollback --collect --on-active=600 /usr/bin/rm -f "$conf"
sudo systemd-run --unit=loki-logout-capture2 --collect -p RuntimeMaxSec=300 -E HOLD=0 /usr/bin/bash "$HOME/.cache/loki-logout-capture2.sh"
echo "armed: log out within 4 minutes; drop-in auto-removed in 10 minutes"
