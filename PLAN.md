# Logout handoff plan

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
   - **CachyOS / PLM:** At 100 Hz, try the temporary greeter-only sysfs
     generator override with automatic removal. Measure cold manager
     startup and greeter return; neither a shorter delay nor a greeter
     wallpaper proves the intermediate modeset is gone.
   - **Manjaro / SDDM:** Keep X11 and test a temporary Xsetup wallpaper
     using a matching static asset. Preserve the existing hook and
     authentication. Roll back if it adds a visible transition or
     fails to improve the measured baseline. The Xorg startup gap is
     outside this hook's reach.

   Do not pre-start a user manager or replace display-manager services.
   First compare visuals with a deliberate pause before re-login; do
   not present that as immediate re-login coverage. Validate rapid
   re-login separately with a reviewed teardown fix and a recovery
   path, alongside lock/unlock and the existing login handoff. Restore
   original settings unless the user explicitly chooses to keep a
   verified change.
