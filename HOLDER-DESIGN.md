# Logout image holder: feasibility gates

A resident process can prepare an image before logout, but it cannot
present on the same output while the desktop or greeter independently
owns DRM master. The physical fd-only A/B did not preserve the CRTC
through the Xorg takeover. That rules out the passive fd holder in
this configuration, not every possible driver-side handoff.

## Design decision: image relay to remove the black (2026-11-26)

**Status:** accepted for a VM prototype at the user's request. Not
installed or validated on any physical machine. It is an attempt to
remove the logout black completely and may fail.

**Context.** On Vandal, console mode matching plus the greeter generator
override reduced filmed black from about 5.5 s to 1.6 s (one run each).
What remains is rendered or console content during desktop teardown,
compositor change and greeter startup.

**Decision.** Keep a trusted picture on scanout across the whole handoff
by relaying it, with three cooperating stages:

1. *Departing desktop:* its compositor keeps painting the wallpaper while
   the Plasma shell stops.
2. *Gap:* a small privileged relay prepares a framebuffer before logout.
   When the output has no DRM master and shows something else, it takes
   master, shows the picture and drops master immediately. Scanout keeps
   the picture without an owner. It repeats if the console restores
   itself.
3. *Incoming greeter:* its compositor paints the same picture from its
   first frame until the greeter UI is ready.

**Safety rules.** The relay never takes master while the greeter's
compositor process exists, because logind fails device activation if
another process is master. It has a deadline and restores the console
buffer if nothing takes over. It changes no authentication, seat or
session ownership. Stage 3 must not be able to block graphical login.

**Not chosen.**

- A resident compositor hosting both sessions: a seat and session
  redesign, kept only as a last resort.
- Painting the console once: it appeared in the guest but did not last
  until the greeter (`preload-1795644288`). Earlier advice here not to
  repaint a VT stands for the console buffer; the relay differs by
  showing its own buffer.
- Passive device handle (loki) and a compositor parked on another VT
  (guest): neither kept the output.

**Order and gates.** Stage 2 first, in the VM, because it is the
unproven part: the picture must replace the console interval and
password re-login must still work, over repeated runs. Then stage 3 and
stage 1 in the VM, then all three together including a stalled greeter
and lock/unlock. Physical installation needs separate approval, an armed
rollback and a recovery path. Emulated captures say nothing about i915
timing or the monitor.

### Relay VM results: gap stage alone

Cold PLM logouts with password re-login, `relay-batch.ic3YRW` (interleaved).
Counts are captures in the first dark stretch, roughly 40 ms or more
apart, with an orange test picture. They are samples, not frame times.

| Condition | Black | Partly dark | Relay picture | Re-login |
| --- | --- | --- | --- | --- |
| Stock, 3 runs | 15, 17, 17 | 2, 0, 0 | none | 3/3 |
| Relay, 3 runs | 7, 7, 8 | 1, 2, 2 | 6, 6, 6 | 3/3 |
| Relay + greeter VT preset to graphics, 3 runs | 7, 7, 6 | 0, 1, 1 | 7, 6, 7 | 3/3 |

One further stock/relay pair (`relay-ab-*-1795691939`) agreed. In its
relay run the framebuffer listing showed desktop KWin → relay → fbcon →
relay → fbcon → relay → greeter KWin. The relay painted two or three
times per logout, holding master for 1-40 ms; the console was still
visible for short periods before a repaint. Black remains before the
first paint (departing KWin) and after the greeter KWin takes the output.
The VT preset had no clear benefit and was removed. Nine batch logouts
cannot rule out the master race, and a greeter that never presents,
lock/unlock and i915 behaviour are untested.

### Relay VM results: all three stages together

The compositor backdrop is
[`patches/kwin-6.8.3-logout-vm-backdrop.patch`](patches/kwin-6.8.3-logout-vm-backdrop.patch),
applied to KWin 6.8.3 (it includes the login project's marker and startup
wallpaper changes). It paints an image whenever no desktop window exists.
Build `kwin_wayland` and `kwin_wayland_wrapper`, then run with
`LOGOUT_VM_RELAY=1 LOGOUT_VM_BACKDROP=1 LOGOUT_VM_GREETER_MARKER=<build>`.
The relay picture is orange and the backdrop cyan, to attribute captures.

