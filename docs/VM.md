# VM tests

`run-vm.sh` boots a throwaway guest, signs in to Plasma Wayland, logs out,
captures the emulated screen and signs in again. Guest changes are discarded at
power-off. Measured results are in [LOG.md](LOG.md).

## Run

Needs `../plasma-login-handoff` checked out next to this repo, and its
verified VM cache. From the repo root:

```bash
base=~/.cache/plasma-handoff-6.8.3/vm
out=~/.cache/plasma-logout-handoff
mkdir -p "$out"
for mode in cold warm; do
    bash run-vm.sh "$base" "$out/$mode-$(date +%s)" "$mode"
done
```

| Mode | Greeter user manager before the second greeter |
| --- | --- |
| `cold` | stopped (as on the live PC) |
| `warm` | started by the driver |
| `sddm` | uses SDDM; needs `SDDM_VM_PACKAGES` |

- The driver takes 175 captures, about one per 40 ms (450 with
  `LOGOUT_VM_STOP_FIX`).
- It signs back in 0.8 s after the new greeter connects
  (`LOGOUT_VM_RELOGIN_DELAY=SECONDS` changes this).
- Host and guest clocks are not synchronized. Compare times within the
  journal or within the captures, not across them.
- QEMU shows emulated pixels. It says nothing about a physical display, GPU or
  DisplayPort link.
- `python3 vmsum.py RESULTS...` summarizes captures. Its "first gap" also
  counts the black after the password, so check by eye which side of the
  greeter it is on.

## Logout holder

| Variable | Effect |
| --- | --- |
| `LOGOUT_VM_HOLDER_BUNDLE=DIR` | install the bundle, then one logout and sign-in |
| `LOGOUT_VM_THEME=DIR` | inject the live login theme |
| `LOGOUT_VM_HOLDER_STALE=1` | simulate a changed package |
| `LOGOUT_VM_HOLDER_BROKEN=library\|symbol` | KWin copy loses a library, or wallpaper copy a symbol |
| `LOGOUT_VM_HOLDER_UPGRADE=NEW_DIR` | remove the bundle and install `NEW_DIR` from the desktop |
| `LOGOUT_VM_HOLDER_RESTORE=1` | remove the last installed bundle from the desktop |
| `LOGOUT_VM_SHUTDOWN=reboot\|halt` | restart or shut down; passes only if the guest goes down |
| `LOGOUT_VM_FAILED_RELOGIN=stuck\|recover` | fail the first sign-in; `stuck` passes if no greeter follows, `recover` if one does and a second sign-in works |
| `LOGOUT_VM_SLOW_GREETER_STOP=SECONDS` | slow the old greeter KWin's stop, so stock fails every time |
| `LOGOUT_VM_GREETER_FORCE_ANIMATIONS=1` | enable greeter animations (the software renderer disables them) |
| `LOGOUT_VM_GREETER_NO_SCALE=1` | apply `greeter-animation-test.sh` |
| `LOGOUT_VM_EFFECTS_PROBE=1` | log the effects the returned greeter loaded, after `LOGOUT_VM_EFFECTS_PROBE_DELAY` seconds |

**Run `reboot` and `halt` after every holder change.** v3 passed logout and
broke Restart on the live PC.

`LOGOUT_VM_HOLDER_BUNDLE` cannot be combined with the marker, relay or
combined options.

## Re-login races

| Variable | Effect |
| --- | --- |
| `LOGOUT_VM_DELAY_STOP=1` | add a unit that takes 6 s to stop with `graphical-session.target` |
| `LOGOUT_VM_DELAY_STOP_SECONDS=N` | change that delay |
| `LOGOUT_VM_CRASH_REPORT=stock\|fixed` | install copies of the DrKonqi launcher units and send a crash report during logout; `fixed` adds the `PartOf=` drop-in |
| `LOGOUT_VM_START_BARRIER=both\|greeter` | wrap the starters so they wait for queued stops (probe only) |
| `LOGOUT_VM_STOP_FIX=DIR` | install starters built with `build-stop-fix.sh` |
| `LOGOUT_VM_GREETER_FIX=FILE` | replace the greeter starter only; use a full path |

