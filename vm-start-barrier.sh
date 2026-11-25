#!/usr/bin/env bash
# Disposable VM prototype. The monitor installs this beside the stock starters.
set -euo pipefail

case "${0##*/}" in
    startplasma-wayland)
        units='graphical-session.target|plasma-workspace.target|plasma-workspace-wayland.target|plasma-kwin_wayland.service'
        ;;
    startplasma-login-wayland)
        units='plasma-login-wayland.target|plasma-login-kwin_wayland.service|plasma-login.service|plasma-wallpaper.service'
        ;;
    *) exit 2 ;;
esac

# Ignore unrelated jobs. Never replace a queued stop with a start.
deadline=$((SECONDS + 12))
waiting=no
while :; do
    jobs=$(systemctl --user list-jobs --no-legend --no-pager --plain)
    if ! grep -Eq "^[[:space:]]*[0-9]+[[:space:]]+($units)[[:space:]]+stop[[:space:]]" <<<"$jobs"; then
        if [[ $waiting == yes ]]; then
            logger -t logout-vm "BARRIER_CLEAR ${0##*/}"
        fi
        break
    fi
    if [[ $waiting == no ]]; then
        logger -t logout-vm "BARRIER_WAIT ${0##*/}"
        waiting=yes
    fi
    if ((SECONDS >= deadline)); then
        logger -t logout-vm "BARRIER_TIMEOUT ${0##*/}"
        exit 1
    fi
    sleep .05
done

exec "$0.logout-vm-stock" "$@"
