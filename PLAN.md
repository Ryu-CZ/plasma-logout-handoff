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

## Active design: image relay (VM prototype)

**Decision, 2026-11-26:** attempt to remove the black completely with a
three-stage picture relay, gap stage first, VM only. See the
[design decision](HOLDER-DESIGN.md#design-decision-image-relay-to-remove-the-black-2026-11-26).
Prototype: `relay.py`, enabled with `LOGOUT_VM_RELAY=1`.
VM result: 1-3 black captures with relay and compositor backdrop, against
15-17 stock ([details](HOLDER-DESIGN.md#relay-vm-results-all-three-stages-together)).
Not yet black-free; nothing installed. This supersedes
the earlier advice below to defer a handoff owner; the two Vandal fixes
are a separate matter.

## Candidate for Vandal: console mode matching (one filmed logout)

**Confirmed live, 2026-11-26, no logout:** `bash vt-mode-probe.sh` saw
DP-1 at 100 Hz (1188000) on the desktop, 60 Hz on tty3, and 100 Hz after
returning. The console also lit the lid-closed eDP-1 at 1920x1200.

**Source reading** (upstream kernel v7.3.6, systemd v262; distro patches
not checked): logind's VT restore sets `KD_TEXT`; fbcon then force-restores
the console configuration even while a compositor holds DRM master
(`drm_fb_helper_set_par`). That is consistent with the 60 Hz switch while
KWin was still stopping; the trigger at that instant was not traced.
`video=DP-1:3840x2160@100` marks the first probed 100 Hz match, which for
this EDID is CTA VIC 117 (1188 MHz), ahead of DisplayID's 906 MHz timing.

**State, 2026-11-26:** the boot started at 11:36 has the parameter in
`/proc/cmdline`; the desktop on tty2 reads 3840x2160@100, clock 1188000,
lid closed. Console probe (step 2): DP-1 stayed at clock 1188000 on tty3
and after return; eDP-1 still lit at 1920x1200. A rerun gave the same
modes; the added 1 s delay stopped the stray newlines in Alacritty. Blink
inconclusive: the mostly black console hides a short blackout. After the
white fill on tty3, only a top-left rectangle was white and the rest black,
likely because the console is 240x75 cells (1920x1200 with an 8x16 font),
sized to the lit eDP-1. During the probe the rectangle appeared immediately,
with **no full-screen black transition** (by eye, not filmed); step 3
skipped. A console image would cover only that area as things stand.
**Step 4 done:** the [filmed logout](README.md#vandal-console-mode-matching-filmed-logout)
held 1188000 and shows no apparent backlight-off phase, but about 4 s of
black remains, mostly before the greeter compositor starts. User's view:
pure dark, no blurred picture; this does not establish whether the
backlight was on. Parameter not persisted by us;
rollback is still pending (reboot without editing).

**Combined run done:** with the greeter generator override too, the
[filmed logout](README.md#vandal-mode-matching-plus-greeter-generator-override-filmed)
showed about 1.6 s of black and sign-in worked. No further filmed run is
planned. The override has expired; the boot parameter lasts until reboot.

**Decision, 2026-11-26:** the user reports lock/unlock still works and
asked to keep both. `vandal-keep-handoff.sh` makes them permanent (Limine
drop-in plus greeter-only `/etc` generator override; `--restore` undoes
both). Staged and syntax-checked, **not yet run**. After running it:
reboot, check `/proc/cmdline`, log out and sign in immediately, then lock
and unlock. Immediate re-login remains untested. The parameter applies to
any display on DP-1.

1. One boot only: in Limine, edit the entry and append the parameter. Use
   the built-in or USB keyboard; Bluetooth does not work there.
2. Check `/proc/cmdline`, then `bash vt-mode-probe.sh`. Expect 1188000 on
   the console. Watch whether the monitor blinks.
3. If it still blinks, suspect enabling the eDP-1 pipe (hypothesis):
   `echo off | sudo tee /sys/class/drm/card1-eDP-1/status`, repeat, then
   restore with `echo detect | sudo tee` on the same file.
4. Then sample a normal logout:
   `sudo systemd-run --unit=dp-sample --collect /usr/bin/bash "$PWD/sample-dp.sh"`
   and afterwards `journalctl -b -u dp-sample`.
5. Pass: only the 1188000 clock throughout, and no backlight-off phase on
   film. Equal clocks alone do not prove i915 skipped a full modeset.
6. Rollback: reboot without editing. If persisted, the parameter also
   affects early boot, and any other display that appears as DP-1.

A search of the local pi session logs on 2026-11-26 found no `video=`
trial. The constant-60 Hz run recorded "one kind of black" but not
whether the backlight stayed on, so a blackout may survive matching.

Follow-up from the [login project](../plasma-login-handoff): paint the
wallpaper in the greeter KWin's first frames
(`physical/kwin-6.8.3-on-lock-handoff.patch`). The magenta marker
suggests this covers only the tail of the gap. The startup wallpaper
itself is untested in a greeter: check in the VM that it works with
`--no-lockscreen`, and install it where `plasmalogin` can read it.
Console painting and the greeter marker were tested separately, not
together.

This cannot remove rendered black. The separate greeter-only generator
trial shortened KWin exit → greeter Connect from 3.24 s to 0.99 s (one
run); test the two changes one at a time. Immediate re-login is untested
with either.

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
     Re-login and automatic removal passed. CachyOS already sped up
     and then removed the workaround upstream. Temporarily disabling
     both leftover files on Vandal kept the manager startup fast but
     did not shorten KWin exit → greeter Connect (3.59 s). Keep the
     originals after rollback; a reused desktop user manager limits
     what the idle GPU check proves. Do not assume cleanup fixes
     logout or send a duplicate fast-probe patch. None of these trials
     measured first visible presentation.
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
