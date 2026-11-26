# Plasma logout handoff

Investigate the black interval and DisplayPort flicker when Plasma Wayland
signs out to Plasma Login Manager on CachyOS (Plasma 6.8.3). This is separate
from the [login](../plasma-login-handoff) and [lock](../plasma-lock-handoff)
handoffs. See [the long-term plan](PLAN.md). No persistent changes to the
live setup.

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

## Next checks

1. Compare saved greeter output settings and, if needed, actual display
   mode across a logout. Don't sync or change settings before comparing.
2. Investigate the rapid re-login failure below in a disposable VM before
   considering another physical experiment. Do not repeat the pre-start
   on the host or enable lingering as a workaround.

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
Prefer a fix to the CachyOS generator over keeping the trial override.

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
