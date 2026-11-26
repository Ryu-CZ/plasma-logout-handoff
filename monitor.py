"""Sample emulated output during an actual Plasma logout in a disposable VM."""
from concurrent.futures import ThreadPoolExecutor
import base64
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

work, results = map(Path, sys.argv[1:])
mode = os.environ["LOGOUT_VM_MODE"]
manager = "sddm" if mode == "sddm" else "plasmalogin"


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
    barrier = os.environ.get("LOGOUT_VM_START_BARRIER")
    if barrier:
        starters = {
            "both": "startplasma-wayland startplasma-login-wayland",
            "greeter": "startplasma-login-wayland",
        }[barrier]
        script = Path(__file__).resolve().with_name("vm-start-barrier.sh").read_bytes()
        encoded = base64.b64encode(script).decode()
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                f'echo {encoded} | base64 -d >/tmp/logout-vm-barrier && '
                f'(for name in {starters}; do '
                'p=/usr/bin/$name; mv "$p" "$p.logout-vm-stock" && '
                'install -m 755 /tmp/logout-vm-barrier "$p" || exit 1; '
                'done) && printf "\\nLOGOUT_VM_BARRIER_INSTALLED\\n"')
        wait_for(b"LOGOUT_VM_BARRIER_INSTALLED", 10)
    time.sleep(5 if os.environ.get("LOGOUT_VM_GREETER_MARKER") else 3)
    if mode == "sddm" and os.environ.get("SDDM_VM_GREETER_FAIL") == "1":
        command('journalctl -b -u sddm --no-pager -n 35; '
                'for i in {1..60}; do '
                'test ! -e /etc/sddm.conf.d/zz-logout-vm-backend.conf && break; sleep .3; done; '
                'test ! -e /etc/sddm.conf.d/zz-logout-vm-backend.conf && '
                'journalctl -b -u logout-vm-revert.service --no-pager && '
                'systemctl restart sddm && '
                'for i in {1..30}; do '
                'pgrep -x Xorg >/dev/null && sleep 1 && '
                'printf "\\nGUEST_X11_RECOVERED\\n" && break; sleep .3; done')
        wait_for(b"GUEST_X11_RECOVERED", 35)
    execute("screendump", filename=str(results / "initial-greeter.ppm"))
    def press(key):
        execute("send-key", keys=[{"type": "qcode", "data": key}], **{"hold-time": 35})
        time.sleep(.07)

    def sign_in():
        for key in ("p", "r", "o", "b", "e", "ret"):
            press(key)

    sign_in()

    command(f'dm={manager}; g=$(id -u "$dm"); u=$(id -u probe); '
            'for i in {1..120}; do '
            's=$(loginctl show-user probe -p Display --value); '
            'if [[ $(loginctl show-session "$s" -p Type --value 2>/dev/null) == wayland '
            '&& $(loginctl show-session "$s" -p Service --value 2>/dev/null) == "$dm" ]] '
            '&& pgrep -u "$u" -x plasmashell >/dev/null '
            '&& [[ $(systemctl show "user@$g.service" -p ActiveState --value) == inactive ]]; '
            'then echo LOGOUT_VM_DESKTOP_READY; break; fi; sleep .25; done')
    wait_for(b"LOGOUT_VM_DESKTOP_READY", 40)
    prep = 'systemctl start "user@$g.service" && ' if mode == "warm" else ""
    expected = "active" if mode == "warm" else "inactive"
    command(prep + f'[[ $(systemctl show "user@$g.service" -p ActiveState --value) == {expected} ]] '
            '&& echo LOGOUT_VM_CONDITION_OK')
    wait_for(b"LOGOUT_VM_CONDITION_OK", 20)
    if os.environ.get("LOGOUT_VM_DELAY_STOP") == "1":
        # A graphical-session member that outlives KWin during shutdown.
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                'runuser -u probe -- env XDG_RUNTIME_DIR="/run/user/$u" '
                'systemd-run --user --unit=logout-vm-delay --property=Type=oneshot '
                '--property=RemainAfterExit=yes --property=After=graphical-session.target '
                '--property=PartOf=graphical-session.target --property="ExecStop=/usr/bin/sleep 6" '
                '/usr/bin/true && printf "\\nLOGOUT_VM_DELAY_STARTED\\n"')
        wait_for(b"LOGOUT_VM_DELAY_STARTED", 10)
    execute("screendump", filename=str(results / "desktop.ppm"))
    variant = os.environ.get("LOGOUT_VM_HOLDER_PROBE")
    if variant:
        if variant not in ("stock", "holder", "stall"):
            raise ValueError("invalid holder probe variant")
        qml = Path(os.environ["LOGOUT_VM_HOLDER_QML"]).read_bytes()
        encoded = base64.b64encode(qml).decode()
        command(f'echo {encoded} | base64 -d >/tmp/holder-probe.qml; '
                'shell_pid=$(pgrep -u "$u" -x plasmashell | head -1); '
                'display=$(tr "\\000" "\\n" <"/proc/$shell_pid/environ" '
                '| grep "^WAYLAND_DISPLAY=" | cut -d= -f2-); '
                'test -n "$display" && '
                'runuser -u probe -- env XDG_RUNTIME_DIR="/run/user/$u" '
                'WAYLAND_DISPLAY="$display" QT_QPA_PLATFORM=wayland '
                f'/usr/lib/qt6/bin/qml /tmp/holder-probe.qml -- {variant} '
                '2>&1 & job=$!')
        wait_for(b"qml: HOLDER_PROBE_READY", 20)
        for index in range(55):
            execute("screendump", filename=str(results / f"holder-{index:02d}.png"),
                    format="png")
            time.sleep(0.07)
        command('wait "$job"; printf "\\nHOLDER_PROBE_EXIT_%s\\n" "$?"')
        wait_for(b"HOLDER_PROBE_EXIT_" + (b"3" if variant == "stall" else b"0"), 10)
        frames = sorted(results.glob("holder-*.png"))
        pixels = subprocess.check_output([
            "magick", *(str(frame) for frame in frames),
            "-gravity", "center", "-crop", "1x1+0+0", "+repage",
            "-depth", "8", "rgb:-",
        ])
        colors = [pixels[i:i + 3].hex() for i in range(0, len(pixels), 3)]
        first = "000000" if variant == "stock" else "bf8030"
        final = "aa36a5" if variant == "stall" else "30965d"
        if first not in colors or final not in colors[colors.index(first) + 1:]:
            raise RuntimeError(
                f"holder probe not visible as expected; observed {sorted(set(colors))}")
        if variant != "stock" and "000000" in colors[colors.index(first):colors.index(final)]:
            raise RuntimeError("black sample between holder and successor")
        sys.exit(0)

    if os.environ.get("LOGOUT_VM_VT_PROBE") == "1":
        command('v=$(fgconsole); k=$(pgrep -u "$u" -x kwin_wayland | head -1); '
                'snap() { echo "VT_PROBE $1 vt=$(fgconsole) kwin=$k"; '
                'for f in /sys/kernel/debug/dri/*/clients; do '
                'test -f "$f" && awk -v pid="$k" '
                """'NR==1 || $4=="y" || $2==pid' "$f"; done; }; """
                'snap before; chvt 9 && sleep 1 && snap away; '
                'chvt "$v" && sleep 1 && snap back && printf "\\nVT_PROBE_DONE\\n"')
        wait_for(b"VT_PROBE_DONE", 15)
    if os.environ.get("LOGOUT_VM_KMS_TRACE") == "1":
        command('k=$(pgrep -u "$u" -x kwin_wayland | head -1); '
                'echo "KMS_DESKTOP_PID=$k"; '
                'grep -E "^(plane|crtc)|^[[:space:]]+(crtc|fb|enable|active)=" '
                '/sys/kernel/debug/dri/0/state; '
                't=/sys/kernel/tracing; echo mono > "$t/trace_clock"; '
                """echo 'p:kms_set_mode drm_atomic_set_mode_for_crtc mode=$arg2' """
                '>> "$t/kprobe_events" && echo 1 > "$t/events/kprobes/kms_set_mode/enable" '
                '&& printf "\\nKMS_TRACE_READY\\n"')
        wait_for(b"KMS_TRACE_READY", 5)
    if os.environ.get("LOGOUT_VM_PAINT_FBCON") == "1":
        # Preload the disposable guest's fbdev backing store; do not change VT.
        paint = """from pathlib import Path
root = Path('/sys/class/graphics/fb0')
height = int((root / 'virtual_size').read_text().split(',')[1])
size = int((root / 'stride').read_text()) * height
assert 0 < size <= 64 * 1024 * 1024
data = b'\\x77' * size
with open('/dev/fb0', 'r+b', buffering=0) as fb:
    assert fb.write(data) == size
    fb.seek(0)
    assert fb.read(size) == data
print('FBCON_PRELOADED')
"""
        payload = base64.b64encode(paint.encode()).decode()
        command(f'echo {payload} | base64 -d | python3')
        wait_for(b"FBCON_PRELOADED", 8)
    if os.environ.get("LOGOUT_VM_KMS_STATE") == "1":
        sampler = """import re, time
from pathlib import Path
state = Path('/sys/kernel/debug/dri/0/state')
with open('/tmp/kms-state', 'w', buffering=1) as out:
    print('\\nKMS_STATE_READY', flush=True)
    last_fb = None
    for _ in range(600):
        start = time.monotonic()
        fields = re.findall(r'^(plane\\[.*|crtc\\[.*|\\s*(?:crtc|fb|enable|active)=.*)$',
                            state.read_text(), re.M)
        print(f'{start:.6f} {time.monotonic():.6f}', *(f.strip() for f in fields), file=out)
        fb = next((f.strip() for f in fields if f.strip().startswith('fb=')), '')
        if fb != last_fb:
            owners = state.with_name('framebuffer').read_text()
            block = re.search(r'(?m)^framebuffer\\[' + fb[3:] + r'\\]:.*(?:\\n[ \\t].*)*', owners)
            with open('/tmp/kms-owners', 'a') as owner_log:
                print(start, fb, block[0].splitlines()[:2] if block else 'unlisted', file=owner_log)
            last_fb = fb
        time.sleep(.005)
"""
        payload = base64.b64encode(sampler.encode()).decode()
        command(f'echo {payload} | base64 -d >/tmp/sample-state.py; python3 /tmp/sample-state.py &')
        wait_for(b"KMS_STATE_READY", 8)
    relay = os.environ.get("LOGOUT_VM_RELAY")
    if relay in ("1", "hold", "vt", "switch", "switch-nocard"):
        mode = {"1": "", "hold": " 30 hold", "vt": " 30 hold vt=1",
                "switch": " 30 switch vt=1",
                "switch-nocard": " 30 switch vt=1 nocard"}[relay]
        payload = base64.b64encode(Path(__file__).resolve().with_name("relay.py").read_bytes()).decode()
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                f'echo {payload} | base64 -d >/tmp/relay.py && '
                f'{{ python3 /tmp/relay.py "$dm"{mode} >/tmp/relay.log 2>&1 & }} && '
                'for i in {1..50}; do grep -q " READY " /tmp/relay.log && break; sleep .1; done; '
                'cat /tmp/relay.log; grep -q " READY " /tmp/relay.log '
                '&& printf "\\nRELAY_STARTED\\n"')
        wait_for(b"RELAY_STARTED", 10)
    if relay in ("vt", "switch", "switch-nocard"):
        # Stopping order is the reverse of After=, so ExecStop runs while the
        # desktop shell is still on screen.
        unit = ("[Unit]\nPartOf=plasma-plasmashell.service\n"
                "After=plasma-plasmashell.service\n"
                "[Service]\nType=oneshot\nRemainAfterExit=yes\n"
                "ExecStart=/usr/bin/true\nExecStop=/usr/bin/touch /tmp/relay-go\n")
        payload = base64.b64encode(unit.encode()).decode()
        command('d=/home/probe/.config/systemd/user; runuser -u probe -- mkdir -p $d; '
                f'echo {payload} | base64 -d >$d/logout-vm-relay-trigger.service && '
                'chown probe: $d/logout-vm-relay-trigger.service && '
                'p() { runuser -u probe -- env XDG_RUNTIME_DIR=/run/user/$u systemctl --user "$@"; }; '
                'p daemon-reload && p start logout-vm-relay-trigger.service && '
                'printf "\\nRELAY_TRIGGER_ARMED\\n"')
        wait_for(b"RELAY_TRIGGER_ARMED", 10)
    # Wait for a new greeter connection, not a fixed delay after sampling.
    command('before=$(journalctl -b -u "$dm.service" --no-pager -o cat '
            '| grep -Fc "Message received from greeter: Connect"); '
            '[[ $before -ge 1 ]] && echo LOGOUT_VM_BASELINE_READY')
    wait_for(b"LOGOUT_VM_BASELINE_READY", 5)
    with (results / "frames.tsv").open("w") as times, ThreadPoolExecutor(1) as worker:
        start = time.monotonic()
        def clock_anchor():
            # The guest uptime read is bracketed by host send/receive times.
            lo = time.monotonic() - start
            command('read up _ </proc/uptime; printf "\\nKMS_CLOCK_%s\\n" "$up"')
            wait_for(rb"KMS_CLOCK_[0-9]+\.[0-9]+", 5)
            with (results / "clock.tsv").open("a") as anchors:
                print(lo, time.monotonic() - start, file=anchors)
        if os.environ.get("LOGOUT_VM_KMS_STATE") == "1":
            clock_anchor()
        command(f'[[ $(systemctl show "user@$g.service" -p ActiveState --value) == {expected} ]] && '
                'logger -t logout-vm LOGOUT_REQUEST && '
                'runuser -u probe -- busctl --address="unix:path=/run/user/$u/bus" '
                'call org.kde.Shutdown /Shutdown org.kde.Shutdown logout '
                '&& for i in {1..280}; do '
                'count=$(journalctl -b -u "$dm.service" --no-pager -o cat '
                '| grep -Fc "Message received from greeter: Connect"); '
                'if [[ $count -gt $before ]]; '
                'then printf "\\nLOGOUT_VM_GREETER_RETURNED\\n"; break; fi; sleep .05; done')
        # Drain serial concurrently so guest TTY output cannot stall logout.
        returned = worker.submit(wait_for, b"LOGOUT_VM_GREETER_RETURNED", 22)
        attempted = False
        keys = iter(("p", "r", "o", "b", "e", "ret"))
        next_key = None
        for index in range(450 if os.environ.get("LOGOUT_VM_STOP_FIX") else 175):
            if returned.done() and next_key is None:
                if returned.exception():
                    break
                # Allow the password field to appear without interrupting captures.
                next_key = time.monotonic() + .8
            if next_key is not None and not attempted and time.monotonic() >= next_key:
                key = next(keys)
                execute("send-key", keys=[{"type": "qcode", "data": key}], **{"hold-time": 35})
                next_key = time.monotonic() + .07
                attempted = key == "ret"
            before = time.monotonic()
            name = f"frame-{index:03}.png"
            execute("screendump", filename=str(results / name), format="png")
            after = time.monotonic()
            print(f"{name}\t{before-start:.6f}\t{after-start:.6f}", file=times)
            time.sleep(max(0, .04 - (after - before)))
        try:
            returned.result()
        except RuntimeError:
            pass  # Still collect the journal for a failed greeter return.
        if os.environ.get("LOGOUT_VM_KMS_STATE") == "1" and not returned.exception():
            clock_anchor()
    command('result=failed; for i in {1..40}; do '
            'n=$(loginctl show-seat seat0 -p ActiveSession --value); '
            'if [[ $n != "$s" && $(loginctl show-session "$n" -p Name --value 2>/dev/null) == probe '
            '&& $(loginctl show-session "$n" -p Service --value 2>/dev/null) == "$dm" ]] '
            '&& pgrep -u "$u" -x plasmashell >/dev/null; '
            'then result=passed; break; fi; sleep .25; done; '
            'echo "LOGOUT_VM_RELOGIN=$result"; '
            'journalctl -b --no-pager -o short-monotonic '
            '"_SYSTEMD_UNIT=$dm.service" + "UNIT=user@$g.service" '
            '+ SYSLOG_IDENTIFIER=plasmalogin-helper + SYSLOG_IDENTIFIER=logout-vm '
            '+ SYSLOG_IDENTIFIER=kwin_wayland + SYSLOG_IDENTIFIER=plasma-login-wallpaper '
            '+ USER_UNIT=plasma-kwin_wayland.service + USER_UNIT=plasma-login-kwin_wayland.service '
            '+ USER_UNIT=logout-vm-delay.service + USER_UNIT=plasma-wallpaper.service '
            '+ _SYSTEMD_UNIT=logout-holder.service + UNIT=logout-holder.service '
            '+ _SYSTEMD_UNIT=polkit.service '
            '+ "_SYSTEMD_UNIT=user@$u.service" _COMM=systemd '
            '+ "_SYSTEMD_UNIT=user@$g.service" _COMM=systemd; '
            'echo LOGOUT_VM_DONE')
    wait_for(b"LOGOUT_VM_DONE", 20)
    if os.environ.get("LOGOUT_VM_KMS_TRACE") == "1":
        command('echo 0 > "$t/events/kprobes/kms_set_mode/enable"; '
                'grep kms_set_mode "$t/trace" | tail -100; printf "\\nKMS_TRACE_END\\n"')
        wait_for(b"KMS_TRACE_END", 10)
    if os.environ.get("LOGOUT_VM_KMS_STATE") == "1":
        command("""head -20 /tmp/kms-owners; awk '{s=$0; sub(/^[^ ]+ [^ ]+ /,"",s); if (s!=last || NR==1) print "KMS_STATE",$0; last=s} END {print "KMS_LAST",$0}' /tmp/kms-state; """
                'printf "\\nKMS_STATE_END\\n"')
        wait_for(b"KMS_STATE_END", 10)
    if relay:
        command('echo RELAY_LOG_BEGIN; cat /tmp/relay.log; printf "\\nRELAY_LOG_END\\n"')
        wait_for(b"RELAY_LOG_END", 10)
    report = (results / "serial.log").read_bytes()
    if not attempted or b"\rLOGOUT_VM_RELOGIN=passed\r\n" not in report:
        raise RuntimeError("Did not reach a new desktop after logout; see serial.log")
    if os.environ.get("LOGOUT_VM_COMBINED"):
        command('saver() { runuser -u probe -- busctl --address="unix:path=/run/user/$u/bus" '
                'call org.freedesktop.ScreenSaver /org/freedesktop/ScreenSaver '
                'org.freedesktop.ScreenSaver "$1"; }; '
                'saver Lock && for i in {1..40}; do '
                'if [[ $(saver GetActive) == "b true" ]]; '
                'then printf "\\nLOGOUT_VM_LOCKED\\n"; break; fi; sleep .25; done')
        wait_for(b"LOGOUT_VM_LOCKED", 15)
        time.sleep(2)
        execute("screendump", filename=str(results / "locked.ppm"))
        press("ret")  # Dismiss the lock clock before entering the VM password.
        time.sleep(.8)
        sign_in()
        command('for i in {1..40}; do '
                'if [[ $(saver GetActive) == "b false" ]]; '
                'then printf "\\nLOGOUT_VM_UNLOCKED\\n"; break; fi; sleep .25; done')
        wait_for(b"LOGOUT_VM_UNLOCKED", 15)
        execute("screendump", filename=str(results / "unlocked.ppm"))
