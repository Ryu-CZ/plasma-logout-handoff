#!/usr/bin/env python3
"""Run drkonqi-repro.sh, every variant, in a throwaway boot of the test VM.

usage: python3 drkonqi-repro-vm.py BASE_CACHE NEW_LOG

BASE_CACHE is the VM cache used by run-vm.sh. The guest has no network, its
disk is a snapshot and everything is discarded at power-off. No display
manager or Plasma session is started.
"""
import base64
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

base, log_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
script = Path(__file__).resolve().with_name("drkonqi-repro.sh").read_bytes()
variants = ("stock", "after", "no-requisite", "socket-partof", "irreversible")
qemu = base / "qemu/usr"

with tempfile.TemporaryDirectory() as tmp, log_path.open("xb", buffering=0) as log:
    serial_path = f"{tmp}/serial"
    vm = subprocess.Popen(
        ["nice", "-n", "19", str(qemu / "bin/qemu-system-x86_64"), "-L", str(qemu / "share/qemu"),
         "-accel", "kvm", "-machine", "q35", "-cpu", "host", "-m", "2048", "-smp", "2",
         "-device", "VGA", "-nic", "none", "-display", "none", "-no-reboot", "-snapshot",
         "-smbios", "type=1,product=drkonqi-repro",
         "-drive", f"file={base}/arch-system.img,format=raw,if=virtio",
         "-kernel", str(base / "arch-vmlinuz"),
         "-append", "root=/dev/vda rootfstype=ext4 rootwait rw console=ttyS0 "
         "systemd.debug_shell=ttyS0 systemd.mask=serial-getty@ttyS0.service "
         "systemd.mask=systemd-firstboot.service",
         "-serial", f"unix:{serial_path},server=on,wait=off"],
        env={**os.environ, "LD_LIBRARY_PATH": str(qemu / "lib"), "QEMU_MODULE_DIR": str(qemu / "lib/qemu")})
    try:
        client = socket.socket(socket.AF_UNIX)
        deadline = time.monotonic() + 15
        while True:
            try:
                client.connect(serial_path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(.1)
        client.settimeout(.5)

        def wait_for(name, timeout, retry=None):
            marker = re.compile(rb"[\r\n]" + name + rb"\r\n")
            data = b""
            deadline = time.monotonic() + timeout
            while not marker.search(data):
                if time.monotonic() > deadline:
                    raise RuntimeError(f"Timed out waiting for {name!r}; see {log_path}")
                try:
                    chunk = client.recv(65536)
                except TimeoutError:
                    if retry:
                        client.sendall(retry)
                    continue
                if not chunk:
                    raise RuntimeError("Guest serial console closed")
                log.write(chunk)
                data = (data + chunk)[-65536:]

        def command(body):
            client.sendall((body + "\n").encode())

        probe = b"\necho REPRO_CONSOLE_READY\n"
        client.sendall(probe)
        wait_for(b"REPRO_CONSOLE_READY", 60, probe)
        # Refuse to go on anywhere but in this guest.
        command("[[ $(systemd-detect-virt --vm) == kvm && "
                "$(< /sys/class/dmi/id/product_name) == drkonqi-repro ]] && "
                "id repro >/dev/null 2>&1 || useradd -m -G systemd-journal repro; "
                "u=$(id -u repro) && systemctl start user@$u.service && echo REPRO_USER_READY")
        wait_for(b"REPRO_USER_READY", 60)
        encoded = base64.encodebytes(script).decode()
        command(f"base64 -d >/tmp/drkonqi-repro.sh <<'REPRO_END'\n{encoded}REPRO_END\n"
                "echo REPRO_COPIED")
        wait_for(b"REPRO_COPIED", 20)
        for variant in variants:
            done = f"REPRO_DONE_{variant}"
            command("runuser -u repro -- env XDG_RUNTIME_DIR=/run/user/$u SYSTEMD_COLORS=0 "
                    f"bash /tmp/drkonqi-repro.sh {variant} >/tmp/{variant}.out 2>&1; "
                    f"echo REPRO_BEGIN_{variant}; cat /tmp/{variant}.out; echo {done}")
            wait_for(done.encode(), 90)
    finally:
        vm.kill()
        vm.wait()
print(log_path)