| Condition (`backdrop-smoke-*`, `backdrop-batch.qw5Vgp`) | Black | Partial | Re-login |
| --- | --- | --- | --- |
| Stock (batch above) | 15, 17, 17 | 2, 0, 0 | 3/3 |
| Backdrop only, 2 runs | 10, 10 | 0, 0 | 2/2 |
| Relay + backdrop, 4 runs | 3, 2, 2, 1 | 0, 1, 2, 2 | 4/4 |

Some "partial" captures in the summariser are orange/cyan splits with no
black; others are part black. Remaining full-black captures seen:

1. Departing desktop, as the Plasma shell stops, before the first relay
   paint. The backdrop did not cover it; cause not traced.
2. A console repaint before the relay replaced it.
3. Greeter UI already drawing (keyboard hint visible) on black, before
   its wallpaper. Hypothesis: a desktop-type greeter window hides the
   backdrop or itself paints black.

Not done: those three, a stalled greeter, relay timeout, lock/unlock, a
real wallpaper, and anything on physical hardware. The backdrop condition
also needs review for direct scanout before any desktop use.

### Relay VM results: console switch and transparent wallpaper window

2026-11-26. Cold PLM logouts with password re-login; first dark stretch
only. `python3 vmsum.py <run dirs>` reproduces the counts.

| Condition | Black | Partial | Re-login |
| --- | --- | --- | --- |
| Hold master, 1 run (`hold-smoke-*`) | 1 | 1 | 1/1 |
| Console switch, 6 runs (`vt-smoke-*`, `vt-batch.asHsds`) | 1, 0, 1, 1, 0, 0 | 1, 1, 0, 0, 1, 1 | 6/6 |
| + wallpaper window delayed, 2 runs (`ready-*`) | 0, 6 | 0, 0 | 2/2 |
| **+ transparent window, 6 runs (`clear-batch.Y2zacD`)** | **0 in all** | **0 in all** | 6/6 |

- **Holding master does not stop the console.** It still replaced the
  relay picture; the kernel forces the console back when its VT returns
  to text mode.
- **Console switch (`LOGOUT_VM_RELAY=vt`).** A user unit's `ExecStop`
  touches `/tmp/relay-go` before `plasma-plasmashell.service` stops. The
  relay puts greeter VT 1 in graphics mode, switches to it, paints, holds
  master and releases it when the greeter's compositor process appears.
  No console frame appeared in these runs. This also covers desktop
  teardown. In `vt-4` the shell took 4.1 s to stop; the picture stayed.
  `vt-2` exited 2 only because the runner script was edited mid-run.
- **Greeter black.** `plasma-login-wallpaper` cleared its window to black.
  Delaying the window fails: the image wallpaper's `TransientImage` loads
  only once its window is exposed (3 s fallback seen).
  [The patch](patches/plasma-login-manager-6.8.3-logout-vm-wallpaper.patch)
  makes the window transparent instead, and the KWin backdrop now stays
  underneath for 3 s after a desktop window appears. Add
  `LOGOUT_VM_WALLPAPER_BIN=<binary>`.

Frames from `clear-1` and `clear-6` were checked by eye: desktop, orange,
cyan, greeter. Sign-in after the password still shows black; it is not
part of this attempt.

This changes the safety rules above: the relay switches VT and holds
master, though never while the greeter's compositor process exists. Open
before any physical trial: the same real wallpaper in all stages; a
stalled or failed greeter and relay timeout; cancelled logout; relay
death while holding; who may trigger a root relay (the `/tmp` file is a
prototype only); an event-driven way to see the greeter start instead of
1 ms polling; the backdrop's 3 s limit and direct scanout; multiple
outputs and i915.

### Switch only, no painting

