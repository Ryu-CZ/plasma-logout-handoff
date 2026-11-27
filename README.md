# Plasma logout handoff

Remove the black interval when Plasma Wayland signs out to Plasma Login
Manager on CachyOS (Plasma 6.8.3); the wallpaper should stay visible. This
is separate from the [login](../plasma-login-handoff) and
[lock](../plasma-lock-handoff) handoffs. See [the long-term plan](PLAN.md).

## Status (2026-11-27)

**Goal met on Vandal.** The logout holder ([holder/](holder/README.md),
v5) was installed and verified; v6 (adds recovery after a failed sign-in)
and then v7 (no login screen scale-in, package guard) replaced it on
2026-11-27; the logout with v7 was smooth. At logout,
the desktop's wallpaper and panel stay on screen until the themed login screen appears over its own wallpaper, with
no black in between. Keyboard sign-in works with the lid closed. Restart
from the Plasma menu works. Shutdown from the Plasma menu works
(Vandal, 2026-11-26 22:56). How it works, how to install, upgrade and undo it, and its
limits: [holder/README.md](holder/README.md). Trials and evidence:
[HOLDER-DESIGN.md](HOLDER-DESIGN.md).

The causes of the black, in the order they were removed:

1. **The console returned to text mode** when the desktop compositor
   exited, before the login screen's compositor started. The helper keeps
   the cards open and switches consoles in graphics mode, so the last
   frame stays on screen.
2. **The login screen's first frames were black** until its wallpaper
   loaded. Patched copies of KWin and `plasma-login-wallpaper` draw the
   wallpaper from the first frame.
3. **The monitor re-synced** (about 2.5 s of black) because the login
   screen's display settings (RGB range, bits per colour) differed from the
   desktop's. The helper now copies the desktop's settings at every exit
   from Plasma.

Two regressions were found and fixed on the way:

- The first KWin copy lacked Arch's backports, so keys did nothing with
  the lid closed.
- v3 switched consoles too early, so Restart from the Plasma menu was
  refused. The VM now tests restart and shutdown (`LOGOUT_VM_SHUTDOWN`).

The sections below are the investigation log, oldest first. They describe
the state at the time; some refer to the earlier DisplayPort setup.

## Baseline

Three observed sign-outs in the system journal show the same ordering:
PLM starts a new greeter after the desktop session exits, then waits for the
greeter account's systemd user manager. User manager startup took 2.42–2.45 s
on those returns, compared with about 0.10 s at initial boot.

On the latest sampled return, measured from the desktop KWin service exit:

| Event | Offset |
| --- | ---: |
| Desktop KWin exited | 0.00 s |
| PLM began starting the greeter | 0.02 s |
| Greeter user manager began starting | 0.04 s |
| Helper logged switching to VT 1 | 2.47 s |
| Greeter KWin reported ready to systemd | 2.91 s |
| Greeter UI connected to PLM | 3.36 s |

These are journal events, not scanout measurements. Much of the return
elapsed before the greeter compositor even started, so a wallpaper behind
the greeter's first frame cannot on its own cover that interval. A mode
change or link retrain may still account for a separate blink. The desktop
uses DP-1 at 4K/100 Hz; the live greeter mode has not yet been measured.

## Physical phone recording

The clip shows the logout confirmation UI first (about 6.5 s), then a
return to desktop content. Near the end it shows two separate dark
intervals. At 0.25 s sampling, the progression is:

| Clip time | Visible |
| --- | --- |
| 13.75 s | Sharp desktop wallpaper |
| 14.00–15.50 s | Very dark, with faint shapes |
| 15.75–17.25 s | Brighter blue/blurred-looking image without controls |
| 17.50–19.25 s | Very dark again, with faint shapes |
| 19.50 s onward | Vandal login greeter |

No obvious input or “No signal” banner was visible in these samples.
The user identifies the dim blue interval as looking like an active
backlight and the darker intervals as looking like the backlight went
off. This makes a display blank worth testing, but the clip doesn't
establish backlight state or distinguish a signal loss from a monitor's
response to black content. The journal for this logout shows 3.25 s from Plasma
starting its shutdown service to desktop KWin exit, another 2.45 s to
the VT switch, and 0.88 s more to the greeter connecting. The recording
has no precise journal clock alignment, so these events don't identify
the cause of either individual dark interval. The video is not committed.

## Open items

