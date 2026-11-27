# Logout holder design

The holder keeps a card open and switches to the login screen's console in
graphics mode. The last desktop frame then stays on screen without anyone
painting it. Diagrams and status: [README.md](README.md). Evidence:
[docs/LOG.md](docs/LOG.md).

## Why logout showed black

| Cause | Fix |
| --- | --- |
| The console returned to text mode when the desktop compositor exited, before the greeter compositor started | helper keeps the cards open and switches VT in graphics mode |
| The greeter's first frames were black until its wallpaper loaded | patched KWin draws the wallpaper underneath; patched wallpaper window is transparent until loaded |
| The monitor re-synced (about 2.5 s) because greeter display settings (RGB range, bits per colour) differed from the desktop's | helper copies the desktop's settings at every exit from Plasma |
| Over the backdrop, KWin's window-open animation dimmed and scaled the greeter | `scaleEnabled=false` for the greeter KWin |

## Parts

| Part | Installed as | Job |
| --- | --- | --- |
| Hook | `/etc/xdg/plasma-workspace/shutdown/logout-holder` | show desktop, wait 0.5 s, start the service |
| Polkit rule | `/etc/polkit-1/rules.d/60-logout-holder.rules` | an active local user may `start` that one unit |
| Service | `/etc/systemd/system/logout-holder.service` | runs the helper as root |
| Helper | `/usr/local/lib/logout-holder/logout-holder` | hold cards, copy settings, switch VT |
| `greeter-start` | same directory | pick the patched copy or the stock program |
| KWin copy, wallpaper copy | `…/greeter/` | backdrop and transparent window |
| `kwinrc` | `…/xdg/kwinrc` | no scale animation, seen by the greeter KWin only |
| Login screen wrapper | `/usr/local/bin/startplasma-login-wayland` | wait for the old greeter to stop |

## Helper

Plasma runs shutdown hooks synchronously, before it stops the desktop. The
helper does this, in order:

1. Refuses unless all hold: seat0 has an active desktop session in front (not
   VT 1, not `plasmalogin`), its user runs `plasma-shutdown`, no greeter
   compositor runs, and at least one card drives a screen.
2. Opens each card with an enabled connector and drops DRM master. Idle cards
   stay closed, so a sleeping discrete GPU is not woken.
3. Reports ready. The hook returns and the logout continues.
4. Copies the display settings.
5. Waits up to 10 s for `plasma-shutdown` to exit.
6. Stops here on restart or shutdown (`systemctl is-system-running` is
   `stopping`, or logind `PreparingForShutdown`). Also stops if the desktop VT
   is no longer in front or a greeter compositor already runs.
7. Logs whether the desktop KWin still has the card (`already gone` would mean
   the switch came late). Puts VT 1 in graphics mode and switches to it (2 s
   limit).
8. Exits 2 s after the greeter compositor opens a card. Gives up after 15 s.

`ExecStopPost` (`--cleanup`) returns VT 1 to text mode if it is in front with
no greeter compositor. The unit has `Conflicts=shutdown.target`, so it cannot
delay a shutdown. It also sets `PrivateNetwork`, `ProtectHome=read-only` and
`NoNewPrivileges`.

### Why it waits for plasma-shutdown

Plasma runs the same hook for logout, restart and shutdown, and does not say
which. For restart and shutdown, `plasma-shutdown` then asks logind, which
requires the asking session to be in front. Switching in the hook (v1–v3)
broke Restart on the live PC
([record](docs/LOG.md#holder-v4-and-v5-0eba4ea)).

### Display settings copy

- Read as the departing user, so a link cannot reach other files.
- Must be KWin's format (a list with an `outputs` part), at most 1 MiB.
- Written as a new file owned by `plasmalogin` (mode 644), then renamed.
- The greeter's first own file is kept as `.before-logout-holder` (or a
  `.none-before-logout-holder` marker). `install.sh --restore` puts it back.
- A failure is logged and does not stop the handoff.

## Greeter

- **Backdrop** ([patch](patches/kwin-6.8.3-logout-vm-backdrop.patch)): KWin
  draws the login wallpaper while no desktop window exists, and for 3 s after
  one appears.
- **Wallpaper window**
  ([patch](patches/plasma-login-manager-6.8.3-logout-vm-wallpaper.patch)):
  transparent until its picture loads.
- **KWin copy needs the distro backports** (KDE 528936 and 528824). Without
  the first, the keyboard did nothing with the lid closed.
- **Package guard:** `greeter-start` runs stock if a package in `PACKAGES`
  changed or `ldd -r` reports a missing library or symbol. `bundle.sh` derives
  the list from the private symbols the copies use. The fallback loses the
  backdrop, never sign-in.
- A copy that loads and fails at run time is not detected. A symbol that keeps
  its name but changes behaviour or layout is caught only by the package list.

## Failed sign-in

If the desktop fails to start, the login manager starts a new greeter while the
old KWin may still be stopping. systemd refuses the start, and the screen stays
black. [login-screen-start](holder/login-screen-start) first joins the pending
stop (`--job-mode=fail`, up to 100 s), then runs the packaged starter.

The trigger of the live failure is separate: DrKonqi's launcher cancels the
pending stop of `graphical-session.target` (shown in the VM, inferred on the
live PC). A user drop-in covers it
([report](drkonqi-report/README.md)).

## Rules for changes

- Never delay or break restart or shutdown. Test both in the VM.
- Change no authentication, seat or session ownership.
- A failure must end in a usable login screen or console.
- The greeter parts must not block graphical login.
- Physical installs need approval, a prepared rollback and a recovery path.
- VM captures prove nothing about GPU timing or the monitor.

## Decisions

| Chosen | Rejected | Reason |
| --- | --- | --- |
| Open card plus VT switch | relay that takes DRM master and paints | painting was unnecessary: 6/6 VM logouts without black |
| Open card plus VT switch | open card alone | on NVIDIA/X11 the controller still detached at VT takeover |
| Keep the card open | VT switch alone | the console framebuffer returned 0.11–0.13 s after the switch (VM) |
| Keep the old frame | resident compositor for both sessions | needs a seat and session redesign |
| Keep the old frame | park the desktop compositor on another VT | it loses DRM master |
| Keep the old frame | paint the console or only the greeter background | neither covered the whole handoff |
| Switch after `plasma-shutdown` exits | switch inside the hook | broke Restart |
| Copy display settings at every exit | manual `sync-greeter-outputs.sh` | had to be rerun after each display change |
| Derived package list and load check | fixed list of 5 packages | the copies link 39 Qt-using packages |
| Disable `scale` in the bundle | separate test drop-in | one install and one undo |
| Shell wrapper before the greeter start | patched greeter starter | patch waits at most 4 s and is lost on package updates |

## Kernel behaviour relied on

- Last close of a card restores the console (`drm_release()` →
  `drm_lastclose()`, Linux 7.0). That an open file prevents this is inferred
  from source plus the VM A/B, not traced.
- Returning a VT to `KD_TEXT` forces the console back even while a compositor
  holds master (`drm_fb_helper_set_par`). So the greeter VT is set to graphics
  mode before the switch.

## Not tested

- NVIDIA-driven outputs, DisplayPort and multiple monitors with the holder.
- A stalled greeter on real hardware. The 15 s give-up and cleanup ran once
  there, when v3 broke Restart and no greeter started.
- Cancelled logout.
- Helper death while it holds a card.
- Direct scanout with the backdrop.
