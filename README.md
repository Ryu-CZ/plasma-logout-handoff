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

For local timing (no sudo, if the current user can read the system journal):

```bash
bash journal-timing.sh
```
