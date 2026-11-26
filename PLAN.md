# Logout handoff plan

## Decision plan for loki

**Success means the physical monitor keeps showing a trusted image from
desktop teardown until the real greeter is visible and usable.** Keep
Plasma Wayland and stock X11 SDDM as the baseline. Do not infer monitor
behavior from VM screenshots or equate greeter connection with presentation.

1. **Separate the two physical intervals.** In the [filmed uptime
   capture](README.md#stock-x11-logout-with-a-filmed-uptime-cue-2331),
   apparent black started roughly a second before the sampled detach,
   near a 144 → 60 Hz transition and desktop teardown. Inspect the
   [follow-up capture](README.md#stock-x11-with-framebuffer-attribution-2340)
   confirms a 4K 60 Hz console framebuffer before Xorg launch and
   a separate detach during the second dark interval. The debugfs read
   blocked through two flip timeouts, so it cannot time the earlier
   change exactly. Do not repeat this capture unchanged. Any follow-up
   should discriminate monitor resync from black content, or test
   exact mode matching as an isolated diagnostic, not as a complete
   fix. Use loki's measured 533.500 MHz console timing, not an unrelated
   60 Hz timing; do not assume Plasma exposes an exact match.
2. **Choose the remedy by interval.** If scanout stays active while pixels
   are black, investigate a coordinated last trusted frame / first greeter
   frame handoff. If the output switches off, investigate whether the
   incoming display server can take over without disabling it; painting
   earlier cannot cover that interval. Both can happen in one logout.
   Stop if the evidence cannot distinguish them or no safe change is
   identified. A resident compositor is a separate architecture decision.
3. **Prove a candidate before deployment.** In a disposable VM, exercise a
   real authenticated logout, first visible greeter frame, stalled-greeter
   recovery, immediate re-login and lock/unlock. Preserve logind seat/VT
   activation and isolate greeter input from the departing session. Only
   then propose a separately approved, reversible physical A/B with
   rollback armed first. Keep a change only if the filmed gap disappears
   without regressions; otherwise restore stock.

### What did not solve the blackout

| Tested approach | Result and limit |
| --- | --- |
| Passive GPU device handle (loki) | Keeping the device open without DRM master did not prevent the sampled controller detach. |
| Stock SDDM Wayland greeter (loki) | The trial clip still showed about 1.5 s of black. X11 was restored. The clip does not identify the cause. |
| X11 Xsetup wallpaper (loki) | Xsetup ran about 1.55 s after Xorg started, too late to cover startup. The two clips are not a verified hook-on/off comparison. |
| Preloaded console image / greeter-only paint (VM) | Each image appeared, but neither covered the whole handoff. |
| Compositor parked on an inactive VT (VM) | The process survived, but did not retain display control. |

A persistent compositor that **remains active** is untested, not disproven.
The [detailed captures](HOLDER-DESIGN.md) distinguish VM pixels from
physical signal state. Do not infer DP link retraining from either.

## Earlier cross-platform investigation (historical, not the current loki checklist)

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
   - **CachyOS / PLM:** The one-logout [generator trial](README.md#vandal-greeter-only-generator-ab)
     reduced KWin exit → greeter Connect from 3.24 s to 0.99 s.
     Re-login and automatic removal passed. Keep the override removed;
     pursue the equivalent sysfs check in the CachyOS generator
     upstream, separately from any attempt to remove display blanking.
     The trial did not measure first visible presentation.
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
