# Logout handoff plan

## Next decision for loki: can a real logout preserve the image?

Leave the physical machine on Plasma Wayland with the stock X11 SDDM
greeter. The passive GPU-fd and stock Wayland greeter trials did not
remove the observed blackout. The [holder tests](HOLDER-DESIGN.md)
showed a synthetic frame switch, not continuity through a real logout.

**Decision after reviewing the VM and physical evidence:** keep the
stock seat/authentication model as the preferred path. In synchronized
guest run `sync-1795644064`, black samples overlapped more than one
framebuffer on an active controller; tracing framebuffer close alone
will not explain the entire visible gap. On physical stock X11 the
controller detached near the VT change. The VM is therefore a test
bed for content continuity, not a reproduction of the monitor going
dark. A one-shot guest fbdev preload (`preload-1795644288`) appeared in two
screenshots but went black again before the greeter. Do not pursue
preloading the console or repeatedly repainting a VT as the solution.
The incoming Wayland KWin background A/B likewise left a black
interval before the marker appeared. Retire greeter-only paint as a
full fix. Before another implementation, map how a trusted frame
could survive the console interval and the first real greeter frame
without changing seat or input ownership. If no credible path exists,
keep stock rather than refine the marker tests.
Pursue a small producer-to-greeter handoff only if it can both
present a trusted frame and preserve the output through takeover.
If the incoming backend disables the physical output regardless,
stop that path. Treat a system compositor as a separate architecture
decision, not the automatic next patch.