2026-11-26, same conditions, batch `switch-batch.Umt8ha`. The program
switches to greeter VT 1 in graphics mode and never takes master or
paints. "Greeter changes" means the KWin backdrop and transparent
wallpaper window above.

| Card held open | Greeter changes | Black captures per run | Re-login |
| --- | --- | --- | --- |
| yes (`switch`) | yes | 0, 0, 0, 0, 0, 0 (`full-*`) | 6/6 |
| **no** (`switch-nocard`) | yes | 9, 9, 8, 8, 9, 8 (`nocard/full-*`) | 6/6 |
| yes (`switch`), alternating rerun | yes | 0, 0, 0 (`alt/switch/*`) | 3/3 |
| no (`switch-nocard`), alternating rerun | yes | 7, 8, 10 (`alt/switch-nocard/*`) | 3/3 |
| yes (`switch`) | no | 6, 6, 6 (`stock-4..6`) | 3/3 |

- With the card held open, the departed desktop's last frame, panel
  included, stayed until the greeter's first frame: 0.45-0.61 s from
  trigger to that frame. With greeter changes, the VM's cyan placeholder
  backdrop and then the greeter followed. With a stock greeter, about
  0.2-0.34 s of black followed.
- **The open file is required.** Without it the plane changed to the
  `[fbcon]` framebuffer about 0.11-0.13 s after the switch. In Linux 7.0,
  `drm_release()` calls `drm_lastclose()` when the last open file goes,
  which restores the console. That this is what happened here is inferred
  from the source and the A/B, not traced.
- So the gap stage needs no picture, buffer or DRM master: keep the card
  open (dropping master if opening granted it), switch the VT, release
  after the greeter's first frame. VT switching still needs privilege.
- `stock-1..3` failed in test setup before logout (missing unit
  directory, fixed in `monitor.py`).

**Verified (2026-11-26, second pass).** Counting near-black pixels in
every capture, not only the centre sample, found no capture over 2 %
black in any card-open run with greeter changes, nor in
`clear-batch.Y2zacD`. The earlier `vmsum.py` missed partly black
captures (one in `stock-4`); it now marks any capture over 2 % black as
partial. The `[fbcon]` framebuffer reached the plane in every card-closed
run and in no card-open run. The alternating rerun rules out run order.
Linux 7.0 source: `drm_fbdev_client_restore()` on last close does an
unforced commit, which yields to a DRM master and ignores the VT's KD
mode; the VM ran 7.3.5-cachyos.

Not tested: the logout confirmation screen's effect on the retained
frame (logout was requested over D-Bus), a missing greeter in this mode,
any physical GPU. The retained frame is readable by the next DRM master.

### First installable version (`holder/`)

2026-11-26, at the user's request to make it exist first and refine later.
[holder/README.md](holder/README.md) describes it. Trigger: Plasma's
shutdown-script hook (`/etc/xdg/plasma-workspace/shutdown/`), which
`plasma-shutdown` runs synchronously before `StopUnit
graphical-session.target`; a polkit rule allows only `start` of
`logout-holder.service`. The helper only keeps the card open and switches
VT (no master, no painting). Greeter: patched KWin with the real login
wallpaper as backdrop, and the transparent wallpaper window.

VM, `holder-batch.OEnXt1`, installed by `holder/install.sh` from a bundle
(`LOGOUT_VM_HOLDER_BUNDLE`), desktop compositor stock:

| Run | Logout black / partial | Re-login |
| --- | --- | --- |
| `h-3` (with `cap_sys_nice`) | 5 / 1 | passed |
| `h-4` … `h-9` | **0 / 0 in all six** | 6/6 |

Seen by eye (`h-4`, `h-5`, `h-9`): desktop with panel, the same wallpaper
without panel, then the login screen. The later dark stretch is sign-in
after the password, out of scope. `h-3` black: `setcap cap_sys_nice` on the
KWin copy makes the loader ignore `LD_LIBRARY_PATH`, so stock `libkwin`
(without backdrop) loaded; the installer no longer sets it. `h-1`, `h-2`
failed in setup (installer bugs: `pacman -Q` in the VM, a missing drop-in
directory). On Vandal, the patched KWin started headless (`--virtual`,
private bus) with its own `libkwin` and exited 0, same warnings as stock.

