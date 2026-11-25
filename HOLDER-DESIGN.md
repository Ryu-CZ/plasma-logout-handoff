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
session was stopped during the probe. Actual greeter recovery and
seat integration remain untested.
