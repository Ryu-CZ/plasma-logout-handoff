#!/usr/bin/env bash
# Compare the chwd environment generator with a read-only sysfs equivalent.
set -eu
original=/usr/lib/systemd/user-environment-generators/20-nvidia-rtd3-workaround
[[ -x $original ]]
TIMEFORMAT='elapsed=%3R s'
printf 'Original (run first to avoid warming the device):\n'
time "$original"
printf 'Sysfs candidate:\n'
time (
    for dev in /sys/bus/pci/devices/*; do
        read -r vendor <"$dev/vendor" || continue
        read -r class <"$dev/class" || continue
        if [[ $vendor == 0x10de && $class == 0x0302?? ]]; then
            printf '%s\n' '__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json'
            break
        fi
    done
)
