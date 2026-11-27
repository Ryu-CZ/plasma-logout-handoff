# Logout handoff plan

The goal is met on the CachyOS PC: no black from Log Out to the login screen.
What remains is checking and upstreaming. Status: [README.md](README.md).

## Scope (user, 2026-11-26)

- In: logout, from choosing Log Out until the greeter is visible.
- Out: login, lock and unlock (sibling projects, no longer gates here).
- Restart and shutdown are not goals. They share Plasma's teardown, so every
  change must leave them behaving as before.

## Success test

The monitor keeps showing a trusted image from desktop teardown until the
greeter is visible and usable. Judge it on the physical screen. A VM capture or
a greeter "Connect" line does not prove it.

## Open items

| Item | Next step |
| --- | --- |
| Restart and Shutdown with v7 | try both from the Plasma menu |
| Recovery after a failed sign-in | seen only in the VM; check the journal if one happens |
| DrKonqi re-login race | watch teardowns; one slow-app logout with the drop-in would be the missing evidence |
| DrKonqi bug report | [draft](drkonqi-report/drkonqi-kde-bug.md), not submitted |
| Greeter exit patch (`patches/startplasma-login-wayland.patch`) | candidate to report upstream |
| Crash notifications after a logout crash | untested for an app with KCrash metadata ([detail](drkonqi-report/README.md#crash-reports-at-logout)) |
| `/etc/profile.d/nvidia-rtd3-workaround.sh` delay | fix proposed, not applied |
| `video=DP-1:…` parameter and generator override | installed; need with the holder not tested. The parameter also affects early boot and any display on DP-1 |
| Package updates | rebuild and reinstall the bundle when the backdrop disappears |
| Black at sign-in | belongs to [plasma-login-handoff](../plasma-login-handoff) |
| NVIDIA flip timeouts (Manjaro PC) | [draft report](NVIDIA-REPORT.md), not filed; no diagnostic bundle attached |
| Reversed boot animation instead of the frozen frame | optional wish |

## Manjaro and SDDM

No fix. About 1.6 s of black remains with stock X11 SDDM.

- Keep stock Xsetup and X11. A wallpaper hook runs about 1.55 s after Xorg
  starts, and the Wayland greeter was no better.
- Xsetup and backend trials were rolled back.
- Do not repeat the 23:40 DRM capture unchanged: its debugfs read blocked
  through two flip timeouts.
- Next evidence needed: an externally started, read-only monitor of the active
  VT and output timing, with the camera aligned to the journal, and
  monitor-side signal status if available.
- A follow-up should tell monitor resync from black content, or test exact mode
  matching (the console timing is 533.500 MHz at 60 Hz; Plasma may not offer
  it).
- Then choose by interval. Black pixels on an active output: hand over a last
  frame. Output off: the new display server must take over without disabling it.
  Both can happen in one logout. Stop if the evidence cannot tell them apart.
- Prove a candidate in a VM first (real logout, first greeter frame, stalled
  greeter recovery, immediate re-login, lock/unlock).
- The holder has not been tried there. Its VT switch differs from the earlier
  open-card test, which failed.

## Rules for new experiments

1. VM first, then one approved, reversible physical A/B with rollback armed.
2. One change per run. Keep it only if the filmed gap goes away without
   regressions.
3. Immediate re-login and lock/unlock are separate checks. A greeter that
   appears is not a passing logout.
4. Do not pre-start a user manager or replace display-manager services. The one test with a
   pre-started greeter manager ended in a failed re-login.
5. Prefer waiting for the real previous stop over sleeps or retries. Leave PAM,
   logind seat activation and session ownership alone.
6. Record the original setting and restore it, even when the test fails.
7. Keep the accepted lock, unlock and login builds from the sibling repos. Do
   not replace them with logout-specific builds.

Older plans (image relay, mode matching, SDDM decision plan) are in
[docs/LOG.md](docs/LOG.md#dropped-approaches).
