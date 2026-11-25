#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
login=$here/../plasma-login-handoff
base=${1:?Usage: bash run-vm.sh BASE_CACHE NEW_RESULTS_DIR cold|warm}
results=$(realpath -m "${2:?Provide a new results directory}")
export LOGOUT_VM_MODE=${3:?Specify cold or warm}
[[ $LOGOUT_VM_MODE == cold || $LOGOUT_VM_MODE == warm ]]
# Reuse the login harness's boot, package verification and guest setup,
# swapping only its QMP/serial driver. Don't change either checkout.
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
mkdir "$tmp/vm"
ln -s "$login/vm/run.sh" "$tmp/vm/"
if [[ -n ${LOGOUT_VM_STOP_FIX:-} ]]; then
    # Insert the guest-only installer just before PLM starts.
    while IFS= read -r line; do
        if [[ $line == 'systemctl start plasmalogin.service' ]]; then
            for name in startplasma-wayland startplasma-login-wayland; do
                printf "base64 -d >/tmp/logout-vm-starter <<'LOGOUT_VM_BINARY'\n"
                base64 "$LOGOUT_VM_STOP_FIX/$name"
                printf 'LOGOUT_VM_BINARY\ninstall -m 755 /tmp/logout-vm-starter /usr/bin/%s\n' "$name"
            done
        fi
        printf '%s\n' "$line"
    done <"$login/vm/guest.sh" >"$tmp/vm/guest.sh"
else
    ln -s "$login/vm/guest.sh" "$tmp/vm/"
fi
cp -r "$login/org.local.wallpaperhandoff" "$tmp/"
ln -s "$here/monitor.py" "$tmp/vm/"
unset KWIN_MARKER_BUILD KWIN_MARKER KWIN_BOOTSTRAP_WALLPAPER
bash "$tmp/vm/run.sh" "$base" "$results"
