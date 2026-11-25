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
`Seat::displayStopped()` evaluates `defaultDisplayServerType()` before
`createDisplay()` reloads the config. Do not assume a staged drop-in
will take effect on the very next logout. Also, deleting a drop-in
does not replace an already-running greeter. The staged trial script
must not be run: it writes the config before arming rollback.

Validate backend selection and recovery in a disposable VM first,
including a greeter that starts but never produces a frame. For the
holder prototype, compare continuous visible frames against stock,
then verify timeout recovery, immediate re-login and lock/unlock.
Do not infer NVIDIA scanout continuity from the VM.
