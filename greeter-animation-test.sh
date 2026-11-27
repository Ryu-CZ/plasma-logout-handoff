#!/usr/bin/env bash
# Live test: turn off KWin's window-open animation (the "scale" effect) for the
# login screen's compositor only. The desktop's KWin and the holder's installed
# files are not touched. The starter's own kdedefaults directory is kept
# (startplasma.cpp setupPlasmaEnvironment); the test directory comes first.
# Applies at the next login screen start (next logout).
# Superseded by holder v7, whose installer sets this itself and removes these
# test files.
#   sudo bash greeter-animation-test.sh apply|undo
#   bash greeter-animation-test.sh status
set -euo pipefail
dir=/usr/local/lib/logout-holder-test/xdg
dropin=/etc/systemd/user/plasma-login-kwin_wayland.service.d/81-no-open-animation.conf
case ${1:-} in
apply)
    [[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
    [[ ! -e $dropin && ! -e $dir ]] || { echo "Already applied: $dropin or $dir exists. Nothing changed." >&2; exit 1; }
    install -d -m755 "$dir"
    printf '[Plugins]\nscaleEnabled=false\n' >"$dir/kwinrc"
    chmod 644 "$dir/kwinrc"
    printf '%s\n' '# Test from plasma-logout-handoff/greeter-animation-test.sh:' \
        '# no window-open animation in the login screen compositor.' \
        '[Service]' "Environment=\"XDG_CONFIG_DIRS=$dir:%E/kdedefaults:/etc/xdg\"" >"$dropin"
    chmod 644 "$dropin"
    echo "Applied. Takes effect at the next logout."
    ;;
undo)
    [[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
    rm -f "$dropin" "$dir/kwinrc"
    rmdir "$dir" /usr/local/lib/logout-holder-test 2>/dev/null || true
    echo "Removed. Takes effect at the next logout."
    ;;
status)
    for f in "$dropin" "$dir/kwinrc"; do
        if [[ -e $f ]]; then echo "== $f"; cat "$f"; else echo "absent: $f"; fi
    done
    ;;
*)
    echo "usage: sudo bash $0 apply|undo  |  bash $0 status" >&2
    exit 2
    ;;
esac
