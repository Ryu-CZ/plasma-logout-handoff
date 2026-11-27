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
if [[ -n ${LOGOUT_VM_HOLDER_BUNDLE:-} && -n ${LOGOUT_VM_GREETER_MARKER:-}${LOGOUT_VM_RELAY:-}${LOGOUT_VM_COMBINED:-} ]]; then
    echo 'LOGOUT_VM_HOLDER_BUNDLE replaces the marker, relay and combined options.' >&2
    exit 1
fi
if [[ -n ${LOGOUT_VM_HOLDER_UPGRADE:-} && -z ${LOGOUT_VM_HOLDER_BUNDLE:-} ]]; then
    echo 'LOGOUT_VM_HOLDER_UPGRADE upgrades from LOGOUT_VM_HOLDER_BUNDLE.' >&2
    exit 1
fi
if [[ $LOGOUT_VM_MODE == sddm || -n ${LOGOUT_VM_STOP_FIX:-}${LOGOUT_VM_GREETER_MARKER:-}${LOGOUT_VM_COMBINED:-}${LOGOUT_VM_HOLDER_BUNDLE:-}${LOGOUT_VM_THEME:-}${LOGOUT_VM_GREETER_FIX:-}${LOGOUT_VM_SLOW_GREETER_STOP:-} ]]; then
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
                if [[ ${SDDM_VM_WAYLAND:-0} == 1 && ${SDDM_VM_GREETER_FAIL:-0} == 1 ]]; then
                    printf '%s\n' 'systemd-run --unit=logout-vm-revert --on-active=15s --timer-property=AccuracySec=1s /usr/bin/rm -f /etc/sddm.conf.d/zz-logout-vm-backend.conf || exit 1'
                fi
                if [[ ${SDDM_VM_WAYLAND:-0} == 1 ]]; then
                    printf '%s\n' \
                        'printf "%s\\n" "[General]" "DisplayServer=wayland" "[Wayland]" "CompositorCommand=/usr/bin/kwin_wayland --no-lockscreen --no-global-shortcuts --no-kactivities --locale1" >/etc/sddm.conf.d/zz-logout-vm-backend.conf'
                fi
                if [[ ${SDDM_VM_WAYLAND:-0} == 1 && ${SDDM_VM_GREETER_FAIL:-0} == 1 ]]; then
                    printf '%s\n' 'sed -i "s|^CompositorCommand=.*|CompositorCommand=/usr/bin/false|" /etc/sddm.conf.d/zz-logout-vm-backend.conf'
                fi
                if [[ ${SDDM_VM_RETRO:-0} == 1 ]]; then
                    # Xorg's built-in stipple is visible before SDDM draws.
                    printf '%s\n' 'printf "%s\\n" "[X11]" "ServerArguments=-nolisten tcp -retro" >>/etc/sddm.conf.d/99-logout-vm.conf'
                fi
                if [[ ${SDDM_VM_ROOT_COLOR:-0} == 1 ]]; then
                    name=xorg-xsetroot-1.1.4-1-x86_64.pkg.tar.zst
                    (cd "$packages"; printf '%s  %s\n' 856b4ef5250a18acc616d0ba93ce85ae7020a7f99bcc9a0830fc29679e1ff1ab "$name" | sha256sum -c - >&2)
                    printf "base64 -d >/tmp/sddm-root.pkg <<'SDDM_BINARY'\n"
                    base64 "$packages/$name"
                    printf '%s\n' 'SDDM_BINARY' 'bsdtar -xpf /tmp/sddm-root.pkg -C / usr/bin/xsetroot' \
                        'printf "%s\\n" "/usr/bin/xsetroot -solid magenta && logger -t logout-vm SDDM_XSETROOT_OK" >>/usr/share/sddm/scripts/Xsetup'
                fi
                if [[ ${SDDM_VM_WALLPAPER:-0} == 1 ]]; then
                    name=xwallpaper-0.7.6-1.1-x86_64_v3.pkg.tar.zst
                    (cd "$packages"; printf '%s  %s\n' 6b182bb1489064b6efda6cdc97f6e47f5ed69fdff84ef9789b5cb9afe91bd069 "$name" | sha256sum -c - >&2)
                    printf "base64 -d >/tmp/sddm-wallpaper.pkg <<'SDDM_BINARY'\n"
                    base64 "$packages/$name"
                    printf '%s\n' 'SDDM_BINARY' 'bsdtar -xpf /tmp/sddm-wallpaper.pkg -C / usr/bin/xwallpaper' \
                        'printf "%s\\n" "/usr/bin/timeout 1s /usr/bin/xwallpaper --zoom $image && logger -t logout-vm SDDM_WALLPAPER_OK" "exit 0" >>/usr/share/sddm/scripts/Xsetup'
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
            if [[ -n ${LOGOUT_VM_GREETER_FIX:-} ]]; then
                # Only the login screen starter, replacing the packaged one.
                printf "base64 -d >/tmp/logout-vm-starter <<'LOGOUT_VM_BINARY'\n"
                base64 "$LOGOUT_VM_GREETER_FIX"
                printf '%s\n' 'LOGOUT_VM_BINARY' \
                    'install -m 755 /tmp/logout-vm-starter /usr/bin/startplasma-login-wayland'
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
            if [[ -n ${LOGOUT_VM_GREETER_MARKER:-} && $LOGOUT_VM_MODE == sddm ]]; then
                [[ ${SDDM_VM_WAYLAND:-0} == 1 && ${SDDM_VM_GREETER_FAIL:-0} != 1 ]] || {
                    echo 'The SDDM compositor marker requires a working Wayland greeter.' >&2
                    exit 1
                }
                printf '%s\n' \
                    "LOGOUT_GREETER_COLOR=${LOGOUT_VM_GREETER_COLOR:-0}" \
                    'install -d -m755 /opt/logout-vm-kwin' \
                    'install -m755 /opt/probe/kwin/{kwin_wayland,libkwin.so.6} /opt/logout-vm-kwin/' \
                    'rm -f /home/probe/.config/systemd/user/plasma-kwin_wayland.service.d/marker.conf' \
                    'printf "%s\n" "#!/bin/sh" "export LD_LIBRARY_PATH=/opt/logout-vm-kwin KWIN_LOGIN_VM_MARKER=$LOGOUT_GREETER_COLOR QT_FORCE_STDERR_LOGGING=1" "exec /opt/logout-vm-kwin/kwin_wayland --no-lockscreen --no-global-shortcuts --no-kactivities --locale1" >/opt/logout-vm-kwin/greeter' \
                    'chmod 755 /opt/logout-vm-kwin/greeter' \
                    'printf "%s\n" "[Wayland]" "CompositorCommand=/opt/logout-vm-kwin/greeter" >/etc/sddm.conf.d/zzz-logout-vm-marker.conf'
            elif [[ -n ${LOGOUT_VM_GREETER_MARKER:-} ]]; then
                # With a backdrop build, the desktop compositor keeps it too.
                drop_desktop='rm -f /home/probe/.config/systemd/user/plasma-kwin_wayland.service.d/marker.conf'
                if [[ ${LOGOUT_VM_BACKDROP:-0} == 1 ]]; then
                    drop_desktop=:
                    # A solid cyan image, so captures can attribute it.
                    printf '%s\n' 'install -d -m755 /opt/logout-vm-backdrop' \
                        "echo $(magick -size 1280x800 'xc:#00ffff' png:- | base64 -w0) | base64 -d >/opt/logout-vm-backdrop/image.png" \
                        'chmod 644 /opt/logout-vm-backdrop/image.png' \
                        'for u in plasma-login-kwin_wayland /home/probe/.config/systemd/user/plasma-kwin_wayland; do' \
                        'case $u in /*) d=$u.service.d ;; *) d=/etc/systemd/user/$u.service.d ;; esac; mkdir -p "$d"' \
                        'printf "%s\\n" "[Service]" "Environment=KWIN_LOGIN_VM_WALLPAPER=/opt/logout-vm-backdrop/image.png" >"$d/zz-backdrop.conf"' \
                        'done'
                fi
                if [[ -n ${LOGOUT_VM_WALLPAPER_BIN:-} ]]; then
                    # Greeter wallpaper program that maps only once loaded.
                    printf "base64 -d >/tmp/logout-vm-wallpaper <<'LOGOUT_VM_BINARY'\n"
                    base64 "$LOGOUT_VM_WALLPAPER_BIN"
                    printf '%s\n' 'LOGOUT_VM_BINARY' \
                        'install -D -m755 /tmp/logout-vm-wallpaper /opt/logout-vm-wallpaper/plasma-login-wallpaper' \
                        'mkdir -p /etc/systemd/user/plasma-wallpaper.service.d' \
                        'printf "%s\\n" "[Service]" "ExecStart=" "ExecStart=/opt/logout-vm-wallpaper/plasma-login-wallpaper" "Environment=QT_FORCE_STDERR_LOGGING=1" >/etc/systemd/user/plasma-wallpaper.service.d/90-logout-vm.conf'
                fi
                printf '%s\n' \
                    "LOGOUT_GREETER_COLOR=${LOGOUT_VM_GREETER_COLOR:-0}" \
                    'install -d -m755 /opt/logout-vm-kwin /etc/systemd/user/plasma-login-kwin_wayland.service.d' \
                    'install -m755 /opt/probe/kwin/{kwin_wayland,libkwin.so.6} /opt/logout-vm-kwin/' \
                    "$drop_desktop" \
                    'printf "%s\\n" "[Service]" "ExecStart=" "ExecStart=/opt/logout-vm-kwin/kwin_wayland --no-lockscreen --no-global-shortcuts --no-kactivities --inputmethod plasma-keyboard --locale1" "Environment=LD_LIBRARY_PATH=/opt/logout-vm-kwin KWIN_LOGIN_VM_MARKER=$LOGOUT_GREETER_COLOR QT_FORCE_STDERR_LOGGING=1" >/etc/systemd/user/plasma-login-kwin_wayland.service.d/90-logout-vm.conf'
            fi
            if [[ -n ${LOGOUT_VM_THEME:-} ]]; then
                # The Vandal login theme as installed on the host
                # (plasmalogin-theme/install-theme.sh): greeter and wallpaper
                # programs, split image, user-unit overrides.
                for name in plasma-login-greeter plasma-login-wallpaper; do
                    printf "base64 -d >/tmp/logout-vm-theme <<'LOGOUT_VM_BINARY'\n"
                    base64 "$LOGOUT_VM_THEME/$name"
                    printf 'LOGOUT_VM_BINARY\ninstall -D -m755 /tmp/logout-vm-theme /usr/local/lib/plasmalogin-theme/%s\n' "$name"
                done
                printf "base64 -d >/tmp/logout-vm-theme <<'LOGOUT_VM_BINARY'\n"
                base64 "$LOGOUT_VM_THEME/vandal-split.jpg"
                printf '%s\n' 'LOGOUT_VM_BINARY' \
                    'install -D -m644 /tmp/logout-vm-theme /var/lib/plasmalogin/wallpapers/vandal-split.jpg' \
                    'sed -i "s|^Image=.*|Image=file:///var/lib/plasmalogin/wallpapers/vandal-split.jpg|" /etc/plasmalogin.conf' \
                    'for p in plasma-login:plasma-login-greeter plasma-wallpaper:plasma-login-wallpaper; do' \
                    'mkdir -p /etc/systemd/user/${p%:*}.service.d' \
                    'printf "[Service]\\nExecStart=\\nExecStart=/usr/local/lib/plasmalogin-theme/%s\\n" ${p#*:} >/etc/systemd/user/${p%:*}.service.d/70-vandal-theme.conf' \
                    'done' 'systemctl daemon-reload'
            fi
            if [[ -n ${LOGOUT_VM_HOLDER_BUNDLE:-} ]]; then
                # The real installer from a bundle made by holder/bundle.sh.
                printf "base64 -d >/tmp/logout-holder.tar <<'LOGOUT_VM_BINARY'\n"
                tar -C "$LOGOUT_VM_HOLDER_BUNDLE" -cf - . | base64
                printf '%s\n' 'LOGOUT_VM_BINARY' \
                    'mkdir /tmp/logout-holder && tar -C /tmp/logout-holder -xf /tmp/logout-holder.tar || exit 1' \
                    '(cd /tmp/logout-holder && sha256sum -c --quiet SHA256SUMS) || exit 1' \
                    'bash /tmp/logout-holder/install.sh || exit 1'
                if [[ -n ${LOGOUT_VM_HOLDER_UPGRADE:-} ]]; then
                    # Unpacked only; the driver installs it from the desktop.
                    printf "base64 -d >/tmp/logout-holder-new.tar <<'LOGOUT_VM_BINARY'\n"
                    tar -C "$LOGOUT_VM_HOLDER_UPGRADE" -cf - . | base64
                    printf '%s\n' 'LOGOUT_VM_BINARY' \
                        'mkdir /tmp/logout-holder-new && tar -C /tmp/logout-holder-new -xf /tmp/logout-holder-new.tar || exit 1' \
                        '(cd /tmp/logout-holder-new && sha256sum -c --quiet SHA256SUMS) || exit 1'
                fi
                if [[ ${LOGOUT_VM_HOLDER_STALE:-0} == 1 ]]; then
                    # Pretend a pinned package changed: greeter-start must fall back.
                    printf '%s\n' 'echo no-such-package-1-1 >>/usr/local/lib/logout-holder/PACKAGES'
                fi
            fi
            if [[ -n ${LOGOUT_VM_SLOW_GREETER_STOP:-} ]]; then
                # The login screen compositor takes this long to stop. In the
                # login screen user's own configuration: the holder's installer
                # refuses to install over drop-ins in /etc.
                [[ $LOGOUT_VM_SLOW_GREETER_STOP =~ ^[0-9]+$ ]]
                printf '%s\n' 'd=/var/lib/plasmalogin/.config; for s in systemd systemd/user systemd/user/plasma-login-kwin_wayland.service.d; do install -d -o plasmalogin -g plasmalogin $d $d/$s; done' \
                    "printf '[Service]\\nExecStopPost=/usr/bin/sleep $LOGOUT_VM_SLOW_GREETER_STOP\\n' >\$d/\$s/zz-logout-vm-slow-stop.conf"
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
