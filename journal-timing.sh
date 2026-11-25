#!/usr/bin/env bash
# Print journal landmarks in order on the boot's monotonic clock.
set -euo pipefail
uid=$(id -u plasmalogin)
journalctl -b --no-pager -o short-monotonic \
    _SYSTEMD_UNIT=plasmalogin.service + "UNIT=user@$uid.service" + SYSLOG_IDENTIFIER=plasmalogin-helper \
    + "USER_UNIT=plasma-kwin_wayland.service" "_UID=$UID" \
    + "USER_UNIT=plasma-login-kwin_wayland.service" "_UID=$uid" |
    grep -E 'User Manager for UID|Greeter starting|Greeter session started|Jumping to VT|Message received from greeter: Connect|Stopped KDE Window Manager|Started KDE Window Manager|plasma-kwin_wayland.service: Consumed'
