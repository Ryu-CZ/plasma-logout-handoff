#!/usr/bin/env bash
# One logout on Vandal: replace only the greeter's cold PCI probe, then expire.
set -euo pipefail

[[ $(hostname -s) == vandal-tomt && -t 0 && -t 1 ]] || {
    echo 'Run this in Konsole on Vandal.' >&2
    exit 1
}
if (( EUID != 0 )); then
    [[ ${XDG_SESSION_TYPE:-} == wayland && -z ${SSH_CONNECTION:-} ]] || {
        echo 'Run this from the local Plasma Wayland desktop, not over SSH.' >&2
        exit 1
    }
    exec sudo /usr/bin/bash "$(realpath -- "$0")"
fi

name=20-nvidia-rtd3-workaround
vendor=/usr/lib/systemd/user-environment-generators/$name
dir=/run/systemd/user-environment-generators
override=$dir/$name
unit=vandal-plm-generator-rollback
greeter_uid=$(id -u plasmalogin)
if ! systemctl is-active --quiet plasmalogin.service ||
   [[ $(systemctl show -p ActiveState --value "user@$greeter_uid.service") != inactive ]] ||
   [[ ! -x $vendor || ! -r /usr/share/glvnd/egl_vendor.d/50_mesa.json ]] ||
   ! grep -Fq 'lspci -d "10de:*:0302"' "$vendor"; then
    echo 'The expected PLM baseline is not present. Do not log out for this trial.' >&2
    exit 1
fi

for path in "$override" /etc/systemd/user-environment-generators/"$name" /usr/local/lib/systemd/user-environment-generators/"$name"; do
    if [[ -e $path || -L $path ]]; then
        echo "Existing generator override: $path. Nothing changed." >&2
        exit 1
    fi
done

umask 022
mkdir -p -- "$dir"
stage=$(mktemp /run/vandal-plm-generator.XXXXXX)
trap 'rm -f -- "$stage"' EXIT
{
    printf '#!/bin/sh\n'
    printf '[ "$(/usr/bin/id -u)" = %s ] || exec "%s"\n' "$greeter_uid" "$vendor"
    tail -n +2 "$(dirname -- "${BASH_SOURCE[0]}")/$name"
} > "$stage"
sh -n "$stage"
chmod 755 "$stage"

# Arm rollback before publishing. Remove only the inode installed by this trial.
systemd-run --unit="$unit" --on-active=120s --timer-property=AccuracySec=1s --collect \
    /usr/bin/bash -c 'if [[ $1 -ef $2 ]]; then rm -f -- "$1"; fi; rm -f -- "$2"' \
    rollback "$override" "$stage"
systemctl is-active --quiet "$unit.timer"
ln -T -- "$stage" "$override"
trap - EXIT

printf '\nTrial armed for two minutes. Use normal Log Out now.\n'
printf 'Wait a few seconds after the greeter appears, then sign back in.\n'
printf 'No refresh-rate change or manager restart is needed.\n'
