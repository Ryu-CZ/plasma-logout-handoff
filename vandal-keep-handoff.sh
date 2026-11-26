#!/usr/bin/env bash
# Keep both Vandal logout changes across reboots, or undo them with --restore.
#   1. Console mode matching: a Limine drop-in adds one kernel parameter.
#   2. Greeter-only generator: an /etc override of the slow PCI probe.
set -euo pipefail

token='video=DP-1:3840x2160@100'
dropin=/etc/limine-entry-tool.d/90-vandal-console-mode.conf
name=20-nvidia-rtd3-workaround
vendor=/usr/lib/systemd/user-environment-generators/$name
override=/etc/systemd/user-environment-generators/$name
conf=/boot/limine.conf

die() { echo "ERROR: $*" >&2; exit 1; }

action=${1:-install}
[[ $action == install || $action == --restore ]] || die "usage: $0 [--restore]"
[[ $(hostname -s) == vandal-tomt && -t 0 && -t 1 ]] || die 'Run this in a terminal on Vandal.'
(( EUID == 0 )) || exec sudo /usr/bin/bash "$(realpath -- "$0")" "$action"

shopt -s nullglob
kernels=()
for f in /usr/lib/modules/*/pkgbase; do kernels+=("$(<"$f")"); done
(( ${#kernels[@]} )) || die 'No installed kernels found.'

cmdline() { limine-entry-tool --get-cmdline "$1" --no-mutex --no-hooks | tail -n 1; }
words() { tr -s ' ' '\n' <<<"$1" | sed '/^$/d' | sort; }

# Rebuild boot entries, keeping a copy of the previous menu.
rebuild() {
    local backup
    mkdir -p /var/backups/vandal-handoff
    backup=/var/backups/vandal-handoff/limine.conf.$(date +%Y%m%d-%H%M%S)
    cp -- "$conf" "$backup"
    echo "Previous boot menu saved to $backup"
    limine-mkinitcpio
}

greeter_uid=$(id -u plasmalogin)
generator() {
    cat <<EOF
#!/bin/sh
# Installed by vandal-keep-handoff.sh. Greeter only: same Mesa EGL setting,
# read from sysfs without waking the GPU. Other users keep the original.
if [ "\$(/usr/bin/id -u)" != $greeter_uid ]; then
    [ -x "$vendor" ] && exec "$vendor"
    exit 0
fi
for dev in /sys/bus/pci/devices/*; do
    read -r vendor <"\$dev/vendor" 2>/dev/null || continue
    read -r class <"\$dev/class" 2>/dev/null || continue
    case "\$vendor:\$class" in
        0x10de:0x0302??)
            printf '%s\\n' '__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json'
            break
            ;;
    esac
done
EOF
}

if [[ $action == --restore ]]; then
    if [[ -e $override ]]; then
        cmp -s <(generator) "$override" || die "$override differs from what this script installs; left in place."
        rm -- "$override"
        echo "Removed $override"
    fi
    rm -f -- "$dropin"
    rebuild
    for k in "${kernels[@]}"; do
        line=$(cmdline "$k")
        [[ " $line " != *" $token "* ]] || die "$k still has $token; check /etc/default/limine."
    done
    echo 'Restored. The console parameter is gone from the next boot.'
    exit 0
fi

[[ ! -e $dropin ]] || die "$dropin already exists. Nothing changed."
[[ ! -e $override && ! -L $override ]] || die "$override already exists. Nothing changed."
[[ -x $vendor ]] && grep -Fq 'lspci -d "10de:*:0302"' "$vendor" || die 'The expected vendor generator is not present. Nothing changed.'

declare -A before
for k in "${kernels[@]}"; do
    before[$k]=$(cmdline "$k")
    [[ ${before[$k]} == *root=* ]] || die "Could not read the command line for $k. Nothing changed."
    [[ ${before[$k]} != *video=* ]] || die "$k already has a video= parameter. Nothing changed."
done

umask 022
mkdir -p -- "${dropin%/*}"
# Until the new command lines are verified, any failure removes the drop-in.
trap 'rm -f -- "$dropin"; echo "Drop-in removed; boot entries were not rebuilt." >&2' EXIT
printf 'KERNEL_CMDLINE[default]+=%s\n' "$token" >"$dropin"
for k in "${kernels[@]}"; do
    after=$(cmdline "$k")
    [[ $(words "$after") == "$(words "${before[$k]} $token")" ]] ||
        die "Unexpected command line for $k: $after"
    echo "$k: $after"
done
trap - EXIT

rebuild
found=$(grep -Ec "^[[:space:]]*(kernel_)?cmdline:.*$token" "$conf" || true)
(( found >= ${#kernels[@]} )) ||
    die "Only $found boot entries contain $token. Do not reboot; run: bash $0 --restore"

mkdir -p -- "${override%/*}"
generator >"$override.new"
sh -n "$override.new"
chmod 755 "$override.new"
mv -T -- "$override.new" "$override"

printf '\nBoth changes installed (%s boot entries have the parameter).\n' "$found"
echo "Undo with: bash $(realpath -- "$0") --restore"