Upstream lead: [LightDM release notes](https://github.com/ubuntu/lightdm/blob/main/NEWS)
describe a `mir-container` session running “inside a custom system
compositor.” This is a precedent for nesting a session, not evidence
that one compositor survived logout or kept an NVIDIA DP output lit.
Trace its lifetime and input routing before borrowing that design.

**First check a simpler handoff in the VM.** The
[kernel DRM UAPI](https://docs.kernel.org/gpu/drm-uapi.html) says
CLOSEFB retains the framebuffer only while a plane uses it.
[KWin v6.8.2](https://github.com/KDE/kwin/blob/v6.8.2/src/backends/drm/drm_buffer.cpp#L41-L48)
already tries CLOSEFB then falls back to RMFB on error. Its separate
[GPU teardown path](https://github.com/KDE/kwin/blob/v6.8.2/src/backends/drm/drm_gpu.cpp)
removes outputs and can commit a modeset disabling unused resources.
During a real Wayland-to-Wayland logout, trace the **displayed** FB ID,
CLOSEFB result, first plane/CRTC detach or disable, caller and VT.
Compare these with the incoming greeter's first commit. Don't patch
framebuffer cleanup unless that trace implicates it; a preserved FB
cannot keep a disabled output lit. VM attribution is not NVIDIA proof.

1. **Map ownership before coding.** Draw the proposed sequence from
   logout request to first greeter frame. At each step name the active
   logind session, DRM owner, input recipient, and process that survives.
   Identify the SDDM/KWin change required. Stop if it needs competing
   DRM owners, bypasses normal seat activation, or lets a departing
   desktop receive greeter input.
2. **Test one real handoff in a disposable VM.** Use a trusted static
   image, not a desktop screenshot. Confirm its presentation before
   desktop teardown. Record the old authenticated session ending, the
   display owner surviving, and the new greeter presenting. Compare
   timestamped output captures with stock; a greeter connection or Qt
   frame swap alone is not a pass.
3. **Try to break it.** Stall the greeter before its first frame.
   Require bounded recovery to a usable stock login screen. Verify
   immediate re-login and lock/unlock. Record failures as well as passes.
4. **Decide whether to proceed.** If any gate fails, document the
   blocker and leave loki unchanged. Only after the VM passes, propose
   a separately approved, reversible physical comparison: a VM cannot
   establish that the NVIDIA/DisplayPort monitor stays lit.

## Supported paths

- CachyOS: Plasma Wayland → Plasma Login Manager (Wayland greeter).
- Manjaro: Plasma Wayland → SDDM (X11 greeter, as configured on the
  reference PC). Test the same backend first; a Wayland SDDM greeter
  would be a separate comparison, not a substitute for the baseline.

Share the VM driver and timing conventions, not assumptions about
the cause. Measure each manager's own teardown, greeter startup, and
first output before choosing changes. The CachyOS GPU-generator
workaround and the PLM-specific greeter patch do not apply to SDDM.

**Reliability first.** A working greeter is not a passing logout test.
The desktop must also start on immediate re-login, with a usable shell
and unchanged lock behavior. The physical warm-start experiment exposed
two overlapping service transactions. Do not repeat that workaround on
the host while those races are unexplained.

**Preserve the working handoffs.** The sibling repositories
[`plasma-lock-handoff`](../plasma-lock-handoff) and
[`plasma-login-handoff`](../plasma-login-handoff) already provide the
accepted physical lock/unlock and login transitions. The combined
desktop KWin build, lock wallpaper transport, and wallpaper-only splash
remain the baseline. Do not replace them with logout-specific builds;
reuse their VM instrumentation and verify the combined behavior before
proposing installation.

1. **Capture the lifecycle in the VM.** Exercise cold and warm greeter
   starts, then re-authenticate immediately. Check a new active PLM
   session and a new shell, and capture conflicting systemd jobs. If the
   stock guest passes, use a guest-only delayed stop on a session unit
   to test the timing hypothesis. Keep the natural and injected results
   separate. Check both the desktop target and greeter target. For
   SDDM, exercise a real password login, logout, and immediate sign-in
   on the X11 greeter, first stock and then with the same injected
   desktop stop. Require a new active SDDM Wayland session and shell;
   don't assume a desktop ordering fix is needed until tested.
2. **Fix ordering at the source, if reproducible.** Identify which job
   and which caller own each start/stop transaction. Prefer waiting for
   the actual previous session stop to finish over sleeps, retries that
   hide failures, or keeping the greeter compositor alive. Keep PAM,
   logind seat activation and normal session ownership unchanged.
3. **Separate content from signal.** Once rapid re-login is reliable,
   measure the interval before VT return separately from the greeter's
   first KMS commit. If a physical blink remains, compare actual
   desktop/greeter mode and DP connector state. A wallpaper frame can
   replace rendered black, not a lost link. Don't design around a
   physical mode mismatch until one has been measured.

   The physical capture found 100 → 60 → 100 Hz. For the A/B, use
   DP-1's preferred 4K timing (59.997 Hz, 533.25 MHz), not the other 4K
   60 Hz timing (594 MHz). Record the original desktop mode and back up
   the greeter output config byte-for-byte. Change only DP-1's mode;
   verify the desktop timing before logout, then sample through the
   greeter and sign-in. Restore and verify both original settings even
   if the test fails. If the timing stays constant but flicker remains,
   mode switching alone does not explain it.
4. **Validate on the real display only after isolated passes.** Keep the
   two experiments separate:
   - **CachyOS / PLM (deferred):** If resumed, test at 100 Hz with the
     temporary greeter-only sysfs generator override and automatic
     removal. Measure cold manager
     startup and greeter return; neither a shorter delay nor a greeter
     wallpaper proves the intermediate modeset is gone.
   - **Manjaro / SDDM:** Keep stock Xsetup and X11. The wallpaper
     trial was rolled back. The journal puts roughly 1.55 s before
     Xsetup and does not support a session ordering change. Both clips
     show about 1.6 s of visible black; the first clip's hook attribution
     is unverified. The Wayland VM comparison does not justify a
     backend switch. Defer further live trials until a synchronized,
     read-only capture can test a specific hypothesis about the
     outgoing frame, VT activation, or display signal.

   Do not pre-start a user manager or replace display-manager services.
   First compare visuals with a deliberate pause before re-login; do
   not present that as immediate re-login coverage. Validate rapid
   re-login separately with a reviewed teardown fix and a recovery
   path, alongside lock/unlock and the existing login handoff. Restore
   original settings unless the user explicitly chooses to keep a
   verified change.
