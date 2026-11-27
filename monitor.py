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
# The first sign-in after logout must fail (injected slow stop). "stuck": no
# login screen may follow. "recover": one must, and the next sign-in must work.
failed = os.environ.get("LOGOUT_VM_FAILED_RELOGIN")
if failed not in (None, "stuck", "recover"):
    raise ValueError("LOGOUT_VM_FAILED_RELOGIN must be stuck or recover")
if failed and (manager != "plasmalogin" or os.environ.get("LOGOUT_VM_SHUTDOWN")):
    raise ValueError("LOGOUT_VM_FAILED_RELOGIN needs a Plasma Login Manager logout")


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
        while not (found := marker.search(data)):
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
        return found[0].strip()

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
    no_scale = os.environ.get("LOGOUT_VM_GREETER_NO_SCALE") == "1"
    if no_scale:
        # The animation override as applied by hand on Vandal, before any
        # upgrade below: runs the real test script.
        script = Path(__file__).resolve().with_name("greeter-animation-test.sh")
        encoded = base64.b64encode(script.read_bytes()).decode()
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                f'echo {encoded} | base64 -d >/tmp/greeter-animation-test.sh && '
                'bash /tmp/greeter-animation-test.sh apply && '
                'printf "\\nLOGOUT_VM_NO_SCALE_%s\\n" OK')
        wait_for(b"LOGOUT_VM_NO_SCALE_OK", 10)
    # Change the installation as on a running machine: from the desktop, with
    # the login manager already running.
    installs = []
    if os.environ.get("LOGOUT_VM_HOLDER_UPGRADE"):
        installs += ["bash /tmp/logout-holder/install.sh --restore",
                     "bash /tmp/logout-holder-new/install.sh"]
        if no_scale:
            # The new installer must take over from the test files.
            installs += ["test ! -e /etc/systemd/user/plasma-login-kwin_wayland.service.d/81-no-open-animation.conf",
                         "test ! -e /usr/local/lib/logout-holder-test",
                         "grep -qx scaleEnabled=false /usr/local/lib/logout-holder/xdg/kwinrc"]
    if os.environ.get("LOGOUT_VM_HOLDER_RESTORE") == "1":
        last = "logout-holder-new" if installs else "logout-holder"
        installs += [f"bash /tmp/{last}/install.sh --restore",
                     "test ! -e /usr/local/lib/logout-holder",
                     "test ! -e /usr/local/bin/startplasma-login-wayland",
                     "test ! -e /etc/systemd/user/plasma-login-kwin_wayland.service.d/80-logout-holder.conf"]
    if installs:
        command(" && ".join(installs) + ' && { ls -l /usr/local/bin/ /usr/local/lib/logout-holder 2>&1; '
                'printf "\\nLOGOUT_VM_INSTALL_%s\\n" OK; }')
        wait_for(b"LOGOUT_VM_INSTALL_OK", 30)
    if os.environ.get("LOGOUT_VM_GREETER_FORCE_ANIMATIONS") == "1":
        # KWin turns script animations off on a software renderer (llvmpipe),
        # so the VM greeter would never run them; Vandal renders in hardware.
        dropin = '[Service]\nEnvironment="KWIN_EFFECTS_FORCE_ANIMATIONS=1"\n'
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                'install -d /etc/systemd/user/plasma-login-kwin_wayland.service.d && '
                f'echo {base64.b64encode(dropin.encode()).decode()} | base64 -d '
                '>/etc/systemd/user/plasma-login-kwin_wayland.service.d/82-force-animations.conf && '
                'printf "\\nLOGOUT_VM_FORCE_ANIM_%s\\n" OK')
        wait_for(b"LOGOUT_VM_FORCE_ANIM_OK", 10)
    breakage = os.environ.get("LOGOUT_VM_HOLDER_BROKEN")
    if breakage:
        # Make an installed copy impossible to load, as a library update could:
        # same-length edits of the names the loader looks up.
        edits = {"library": ("kwin_wayland", r"s/libQt6Core\.so\.6/libQt6Gone.so.6/g"),
                 "symbol": ("plasma-login-wallpaper",
                            r"s/_ZN10QQuickItem13setParentItemEPS_/_ZN10QQuickItem13setParentGoneEPS_/g")}
        name, edit = edits[breakage]
        path = f"/usr/local/lib/logout-holder/greeter/{name}"
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                f'cp {path} /tmp/logout-vm-copy && sed -i "{edit}" {path} && '
                f'! cmp -s {path} /tmp/logout-vm-copy && printf "\\nLOGOUT_VM_BROKEN_%s\\n" OK')
        wait_for(b"LOGOUT_VM_BROKEN_OK", 10)
    crash = os.environ.get("LOGOUT_VM_CRASH_REPORT")
    if crash not in (None, "stock", "fixed"):
        raise ValueError("LOGOUT_VM_CRASH_REPORT must be stock or fixed")
    if os.environ.get("LOGOUT_VM_DELAY_STOP") == "1" or crash or failed:
        # A graphical-session member that outlives KWin during shutdown, like
        # an app that is slow to quit (NetBird took 2.4 s on Vandal).
        seconds = int(os.environ.get("LOGOUT_VM_DELAY_STOP_SECONDS", "6"))
        command('[[ $(systemd-detect-virt --vm) == kvm ]] && '
                'runuser -u probe -- env XDG_RUNTIME_DIR="/run/user/$u" '
                'systemd-run --user --unit=logout-vm-delay --property=Type=oneshot '
                '--property=RemainAfterExit=yes --property=After=graphical-session.target '
                f'--property=PartOf=graphical-session.target --property="ExecStop=/usr/bin/sleep {seconds}" '
                '/usr/bin/true && printf "\\nLOGOUT_VM_DELAY_STARTED\\n"')
        wait_for(b"LOGOUT_VM_DELAY_STARTED", 10)
    if crash:
        # Copies of drkonqi 6.8.3's coredump launcher units, dependencies
        # unchanged; the service activates the portal and a11y bus as the Qt
        # launcher does, then fails as it does without a display.
        files = {
            "logout-vm-crash.socket":
                "[Unit]\nDefaultDependencies=no\nPartOf=plasma-core.target\n"
                "After=plasma-kwin_wayland.service\nAfter=sockets.target\n"
                "[Socket]\nListenSequentialPacket=%t/logout-vm-crash\n"
                "SocketMode=0600\nAccept=yes\n",
            "logout-vm-crash@.service":
                "[Unit]\nPartOf=graphical-session.target\n"
                "Requisite=graphical-session.target\n"
                "[Service]\nRestart=no\nExecStart=/bin/sh -c '"
                "logger -t logout-vm CRASH_REPORT_STARTED; "
                "{ busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop "
                "org.freedesktop.portal.Settings ReadOne ss org.freedesktop.appearance color-scheme; "
                "busctl --user call org.a11y.Bus /org/a11y/bus org.a11y.Bus GetAddress; } 2>&1 "
                "| logger -t logout-vm; "
                # On Vandal xdg-desktop-portal kept re-activating portal-kde,
                # which crashed without a display until its start limit.
                "n=0; for i in $$(seq 40); do busctl --user call org.freedesktop.impl.portal.desktop.kde "
                "/org/freedesktop/portal/desktop org.freedesktop.DBus.Peer Ping >/dev/null 2>&1 "
                "|| n=$$((n+1)); sleep .1; done; logger -t logout-vm CRASH_REPORT_PINGS_FAILED=$$n; exit 1'\n",
        }
        if crash == "fixed":
            files["logout-vm-crash.socket.d/stop-with-graphical-session.conf"] = (
                "[Unit]\nPartOf=graphical-session.target\n")
        install = "".join(
            f'runuser -u probe -- mkdir -p "$(dirname "$d/{name}")" && '
            f'echo {base64.b64encode(text.encode()).decode()} | base64 -d '
            f'| runuser -u probe -- tee "$d/{name}" >/dev/null && '
            for name, text in files.items())
        command('d=/home/probe/.config/systemd/user; '
                'p() { runuser -u probe -- env XDG_RUNTIME_DIR=/run/user/$u systemctl --user "$@"; }; '
                + install +
                'p daemon-reload && p start logout-vm-crash.socket && '
                'p show logout-vm-crash.socket -p PartOf | sed "s/^/CRASH_SOCKET /" && '
                'printf "\\nLOGOUT_VM_CRASH_ARMED\\n"')
        wait_for(b"LOGOUT_VM_CRASH_ARMED", 10)
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
    shutdown = os.environ.get("LOGOUT_VM_SHUTDOWN")
    if shutdown:
        # Restart or shut down from the desktop, as the Plasma menu does. QEMU
        # runs with -no-reboot, so either one ends QEMU and closes the serial
        # console. A guest still running afterwards means it was refused.
        method = {"reboot": "logoutAndReboot", "halt": "logoutAndShutdown"}[shutdown]
        # Follow the helper's log on the console; the guest's disk is discarded.
        command('(journalctl -f -n0 -o cat -u logout-holder.service '
                '| sed -u "s/^/HOLDER_LOG /") &')
        command('logger -t logout-vm SHUTDOWN_REQUEST && '
                'runuser -u probe -- busctl --address="unix:path=/run/user/$u/bus" '
                f'call org.kde.Shutdown /Shutdown org.kde.Shutdown {method} && '
                '(sleep 25; journalctl -b --no-pager -o short-monotonic '
                '_SYSTEMD_UNIT=logout-holder.service + UNIT=logout-holder.service '
                '+ _SYSTEMD_UNIT=polkit.service + SYSLOG_IDENTIFIER=logout-vm; '
                'echo LOGOUT_VM_STILL_RUNNING) &')
        try:
            wait_for(b"LOGOUT_VM_STILL_RUNNING", 40)
        except RuntimeError as error:
            if str(error) != "Guest serial console closed":
                raise
            print(f"LOGOUT_VM_SHUTDOWN={shutdown} passed")
            sys.exit(0)
        raise RuntimeError(f"{shutdown} did not happen; see serial.log")
    if crash:
        # Report a "crash" once the slow app is stopping, i.e. while the stop
        # job of graphical-session.target is still waiting for it.
        connect_crash = ("import socket, sys; s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET); "
                         "s.connect(sys.argv[1]); s.send(b'x')")
        command('(for i in {1..400}; do '
                '[[ $(p is-active logout-vm-delay.service) == deactivating ]] && break; sleep .025; done; '
                'sleep .3; logger -t logout-vm "CRASH_TRIGGER delay=$(p is-active logout-vm-delay.service) '
                'jobs=$(p list-jobs --no-legend | awk \'{print $2"/"$3}\' | tr "\\n" " ")"; '
                f'if runuser -u probe -- python3 -c "{connect_crash}" "/run/user/$u/logout-vm-crash" 2>/dev/null; '
                'then logger -t logout-vm CRASH_TRIGGER_CONNECTED; '
                'else logger -t logout-vm CRASH_TRIGGER_REFUSED; fi; '
                'sleep 3; logger -t logout-vm "AFTER_TEARDOWN graphical-session.target=$(p is-active graphical-session.target) '
                'jobs=$(p list-jobs --no-legend | awk \'{print $2"/"$3}\' | tr "\\n" " ")") &')
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
                'then printf "\\nLOGOUT_VM_GREETER_RETURNED\\n"; break; fi; sleep .05; done'
                + ('; sleep ' + str(float(os.environ.get("LOGOUT_VM_EFFECTS_PROBE_DELAY", ".3"))) + '; k() { runuser -u "$dm" -- busctl --address="unix:path=/run/user/$g/bus" "$@"; }; '
                   'k get-property org.kde.KWin /Effects org.kde.kwin.Effects loadedEffects '
                   '| sed "s/^/GREETER_EFFECTS /"; '
                   'k call org.kde.KWin /KWin org.kde.KWin supportInformation '
                   '| grep -o -E "(Compositing Type|OpenGL renderer|OpenGL platform|Painting backend)[A-Za-z ]*: [A-Za-z0-9 ._()/:-]*" '
                   '| sed "s/^/GREETER_RENDER /"'
                   if os.environ.get("LOGOUT_VM_EFFECTS_PROBE") == "1" else ""))
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
                next_key = time.monotonic() + float(os.environ.get("LOGOUT_VM_RELOGIN_DELAY", ".8"))
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
    def shot(name):
        execute("screendump", filename=str(results / name), format="png")
        mean = float(subprocess.check_output(
            ["magick", str(results / name), "-format", "%[fx:mean]", "info:"]))
        print(f"{name}: mean brightness {mean:.4f}")
        return mean

    if failed:
        if returned.exception() or not attempted:
            raise RuntimeError("No sign-in attempt after logout; see serial.log")
        command('refused() { journalctl -b --no-pager -o cat "_SYSTEMD_UNIT=user@$1.service" _COMM=systemd '
                '| grep -Fc "Transaction for $2/start is destructive"; }; '
                'connects() { journalctl -b -u "$dm.service" --no-pager -o cat '
                '| grep -Fc "Message received from greeter: Connect"; }; '
                'p() { runuser -u probe -- env XDG_RUNTIME_DIR=/run/user/$u systemctl --user "$@"; }; '
                'for i in {1..40}; do [[ $(refused $u plasma-workspace-wayland.target) -ge 1 ]] '
                '&& { printf "\\nLOGOUT_VM_DESKTOP_%s\\n" REFUSED; break; }; sleep .25; done')
        wait_for(b"LOGOUT_VM_DESKTOP_REFUSED", 15)
        # Long enough for the injected stop to finish, so a late login screen counts.
        command('n=0; for i in {1..80}; do [[ $(connects) -ge $((before+2)) ]] && { n=1; break; }; '
                'sleep .25; done; printf "\\nLOGOUT_VM_SECOND_GREETER=%s\\n" $n')
        second = wait_for(rb"LOGOUT_VM_SECOND_GREETER=[01]", 60).endswith(b"1")
        if failed == "recover":
            if not second:
                shot("no-greeter.png")
            else:
                command('for i in {1..80}; do '
                        'm=$(systemctl show "user@$u.service" -p ActiveState --value); '
                        'if [[ $m == inactive ]] || { [[ $(p is-active graphical-session.target) == inactive ]] '
                        '&& ! p list-jobs --no-legend | grep -qw stop; }; then '
                        'printf "\\nLOGOUT_VM_OLD_STOP_%s manager=%s\\n" DONE "$m"; '
                        'logger -t logout-vm "SECOND_SIGN_IN user-manager=$m"; break; fi; sleep .25; done')
                wait_for(rb"LOGOUT_VM_OLD_STOP_DONE manager=[a-z]+", 30)
                time.sleep(2)  # Allow the password field to appear.
                if shot("recovered-greeter.png") < .02:
                    raise RuntimeError("The second login screen is black")
                sign_in()
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
            '+ _SYSTEMD_USER_UNIT=plasma-login-kwin_wayland.service '
            '+ _SYSTEMD_USER_UNIT=plasma-wallpaper.service '
            '+ SYSLOG_IDENTIFIER=logout-holder '
            '+ _SYSTEMD_UNIT=logout-holder.service + UNIT=logout-holder.service '
            '+ _SYSTEMD_UNIT=polkit.service '
            '+ "_SYSTEMD_UNIT=user@$u.service" _COMM=systemd '
            '+ "_SYSTEMD_UNIT=user@$g.service" _COMM=systemd; '
            'o=/var/lib/plasmalogin/.config/kwinoutputconfig.json; '
            'ls -la "$o"* 2>&1 | sed "s/^/OUTPUTS /"; '
            'cmp "$o" "$(getent passwd probe | cut -d: -f6)/.config/kwinoutputconfig.json" '
            '&& echo "OUTPUTS same as the desktop"; '
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
    if failed:
        time.sleep(3)
        shot("after.png")
        command('printf "\\nLOGOUT_VM_END desktop_refused=%s greeter_refused=%s graphical_session=%s greeter_ui=%s\\n" '
                '$(refused $u plasma-workspace-wayland.target) $(refused $g plasma-login-wayland.target) '
                '"$(p is-active graphical-session.target 2>/dev/null | grep -x active || echo no)" '
                '$(pgrep -u "$g" -fc plasma-login-greeter)')
        end = wait_for(rb"LOGOUT_VM_END desktop_refused=\d+ greeter_refused=\d+ "
                       rb"graphical_session=[a-z]+ greeter_ui=\d+", 15).decode()
        state = dict(field.split("=") for field in end.split()[1:])
        report = (results / "serial.log").read_bytes()
        relogin = b"\rLOGOUT_VM_RELOGIN=passed\r\n" in report
        print(f"{end} second_greeter={second:d} relogin={relogin:d}")
        if failed == "stuck":
            ok = (not second and not relogin and int(state["greeter_refused"]) >= 1
                  and state["greeter_ui"] == "0")
        else:
            ok = (second and relogin and state["desktop_refused"] == "1"
                  and state["greeter_refused"] == "0" and state["graphical_session"] == "active")
        if not ok:
            raise RuntimeError(f"LOGOUT_VM_FAILED_RELOGIN={failed} failed; see serial.log")
        print(f"LOGOUT_VM_FAILED_RELOGIN={failed} passed")
    report = (results / "serial.log").read_bytes()
    if failed == "stuck":
        sys.exit(0)
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
