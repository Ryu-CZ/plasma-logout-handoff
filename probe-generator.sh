#!/usr/bin/env bash
# Compare the chwd environment generator with a read-only sysfs equivalent.
set -eu
original=/usr/lib/systemd/user-environment-generators/20-nvidia-rtd3-workaround
[[ -x $original ]]
TIMEFORMAT='elapsed=%3R s'
printf 'Original (run first to avoid warming the device):\n'
time "$original"
printf 'Sysfs candidate:\n'
time /bin/sh "$(dirname -- "$0")/20-nvidia-rtd3-workaround"
