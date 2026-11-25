#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
login=$here/../plasma-login-handoff
base=${1:?Usage: bash run-vm.sh BASE_CACHE NEW_RESULTS_DIR cold|warm|sddm}
results=$(realpath -m "${2:?Provide a new results directory}")
export LOGOUT_VM_MODE=${3:?Specify cold or warm}
[[ $LOGOUT_VM_MODE =~ ^(cold|warm|sddm)$ ]]
if [[ $LOGOUT_VM_MODE == sddm ]]; then
    packages=$(realpath "${SDDM_VM_PACKAGES:?Directory containing the verified SDDM packages}")
    (cd "$packages"; sha256sum -c "$here/sddm-packages.sha256")
fi
# Reuse the login harness's boot, package verification and guest setup,
# swapping only its QMP/serial driver. Don't change either checkout.
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
mkdir "$tmp/vm"
ln -s "$login/vm/run.sh" "$tmp/vm/"
if [[ $LOGOUT_VM_MODE == sddm || -n ${LOGOUT_VM_STOP_FIX:-}${LOGOUT_VM_GREETER_MARKER:-}${LOGOUT_VM_COMBINED:-} ]]; then
    # Insert guest-only configuration just before PLM starts.
    while IFS= read -r line; do
        if [[ $line == 'systemctl start plasmalogin.service' ]]; then
            if [[ $LOGOUT_VM_MODE == sddm ]]; then
                while read -r _ name; do
                    printf "base64 -d >/tmp/sddm-vm.pkg <<'SDDM_BINARY'\n"
                    base64 "$packages/$name"
                    printf 'SDDM_BINARY\nbsdtar -xpf /tmp/sddm-vm.pkg -C / --exclude .PKGINFO --exclude .BUILDINFO --exclude .MTREE --exclude .INSTALL\n'
                done <"$here/sddm-packages.sha256"
                printf '%s\n' 'rm /tmp/sddm-vm.pkg' 'systemd-sysusers sddm.conf' 'systemd-tmpfiles --create sddm.conf' \
                    'mkdir -p /etc/sddm.conf.d' \
                    'printf "%s\\n" "[General]" "DisplayServer=x11" "[Theme]" "Current=" "[Users]" "RememberLastUser=true" >/etc/sddm.conf.d/99-logout-vm.conf' \
                    'install -d -o sddm -g sddm /var/lib/sddm' \
                    'printf "%s\\n" "[Last]" "Session=plasma.desktop" "User=probe" >/var/lib/sddm/state.conf' \
                    'chown sddm:sddm /var/lib/sddm/state.conf' 'systemctl daemon-reload'
                if [[ ${SDDM_VM_RETRO:-0} == 1 ]]; then
                    # Xorg's built-in stipple is visible before SDDM draws.
                    printf '%s\n' 'printf "%s\\n" "[X11]" "ServerArguments=-nolisten tcp -retro" >>/etc/sddm.conf.d/99-logout-vm.conf'
                fi
                line='systemctl start sddm.service'
            fi
            if [[ -n ${LOGOUT_VM_STOP_FIX:-} ]]; then
                starters=(startplasma-wayland)
                if [[ $LOGOUT_VM_MODE != sddm ]]; then
                    starters+=(startplasma-login-wayland)
                fi
                for name in "${starters[@]}"; do
                    printf "base64 -d >/tmp/logout-vm-starter <<'LOGOUT_VM_BINARY'\n"
                    base64 "$LOGOUT_VM_STOP_FIX/$name"
                    printf 'LOGOUT_VM_BINARY\ninstall -m 755 /tmp/logout-vm-starter /usr/bin/%s\n' "$name"
                done
            fi
            if [[ -n ${LOGOUT_VM_COMBINED:-} ]]; then
                printf "install -d -m755 /opt/logout-vm-combined\nbase64 -d <<'LOGOUT_VM_COMBINED_PAYLOAD' | tar -xzf - -C /opt/logout-vm-combined\n"
                tar -chzf - -C "$LOGOUT_VM_COMBINED" bin lib share | base64
                printf 'LOGOUT_VM_COMBINED_PAYLOAD\n'
                printf '%s\n' \
                    'd=/opt/logout-vm-combined; chmod -R a+rX "$d"' \
                    'mkdir -p /etc/systemd/user/{plasma-kwin_wayland,plasma-plasmashell}.service.d' \
                    'printf "%s\\n" "[Service]" "ExecStart=" "ExecStart=$d/bin/kwin_wayland_wrapper --xwayland" "Environment=PATH=$d/bin:/usr/bin LD_LIBRARY_PATH=$d/lib KWIN_LOGIN_VM_WALLPAPER=$image KWIN_EXPERIMENTAL_MANAGED_LOCK_WALLPAPER=1 KSCREENLOCKER_EXPERIMENTAL_WALLPAPER_UNDERLAY=1" >/etc/systemd/user/plasma-kwin_wayland.service.d/90-logout-vm-combined.conf' \
                    'printf "%s\\n" "[Service]" "ExecStart=" "ExecStart=$d/bin/plasmashell --no-respawn" "Environment=LD_LIBRARY_PATH=$d/lib XDG_DATA_DIRS=$d/share:/usr/share PLASMA_EXPERIMENTAL_MANAGED_LOCK_WALLPAPER=1" >/etc/systemd/user/plasma-plasmashell.service.d/90-logout-vm-combined.conf'
            fi
            if [[ -n ${LOGOUT_VM_GREETER_MARKER:-} ]]; then
                printf '%s\n' \
                    "LOGOUT_GREETER_COLOR=${LOGOUT_VM_GREETER_COLOR:-0}" \
                    'install -d -m755 /opt/logout-vm-kwin /etc/systemd/user/plasma-login-kwin_wayland.service.d' \
                    'install -m755 /opt/probe/kwin/{kwin_wayland,libkwin.so.6} /opt/logout-vm-kwin/' \
                    'rm -f /home/probe/.config/systemd/user/plasma-kwin_wayland.service.d/marker.conf' \
                    'printf "%s\\n" "[Service]" "ExecStart=" "ExecStart=/opt/logout-vm-kwin/kwin_wayland --no-lockscreen --no-global-shortcuts --no-kactivities --inputmethod plasma-keyboard --locale1" "Environment=LD_LIBRARY_PATH=/opt/logout-vm-kwin KWIN_LOGIN_VM_MARKER=$LOGOUT_GREETER_COLOR QT_FORCE_STDERR_LOGGING=1" >/etc/systemd/user/plasma-login-kwin_wayland.service.d/90-logout-vm.conf'
            fi
        fi
        printf '%s\n' "$line"
    done <"$login/vm/guest.sh" >"$tmp/vm/guest.sh"
else
    ln -s "$login/vm/guest.sh" "$tmp/vm/"
fi
cp -r "$login/org.local.wallpaperhandoff" "$tmp/"
ln -s "$here/monitor.py" "$tmp/vm/"
unset KWIN_MARKER_BUILD KWIN_MARKER KWIN_BOOTSTRAP_WALLPAPER
if [[ -n ${LOGOUT_VM_GREETER_MARKER:-} ]]; then
    export KWIN_MARKER_BUILD=$LOGOUT_VM_GREETER_MARKER KWIN_MARKER=0
    [[ ${LOGOUT_VM_GREETER_COLOR:-0} =~ ^[01]$ ]]
fi
bash "$tmp/vm/run.sh" "$base" "$results"