Not tested yet: shutdown and restart with it installed, a stalled or
failed login screen, cancelled logout.

### First host trial on Vandal (2026-11-26 15:51, one filmed logout)

Installed by the user from `holder-bundle-vandal` at 15:49. Acer X28 on
`HDMI-A-1` (3840x2160@60), **lid closed**, eDP-1 disabled. Video
`video_2026-11-26_15-52-47.mp4` (30 fps, not committed); journal of boot
`1e8300cb…`. Video zero mapped by the logout prompt closing (8.73 s ↔
6306.6 s monotonic, about ±0.1 s).

| Monotonic | Event | On film |
| ---: | --- | --- |
| 6306.71 | helper holds card1 from VT 3, switches to VT 1 | last desktop frame, **including a terminal window** (Alacritty had closed 50 ms before; closing animation) |
| 6308.53 | greeter session `c3` | frozen frame |
| 6311.10 | greeter KWin (patched copy) starts; 6311.21 has the card | frozen until ≈6311.8 |
| ≈6311.8–6313.3 | | **≈1.5 s pure black** (30 fps: no intermediate frame) |
| 6312.34 | greeter Connect | |
| 6313.25 | helper exits (2 s linger) | ≈6313.3 login wallpaper with clock, **no password form** |
| 6312–6335 | user presses keys | nothing changes |
| 6335.67–6341.39 | suspend and resume (trigger not logged; BT wake) | |
| 6347.50 | sign-in succeeds | |

**Dead keys, cause found (source + bug report, not re-tested):** the KWin
copy was built from upstream v6.8.3, while the distribution's
`kwin 6.8.3-3.1` carries two backports (Arch PKGBUILD 6.8.3-2/-3):
`47f03822` for [KDE 528936](https://bugs.kde.org/528936) "Booting/exiting
session with an external screen connected to a notebook with its built-in
screen closed causes the built-in screen to be treated as primary" (libinput
switch events were processed before KWin's filters existed, so the lid
state was lost), and `19404161` for KDE 528824 (crash at logout/login). With
the lid state lost, the greeter's active window, and so keyboard focus,
would go to the dark built-in screen: the external one shows only the
clock, keys go elsewhere. The three "Input method is trying to show itself
but without a context" lines at greeter start (stock: one) and recovery
after resume (lid state re-sent) fit. The greeter's `GreeterState.qml:98`
TypeError also appears with stock KWin at boot and at the 286 s logout,
where sign-in worked, so it is not the cause.

**Black ≈1.5 s, cause open.** Either the backdrop was not drawn, or the
monitor re-synchronized after a full modeset. The new KWin's backdrop is
the same image as the greeter wallpaper, so film alone cannot tell. With
the lid bug, the greeter KWin would also try to light eDP-1, which on i915
may force a full modeset on HDMI too. Desktop and greeter settings also
differ: the desktop sets `Broadcast RGB` Limited and `max bpc` 8 (read
live from the connector); a greeter without synced settings uses Automatic
and 10, which may or may not change the pipe configuration.

**Changes for the second host trial (`holder-bundle-vandal-2`):**

- KWin copy rebuilt with both backports
  (`patches/kwin-6.8.3-arch-backport-{528824,528936}.patch`) under the
  backdrop patch. The bundle records the matching package (`KWIN_PACKAGE`,
  `kwin 6.8.3-3.1`); the installer refuses any other installed KWin package.
- Backdrop logs `logout-holder backdrop: first paint` and `…: desktop window
  covers it, stopped` once each, so the next film can be split into
  "not drawn" versus "monitor re-sync". Headless smoke on Vandal with the
  4K split image: first paint logged, exit 0.
- Hook: before starting the helper it calls KWin `showDesktop(true)` on the
  session bus and waits 0.5 s, so the kept frame shows wallpaper and panel
  instead of open windows or closing animations.

