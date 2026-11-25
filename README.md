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
2. Reproduce the return in a disposable VM and compare cold versus
   already-running greeter user-manager startup. If the result warrants a
   physical test, temporarily pre-start just the greeter's user manager,
   not a greeter session or compositor. Don't change seat ownership or
   enable persistent lingering for a timing experiment.
3. Check whether the shortened startup removes either dark interval.
   A shorter startup does not establish glitch-free scanout.

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

For local timing (no sudo, if the current user can read the system journal):

```bash
bash journal-timing.sh
```
