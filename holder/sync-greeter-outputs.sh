#!/usr/bin/env bash
# Give the login screen the same display settings as your desktop, so its
# compositor does not change the mode (and the monitor does not re-sync)
# when it takes over at logout. Copies only kwinoutputconfig.json.
#   sudo bash sync-greeter-outputs.sh            copy (keeps a backup)
#   sudo bash sync-greeter-outputs.sh --restore  put the previous file back
# Re-run after changing display settings on the desktop.
set -euo pipefail
src_user=${SUDO_USER:?run with sudo from your own account}
src=$(getent passwd "$src_user" | cut -d: -f6)/.config/kwinoutputconfig.json
dir=/var/lib/plasmalogin/.config
dst=$dir/kwinoutputconfig.json
backup=$dst.before-logout-holder
none=$dst.none-before-logout-holder

if [[ ${1:-} == --restore ]]; then
    if [[ -f $backup ]]; then
        mv -f -- "$backup" "$dst"
        echo "Restored the previous $dst"
    elif [[ -f $none ]]; then
        rm -f -- "$dst" "$none"
        echo "Removed $dst (there was none before)"
    else
        echo "Nothing recorded to restore." >&2
        exit 1
    fi
    exit 0
fi

[[ -f $src ]] || { echo "No $src" >&2; exit 1; }
python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))' "$src"
[[ -d $dir ]] || install -d -o plasmalogin -g plasmalogin -m 755 "$dir"
if [[ ! -e $backup && ! -e $none ]]; then
    if [[ -f $dst ]]; then
        cp -a -- "$dst" "$backup"
        echo "Previous login screen settings kept in $backup:"
        python3 -I -m json.tool "$dst" | grep -E '"(connectorName|rgbRange|maxBitsPerColor|colorProfileSource)"' || true
    else
        : >"$none"
        echo "The login screen had no saved display settings."
    fi
fi
install -o plasmalogin -g plasmalogin -m 644 -- "$src" "$dst"
echo "Copied $src to $dst. Takes effect when the login screen next starts."
echo "Undo: sudo bash $(realpath "$0") --restore"
