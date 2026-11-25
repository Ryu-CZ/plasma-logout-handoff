#!/usr/bin/env bash
# Diagnostic only. Run from a local text console after signing out of Plasma.
set -euo pipefail
[[ $(hostname -s) == loki && $(tty) =~ ^/dev/tty[0-9]+$ ]] || {
    echo 'Run from a local text console on loki, not SSH or a desktop terminal.' >&2
    exit 1
}
case ${1:-trial} in trial|restore) ;; *) exit 2 ;; esac
sessions=$(loginctl list-sessions --no-legend)
while read -r sid _; do
    [[ -n $sid ]] || continue
    props=$(loginctl show-session "$sid" -p Class -p Type)
    if grep -qx 'Class=user' <<<"$props" && grep -Eq '^Type=(x11|wayland)$' <<<"$props"; then
        echo 'A graphical user session is still open. Sign out first.' >&2
        exit 1
    fi
done <<<"$sessions"

conf=/etc/sddm.conf.d/zz-logout-wayland-trial.conf
sudo -v
if [[ ${1:-trial} == restore ]]; then
    sudo rm -f -- "$conf"
    sudo systemctl restart sddm
    exit
fi

[[ ! -e $conf && ! -L $conf ]] || { echo "Already exists: $conf" >&2; exit 1; }
sudo systemd-run --unit=loki-wayland-diagnostic-revert --collect \
    --on-active=10min --timer-property=AccuracySec=1s /usr/bin/rm -f -- "$conf"
systemctl is-active --quiet loki-wayland-diagnostic-revert.timer
printf '%s\n' '[General]' 'DisplayServer=wayland' '[Wayland]' \
    'CompositorCommand=/usr/bin/kwin_wayland --no-lockscreen --no-global-shortcuts --no-kactivities --locale1' |
    sudo tee "$conf" >/dev/null
echo 'Restarting SDDM now. The timer removes the drop-in; it never restarts SDDM.'
sudo systemctl restart sddm