Builds:

```bash
bash build-stop-fix.sh DESKTOP_BUILD GREETER_BUILD NEW_OUTPUT_DIR
bash build-greeter-fix.sh PLASMA_LOGIN_MANAGER_GIT NEW_OUTPUT_DIR
```

`build-stop-fix.sh` needs configured 6.8.3 build trees.
`build-greeter-fix.sh` clones tag `v6.8.3` and builds both the stock and the
patched starter.

## Investigation probes

| Variable | Effect |
| --- | --- |
| `LOGOUT_VM_GREETER_MARKER=BUILD` | greeter-only instrumented KWin; `BUILD` has `bin/` |
| `LOGOUT_VM_GREETER_COLOR=0\|1` | black or magenta marker background |
| `LOGOUT_VM_BACKDROP=1` | compositor backdrop (with the marker build) |
| `LOGOUT_VM_WALLPAPER_BIN=FILE` | patched greeter wallpaper program (with the marker build) |
| `LOGOUT_VM_RELAY=1\|hold\|vt\|switch\|switch-nocard` | run `relay.py` in the given variant |
| `LOGOUT_VM_COMBINED=DIR` | add the combined login and lock build (`bin/`, `lib/`, `share/`) |
| `LOGOUT_VM_VT_PROBE=1` | record DRM master across a VT switch |
| `LOGOUT_VM_KMS_TRACE=1` | trace `drm_atomic_set_mode_for_crtc` |
| `LOGOUT_VM_KMS_STATE=1` | sample DRM state and framebuffer allocator |
| `LOGOUT_VM_PAINT_FBCON=1` | paint the console framebuffer before logout |
| `LOGOUT_VM_HOLDER_PROBE=stock\|holder\|stall` | synthetic frame switch; needs `LOGOUT_VM_HOLDER_QML=FILE` (`holder-probe.qml`) |

`COMBINED` setup: copy `bin/`, `lib/` and `share/` from the lock project's
install prefix into a temporary directory. Overlay the login prefix's KWin
binaries and `libkwin.so.6`. Use it with `LOGOUT_VM_STOP_FIX` and
`LOGOUT_VM_DELAY_STOP=1`.

Backdrop runs also need `kwin_wayland` and `kwin_wayland_wrapper` built with
`patches/kwin-6.8.3-logout-vm-backdrop.patch`.

## SDDM

`SDDM_VM_PACKAGES=DIR` must hold the packages listed in
`sddm-packages.sha256`.

| Variable | Effect |
| --- | --- |
| `SDDM_VM_WAYLAND=1` | Wayland greeter instead of X11 |
| `SDDM_VM_GREETER_FAIL=1` | broken Wayland greeter, then restore X11 |
| `SDDM_VM_RETRO=1` | Xorg `-retro` stipple background |
| `SDDM_VM_ROOT_COLOR=1` | magenta root from Xsetup (needs the `xorg-xsetroot` package) |
| `SDDM_VM_WALLPAPER=1` | `xwallpaper --zoom` from Xsetup (needs the `xwallpaper` package) |

## Physical probes

All are read-only unless noted.

| Script | Use |
| --- | --- |
| `journal-timing.sh` | logout landmarks on the boot clock; `bash journal-timing.sh`, no sudo if you can read the system journal |
| `sample-dp.sh` | Intel DP-1 mode and active VT during a logout: `sudo systemd-run --unit=dp-sample --collect /usr/bin/bash "$PWD/sample-dp.sh"`, then `journalctl -b -u dp-sample` |
| `vt-mode-probe.sh` | switches to a text console and back, prints CRTC modes (changes VT, no root) |
| `probe-generator.sh` | times the NVIDIA environment generator against the sysfs version |
| `loki-logout-capture2.sh` | NVIDIA DRM state during a logout; `HOLD=1` also keeps the card open |

Trial scripts that change the system, each limited to its own host:
`vandal-greeter-generator-trial.sh`, `vandal-rtd3-cleanup-trial.sh`
(`--restore`), `loki-wayland-greeter-trial.sh` (`restore`). Their results are
in [LOG.md](LOG.md).