VM with the Vandal login theme injected (`LOGOUT_VM_THEME`, host greeter
and wallpaper binaries, split image): v1 bundle `theme-batch.pUUOHz`
`th-1..3` and v2 bundle `v2-batch.wMJrmJ` `v2-1..3`: desktop → backdrop →
themed greeter with **no black capture at logout**, re-login 6/6, "first
paint" logged in each v2 run. vmsum's "partial" count there is the dark
left part of the split image; the black block after the greeter is
sign-in, out of scope. Theme without helper (`tc-1`, `tc-2`): 18 black
captures at logout. The VM has no lid and no open windows, so it cannot
test the backport or the show-desktop step.

### Second host trial on Vandal (2026-11-26 ≈16:20, v2 bundle)

Installed by the user (`--restore` of v1, then v2; installed hashes match
the bundle). Lid closed, `HDMI-A-1`. Journal only so far (no video found):

| Monotonic | Event |
| ---: | --- |
| 8183.41 | logout prompt closed |
| 8184.47 | Alacritty closed |
| 8185.02 | helper switched to VT 1 (≈0.55 s later: show-desktop wait) |
| 8186.88 | greeter session `c4` |
| 8187.10 / 8187.22 | greeter KWin starts / has the card |
| 8187.72 | **backdrop first paint** |
| 8187.98 | greeter Connect; one "Input method … without a context" line (as stock) |
| 8192.14 | **Login** (keys worked, ≈4.2 s after Connect) |

Sign-in worked with the lid closed, but **the user touched the mouse**,
and pointer motion over the greeter activates its window
(`Main.qml` `onPositionChanged`), so this does not yet show the backport
fixed keyboard-only input. Only one "Input method" line (trial 1: three)
is weak support. Frozen frame to backdrop: ≈2.7 s.

### Third host trial (2026-11-26 16:25, v2, keyboard only, filmed)

`video_2026-11-26_16-25-09.mp4`; anchor: logout prompt gone 7.7 s ↔
8298.38. Helper switched 8298.97; greeter KWin has card 8303.37,
**backdrop first paint 8303.86**, Connect 8304.13, helper exit 8305.40,
Login 8311.99.

- Kept frame: wallpaper and panel only, **no terminal** (show-desktop works).
- **Keyboard-only sign-in worked** with the lid closed: form visible, password
  typed without touching the mouse. Backport fix confirmed in use.
- **≈2.5 s black** (13.3–15.8 s ↔ ≈8304.0–8306.5) starting with the greeter
  KWin's first frame, although that frame already had the backdrop. Read as
  a **full modeset and monitor re-sync** on `HDMI-A-1`, not missing content.
  The desktop and greeter output settings differ (desktop: `Broadcast RGB`
  Limited, `max bpc` 8). Next: `holder/sync-greeter-outputs.sh` copies the
  desktop's `kwinoutputconfig.json` to the greeter (backup, `--restore`).

### Fourth host trial (2026-11-26 16:31, v2 + synced greeter outputs)

Before the trial the user ran `holder/sync-greeter-outputs.sh`. The greeter
had `HDMI-A-1` at rgbRange Automatic, maxBitsPerColor 0 (KWin then asks 10)
and colour profile sRGB; the desktop has Limited, 8 and EDID. Now the
greeter has the desktop's file (backup `….before-logout-holder`).

