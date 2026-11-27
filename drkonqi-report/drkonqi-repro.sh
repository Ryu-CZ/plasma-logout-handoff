#!/usr/bin/env bash
# Plain systemd user units: a socket-activated Requisite= service cancels the
# pending stop of a target, and the next start of the session is then refused.
# Creates repro-* units under $XDG_RUNTIME_DIR/systemd/user and removes them
# on exit. Meant for a disposable VM or a test account.
#
# usage: bash drkonqi-repro.sh [stock|after|no-requisite|socket-partof|irreversible]
set -u
variant=${1:-stock}
case $variant in
    stock|after|no-requisite|socket-partof|irreversible) ;;
    *) echo "unknown variant: $variant" >&2; exit 2 ;;
esac
dir=${XDG_RUNTIME_DIR:?}/systemd/user
sock=$XDG_RUNTIME_DIR/repro-crash.sock
ctl() { systemctl --user "$@"; }
cleanup() {
    ctl stop repro-crash.socket 'repro-crash@*.service' repro-workspace.target \
        repro-session.target repro-slow.service repro-portal.service 2>/dev/null
    rm -f "$sock" "$dir"/repro-*
    ctl daemon-reload
    ctl reset-failed 'repro-*' 2>/dev/null
}
trap cleanup EXIT
mkdir -p "$dir"

# graphical-session.target
printf '%s\n' '[Unit]' 'StopWhenUnneeded=yes' >"$dir/repro-session.target"

# plasma-workspace.target
printf '%s\n' '[Unit]' 'BindsTo=repro-session.target' 'Before=repro-session.target' \
    >"$dir/repro-workspace.target"

# an app that takes a while to quit
printf '%s\n' '[Unit]' 'PartOf=repro-session.target' 'After=repro-session.target' \
    '[Service]' 'Type=oneshot' 'RemainAfterExit=yes' \
    'ExecStart=/usr/bin/true' 'ExecStop=/usr/bin/sleep 4' >"$dir/repro-slow.service"

# a D-Bus activated portal: slow enough to start and stop to be observable
printf '%s\n' '[Unit]' 'PartOf=repro-session.target' 'After=repro-session.target' \
    '[Service]' 'Type=oneshot' 'RemainAfterExit=yes' \
    'ExecStart=/usr/bin/sleep 3' 'ExecStop=/usr/bin/sleep 3' >"$dir/repro-portal.service"

# drkonqi-coredump-launcher.socket
{
    echo '[Unit]'
    [[ $variant == socket-partof ]] && echo 'PartOf=repro-session.target'
    printf '%s\n' '[Socket]' 'ListenStream=%t/repro-crash.sock' 'Accept=yes'
} >"$dir/repro-crash.socket"

# drkonqi-coredump-launcher@.service; it activates the "portal" and exits
{
    printf '%s\n' '[Unit]' 'PartOf=repro-session.target'
    [[ $variant != no-requisite ]] && echo 'Requisite=repro-session.target'
    [[ $variant == after ]] && echo 'After=repro-session.target'
    printf '%s\n' '[Service]' \
        "ExecStart=/bin/sh -c 'sleep 1; systemctl --user start --no-block repro-portal.service; sleep 1'"
} >"$dir/repro-crash@.service"

state() {
    echo "--- $1"
    for u in repro-session.target repro-workspace.target repro-slow.service repro-portal.service repro-crash.socket; do
        echo "$u: $(ctl is-active "$u")"
    done
    echo 'jobs:'
    ctl list-jobs --no-legend | grep repro- | awk '{print "  " $2, $3, $4}'
}

ctl daemon-reload
begin=$(date +%s)
echo "=== variant: $variant; $(systemctl --version | head -n1)"
ctl start repro-workspace.target repro-slow.service repro-crash.socket || exit 1
state 'logged in'

mode=fail   # what plasma-shutdown uses
[[ $variant == irreversible ]] && mode=replace-irreversibly
echo "=== logout: stop repro-session.target (--job-mode=$mode)"
ctl --job-mode="$mode" stop repro-session.target &
stop=$!
sleep 1
state 'stop pending'

echo '=== crash report: connect to the socket'
python3 -c 'import socket, sys, time
s = socket.socket(socket.AF_UNIX)
try:
    s.connect(sys.argv[1])
    print("connected")
    time.sleep(.5)
except OSError as e:
    print(e)' "$sock"
wait "$stop"
echo "stop command exit status: $?"
sleep 7
state 'after logout'

# startplasma: reset-failed, daemon-reload, start the session in "fail" mode
echo '=== next login: daemon-reload, then start repro-workspace.target (--job-mode=fail)'
ctl reset-failed 'repro-*' 2>/dev/null
ctl daemon-reload
if ctl --job-mode=fail start repro-workspace.target; then
    echo 'next login: started'
else
    echo 'next login: REFUSED'
fi
sleep 5
state 'end'

echo '=== journal'
journalctl -q --no-pager --no-hostname -o short-precise --since "@$begin" _UID="$(id -u)" |
    grep -E 'systemd\[' | grep -E 'repro|destructive'
