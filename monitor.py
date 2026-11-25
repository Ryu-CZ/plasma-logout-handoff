"""Sample emulated output during an actual Plasma logout in a disposable VM."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import socket
import sys
import time

work, results = map(Path, sys.argv[1:])
mode = os.environ["LOGOUT_VM_MODE"]


def connect(name):
    deadline = time.monotonic() + 15
    with_error = (FileNotFoundError, ConnectionRefusedError)
    client = socket.socket(socket.AF_UNIX)
    while True:
        try:
            client.connect(str(work / name))
            return client
        except with_error:
            if time.monotonic() > deadline:
                client.close()
                raise
            time.sleep(.1)


with (connect("serial") as serial, connect("qmp") as qmp,
      (results / "serial.log").open("wb", buffering=0) as log,
      qmp.makefile("rwb") as stream):
    serial.settimeout(.5)
    qmp.settimeout(10)

    def wait_for(name, timeout, retry=None):
        marker = re.compile(rb"[\r\n]" + name + rb"\r\n")
        data = b""
        deadline = time.monotonic() + timeout
        while not marker.search(data):
            if time.monotonic() > deadline:
                raise RuntimeError(f"Timed out waiting for {name!r}; see serial.log")
            try:
                chunk = serial.recv(65536)
            except TimeoutError:
                if retry:
                    serial.sendall(retry)
                continue
            if not chunk:
                raise RuntimeError("Guest serial console closed")
            log.write(chunk)
            data = (data + chunk)[-65536:]

    def command(body):
        serial.sendall((body + "\n").encode())

    def execute(name, **args):
        stream.write(json.dumps({"execute": name, "arguments": args}).encode() + b"\n")
        stream.flush()
        while True:
            reply = json.loads(stream.readline())
            if "error" in reply:
                raise RuntimeError(reply["error"])
            if "return" in reply:
                return reply["return"]

    json.loads(stream.readline())
    execute("qmp_capabilities")
    # The ready command can be echoed by the tty; match a separate output line.
    probe = b"\necho LOGOUT_VM_CONSOLE_READY\n"
    serial.sendall(probe)
    wait_for(b"LOGOUT_VM_CONSOLE_READY", 60, probe)
    command('mkdir -p /opt/probe; mount -o ro /dev/vdb /opt/probe && '
            'bash /opt/probe/arch-guest-setup.sh && echo LOGOUT_VM_SETUP_OK')
    wait_for(b"LOGOUT_VM_SETUP_OK", 60)
    time.sleep(3)
    execute("screendump", filename=str(results / "initial-greeter.ppm"))
    for key in ("p", "r", "o", "b", "e", "ret"):
        execute("send-key", keys=[{"type": "qcode", "data": key}], **{"hold-time": 35})
        time.sleep(.07)

    command('g=$(id -u plasmalogin); u=$(id -u probe); '
            'for i in {1..120}; do '
            's=$(loginctl show-user probe -p Display --value); '
            'if [[ $(loginctl show-session "$s" -p Type --value 2>/dev/null) == wayland '
            '&& $(loginctl show-session "$s" -p Service --value 2>/dev/null) == plasmalogin ]] '
            '&& pgrep -u "$u" -x plasmashell >/dev/null '
            '&& [[ $(systemctl show "user@$g.service" -p ActiveState --value) == inactive ]]; '
            'then echo LOGOUT_VM_DESKTOP_READY; break; fi; sleep .25; done')
    wait_for(b"LOGOUT_VM_DESKTOP_READY", 40)
    prep = 'systemctl start "user@$g.service" && ' if mode == "warm" else ""
    expected = "active" if mode == "warm" else "inactive"
    command(prep + f'[[ $(systemctl show "user@$g.service" -p ActiveState --value) == {expected} ]] '
            '&& echo LOGOUT_VM_CONDITION_OK')
    wait_for(b"LOGOUT_VM_CONDITION_OK", 20)
    execute("screendump", filename=str(results / "desktop.ppm"))

    with (results / "frames.tsv").open("w") as times, ThreadPoolExecutor(1) as worker:
        start = time.monotonic()
        command(f'[[ $(systemctl show "user@$g.service" -p ActiveState --value) == {expected} ]] && '
                'logger -t logout-vm LOGOUT_REQUEST && '
                'runuser -u probe -- busctl --address="unix:path=/run/user/$u/bus" '
                'call org.kde.Shutdown /Shutdown org.kde.Shutdown logout '
                '&& printf "\\nLOGOUT_VM_REQUEST_OK\\n"')
        # The guest TTY can block while echoing if the serial socket isn't read.
        requested = worker.submit(wait_for, b"LOGOUT_VM_REQUEST_OK", 10)
        for index in range(175):
            before = time.monotonic()
            name = f"frame-{index:03}.png"
            execute("screendump", filename=str(results / name), format="png")
            after = time.monotonic()
            print(f"{name}\t{before-start:.6f}\t{after-start:.6f}", file=times)
            time.sleep(max(0, .04 - (after - before)))
        requested.result()
    command('for i in {1..40}; do '
            'if [[ $(loginctl show-seat seat0 -p ActiveSession --value) != "$s" ]] '
            '&& pgrep -u "$g" -x plasma-login-gr >/dev/null; '
            'then echo LOGOUT_VM_GREETER_RETURNED; break; fi; sleep .25; done')
    wait_for(b"LOGOUT_VM_GREETER_RETURNED", 12)
    command('journalctl -b --no-pager -o short-monotonic '
            '_SYSTEMD_UNIT=plasmalogin.service + "UNIT=user@$g.service" '
            '+ SYSLOG_IDENTIFIER=plasmalogin-helper + SYSLOG_IDENTIFIER=logout-vm '
            '+ USER_UNIT=plasma-kwin_wayland.service + USER_UNIT=plasma-login-kwin_wayland.service; '
            'echo LOGOUT_VM_DONE')
    wait_for(b"LOGOUT_VM_DONE", 10)