- **Re-login can fail after logout (2026-11-26 21:01, Vandal).** The
  password was accepted, then the screen stayed black; reboot needed. Cause
  traced in the journal and the VM; user drop-in installed and passed one
  logout. See
  [the log entry](#vandal-failed-re-login-after-logout-2026-11-26-2101).
- Bundle v6 (a failed sign-in returns to the login screen instead of staying
  black) installed on Vandal 2026-11-27 12:35. The greeter runs through the
  wrapper after logout; no failed sign-in has happened there since, so the
  recovery itself is not seen in use
  ([install record](#vandal-v6-installed-2026-11-27)).
- Bundle v7 (no-animation setting in the bundle, new package guard) installed
  on Vandal 2026-11-27 16:56; first logout and sign-in at 17:01–17:02 worked
  ([record](#vandal-v7-installed-2026-11-27)). Restart and Shutdown have not
  been tried on Vandal with v7 (both passed in the VM).
- After an update of a package in the bundle's `PACKAGES` (Qt, KWin, the
  login manager, `kdecoration`, `kwindowsystem`), or one that leaves a copy
  unable to load, rebuild and reinstall the bundle to get the backdrop back.
  Sign-in keeps working meanwhile, on the stock programs. `kwindowsystem`
  changes with every KDE Frameworks release (v7 and later).
- Optional: replace the frozen frame with a reversed boot animation. This
  is a wish, not required.

## Reproduce in the disposable VM

With the login project checked out next to this one and its verified VM
cache available, run both conditions from this directory:

```bash
base=~/.cache/plasma-handoff-6.8.3/vm
out=~/.cache/plasma-logout-handoff
mkdir -p "$out"
for mode in cold warm; do
    bash run-vm.sh "$base" "$out/$mode-$(date +%s)" "$mode"
done
```

Both conditions use stock KWin and a genuine password-based PLM Wayland
login. The driver waits for the original greeter user manager to stop,
then starts only that manager in the warm condition. It calls Plasma's
normal logout service, samples the emulated screen about every 40 ms,
and records journal landmarks. Guest disk and service changes are discarded
at power-off. The two clocks are not aligned; measure intervals within
the journal or within the frame timestamps, not across them.

### Cold vs. warm result

Both runs (`cold-1795616876`, `warm-1795616876`) returned to the actual
PLM greeter. Timing starts at desktop KWin exit:

| Journal event | Cold | Warm |
| --- | ---: | ---: |
| Switch to greeter VT requested | 135 ms | 70 ms |
| Greeter KWin ready to systemd | 340 ms | 250 ms |
| Greeter UI connected to PLM | 413 ms | 321 ms |

The cold user manager took 56 ms in the VM, versus about 2.45 s on the
physical PC. Pre-starting it avoided the cold start and advanced the
journal milestones, but **both runs still sampled 13 fully black images
out of 175**. These are sampled pixels, not counts of physical frames,
and the experiment does not reproduce the PC's DP flicker. This is a
candidate for a shorter physical return, not a fix for all black frames.

### Physical warm test: failed re-login

On the physical one-off warm test, desktop KWin exited at monotonic
7455.137 s, and the greeter session started at 7455.197 s (60 ms later,
versus about 2.51 s on the filmed cold run). This verifies a shorter
startup interval, not a visual improvement. The user could not sign back
in and had to reboot.

The journal shows authentication succeeded. The desktop user manager
then rejected the new `plasma-workspace-wayland.target` start because
`graphical-session.target` still had a stop job queued. The greeter's
subsequent restart was also rejected because its KWin still had a stop
job queued. These are startup/shutdown races, not an authentication
failure. This test does not establish whether prewarming was necessary
to trigger the race. The VM experiment above ended after the greeter
returned and did not test rapid re-login.

After reboot, normal sign-in succeeded, the greeter user manager was
inactive in the desktop session, and the existing patched desktop KWin
was still selected. No persistent configuration or lingering was added.

### VM re-login coverage

The runner now signs back in after the second greeter connects, allowing
800 ms for its password field to appear before sending keys. This is test
driver pacing, not a delay added to Plasma. The `cold-roundtrip-1795617733`
and `warm-roundtrip-1795617733` runs each logged two successful PLM
authentications and reached a new active desktop session with plasmashell
running. Neither logged a conflicting start/stop transaction. This is one
pass per condition; the physical failure is not reproduced by the
unmodified guest.

With `LOGOUT_VM_DELAY_STOP=1`, the runner adds a transient guest-only
service ordered after and stopped with `graphical-session.target`.
Its stop command takes six seconds without keeping KWin running.
`warm-delay-1795618054` reproduced **both** physical errors: the password
was accepted, but desktop startup collided with the queued
`graphical-session.target` stop; then greeter restart collided with its
own KWin stop. The runner correctly failed because no new desktop
appeared. This establishes that overlapping shutdown can cause the
observed failure, not that the physical PC had the same slow service.

### VM ordering experiment

Desktop logout queues `StopUnit(graphical-session.target, fail)`.
The desktop starter exits when KWinWrapper and Shutdown release their
bus names, which can precede completion of that stop transaction.
The greeter starter likewise queues `StopUnit` calls without waiting
for completion, including the KWin stop. Both incoming starters use
`StartUnit(..., fail)`, correctly refusing to cancel previous stops.

In the snapshot VM, combine `LOGOUT_VM_DELAY_STOP=1` with
`LOGOUT_VM_START_BARRIER=both` (or `greeter` for the recovery control).
The shell prototype waits only when relevant stop jobs are present
and then execs the original starter:

- Both barriers: `warm-barrier-1795618225` waited 4.18 s for desktop
  teardown and reached a new desktop without a transaction conflict.
- Greeter only: `warm-greeter-barrier-1795618242` still hit the desktop
  race and could not reach a new desktop. The greeter waited 58 ms for
  its own stop jobs and then connected a third time, restoring the
  chance to retry rather than leaving a black screen.

This is an isolation probe, not an installable fix. The job-list check
and start are separate operations, and the test timeout does not define
production recovery. A source fix should bind a wait to the original
stop transaction and preserve normal failure handling.

### Source-level teardown prototype

The two 6.8.3 patches under `patches/` wait for blocking
`systemctl --user --job-mode=fail stop` calls in the outgoing starters.
This joins a pending stop rather than replacing it. Desktop teardown
waits for `graphical-session.target`; greeter teardown waits for both
its target and KWin, within the helper's existing five-second timeout.
A timeout is logged; the prototype does not guarantee recovery if a
stop hangs. No live binaries were replaced.

Build with `bash build-stop-fix.sh DESKTOP_BUILD GREETER_BUILD NEW_OUTPUT_DIR`
against current, configured 6.8.3 build trees. Pass the output directory
as `LOGOUT_VM_STOP_FIX` to the VM runner. Use `LOGOUT_VM_DELAY_STOP=1`
for the injected six-second stop; leave it unset for controls.

The patched warm run with the delay (`warm-source-1795618465`) returned
to the greeter and signed back into a fresh desktop. It queued no
conflicting starts; greeter launch occurred 5.895 s after desktop KWin
stopped, rather than racing the old session. This fixes the observed
failure in this test but exposes the tradeoff: waiting after KWin exits
can extend the period with no desktop compositor. The patched cold and
warm controls (`*-source-control-1795618518`) also both passed, with
greeter launch 58 ms and 42 ms after KWin stopped respectively. These
are journal landmarks, not physical scanout measurements.

### Greeter first-frame probe

Set `LOGOUT_VM_GREETER_MARKER` to the login project's marker build
directory (with `bin/`), and `LOGOUT_VM_GREETER_COLOR=0` or `1`. The
greeter alone gets instrumented KWin; the desktop uses stock KWin.
Both warm runs with the teardown prototype (`greeter-marker-{0,1}-1795618717`)
passed re-login. The greeter requested VT 1 roughly 74 ms after desktop
KWin stopped. The first successful non-test atomic ioctl followed the
VT request by 248 ms (black background) and 234 ms (magenta).

The black control sampled fully black images at indices 007–015.
The magenta run still sampled black at 006 and 008–013; magenta
appeared before the wallpaper at 015. So replacing the incoming KWin
background can cover some rendered black, but it did not cover the
earlier interval. QMP sees emulated pixels, and an ioctl return does not
establish scanout or say anything about the physical DisplayPort link.
The physical desktop is 3840×2160 at 100 Hz; its output advertises 60 Hz
as preferred. A subsequent read-only physical capture measured the actual modes below.

### Physical display mode during normal logout

The sampler (`sample-dp.sh`) recorded changes in Intel DRM atomic
state and the active VT, roughly every 50 ms. Nothing was installed or
changed, and no screen contents were captured. In boot-relative time:

| Time (s) | Observed state |
| --- | --- |
| 173.544 | Desktop KWin service began stopping |
| 173.570 | DP-1 switched from 3840×2160 at 100 Hz (1188 MHz pixel clock) to 60 Hz (533.25 MHz), still on the desktop VT |
| 173.895 | Desktop KWin service finished stopping |
| 176.370 | Greeter VT became active; DP-1 still at 60 Hz |
| 176.890 | Greeter switched DP-1 back to 100 Hz, same pixel clock as desktop |
| 177.268 | Greeter UI connected |
| 183.850 | New desktop VT active, still at 100 Hz |

The user saw pitch black → dark gray (backlight visibly on) → pitch
black. The two mode changes are consistent with the two dark intervals
around a roughly 3.3 s stretch at 60 Hz. The observation has no
frame-level timestamps. Sampled connector/CRTC state stayed enabled
and active; that does **not** prove the link stayed trained through
each mode change, and no link-loss event was confirmed.

The greeter and desktop already agree at 100 Hz, so syncing their
output settings would not address the intermediate 60 Hz mode. The
next useful A/B is to align both endpoints temporarily with the
intermediate timing (match the pixel clock, not just the refresh
label), then restore 100 Hz. That would test how much flicker the mode
changes explain; it would not change the cold greeter startup delay.

The 60 Hz comparison sampled the same 533.25 MHz timing on the old
desktop VT, greeter VT, and new desktop VT. Greeter connection was
3.237 s after desktop KWin stopped, versus 3.372 s at 100 Hz. Re-login
succeeded. The desktop returned to 100 Hz (1188 MHz verified in DRM
state) and the greeter configuration was restored byte-for-byte.
The user saw what looked like **one kind of black** at constant timing,
rather than the distinct pitch-black and backlit dark-gray phases from
the 100 Hz run. That supports the intermediate mode change contributing
to the visible flicker, but one comparison cannot establish whether the
DP link retrained or whether the remaining black was rendered content.
For now, keep 100 Hz; holding 60 Hz was diagnostic, not a proposed fix.

### Cold user-manager delay: CachyOS NVIDIA generator

The journal places about 2.35 s between the greeter manager's PAM
session opening and systemd queuing the default target. The target
then completes in about 12 ms. The same early gap occurred starting
the desktop user manager after boot, so it is not greeter rendering.

`bash probe-generator.sh` compares the installed
`20-nvidia-rtd3-workaround` generator with a read-only sysfs lookup.
The installed generator comes from [chwd PR #149](https://github.com/CachyOS/chwd/pull/149)
and runs `lspci -d '10de:*:0302'` to select Mesa EGL on hybrid systems.
Three cold standalone runs took 2.28–2.32 s and changed NVIDIA runtime
status from suspended to active where checked. Warm runs took 8 ms.
The sysfs vendor/class check emitted the identical EGL setting in
under 1 ms. This matches the missing time closely, but a controlled
manager-start A/B is needed before assigning the entire delay to it.

An administrator override of the same basename can preserve the EGL
workaround rather than disabling it. Systemd runs these generators for
all user managers, so even a temporary override has that scope unless
it checks the UID. No override, runtime-PM setting change, or
prestarted manager was applied during this probe.

The standalone candidate is `20-nvidia-rtd3-workaround`. In a follow-up
test it emitted the same assignment in 2 ms with the NVIDIA device
suspended both before and after. The [systemd environment generator
manual](https://www.freedesktop.org/software/systemd/man/latest/systemd.environment-generator.html)
confirms that a same-named file in `/run/systemd/user-environment-generators/`
takes precedence over the generated vendor file. For a physical trial,
scope the override to the greeter UID, delegate all other UIDs to
the original, and remove the override after one logout. Leave the
desktop and greeter at 100 Hz and do not pre-start the manager. Measure
the original journal landmarks and allow teardown to finish before
signing back in, since the live starters do not have the VM fixes.

### Vandal: greeter-only generator A/B

The installed probe still took 2.286 s in a standalone run; the
sysfs probe took 2 ms and emitted the identical Mesa EGL assignment.
The [one-logout trial](vandal-greeter-generator-trial.sh) used a
greeter-only runtime override; it delegated other UIDs to the
installed probe. No display setting was changed.

| Journal interval | Recent stock logout | Override logout |
| --- | ---: | ---: |
| Greeter user-manager PAM opened → first target queued | 2.348 s | 0.058 s |
| Desktop KWin ended → PLM greeter Connect | 3.237 s | 0.987 s |

The greeter returned and a new Plasma Wayland session started on
re-login. The armed timer removed the override and staging file
without restarting PLM; both paths were verified absent. Local
artifacts are under `~/.cache/plasma-logout-handoff/vandal-generator.XyZwIj/`.

This one comparison supports the cold PCI probe as a main contributor
to greeter startup delay. GPU runtime state was not captured
immediately before both logouts, so it is not a controlled cold-state
repeat. Connect does not measure display presentation; this run was
not filmed and did not test immediate re-login or lock/unlock.
CachyOS already [replaced the PCI probe](https://github.com/CachyOS/chwd/pull/282)
and then [removed the workaround](https://github.com/CachyOS/chwd/pull/283).
Vandal's installed `chwd 1.25.0-1` graphics profile no longer references
it, but the generated files at
`/usr/lib/systemd/user-environment-generators/20-nvidia-rtd3-workaround`
and `/etc/profile.d/nvidia-rtd3-workaround.sh` are still present and not
owned by a package. Treat them as leftovers on this machine, not a
reason to submit a duplicate fast-probe patch. The trial preserved the
Mesa EGL selection; the removal trial below tested a different change.

### Vandal: temporarily disabling both retired files

The [cleanup trial](vandal-rtd3-cleanup-trial.sh) moved both generated
files aside before logout. No display settings changed.

| Journal interval | Stock | Fast probe, Mesa EGL kept | Both files disabled |
| --- | ---: | ---: | ---: |
| Greeter user-manager PAM opened → first target queued | 2.348 s | 0.058 s | 0.061 s |
| PLM greeter session started → greeter Connect | 0.810 s | 0.840 s | 3.458 s |
| Desktop KWin ended → greeter Connect | 3.237 s | 0.987 s | 3.588 s |

Full removal avoided the slow probe but was not faster overall in
this run: the greeter's KWin service took 2.94 s from Starting to
Started. The logs do not establish why it took longer. A new Wayland
desktop session started, the locker ran and the session returned to
unlocked, and the NVIDIA GPU reported `suspended` / `D3cold`.
The desktop reused its existing user manager, which still had the
Mesa EGL assignment. Thus this did not validate idle GPU behavior
or login from a fresh desktop manager without the workaround.
No video measured presentation. Local artifacts:
`~/.cache/plasma-logout-handoff/vandal-rtd3-cleanup.w4pqL3/`.

The original rollback timer fired but did not restore the files:
systemd expanded the inline shell's parameter expressions before
passing them to Bash. Both backups survived. Manual `--restore` in
a local terminal restored both original files with their expected
ownership and modes; both backup directories were verified absent.
The script now passes
`--expand-environment=no`; a transient timer test against temporary
files verified the correction. Keep the originals for now; only the
fast probe with Mesa EGL preserved showed a shorter connection time.

### Vandal: console mode matching, filmed logout

One boot with `video=DP-1:3840x2160@100`, lid closed, 2026-11-26. The
greeter generator override was not part of this run.
`video_2026-11-26_11-57-30.mp4` shows live `/proc/uptime`; video zero is
near boot time 1216.45 s (about 0.2 s uncertainty). The video is not
committed. Local artifacts: `~/.cache/plasma-logout-handoff/vandal-modematch.y2QmY5/`.

The sampler logged DP-1 enabled and pipe B active at 100 Hz (1188000)
for the desktop VT, greeter VT (1228.62) and new session VT (1236.59).
It recorded no other mode or connector state.

| Clip time | Boot time (approx.) | Observation |
| ---: | ---: | --- |
| 9.19 s | 1225.64 | Wallpaper goes black as the Plasma shell stops; cursor still visible |
| | 1225.99 | Desktop KWin service stopped |
| 9.3–9.5 s | 1225.8–1225.9 | Image brightens to a blurred pattern, which then holds |
| | 1228.53 | Greeter user manager started (2.44 s startup); jump to VT 1 |
| 13.0 s | 1229.45 | Cursor visible on black; greeter Connect at 1229.46 |
| 13.2 s | 1229.65 | Greeter wallpaper visible |

About **4 s of black remains** (desktop KWin end → Connect: 3.48 s). The
blurred pattern is also present when the earliest black frame is
brightened, so it is read as the camera's exposure rising on a black
screen (likely reflections), not as displayed content. The user then
reported that it was pure dark, agreeing with this reading.

Brightness compared with the stock clip of 2026-11-25
(`video_2026-11-25_15-20-25.mp4`, mean frame luma):

- Stock: about 32 (13.9–15.8 s) → 63 (15.8–17.5 s) → 30 (17.5–19.4 s),
  with sharp steps, matching the two kinds of black seen then.
- Matched: 26 for about 0.15 s, a rise over about 0.2 s, then a steady
  66–67 until the greeter, apart from one gradual dip to about 59.

No backlight-off phase is apparent in the matched run. Framing and
exposure differ between the clips and each condition has one run, so this
does not measure backlight state or link training. The new desktop session
started on tty7; gettys held tty2–6. Beeper dumped core during logout,
before the black began.

### Vandal: mode matching plus greeter generator override, filmed

Same boot, 2026-11-26, with the one-logout greeter-only generator
override added. `video_2026-11-26_12-07-08.mp4` (not committed); no
sampler or on-screen clock. Video zero is placed near boot time 1782.9 s
by matching dismissal of the logout prompt to its journal exit, so boot
times are approximate. Local artifacts: `~/.cache/plasma-logout-handoff/vandal-combined.6ad2c2rf/`.

| Clip time | Event |
| ---: | --- |
| 18.70 s | Wallpaper goes black (Plasma shell stopped 1801.61) |
| | Desktop KWin ended 1801.92; greeter user manager started in 65 ms |
| | Greeter Connect 1802.97 |
| 20.30 s | Greeter wallpaper visible |
| ~31 s | Desktop wallpaper after sign-in |

| Measure, one run each | Stock film (11-25) | Mode matched | Both changes |
| --- | ---: | ---: | ---: |
| Black on film | about 5.5 s | about 4.0 s | **about 1.6 s** |
| Desktop KWin end → greeter Connect | not compared | 3.48 s | 1.05 s |

The dark interval holds one level after the camera settles, with no
apparent backlight-off phase; reflections of the room are visible in it.
The mode was not sampled in this run. The override and staging file were
verified absent afterwards. Sign-in at 1810.63 (about 8.7 s after desktop
KWin ended) reused the desktop user manager; KWin, the Plasma shell and
ksmserver were active and no user units were failed. This is one successful
quick re-login, not coverage of the earlier re-login race. Lock/unlock was
not tested. Beeper again dumped core just before the black began.

### Vandal: kept changes, home monitor, second GPU lookup found

2026-11-26, after `vandal-keep-handoff.sh` ran (14:05) and a reboot.
Acer X28 on `HDMI-A-1`, 3840x2160 at 60 Hz, internal panel disabled, so
`video=DP-1:...` did not apply. One logout, journal only, not filmed;
not comparable one-to-one with the `DP-1` runs.

| Journal interval | This logout |
| --- | ---: |
| Greeter user-manager PAM opened -> first target queued | 0.078 s |
| PLM greeter session started -> greeter Connect | 3.49 s |
| Desktop KWin ended -> greeter Connect | 3.62 s |

The generator override worked, but 2.4 s passed between the greeter
session start and its first user unit. The greeter's shell is `nologin`,
so `wayland-session` sources `/etc/profile`, and the leftover
`/etc/profile.d/nvidia-rtd3-workaround.sh` runs the same `lspci` probe.
Afterwards, with the GPU `suspended`, that script took 2.322 s (0.008 s
once awake). The user then reported that lock and unlock worked
perfectly. This probably explains the gap; the GPU state was not
captured at logout. It likely also means the earlier 0.99 s and 1.05 s
runs found the GPU already awake. The keep script does not cover this
file, and no change to it has been made.

### Combined login and lock regression

`warm-combined-1795618921` ran the patched starters with the existing
combined desktop KWin, private screen locker, wallpaper producer and
wallpaper-only login splash. It used a synthetic wallpaper and the stock
VM greeter theme, not the physical theme or photo. With the six-second
injected stop, re-login reached a new desktop, the D-Bus lock state
changed to active, and a password entered via QMP unlocked it.
This is functional coexistence in the VM, not physical visual acceptance.

To reproduce, stage `bin/`, `lib/`, and `share/` from the lock prefix in
a temporary directory, overlay the login prefix's KWin binaries and
`libkwin.so.6`, and pass that directory as `LOGOUT_VM_COMBINED`. Use
`LOGOUT_VM_STOP_FIX` and `LOGOUT_VM_DELAY_STOP=1` as above.

### Manjaro / SDDM comparison

On a second machine (Manjaro, Plasma/KWin 6.8.2, SDDM 0.21.0),
the desktop ran Wayland and SDDM used an X11 greeter. The monitor
was connected directly to the NVIDIA-driven output. The user saw
one brief black screen on normal logout, no “No signal” message,
and signed back in. The absence of that message does not rule out a
brief interruption.
SDDM's greeter connected 1.757 s after desktop KWin stopped.
The sampled connector remained connected, although its enabled flag
went from enabled on the old desktop to disabled on the greeter VT
and enabled again after returning to the desktop. That flag does not
measure physical link state or tell us the greeter refresh rate.
The CachyOS generator was absent. Different GPU wiring, login manager,
and greeter backend make this a comparison, not a controlled A/B.
No changes were applied on Manjaro.

A second, read-only physical capture measured **4K 144 → 60 → 144 Hz**:
the desktop had a 1328.8 MHz DRM pixel clock before and after logout;
Xrandr marked 60 Hz current in the X11 greeter. The intervening DRM mode
was unavailable at some samples. The user saw one uniform black interval,
not the distinct phases observed on CachyOS. Re-login worked. This
confirms an endpoint refresh mismatch on Manjaro, not a measured link
drop or a causal explanation for the black interval.

Before adding a wallpaper hook, compare with the desktop temporarily
at the monitor's preferred 4K 60 Hz, leaving SDDM untouched. Verify the
actual timing on both sides and restore 144 Hz after login. If black
remains with matched timings, a wallpaper hook still cannot cover the
earlier Xorg initialization gap.

The desktop-only comparison sampled 4K 60 Hz before logout and after
sign-in (533.5 MHz DRM pixel clock), and Xrandr reported 4K 60 Hz in
the unchanged greeter. The greeter's exact pixel clock was not captured,
and there were samples with no readable mode during VT changes. SDDM
connected 1.789 s after desktop KWin stopped, versus 1.743 s on the
preceding 144 Hz run. Sign-in succeeded. The original 4K 144 Hz mode
was restored and verified at 1328.8 MHz. The user saw the same uniform
black, but reported it looked a little shorter at 60 Hz. This single
subjective comparison suggests the refresh mismatch may contribute;
it did not remove the blackout or shorten measured greeter startup.

#### SDDM rapid re-login in the VM

Run `SDDM_VM_PACKAGES=DIR bash run-vm.sh BASE NEW_RESULTS sddm`.
The networkless snapshot uses the same signed SDDM and Xorg package
versions as the Manjaro reference machine (see `sddm-packages.sha256`),
with the existing CachyOS/Arch Plasma 6.8.3 base and SDDM's built-in
theme. It matches the X11 greeter → Wayland session path, not the full
Manjaro installation or physical GPU. Only the VM receives packages.

- Stock (`sddm-baseline-1795632543`): rapid re-login passed. Xorg
  started 58 ms after KWin stopped; greeter connected 337 ms after stop.
- Stock + six-second desktop stop (`sddm-delay-1795632579`): the
  password was accepted, but Plasma's start collided with the queued
  workspace stop. SDDM brought the greeter back without its own
  transaction error.
- Same delayed stop + desktop teardown patch only
  (`sddm-delay-fixed-1795632626`): rapid re-login passed. The greeter
  connected 6.23 s after KWin stopped; the wait resolved the race but
  did not shorten the outage. SDDM was unmodified.

This establishes a shared Plasma desktop ordering issue under slow
teardown. The PLM greeter-specific patch is not needed on this SDDM path.

In the continuous stock capture (`sddm-continuous-1795632701`),
Xorg was ready 241 ms after desktop KWin stopped and the greeter
connected another 99 ms later. Sample 011 showed a dark console-like
frame, 012–015 were fully black, and 016 showed the greeter. In the
`SDDM_VM_RETRO=1` run (`sddm-retro-1795632745`), earlier black samples
remained, but Xorg's stippled root appeared in samples 013–019 before
the greeter at 020. KWin stop to Xorg ready was 238 ms, then another
112 ms to greeter connection. Both runs passed re-login. The stipple
is a diagnostic, not a visual improvement; it shows that changing
Xorg's first background can affect the incoming portion, not the
earlier gap. Frame indices are not synchronized to the guest journal.

`SDDM_VM_ROOT_COLOR=1` tests the supported X11 display setup hook
with the separately verified `xorg-xsetroot` package. In
`sddm-root-color-1795632820`, the hook ran on both starts; the returning
greeter's root was magenta at samples 013–016 and the greeter appeared
at 017. Earlier black remained, and re-login passed. The color is a
marker, not a proposed live setting. The hook can fill the window
between Xorg startup and the greeter rendering, but it cannot cover
the earlier Xorg startup gap.

The physical Manjaro journal confirms that boundary: the X11 display
setup hook ran about 1.59 s after Xorg launched, and the greeter connected
about 150 ms after the hook. Xorg's own log had an approximately 886 ms
gap around NVIDIA driver detection. That gap does not identify which
operation consumed the time. A wallpaper in the X11 setup hook could
only cover the tail, so it is not a good first physical experiment.
A separate VM A/B tested whether an SDDM Wayland greeter reduced
startup time without replacing the measured X11 baseline.

The backend comparison (`sddm-backend-{0,1}-1795632902`; opt in
with `SDDM_VM_WAYLAND=1`) passed rapid re-login in both guests.
KWin stop to greeter connect was 382 ms with X11 and 351 ms with
Wayland. X11 first showed the greeter at sample 020, Wayland at
021, with black samples before both. The Wayland display server
reported ready earlier, but that did not translate to a shorter
visible gap in this pair. QEMU cannot model the physical NVIDIA
Xorg startup; this result does not justify a live backend change.

The X11 wallpaper candidate (`SDDM_VM_WALLPAPER=1`) instead uses
`xwallpaper --zoom` in Xsetup, with a one-second upper bound and no
change to the greeter or its authentication. Supply the separately
verified xwallpaper package alongside the other VM packages.
In `sddm-combined-wallpaper-{0,1}-1795632992`, the same synthetic desktop
wallpaper appeared at sample 014 (~0.56 s after the host request)
with the hook; the control was still black then. The greeter appeared
at 019 in the control and 020 with wallpaper. Both logged successful
re-login and password-driven lock/unlock with the combined setup and
desktop teardown patch. The VM greeter theme used a different photo,
so this verifies an earlier wallpaper frame, not visual continuity
into a matching greeter. The hook did not cover the earlier black
samples, and it did not speed up greeter readiness (343 ms after
KWin stopped in the control vs. 405 ms with the hook in this pair).
On physical Manjaro it can only address the short interval after Xorg
starts; do not describe it as a complete blackout fix.

#### Physical follow-up on loki

The Nov 25 journal identifies three returns at the usual 144 Hz
desktop setting. Times at left are local; intervals are from the
same boot's monotonic clock, rounded to milliseconds.

| Xorg launch | Xsetup | Plasma shutdown service start → KWin exit | KWin exit → Xorg launch | Xorg launch → Xsetup | Xsetup → greeter connect |
| --- | --- | ---: | ---: | ---: | ---: |
| 20:21:04 | Wallpaper hook | 705 ms | 17 ms | 1546 ms | 309 ms |
| 20:25:41 | Stock | 657 ms | 17 ms | 1582 ms | 169 ms |
| 20:41:39 | Stock | 675 ms | 17 ms | 1550 ms | 163 ms |

SDDM selected VT 2 just before launching Xorg. That log records the
requested VT. Earlier stock captures used a sampler that read the
actual active VT from `/sys/class/tty/tty0/active`. Their boot-relative
timestamps show that activation preceded mode availability and greeter
connection in both comparisons:

| Outgoing desktop | Xorg launch | Active VT 2, mode unavailable | VT 2, Xrandr reports 4K 60 Hz | Greeter connect |
| --- | ---: | ---: | ---: | ---: |
| 4K 144 Hz | 9844.253 | 9845.22 | 9845.84 | 9845.979 |
| 4K 60 Hz | 10117.367 | 10118.30 | 10118.94 | 10119.138 |

The VT/mode columns use the sampler's loop timestamps, not journal
receipt times. The 60 Hz lines reached the journal before greeter
connect in both runs. A mode being unreadable is not evidence that
scanout stopped, and Xrandr reporting a mode is not evidence of an
already visible frame. These samples do not identify the exact VT
switch instant, first visible frame, or link state.

Separately, the two retained stock Xorg logs both show an 886–887 ms
gap after applying the NVIDIA
OutputClass and before logging the autoconfigured driver list. The
driver logged setting the mode about 1.14 s after launch. Neither
landmark measures link training or tells us which operation caused
the gap. The greeter's socket connection is not its first frame.

The one confirmed hook draw logged success 154 ms into Xsetup, still
after the long Xorg startup. Rollback completed at 20:23:44; a later
read-only check found the helper absent and `pacman -Qkk sddm` reported
zero altered package files. The confirmed trial ended in a successful
sign-in after a deliberate pause, not a rapid re-login or lock test.

At 10 samples/s, `video_2026-11-25_20-26-33.mp4` and the requested stock
clip `video_2026-11-25_20-42-24.mp4` each show about 1.6 s of visible
black on logout (11.6–13.2 s and 8.4–10.0 s, respectively). The first
clip was initially labeled hook-enabled, but its media timestamp is
closer to the 20:25 stock return than to the 20:21 confirmed hook run.
The camera clock was not aligned to the journal; do not treat the
clips as a verified stock-versus-hook visual A/B. They also cannot
distinguish signal loss from rendered black.

Keep stock Xsetup and the X11 backend. The hook cannot cover the
measured Xorg startup, and the Wayland VM comparison found no shorter
visible gap and did not model the physical NVIDIA path. Nothing here
justifies changing session ordering or forcing an Xorg driver or mode.

#### Same-run stock video and telemetry, unaligned clocks (21:10)

A read-only sampler ran as a root transient unit (50 ms loop) during
one stock logout at 4K 144 Hz while the user filmed the monitor
(`video_2026-11-25_21-11-28.mp4`, reviewed at 10 samples/s):

| Boot clock | Event |
| ---: | --- |
| 13557.059 | Plasma shutdown service started |
| 13557.775 | Desktop KWin exited |
| 13557.792 | SDDM launched Xorg on VT 2 |
| ≤13558.72 | tty1 DRM state still reported 144 Hz |
| 13558.72 | Active VT 2, mode unavailable |
| 13559.31 | Xrandr reports 4K 60 Hz in the greeter's Xorg |
| 13559.480 | Greeter connected |

| Clip time | Visible |
| --- | --- |
| 17.1–17.7 s | Logout dialog |
| 17.8–18.1 s | Desktop wallpaper, windows closed |
| 18.2–19.2 s | Dark grey, backlight visibly on, cursor dot |
| 19.3 s | Faint red at the bottom edge (one frame) |
| 19.4–20.8 s | Fully black, backlight visibly off |
| 20.9 s | Dark, backlight on |
| 21.0 s | Breath greeter |

The video and sampler describe the same run, but the clocks have no
shared timing cue. SDDM greeter Connect is not first visible presentation
and cannot anchor the two timelines. The video distinguishes visibly
backlit dark gray from apparent black; it does not measure signal or
backlight state. The sampler reported the earlier 144 Hz mode and the
later Xrandr 60 Hz mode, not the CRTC's active state in between. Neither
timeline locates the start of the apparent blackout relative to KWin
exit or VT activation.

`nvidia_drm` had `modeset=Y fbdev=Y`.

#### Output state capture (21:25)

`loki-logout-capture2.sh` (20 ms loop, root, read-only) logged the
DP-3 CRTC `enable/active` from DRM debugfs plus sysfs `dpms`/`enabled`
for two stock logouts. In the second, `HOLD=1` also kept
`/dev/dri/card2` open without becoming master, to test whether the
blank was the last-close fbdev restore.

| Event | Stock | Fd held |
| --- | ---: | ---: |
| Desktop KWin exited | 14478.52 | 14612.60 |
| Active VT 2, CRTC still `active=1` 144 Hz | 14479.43 | 14613.52 |
| CRTC detached, `dpms=Off` | 14479.46 | 14613.54 |
| Greeter connected | 14480.32 | 14614.38 |

In both runs the sampled CRTC stayed active until roughly 0.9 s after
KWin exited. The next sample after VT 2 activation showed detach and
DPMS-off, about 20–30 ms later. A passive fd did not prevent it. These
are not the 21:10 video run: do not map the detach onto its black
frames. The trace does not establish when Xorg restored visible output.

On stock X11 the detach coincided with the VT takeover. This does not
identify the responsible operation or prove physical DP link retraining.
The physical stock Wayland greeter trial has since been completed: the
visible blackout remained, X11 was restored, and the drop-in was absent.
See [the decision plan](PLAN.md) for what did not work and
[the trial record](HOLDER-DESIGN.md) for measurement limits.

#### Stock X11 logout with a filmed uptime cue (23:31)

`video_2026-11-25_23-31-33.mp4` shows live `/proc/uptime` in Konsole
before logout. The visible clock at clip times ~1 s and ~5 s places
video zero near boot time 21961.6 s, to within a few tenths of a second
(clock display cadence 0.2 s, rendering delay not calibrated).
Use the sampler's embedded uptime, not the journal arrival timestamp:
one sample arrived ~0.10 s later. The cue matches the second sampler
invocation. Local artifacts: `~/.cache/plasma-logout-handoff/loki-sync.MmjqHU/`.

| Boot time (s) | Observation |
| ---: | --- |
| 21976.16 | tty5, CRTC active, DPMS On; sampled refresh changes from 144 to 60 Hz |
| ~21976.2 | Panel goes apparently black (clip ~14.6 s) |
| 21976.27–.29 | Desktop KWin service ends; SDDM starts Xorg on tty1 |
| 21977.18 → .21 | tty1 first sampled active at 60 Hz, then detached with DPMS Off |
| 21978.046 | SDDM greeter Connect; the clip is still dark |
| ~21979.2 | Greeter artwork first visible (clip ~17.6 s) |
| 21992.47 | Successful sign-in starts a new Plasma Wayland session |

This run shows about 3 s from apparent black to visible greeter
artwork. Black starts roughly a second **before** the sampled detach;
the detach cannot explain the entire gap. Onset is near a sampled
refresh change and desktop teardown, but neither is established as
the cause. In particular, active DRM state does not distinguish black
pixels from a blanking or resynchronizing monitor, and the sampler
does not show Xorg's eventual visible output. No measured DP
link-training event or monitor signal status was captured.

**Refresh transition follow-up.** Saved kernel and session logs
(`refresh.log` in the artifact directory) show both 23:31 invocations
reached active 60 Hz on tty5 before SDDM launched Xorg. The unfilmed
invocation had two NVIDIA head-0 flip-event timeouts and a warning
amid KWin teardown; its 60 Hz sample began at 21871.99 but only
returned by 21878.14. The filmed invocation had no equivalent timeout
in the handoff window. Use sample start and journal arrival as a
bracket, not as the precise time of the mode change.

The boot journal identifies fb0 as `nvidia-drmdrmfb`. The [matching
NVIDIA release source](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/620.70.06/kernel-open/nvidia-drm/nvidia-drm-drv.c)
sets up the DRM client/fbdev path, making console restore during
desktop teardown a candidate. The capture lacks the primary-plane FB,
its allocator and the modeset caller. It cannot distinguish a console
restore from another teardown operation or determine monitor signal
state. The earlier passive-fd run tested the later detach, not this
144 → 60 Hz transition.

#### Stock X11 with framebuffer attribution (23:40)

`video_2026-11-25_23-40-25.mp4`; local artifacts
`~/.cache/plasma-logout-handoff/loki-fb.9WI2iP/`. The newest
visible cues at clip times 11 and 13 s read 22493.29 and 22495.29.
Video zero is therefore near boot time 22482.3 s, with a few tenths
of uncertainty. 10 Hz video sampling:

| Clip time | Panel appearance |
| ---: | --- |
| 17.6–19.0 s | Apparently black |
| 19.1–24.6 s | Dim visible field |
| 24.7–26.2 s | Apparently black again |
| ~26.4 s | Greeter artwork visible |

The last pre-gap DRM sample at 22499.92 showed active DP-3,
4K 144 Hz at 1328.800 MHz, and KWin buffers. The next sample
blocked from 22500.03 to 22506.17. On return, plane 64 used
FB 854, allocated by `[fbcon]`, at 4K 60 Hz (533.500 MHz) with
the CRTC active on tty5. Two NVIDIA flip-event timeouts occurred
within the blocked read. This confirms the console buffer and 60 Hz
were present before Xorg launched at 22506.23; it does not time the
change within the blocked read or attribute either black interval
to that commit or to link retraining.

At 22507.13 (clip ~24.8 s) tty1 still sampled the same console scanout;
22507.15–.18 showed detach/DPMS-off during the **second** dark interval.
Greeter Connect followed at 22508.11; visible artwork followed later.
SDDM started a new Plasma Wayland session on re-login. Do not generalize
this timeout-lengthened trace to the earlier filmed run without timeouts.

To repeat the stock capture, use an externally started, read-only
monitor for the actual active VT and output timing. Align a camera time reference with
the host journal, and capture monitor-side signal status if available.
Test a change only if that capture gives a specific hypothesis, with
local user participation and rollback prepared. Check immediate
re-login and lock/unlock separately; sign-in visuals are out of scope.

For local timing (no sudo, if the current user can read the system journal):

```bash
bash journal-timing.sh
```

### Vandal: failed re-login after logout (2026-11-26 21:01)

Holder v5 installed. The user logged out and signed back in about 8 s
later. The password was accepted, but the screen stayed black and the PC
had to be rebooted. Evidence: `journalctl -b -1` of boot `8e3c1363…`.
Nothing was changed on the system during this analysis.

Timeline (user manager of the desktop session):

| Time | Event |
| --- | --- |
| 21:01:28.24 | Logout stops `plasma-workspace-wayland.target`; a stop job for `graphical-session.target` is queued and waits for the apps ordered after it. |
| 21:01:28.28 | Holder switches to VT 1 (desktop KWin still has the card). |
| 21:01:28.25–30.62 | NetBird takes 2.4 s to stop (17 ms in the 20:43 logout, which worked). |
| 21:01:29.73 | Beeper's main process exits with a core dump (SIGTRAP). |
| 21:01:30.046 | `plasma-workspace.target` stops **without** `graphical-session.target` having stopped first. |
| 21:01:30.047 | `drkonqi-coredump-launcher@…` starts for Beeper's crash. |
| 21:01:30.63–30.75 | Portal, document portal, a11y bus and `plasma-xdg-desktop-portal-kde` are D-Bus-activated again. |
| 21:01:30.766 | `graphical-session.target: Failed to enqueue stop job, ignoring: … destructive (plasma-xdg-desktop-portal-kde.service has 'start' job queued …)`. |
| 21:01:30.79 | Desktop KWin stops, the session closes; portal-kde crash-loops without a display until `start-limit-hit`. |
| 21:01:31.70 | Greeter KWin: `logout-holder backdrop: first paint`. |
| 21:01:36.55 | New login: `startplasma-wayland` reloads the user manager; a stop of `graphical-session.target` is queued right after. |
| 21:01:36.65 | `Transaction for plasma-workspace-wayland.target/start is destructive (graphical-session.target has 'stop' job queued …)`. The desktop session ends. |
| 21:01:36.76 | Restarted greeter: `plasma-login-wayland.target/start is destructive (plasma-login-kwin_wayland.service has 'stop' job queued …)`. No greeter appears; black until reboot. |

The same signature occurred once before, at 17:14:49 (v3, Restart from
the Plasma menu): JetBrains Toolbox took 4 s to stop, Beeper crashed, and
`plasma-workspace.target` stopped 1 ms before the DrKonqi launcher
started, without `graphical-session.target` stopping. Of 21 exits from
Plasma in today's journals (boots −5 to 0), 19 stopped
`graphical-session.target` within 0.2 s of Beeper stopping, and 2 (these
two) never did. Beeper dumped core at 18 of them, so the crash itself is
routine; what differs is a slow app keeping the target's stop job pending
when the crash report arrives.

Explanation (from the journal and systemd's job rules; not yet
reproduced): `drkonqi-coredump-launcher@.service` (drkonqi 6.8.3) has
`Requisite=graphical-session.target` and is started by its socket in
`replace` mode. Starting it adds a "verify active" job for
`graphical-session.target`, which conflicts with the pending stop job, so
the stop is cancelled. That lets `plasma-workspace.target` stop at once
(the 1 ms ordering above). The launcher, a Qt program, then activates the
portals and a11y bus, which are `PartOf=graphical-session.target`. When
systemd later tries to stop the now-unneeded target, the portals' queued
start jobs make that stop "destructive", and systemd gives up
("ignoring"). The target stays active and empty until the next login's
reload queues its stop, which collides with the new session's start.
It is the only unit on Vandal with `Requisite=graphical-session.target`.

This is independent of the holder (the 17:14 case was a restart, and
nothing in the chain uses the VT), but the holder makes a fast re-login
easy. The source-level teardown prototype above would not have helped:
by the time `startplasma-wayland` exits, the target has queued start
jobs, so its `--job-mode=fail` stop is refused. The second failure
(greeter restart refused while its old KWin is still stopping) is what
turns a failed login into a permanent black screen; the greeter half of
that prototype addresses it.

#### VM reproduction and candidate fix (`crash-batch.i7moFf`)

The guest has no DrKonqi, so `LOGOUT_VM_CRASH_REPORT=stock|fixed` installs
copies of its two coredump-launcher units under other names, dependencies
unchanged. The service activates the portal, the a11y bus and (40 times,
0.1 s apart) portal-kde, as the crash loop on Vandal did. A user unit that
takes `LOGOUT_VM_DELAY_STOP_SECONDS` (2 here, like NetBird) to stop stands
in for the slow app. Once that unit is stopping, a root job connects to the
socket ("crash report") and logs the pending jobs; 3 s later it logs the
state of `graphical-session.target`. `fixed` adds the candidate drop-in,
`PartOf=graphical-session.target`, on the socket.
`LOGOUT_VM_RELOGIN_DELAY=5` signs back in 5 s after the greeter connects
(the default 0.8 s is far quicker than a person). Holder v5 installed, cold
greeter.

| Run | Pending jobs at the report | Report | `graphical-session.target` | Re-login |
| --- | --- | --- | --- | --- |
| stock-1…4 | slow unit, `plasma-workspace.target`, `graphical-session.target` stop | accepted; `plasma-workspace.target` stopped < 0.1 ms after the report's unit was created, without the target stopping first | stock-1, -3, -4: not stopped during logout; stock-4: still `active`, no jobs, 3 s after the report. stock-2 (no portal-kde loop): stopped 1.7 s later, once the portal had started | passed |
| fixed-1, fixed-2 | same | refused: socket already closed 0.6 s after the logout request | stopped when the slow unit finished (2.0 s) | passed |
| control-1 (no report) | — | — | stopped when the slow unit finished | passed |
| fixed-reboot, fixed-halt | — | — | — | guest went down |

So the VM reproduces the cause (the report cancels the pending stop) and
the stuck target, and the drop-in removes both. It did not reproduce the
final failure: the guest signed in again even with the stuck target, so the
reload at sign-in did not queue the late stop here as it did on Vandal
(where the re-activated portals were still running). Whether the drop-in
prevents the black screen on Vandal can only be shown there.
Runs 1–2 predate the portal-kde loop and the state log; stock-3 has the
loop but not the log.

#### Vandal: drop-in installed (2026-11-26)

Installed as the user (no sudo), after the VM runs above:
`~/.config/systemd/user/drkonqi-coredump-launcher.socket.d/stop-with-graphical-session.conf`
(`[Unit]` / `PartOf=graphical-session.target`), then
`systemctl --user daemon-reload`. Verified: the socket's `PartOf` is now
`plasma-core.target graphical-session.target`, its drop-in path is listed,
and it is still active. Undo: delete the file and reload again.

Verified by one logout (below). To check a later logout, look at the
previous user session's teardown (`journalctl -b --user` or the system
journal) for:

- `Closed Socket to launch DrKonqi for a systemd-coredump crash` right at
  the start of teardown (it used to close only after the Plasma workspace
  target stopped);
- no `Started Launch DrKonqi for a systemd-coredump crash` during teardown,
  although Beeper dumps core;
- `Stopped target Current graphical user session`, and no
  `graphical-session.target: Failed to enqueue stop job`.

```bash
journalctl --since -10min -o short-precise --no-pager \
  -g 'Socket to launch DrKonqi|Launch DrKonqi|Current graphical user session|Failed to enqueue|contradicts existing jobs|Stopped Beeper|Removed session'
```

Beeper's own crash was reported to Beeper by the user (in-app report). A
researcher found Chromium issue 580525223 (marked fixed upstream, November
2026): the browser process sits in its own scope, so stopping the launcher
unit kills its zygote and GPU helpers and the browser hits "GPU process
isn't usable". The journal's `app-Beeper-….scope` fits this. The issue page
could not be opened here; this is the researcher's reading.

First logout with the drop-in (2026-11-26 22:14, holder v5): Beeper dumped
core again (SIGTRAP), but the socket was already closed
(`Closed Socket to launch DrKonqi` at 22:14:13.584, 0.1 ms after
`plasma-workspace-wayland.target` stopped; it used to close after the
Plasma workspace target). DrKonqi's system-side processor logged
`"Connection refused"` and no launcher started. `Stopped target Current
graphical user session` followed 1 ms after Beeper stopped; no
`Failed to enqueue` and no conflicting transaction. Sign-in 6.4 s after
the session closed reached a new desktop, and the socket was listening
again at 22:14:22. One logout, without a slow app, so this shows the
trigger is gone, not that the 2-in-21 race can no longer happen.

Unrelated to the drop-in: 2.4 s passed between the greeter session start
and its first user unit (22:14:15.50 → 17.90), against 0.4 s at 21:01. That
matches the known `/etc/profile.d/nvidia-rtd3-workaround.sh` `lspci` delay
with the GPU suspended (see "Cold user-manager delay"); the file is still
installed. The holder kept the picture meanwhile (backdrop first paint
22:14:18.58).

Later observations (2026-11-26/27, drop-in and holder v5 installed):

- Shut Down from the Plasma menu at 22:56:49: the helper armed and copied
  the display settings, did not switch consoles, `graphical-session.target`
  stopped normally, and the PC powered off. First live check of Shutdown;
  before this only the VM had tested it.
- Crashes during logout get no DrKonqi notification. The core dump is
  kept (`coredumpctl`), and at the next sign-ins (22:15:22, 09:49:01) a
  pickup handed each stored Beeper dump to the launcher. But Beeper has no
  KCrash metadata ("Unable to find file for pid …"), and the 6.8.3 launcher
  does not notify for pickups, so nothing was shown. Since 11-26 21:00 the
  processor logged 18 refused reports ("Connection refused"); 17 of them
  predate the drop-in (installed 22:13), since the stock socket also refuses
  reports that arrive after it closes. Whether a KCrash-enabled app's crash
  at logout is shown at the next sign-in is untested. Details:
  [drkonqi-report/README.md](drkonqi-report/README.md).

### Greeter recovery after a failed sign-in (VM)

2026-11-26 and 27, VM only; nothing was installed or changed on Vandal. The
goal is the second failure at 21:01: the restarted greeter is refused and the
screen stays black. Making the desktop start succeed is the DrKonqi drop-in
above and is not part of this test.

#### How it is tested

`LOGOUT_VM_FAILED_RELOGIN=stuck|recover` (new) adds the six-second
`graphical-session.target` stop used before, logs out, and signs in 0.8 s after
the login screen connects, so the desktop start is refused.

- `stuck` passes if the greeter's start is refused too, no greeter connects
  within 20 s, no greeter UI process runs and no desktop appears.
- `recover` passes if the desktop start was refused exactly once, the greeter's
  never, a new greeter connects, its screen is not black, and a second sign-in,
  made after the old stop finished, reaches a desktop with
  `graphical-session.target` active.

`LOGOUT_VM_SLOW_GREETER_STOP=SECONDS` (new) adds an `ExecStopPost` sleep to the
greeter's KWin. All runs use holder bundle v5 (`holder-bundle-vm-5`) unless
another is named. Results are under
`~/.cache/plasma-logout-handoff/greeter-recovery/`; `summary` there has a line
for each run except `stock-cold-stuck-1`, the first (earlier lines lack the
later columns). In the reproduction and patch runs the sleep was a drop-in in
`/etc/systemd/user`; the delivery runs use the greeter user's configuration, so
that the holder can be reinstalled over it.

The guest has Plasma 6.8.3, Qt 6.12.1, KDE Frameworks 6.32.0 and systemd 262.2,
the same upstream versions as Vandal, and the same `plasma-login-manager`
6.8.3-1 package file.

#### Reproduction with the packaged starter

| Runs | Greeter KWin stop | Result |
| --- | --- | --- |
| `stock-cold-stuck-1…5` | as is | stuck in 1 of 5 (`-4`); otherwise the new greeter came up |
| `stock-warm-stuck-1…5` | as is | stuck in 0 of 5 |
| `stock-slow1-cold-0…3`, `stock-slow1-warm-1…2` | 1 s slower | stuck 6 of 6; final screen sampled fully black |
| `stock-slow6-cold-1` | 6 s slower | stuck |

So cold mode, which Vandal uses, reproduces both errors, but without help it is
a race. In the ten unslowed runs the old greeter's KWin finished stopping
26–38 ms after "Greeter starting"; in nine the new starter was not refused, and
in the reproduced run it asked 3 ms too early. On Vandal at 21:01:36 the refusal
came 25 ms before the old KWin finished (journal, read only). With the
one-second slowdown the packaged starter asked about 1 s too early every time.

#### Greeter-only source patch

`build-greeter-fix.sh` builds
[the patch](patches/startplasma-login-wayland.patch) from a private clone of tag
`v6.8.3` (here, of `../plasmalogin-theme/upstream`, whose startkde sources are
unmodified). The unpatched build made the same way imports exactly the same
symbols and libraries as the installed package's program; the patched build's
imports differ from it only as the patch's added and removed calls would. The
builds used are in `build-2/` in the results directory; `stop-fix-2` from 25
November was not used for these results. Add `LOGOUT_VM_GREETER_FIX=build-2/patched/startplasma-login-wayland`
(full path) to replace only the guest's greeter starter.

| Runs | Greeter KWin stop | Result |
| --- | --- | --- |
| `patch-slow1-cold-1…3`, `patch-slow1-warm-1…2` | 1 s slower | recovered 5 of 5 |
| `patch-cold-1…3`, `patch-warm-1…3` | as is | recovered 6 of 6 |
| `patch-slow6-cold-1` | 6 s slower | **stuck**: the starter stops waiting after 4 s |
| `ctl-patch-cold`, `ctl-patch-warm` | normal logout and sign-in | passed |
| `ctl-patch-reboot`, `ctl-patch-halt` | restart, shutdown | passed ("Restarting system", "Power down") |

In all eleven recovered runs the new greeter was started 6–8 ms after the old
KWin had stopped; with the packaged starter in the slowed runs it was started
about 1 s before. In the unslowed runs the new greeter connected 0.3 s after
the desktop start was refused. Because the packaged starter also survives most
unslowed runs, the slowed runs are the evidence that the patch matters.

On Vandal, 24 greeter teardowns in the journals of six boots (26 and 27
November) took 59–122 ms from "Stopped target plasma-login-wayland.target" to
the greeter KWin stopped, well inside 4 s. The longest was the 21:01 failure.

#### Delivery proposal

Ship [holder/login-screen-start](holder/login-screen-start) in the holder
bundle instead of the compiled patch. It is installed as
`/usr/local/bin/startplasma-login-wayland`, joins the pending stop of the old
greeter (`systemctl --user --job-mode=fail stop`, up to 100 s) and then runs
the packaged starter. Plasma Login Manager looks the command up on its `PATH`
each time it starts a greeter.

| | Wrapper | Compiled patch |
| --- | --- | --- |
| Where it waits | before the new greeter starts | while the old one exits |
| Wait limit | 100 s | 4 s (the login manager allows 5 s) |
| After a package update | stays in use | needs a rebuild; under `PACKAGES` it would fall back to the packaged starter, and the black screen could return unnoticed |
| Tested as installed | yes, below | no (only copied over `/usr/bin` in the guest) |

The patch remains the candidate to report upstream. `install.sh` installs the
wrapper with the other files, refuses if the running login manager does not
search `/usr/local/bin` before `/usr/bin` or sets `PLASMALOGIN_GREETER_EXEC`,
and `--restore` removes it. No restart is needed.

New runner options: `LOGOUT_VM_HOLDER_UPGRADE=NEW_DIR` removes the installed
bundle with its own installer and installs `NEW_DIR` from the desktop, with the
login manager running, as on Vandal. `LOGOUT_VM_HOLDER_RESTORE=1` then removes
the last bundle again. `holder-bundle-vm-6` (in the results directory) is v5's
KWin, wallpaper program and helper plus the new installer and wrapper.

| Runs | Installation | Result |
| --- | --- | --- |
| `upgrade-slow1-cold-1…3`, `upgrade-slow1-warm-1…2` | v5 → v6 from the desktop, 1 s slower | recovered 5 of 5 |
| `upgrade-cold-1…3` | v5 → v6, as is | recovered 3 of 3 |
| `wrapper-slow6-cold-1…2` | v6, 6 s slower | recovered 2 of 2 |
| `theme-slow1-cold-1`, `theme-cold-1` | v6 with the Vandal theme | recovered 2 of 2 |
| `stale-slow1-cold-1` | v6, changed package simulated | recovered; no backdrop, so the packaged KWin ran, and the wrapper stayed in use |
| `restore-slow1-cold-1`, `upgrade-restore-slow1-cold-1` | v6, or v5 → v6, then `--restore` | stuck, as packaged; the greeter ran from `/usr/bin` again |
| `ctl-upgrade-cold`, `ctl-upgrade-warm`, `ctl-upgrade-theme-cold` | normal logout and sign-in | passed |
| `ctl-upgrade-reboot`, `ctl-upgrade-halt` | restart, shutdown | passed ("Restarting system", "Power down") |

The recovery runs after an installation logged the greeter command as
`/usr/local/bin/startplasma-login-wayland`; none logged a failed stop. From
"Starting Wayland user session" to the greeter KWin starting, the median after
logout was 34 ms with the packaged starter (cold, 10 runs) and 48 ms with the
wrapper (cold, 6 runs). In the normal-logout controls with the
holder (patched starter and wrapper) no capture was black between logout and
the login screen; 12–13 black captures followed the password, as in
`ctl-v5-cold`. Existing modes without the new options still passed:
`ctl-v5-cold`, and without a holder `ctl-plain-cold` and `ctl-stockfix-warm`.
After a last change to `monitor.py` (escaping of line breaks in new commands),
nine runs across the new modes were repeated as `final-*`; all passed.

To install on Vandal (done 2026-11-27, see below), from a checkout that has this change:

```bash
cd holder
old=~/.cache/plasma-logout-handoff/holder-bundle-vandal-5
new=~/.cache/plasma-logout-handoff/holder-bundle-vandal-6
BUNDLE_PACKAGES="$(cat $old/PACKAGES)" bash bundle.sh $new $old/greeter/plasma-login-wallpaper
sudo bash $old/install.sh --restore && sudo bash $new/install.sh
```

`bundle.sh` takes KWin from `backdrop/build`, which matched v5's copy when this
was written. After the next logout,
`journalctl -b -g 'startplasma-login-wayland'` should show the
`/usr/local/bin` path.

Checked read only on 27 November: the packages v5 pins are installed, systemd's
`PATH` is `/usr/local/sbin:/usr/local/bin:/usr/bin`, and `plasmalogin.service`
sets no environment of its own, so the installer's new check should accept this
machine.

#### Vandal: v6 installed (2026-11-27)

The user ran, at 12:34:59, `sudo bash …/holder-bundle-vandal-5/install.sh
--restore && sudo bash …/holder-bundle-vandal-6/install.sh`; both finished
within 0.4 s and the installer's `PATH` check accepted the machine. Checked
afterwards as the user: `/usr/local/bin/startplasma-login-wayland` is the
bundle's `login-screen-start` byte for byte, and every file in
`/usr/local/lib/logout-holder/MANIFEST` matches its hash except
`/etc/polkit-1/rules.d/60-logout-holder.rules`, which only root can read.
The DrKonqi socket drop-in is still in place. No logout yet with v6; the
login screen running at install time was started by v5.

Check after the next logout:

```bash
journalctl -b --since -10min -o short-precise --no-pager \
  -g 'startplasma-login-wayland|logout-holder|contradicts existing jobs|Failed to enqueue'
```

#### Vandal: first logout with v6 (2026-11-27 12:46)

Reboot at 12:43 after a package update (kernel, pipewire; no KWin, Qt or
Plasma Login Manager change, so `PACKAGES` still matched). Logout at 12:46:49
and sign-in at 12:47:00 both worked. The login manager started the greeter through the
wrapper (`Starting Wayland user session: … "/usr/local/bin/startplasma-login-wayland"`),
which logged nothing, so there was no pending stop to wait for. The DrKonqi
socket closed at 12:46:49.72; Beeper's crash at 12:46:49.77 was refused
(`"Connection refused"`) and the session stopped normally.

The user reported two visual problems:

1. As the login screen appears, it dims, then the sign-in UI scales up from the
   centre and slides into place; only the end of that is visible. The user had
   seen this before v6 ("not top importance") and thinks it began with a later
   greeter change.
2. One dark frame between the login screen and the desktop at sign-in.

Checked read only:

- The greeter theme has not changed since 2026-11-20: its binary
  (`/usr/local/lib/plasmalogin-theme/plasma-login-greeter`) and QML sources
  are dated 2026-11-20. The 2026-11-26 anchor fix (vandal-lock-screen
  `994cb5e`) changed only `/usr/share/vandal-login-branding/…/SessionManagementScreen.qml`.
  The greeter imports `org.kde.breeze.components` from the package
  (`plasma-workspace` 6.8.3-1.1, unaltered per `pacman -Qkk`) and takes only the
  logo and fonts from `vandal-login-branding`.
- The greeter KWin runs with no configuration of its own, so KWin's default
  window-open animation applies to the greeter window. Before the holder, the
  screen was black until the greeter drew. Since the holder, the backdrop
  shows the wallpaper first, so an animation of the greeter window would now
  be visible. This is a hypothesis; nothing in the journal shows animations.
- Last sign-in confirmed smooth: plasma-login-handoff `dcb7adf`
  (2026-11-25), before any holder bundle. Since then, the holder has
  replaced the greeter's KWin and wallpaper programs and copies the desktop's
  display settings to the greeter. At sign-in: `Jumping to VT 2` at
  12:47:00.470, session KWin started at 12:47:00.690.

The other session (plasma-lock-handoff) reports that the user does not see
the scale-in at boot, only after logout. Both paths paint the backdrop
first. After logout the greeter connected 0.33 s after the backdrop's first
paint; at boot, 1.5 s after.

VM frames from `greeter-recovery/theme-cold-1` (Vandal theme, v6, about one
capture every 47 ms after logout) show no scale-in. The sign-in UI appears
whole between two captures (`frame-036` → `037`), fades out about 0.3 s later
(`044`–`046`), and fades back in (`055`–`059`). That fade follows the greeter's
`uiVisible` (`GreeterState.activeWindow === Window.window` in `Main.qml`).
The guest's renderer is not logged, so the run does not show whether KWin's
scale effect could run there at all.

#### Login screen scale-in reproduced in the VM

KWin turns script animations off on a software renderer, so the VM's llvmpipe
greeter never ran the `scale` window animation (the effects loaded then are the
11 built-in ones). With `LOGOUT_VM_GREETER_FORCE_ANIMATIONS=1`
(`KWIN_EFFECTS_FORCE_ANIMATIONS=1` in the greeter KWin) the greeter loads 29
effects including `scale`. With `LOGOUT_VM_GREETER_NO_SCALE=1` on top, the
same list without `scale` (28).

The candidate fix, as tested: drop-in
`plasma-login-kwin_wayland.service.d/81-no-open-animation.conf` setting
`XDG_CONFIG_DIRS=/usr/local/lib/logout-holder-test/xdg:%E/kdedefaults:/etc/xdg`
(the starter's own `kdedefaults` directory is kept), with a `kwinrc` there
containing `[Plugins] scaleEnabled=false`. Results in `anim-batch/` (v6 VM
bundle, Vandal theme, animations forced):

| Run | Greeter after logout | Result |
| --- | --- | --- |
| `ctl-forced-1` (no fix) | dimmed, scaled copy of the screen over the backdrop (`frame-037`), then the sign-in UI grows from the centre into place (`038`–`039`) | passed |
| `noscale-forced-1`, `fix-cold`, `fix-warm` | no scaled or ghosted frame; the UI appears at full size and opacity (one capture each catches the clock half drawn) | sign-in passed |
| `ctl-cold` (no fix) | same scaled and dimmed frames as `ctl-forced-1` (`frame-035`–`038`) | sign-in passed |
| `ctl-forced-2` | login screen not shown until after the capture window (host load) | no sign-in |
| `noscale-forced-2`, `fix-reboot`, `fix-halt` | first sign-in not ready in 40 s (host load above 20), before the change was installed | not a test |
| `fix-reboot-2`, `fix-halt-2` | restart, shutdown from the desktop with the fix installed | passed ("Restarting system", "Power down") |

The control matches the user's description ("dims, scales up from the middle
and slides into place"). In both the control and the fix, the sign-in UI also
fades out about 0.4 s after appearing until a key is pressed; that is the
greeter's own `uiVisible` behaviour, not this animation.

Live script: `greeter-animation-test.sh apply|undo|status`. Applied on Vandal
by the user on 2026-11-27 13:29:41 (first prompt had timed out); the greeter's
user manager was inactive, so the next greeter start reads the drop-in.

First logout with it, 13:32 (journal): session stopped normally (crash report
refused, no `Failed to enqueue` or `destructive`); greeter started through the
wrapper, backdrop first paint 13:32:14.85, greeter connected 15.19, sign-in
13:32:18.59 reached the session KWin. The journal does not show which effects
the greeter KWin loaded.

Two more logouts followed, at 13:34:43 and 13:35:39, each with sign-in and
without `Failed to enqueue` or `destructive`. The user then reported (about
13:36): "logout and login looks correct, no scaling or dimm". The scale-in is
gone on Vandal. The override stays installed as the test files; it is not part
of the holder bundle yet.

#### Limits

- The desktop failure is injected with a slow stopping unit, and the greeter
  race is made certain with a second one. Neither is the DrKonqi chain.
- The screen is QEMU's emulated one; nothing here shows a physical display.
- The second sign-in waited for the old stop to finish. Signing in again before
  that was not tested; the desktop start would be expected to fail again.
- The recovered login screen shows no message about the failed sign-in.
- The wrapper stops running greeter units before starting new ones, which
  assumes one seat.
- Not exercised in the VM: the installer's two new refusals (the `PATH` test was
  only tried on sample strings) and the wrapper's path for a stop that fails or
  times out.
- One run was cut off when the working session ended
  (`interrupted-wrapper-slow6-cold-1`); it was repeated and is not counted.

### Holder v7: animation setting and package guard (VM)

Two changes against v6; the helper and the patched programs are byte-identical.

1. **No window-open animation on the login screen**, from the bundle:
   `/usr/local/lib/logout-holder/xdg/kwinrc`, put on the greeter KWin's
   configuration path by the bundle's drop-in. The installer accepts the
   unchanged `greeter-animation-test.sh` files and removes them after a
   successful install.
2. **Package guard.** `PACKAGES` was a fixed list of 5, while the copies link
   39 packages that are Qt or use Qt. `bundle.sh` now derives it: the dynamic
   loader reports which libraries supply private symbols to the copies, and
   `kwin`, `plasma-login-manager` and `qt6-wayland` are added. On Vandal:
   `kdecoration` 6.8.3-1.1, `kwin` 6.8.3-3.1, `kwindowsystem` 6.32.0-1.1,
   `plasma-login-manager` 6.8.3-1, `qt6-base`, `qt6-declarative` and
   `qt6-wayland` 6.12.1-1.1. For everything else, `greeter-start` runs
   `ldd -r` on the copy (about 48 ms for KWin, 30 ms for the wallpaper
   program) and starts the stock program if a library or symbol is missing.
   The installer refuses such a bundle.

VM runs (`holder7-batch/`, Vandal theme, VM bundle with the same scripts as
the Vandal one), all passed, with host load at most 10.2 after each run. "Upgrade" means v6 and the
test files installed first, then v6 removed and v7 installed from the desktop:

| Run | Start | Result |
| --- | --- | --- |
| `upgrade-cold`, `upgrade-warm` | upgrade; animations forced | test files gone after install; greeter loaded 28 effects, no `scale`; backdrop painted; no scaled or dimmed copy and no black between desktop and login screen in the captures; sign-in passed |
| `fresh-cold` | v7 only; animations forced | same |
| `upgrade-reboot`, `upgrade-halt` | upgrade | restart ("Restarting system") and shutdown ("Power down") from the desktop |
| `broken-library` | v7; a library name in the installed KWin copy changed | stock KWin started, logged `libQt6Gone.so.6 => not found`; black before the login screen, as without the backdrop; sign-in passed |
| `broken-symbol` | v7; a symbol name in the installed wallpaper copy changed | stock wallpaper program started, logged `undefined symbol`; sign-in passed |
| `stale` | v7; a package listed that is not installed | both stock programs started; black before the login screen; sign-in passed |
| `restore` | upgrade, then v7 `--restore` | no backdrop at the next login screen; sign-in passed |
| `recover` | v7; failed sign-in, slow login screen stop | login screen came back; second sign-in passed |

In the three runs with captures and good copies, the desktop is followed
directly by the login screen. The black captures after the password (10–17)
are the sign-in gap that earlier runs also show (12–13 in the v6 controls).

Outside the VM, on Vandal as the user, nothing installed: `greeter-start` with
its paths redirected ran the good copies, and chose the stock program for a
missing library, a missing symbol (in `libkwin` and in the wallpaper copy) and
a changed package; the installer's load check passed the Vandal bundle and
refused the two broken ones.

Limits: the VM installs packages without pacman's database, so its `PACKAGES`
is empty except in `stale`; the derived list and `bundle.sh`'s derivation ran
on Vandal only. A copy that loads and then fails while running is not
detected. A symbol that keeps its name but changes behaviour or layout is
caught only through the package pins.

Bundle for Vandal:
`~/.cache/plasma-logout-handoff/holder-bundle-vandal-7`. To install over v6:

```bash
c=$HOME/.cache/plasma-logout-handoff
sudo bash $c/holder-bundle-vandal-6/install.sh --restore &&
    sudo bash $c/holder-bundle-vandal-7/install.sh
```

To go back to v6, swap the two versions in that command (the scale-in then
returns unless `greeter-animation-test.sh apply` is run again).

#### Vandal: v7 installed (2026-11-27)

The user ran, at 16:56:15, `sudo bash -c 'bash …/holder-bundle-vandal-6/install.sh
--restore && bash …/holder-bundle-vandal-7/install.sh'`. Checked afterwards as
the user:

- Every file in `/usr/local/lib/logout-holder/MANIFEST` matches its hash except
  the polkit rule, which only root can read. The helper, `greeter-start`, the
  patched copies, the login-screen wrapper and `PACKAGES` are the bundle's, byte
  for byte.
- The greeter KWin drop-in sets `XDG_CONFIG_DIRS` to the bundle's directory,
  whose `kwinrc` has `scaleEnabled=false`. The test drop-in
  `81-no-open-animation.conf` and `/usr/local/lib/logout-holder-test` are gone.
- Every package in `PACKAGES` is installed at that version, and `ldd -r` on the
  installed copies reports nothing missing.
- The DrKonqi socket drop-in is still in place, and the wallpaper fallback is
  the theme's program.
- The greeter's user manager was inactive, so the next greeter start reads the
  new units.

Check after the next logout (no output from the second command, which looks for
`starting the stock`, means both copies ran):

```bash
journalctl -b --since -10min -o short-precise --no-pager \
  -g 'logout-holder|startplasma-login-wayland|Failed to enqueue|destructive'
journalctl -b --since -10min --no-pager -g 'starting the stock'
```

First logout with v7, 17:01:55 (journal): the login screen started through the
wrapper, backdrop first paint 17:01:58.96, greeter connected 17:01:59.29, the
helper stopped 17:02:00.52. No `starting the stock` message since the install,
so neither copy was replaced; no `Failed to enqueue` or `destructive`. Sign-in
at 17:02:03.86 reached the desktop.

The user reported: "logout was totaly smooth, login black screen is probably
none of your concern". The black at sign-in is followed by the
[login handoff](../plasma-login-handoff); it was already reported with v6
before the no-animation setting existed. The journal does not show frames, so
it says nothing about that black.