`video_2026-11-26_16-32-09.mp4`: desktop wallpaper (shown-desktop frame)
→ themed greeter at 10.7 s in one step, **no dark frame**; the drop in
mean brightness is the darker split image, and the camera then adjusts
(the user's reading too). Journal: switch 8671.04, greeter KWin has card
8675.63, backdrop first paint 8676.12, Connect 8676.46, Login 8681.46
(keyboard). Sign-in afterwards showed only ≈2 dark frames (≈0.07 s).

**Goal met on Vandal for this configuration:** logout from desktop to
login screen without black, wallpaper visible throughout, keyboard sign-in
works with the lid closed. One run; repeatability, shutdown/restart and
package updates still to cover.

### Package updates must not break the login screen

The KWin and wallpaper copies use private Qt/KWin interfaces and must
carry the distribution's backports. v3 (`holder-bundle-vandal-3`): both
greeter units start `greeter-start`, which runs the copies only while
every package in `PACKAGES` (kwin, qt6-base, qt6-declarative, qt6-wayland,
plasma-login-manager; pacman database names) is installed at the same
version, otherwise `/usr/bin/kwin_wayland` and the wallpaper command that
was active before install (the theme's, on Vandal). The fallback only loses
the backdrop, never sign-in. `LD_LIBRARY_PATH` moved from the drop-in into
the launcher, so the stock binary never sees it. Logic tested on Vandal with
a copy that prints instead of exec (current, stale, empty list).

VM, v3 bundles: theme (`v3-batch.HUQcYT` `t-1`, `t-2`) and stock
(`v3b-batch.uBqClB` `s-1`, `s-2`): no black at logout, re-login 4/4 (the
black block vmsum counts in `s-*` is sign-in after the password).
Stale package simulated (`LOGOUT_VM_HOLDER_STALE=1`, `st-1`): no backdrop
"first paint" (stock KWin ran), ≈5 black captures at logout as without the
greeter changes, sign-in passed. The first `s-*` attempt failed in setup:
with no theme drop-in, an unmatched glob under `set -o pipefail` aborted the
installer; fixed with `nullglob`.

### Shutdown and reboot must not start the holder

Not tested; from source. The prototype trigger fires whenever
`plasma-plasmashell.service` stops, so it would also fire on shutdown and
reboot. In plasma-workspace 6.8.3,
`startkde/plasma-shutdown/shutdown.cpp`, `logoutComplete()` queues
`StopUnit graphical-session.target` and only then asks logind to power off
or reboot, so logind's shutting-down state may not be set yet when the
trigger runs. Proposed: `plasma-shutdown` starts the holder itself, before
`StopUnit`, only for `ShutdownTypeLogout`; cancelled logouts never reach
that point. Not implemented.

## Candidate: keep the scanout owner, switch its producer

Use a single compositor/KMS owner as a VM research prototype. While
the desktop is active the holder sleeps. On logout, the owner presents
a trusted static wallpaper (not a screenshot of private windows) and
acknowledges presentation. Then the normal session teardown proceeds.
The greeter produces its first frame without independently acquiring
that output; the owner switches to it on a frame boundary. The holder
can exit once the new frame is presented. Initially test the frame
switch with synthetic clients; that does not validate SDDM integration.

The open integration question is whether the compositor can remain
seat owner while hosting isolated desktop and greeter producers without
changing authentication, exposing greeter input to the old session,
or violating normal logind activation. Never give the desktop the
greeter's input or credentials. Start a bounded deadline at handoff;
on failure discard the handoff and return to the stock display-manager
path. A visible blink on fallback is preferable to an unusable seat.

### Can the holder stay on a separate VT?

Guest run `vt-owner-1795642476` switched from the Plasma VT to an
unused text VT and back, without logging out. DRM debugfs reported
the master client under systemd-logind on VT 1, no master client on
VT 9, then the original logind client again on VT 1. KWin returned
with the same PID but new DRM clients. Subsequent logout/re-login
passed. Keeping KWin alive on its own inactive VT therefore does not
keep the seat's master active in this VM. This test does not measure
retained scanout pixels or NVIDIA behavior.

## Backend comparison is not a holder trial

A stock Wayland greeter is a separate diagnostic. SDDM 0.21.0
[`HelperStartWayland.cpp`](https://github.com/sddm/sddm/blob/v0.21.0/src/helper/HelperStartWayland.cpp)
starts the configured compositor before the greeter and stops it when
the helper exits. Stock configuration does not attach the greeter to
an independent resident compositor. The single-owner design would
need an integration change, not just a backend switch.

SDDM 0.21.0
`Seat::displayStopped()` evaluates `defaultDisplayServerType()` before
`createDisplay()` reloads the config. Do not assume a staged drop-in
will take effect on the very next logout. Also, deleting a drop-in
does not replace an already-running greeter. The original trial script wrote the config
before arming rollback and was replaced before the physical test.

The guest recovery run `wayland-recovery-1795640971` used
`SDDM_VM_WAYLAND=1 SDDM_VM_GREETER_FAIL=1`. Removing the drop-in
and explicitly restarting SDDM restored Xorg; the normal VM login,
logout and re-login checks then passed. This verifies the recovery
procedure, not SDDM's automatic fallback. In a subsequent guest run
(`wayland-timer-1795641108`), the pre-armed timer removed the config;
a separate explicit restart restored X11. The timer does not restart
SDDM underneath an active desktop.

Validate backend selection and recovery in a disposable VM first,
including a greeter that starts but never produces a frame. For the
holder prototype, compare continuous visible frames against stock,
then verify timeout recovery, immediate re-login and lock/unlock.
Do not infer NVIDIA scanout continuity from the VM.

## Baseline and first prototype boundary

The fresh stock SDDM VM run `holder-stock-1795640054` captured
175 frames. Its serial log confirms password authentication and a
new Plasma Wayland session after logout. Keep those frames as the
stock reference; the run did not exercise holder recovery.

For the first prototype, keep the outer compositor alive and use
two synthetic producers with unmistakable colors. Shut down the
first producer only after the wallpaper is presented; delay the
second producer and then allow its first frame. Sample the outer
output throughout. Repeat without the holder, and with the second
producer stalled past the timeout. A successful synthetic run is
only a frame-switch test: it cannot satisfy the SDDM authentication
or seat-isolation checks.

The initial guest run missed the probe because sampling started
before its first frame. After synchronizing on that frame, QEMU
screenshots passed all three synthetic scenarios:

| VM artifact | Center-pixel sequence |
| --- | --- |
| `holder-probe-stock-1795640613` | Black → fake greeter |
| `holder-probe-1795640578` | Holder → fake greeter, no sampled black |
| `holder-probe-stall-1795640638` | Holder → timeout marker, no sampled black |

These are full-screen colors in one Qt window on a running
compositor. The timeout marker does not restart SDDM; no desktop
session was stopped during the probe. Actual holder recovery and
seat integration remain untested.

## Guest trace: who clears the controller mode?

Run `kms-1795643272` (`SDDM_VM_WAYLAND=1 LOGOUT_VM_KMS_TRACE=1`):
before logout KWin PID 547 had a desktop on active CRTC 38 with FB 43.
The logout request at guest monotonic 19.651031 preceded a greeter
connection at 20.192441; re-login passed. A kprobe on
`drm_atomic_set_mode_for_crtc` saw only non-null mode arguments,
first from (sd-close) at 19.853173 and then systemd-logind. These
are helper calls, not proof of committed changes. No first disable
can be attributed from this trace. Next, instrument the **committed**
old/new CRTC active and primary-plane FB state (including atomic
property-blob paths), and distinguish test-only from real commits.
Do not infer NVIDIA behavior or visual black from this guest trace.

## Guest trace: committed state samples

`state-1795643557` (`LOGOUT_VM_KMS_STATE=1 SDDM_VM_WAYLAND=1`)
sampled DRM debugfs with 5 ms sleeps and monotonic read boundaries.
Plane 36 was attached to CRTC 38 with FB 46 before the logout request
at 19.709867 s. The first changed sample showed FB 44 at 19.896950,
then FB 42 by 19.931876 and FB 47 by 20.283064. The greeter connected
at 20.301475 and re-login passed. No sample during this handoff showed
the controller disabled or the plane detached. Sampling can miss short
transitions; FB IDs don't identify content or the committing process.
In this VM, compare the captured pixels against those transitions
before chasing a controller disable. This is not an NVIDIA DP trace.

### Pixels from that same run (offline)

In `state-1795643557`, inspect whole images, not just a center pixel:

```sh
for f in frame-*.png; do
    magick "$f" -colorspace sRGB -format '%f %[fx:mean] %[fx:maxima]\n' info:
done
```

Match filenames to host-relative screendump start/end in `frames.tsv`.
Frames 006–018 (13 samples; capture starts 0.241–0.723 s) have mean
RGB ≤0.000011 on a 0–1 scale. Ten are entirely black (007 and 010–018);
the other three have a few nonblack pixels. Frame 005 has mean 0.285
and frame 019 has mean 0.278. Thus near-black samples span about
0.48 s; this is not a measurement of uninterrupted darkness between
samples.

The 175-frame capture also includes immediate re-login. Later, frames
048–058 (starts 1.931–2.333 s) and 060–066 (2.414–2.655 s) were
entirely black, separated by nonblack frame 059 (mean 0.275291).
Count these separately, not as part of the initial logout interval.
Across all 175 images, 31 met the near-black threshold and 28 were
entirely black.

In the same logout, guest DRM samples showed changing FBs
without observed controller disable. The host and guest clocks were
not synchronized: no single FB ID, commit or process can be assigned
to a black screenshot from these data. QEMU cannot measure DP signal.

Synchronized repeat `sync-1795644064`: serial round trips bracketed
guest uptime 19.74 s at host-relative 0.000–0.002 s and 26.77 s at
7.031–7.033 s (uptime resolution 10 ms, guest not suspended).
Frames 010–013 were entirely black inside the sampled FB 42 interval;
frames 016–017 were also black after the transition to FB 43. Frame
014 straddles the change to FB 47 and cannot be assigned uniquely.
Greeter Connect was at guest 20.327 s; frame 018 was nonblack.
Re-login passed. These are time correlations with sampled state, not
proof of framebuffer authorship, exact scanout, or physical link state.

Framebuffer allocator repeat `owner-1795644184`: when plane 36
changed FB, the guest sampler also read the DRM framebuffer listing.
After desktop KWin FB 44, the plane used FB 42 (allocated by
`[fbcon]`) for about 0.34 s, then switched to KWin-allocated FB 47
and 41. With the synchronized screenshot clock, near-black/black
frames 006–012 fall inside the fbcon interval; frames 015–016 were
still entirely black in the subsequent KWin interval. Frame 017 was
nonblack and re-login passed. Allocator is not a record of who
submitted a commit. This favors testing a trusted image across both
the console fallback and first compositor frames rather than just
preserving the outgoing KWin framebuffer. No physical attribution.

### Incoming compositor background A/B

Both runs used the same KWin marker build via
`SDDM_VM_WAYLAND=1 LOGOUT_VM_KMS_STATE=1 LOGOUT_VM_GREETER_MARKER=<build>`;
only `LOGOUT_VM_GREETER_COLOR` changed. Real logout and immediate
re-login passed in both runs.

| Guest run | Near-black before first nonblack capture | Following captures |
| --- | --- | --- |
| `sddm-early-0.f9yDCE/run` (black) | 006–018, starts 0.244–0.727 s | Greeter from 019 |
| `sddm-early-1.47enSy/run` (magenta) | 007–017, starts 0.284–0.685 s | Magenta 018–021, greeter from 022 |

In the magenta run the controller remained active in sampled states.
It showed the fbcon framebuffer earlier, and the first magenta
capture coincided with the switch back to a KWin-allocated FB,
within the clock bracket and polling uncertainty. Changing the
incoming compositor background can color its early frames but does
not bridge the preceding console interval. Single runs are not
evidence of a speedup; there was no physical DP measurement.

## Physical stock Wayland diagnostic

On Nov 25, logind recorded Wayland SDDM greeter sessions and the
helper started KWin; a greeter connected at 22:26:11. The user supplied
`video_2026-11-25_22-28-48.mp4` for the trial. At 4 samples/s it shows
roughly 1.5 s of apparent black, then a dim lit frame before Breath
appears near 10 s. The clip clock was not aligned to the journal, so
the precise session and display-state transitions cannot be inferred
from it. The evidence does not support recommending stock Wayland as
a blackout fix. The journal shows Xorg returning after the 22:26:31
restart, and the trial drop-in was absent when checked.
