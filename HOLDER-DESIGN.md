# Logout image holder: feasibility gates

A resident process can prepare an image before logout, but it cannot
present on the same output while the desktop or greeter independently
owns DRM master. The physical fd-only A/B did not preserve the CRTC
through the Xorg takeover. That rules out the passive fd holder in
this configuration, not every possible driver-side handoff.

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
does not replace an already-running greeter. The staged trial script
must not be run: it writes the config before arming rollback.

The guest recovery run `wayland-recovery-1795640971` used
`SDDM_VM_WAYLAND=1 SDDM_VM_GREETER_FAIL=1`. Removing the drop-in
and explicitly restarting SDDM restored Xorg; the normal VM login,
logout and re-login checks then passed. This verifies the recovery
procedure in the VM, not a timer or an automatic fallback. A physical
trial must separate restoring configuration from restarting SDDM:
a timer must not restart the manager underneath an active desktop.

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
