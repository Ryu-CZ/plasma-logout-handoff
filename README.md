# Plasma logout handoff

Investigate the black interval and DisplayPort flicker when Plasma Wayland
signs out to Plasma Login Manager on CachyOS (Plasma 6.8.3). This is separate
from the [login](../plasma-login-handoff) and [lock](../plasma-lock-handoff)
handoffs. No changes to the live setup.

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

## Next checks

1. Capture a physical logout without recording credentials. Note any monitor
   input banner or “No signal” message and where any blink occurs relative to
   greeter appearance. The absence of a banner does not rule out a signal drop.
2. Compare saved greeter output settings and, if needed, actual display mode
   across a logout. Don't sync or change settings before taking a baseline.
3. In a disposable VM, reproduce the return path and compare cold versus
   already-running greeter user-manager startup. Measure before considering
   a live change. A shorter startup does not establish glitch-free scanout.

For local timing (no sudo, if the current user can read the system journal):

```bash
bash journal-timing.sh
```
