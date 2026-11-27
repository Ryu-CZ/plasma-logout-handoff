# Logout handoff log

Newest first. Each entry describes the state at the time. For the current
state see [README.md](../README.md).

Machines:

- **Vandal**: CachyOS laptop (Intel plus NVIDIA GPU), Plasma 6.8.3 Wayland,
  Plasma Login Manager (PLM, Wayland greeter).
- **loki**: Manjaro desktop (RTX 4090), Plasma 6.8.2, SDDM 0.21.0 with an
  X11 greeter, DisplayPort 4K at 144 Hz.

"Black captures" in VM runs are `screendump` samples, about 40 ms or more
apart. They are not frame times. QEMU shows emulated pixels, not a physical
display. Run directories are under `~/.cache/plasma-logout-handoff/` and are
not committed. Videos are not committed. VM options: [VM.md](VM.md).

## 2026-11-27

### Vandal: first logout with holder v7, 17:01 (27cc57f)

- Logout 17:01:55. Greeter started through the wrapper; backdrop first paint
  17:01:58.96; greeter connected 17:01:59.29; helper stopped 17:02:00.52.
- No `starting the stock` message since the install. No `Failed to enqueue`
  or `destructive`. Sign-in at 17:02:03.86 reached the desktop.
- User: "logout was totaly smooth, login black screen is probably none of
  your concern". The black at sign-in belongs to the
  [login handoff](../../plasma-login-handoff). It was already reported with
  v6, before the no-animation setting existed. The journal shows no frames.

### Vandal: v7 installed, 16:56:15 (3fd9ccb)

User ran `sudo bash -c 'bash …/holder-bundle-vandal-6/install.sh --restore
&& bash …/holder-bundle-vandal-7/install.sh'`. Checked as the user:

- All files in `MANIFEST` match, except the polkit rule (only root can read
  it). Helper, `greeter-start`, patched copies, wrapper and `PACKAGES` equal
  the bundle byte for byte.
- Greeter KWin drop-in sets `XDG_CONFIG_DIRS` to the bundle directory, whose
  `kwinrc` has `scaleEnabled=false`. Test drop-in
  `81-no-open-animation.conf` and `/usr/local/lib/logout-holder-test` gone.
- Every package in `PACKAGES` installed at that version; `ldd -r` on the
  copies reports nothing missing.
- DrKonqi socket drop-in in place; wallpaper fallback is the theme's program;
  greeter user manager inactive.

### Holder v7: animation setting and package guard, VM (92ce937)

Helper and patched programs are byte-identical to v6. Changes:

1. No window-open animation on the greeter, set by the bundle
   (`/usr/local/lib/logout-holder/xdg/kwinrc` through the greeter KWin
   drop-in). The installer accepts the unchanged `greeter-animation-test.sh`
   files and removes them after a successful install.
2. `PACKAGES` was a fixed list of 5, while the copies link 39 packages that
   are Qt or use Qt. `bundle.sh` now derives it from the libraries that
   supply private symbols, plus `kwin`, `plasma-login-manager`,
   `qt6-wayland`. On Vandal: `kdecoration` 6.8.3-1.1, `kwin` 6.8.3-3.1,
   `kwindowsystem` 6.32.0-1.1, `plasma-login-manager` 6.8.3-1, `qt6-base`,
   `qt6-declarative`, `qt6-wayland` 6.12.1-1.1. `greeter-start` also runs
   `ldd -r` on the copy (48 ms KWin, 30 ms wallpaper) and starts the stock
   program if a library or symbol is missing. The installer refuses such a
   bundle.

VM runs in `holder7-batch/` (Vandal theme, same scripts as the Vandal
bundle). All passed; host load at most 10.2 after each run. "Upgrade" = v6
plus test files installed, then v6 removed and v7 installed from the desktop.

| Run | Start | Result |
| --- | --- | --- |
| `upgrade-cold`, `upgrade-warm` | upgrade, animations forced | test files gone; greeter loaded 28 effects, no `scale`; backdrop painted; no scaled or dimmed copy and no black between desktop and greeter; sign-in passed |
| `fresh-cold` | v7 only, animations forced | same |
| `upgrade-reboot`, `upgrade-halt` | upgrade | "Restarting system", "Power down" |
| `broken-library` | library name changed in the KWin copy | stock KWin, logged `libQt6Gone.so.6 => not found`; black before greeter; sign-in passed |
| `broken-symbol` | symbol name changed in the wallpaper copy | stock wallpaper program, logged `undefined symbol`; sign-in passed |
| `stale` | a listed package not installed | both stock; black before greeter; sign-in passed |
| `restore` | upgrade, then v7 `--restore` | no backdrop at next greeter; sign-in passed |
| `recover` | failed sign-in, slow greeter stop | greeter came back; second sign-in passed |

- In the three runs with captures and good copies, the greeter follows the
  desktop directly. Black captures after the password: 10–17 (v6 controls:
  12–13).
- On Vandal, as the user, nothing installed: `greeter-start` with redirected
  paths ran the good copies and chose stock for a missing library, a missing
  symbol (in `libkwin` and in the wallpaper copy) and a changed package. The
  installer's load check passed the Vandal bundle and refused both broken
  ones.
- Limits: the VM has no pacman database, so `PACKAGES` is empty there except
  in `stale`. The derivation ran on Vandal only.
- Bundle: `holder-bundle-vandal-7`.

### Vandal: scale-in removed live, 13:29–13:36 (99ca30d)

- `sudo bash greeter-animation-test.sh apply` at 13:29:41 (the first
  password prompt had timed out). Greeter user manager inactive.
- Logout 13:32: session stopped normally (crash report refused), greeter
  through the wrapper, backdrop first paint 13:32:14.85, connected 15.19,
  sign-in 13:32:18.59 reached session KWin. The journal does not show which
  effects the greeter loaded.
- Logouts 13:34:43 and 13:35:39, each with sign-in; no `Failed to enqueue`
  or `destructive`. User (about 13:36): "logout and login looks correct, no
  scaling or dimm".
- The test files stayed installed until v7.

### Greeter scale-in reproduced and fixed, VM (99ca30d)

KWin turns script animations off on a software renderer, so the llvmpipe
greeter never ran `scale` (11 built-in effects loaded). With
`KWIN_EFFECTS_FORCE_ANIMATIONS=1` it loads 29 effects including `scale`;
with no-scale on top, 28. Fix: drop-in
`plasma-login-kwin_wayland.service.d/81-no-open-animation.conf` setting
`XDG_CONFIG_DIRS=/usr/local/lib/logout-holder-test/xdg:%E/kdedefaults:/etc/xdg`
(keeps the starter's `kdedefaults`), `kwinrc` there with
`[Plugins] scaleEnabled=false`. Runs in `anim-batch/` (v6 VM bundle, Vandal
theme):

| Run | Greeter after logout | Result |
| --- | --- | --- |
| `ctl-forced-1` (no fix) | dimmed, scaled copy over the backdrop (`frame-037`), UI grows from the centre into place (`038`–`039`) | passed |
| `noscale-forced-1`, `fix-cold`, `fix-warm` | no scaled or ghosted frame; UI at full size and opacity (one capture each shows the clock half drawn) | sign-in passed |
| `ctl-cold` (no fix) | same scaled and dimmed frames (`frame-035`–`038`) | sign-in passed |
| `ctl-forced-2` | greeter not shown within the capture window (host load) | no sign-in |
| `noscale-forced-2`, `fix-reboot`, `fix-halt` | first sign-in not ready in 40 s (host load above 20), before the change was installed | not a test |
| `fix-reboot-2`, `fix-halt-2` | restart, shutdown with the fix | "Restarting system", "Power down" |

In control and fix alike, the sign-in UI fades out about 0.4 s after
appearing until a key is pressed. That is the greeter's own `uiVisible`
behaviour.

### Vandal: first logout with v6, 12:46 (99ca30d)

- Reboot 12:43 after a package update (kernel, pipewire; `PACKAGES` still
  matched). Logout 12:46:49 and sign-in 12:47:00 worked.
- Greeter command `/usr/local/bin/startplasma-login-wayland`; the wrapper
  logged nothing (no pending stop).
- DrKonqi socket closed 12:46:49.72; Beeper's crash at .77 refused
  (`"Connection refused"`); session stopped normally.
- User reports: (1) the greeter dims, then the sign-in UI scales up from the
  centre and slides into place; only the end is visible. Seen before v6
  ("not top importance"); user thinks a later greeter change started it.
  (2) One dark frame between greeter and desktop at sign-in.

Read-only checks:

- Greeter theme unchanged since 2026-11-20 (binary
  `/usr/local/lib/plasmalogin-theme/plasma-login-greeter` and QML). The 11-26
  anchor fix (vandal-lock-screen `994cb5e`) changed only
  `/usr/share/vandal-login-branding/…/SessionManagementScreen.qml`. The
  greeter imports `org.kde.breeze.components` from `plasma-workspace`
  6.8.3-1.1 (unaltered, `pacman -Qkk`) and takes only logo and fonts from
  `vandal-login-branding`.
- Greeter KWin has no configuration of its own, so KWin's default
  window-open animation applies. Before the holder the screen was black until
  the greeter drew; now the backdrop shows first, so the animation is visible
  (hypothesis then; confirmed by the VM entry above).
- Last smooth sign-in: plasma-login-handoff `dcb7adf` (11-25), before any
  holder bundle. At 12:47: `Jumping to VT 2` .470, session KWin .690.
- plasma-lock-handoff session reports: no scale-in at boot, only after
  logout. Greeter connected 0.33 s after backdrop first paint after logout,
  1.5 s at boot.
- VM `greeter-recovery/theme-cold-1` (about one capture per 47 ms) showed no
  scale-in: UI appears whole (`frame-036` → `037`), fades out about 0.3 s
  later (`044`–`046`), back in (`055`–`059`). The fade follows `uiVisible`
  (`GreeterState.activeWindow === Window.window` in `Main.qml`). The guest
  renderer was not logged.

### Vandal: v6 installed, 12:34:59 (88f7b46)

User ran v5 `install.sh --restore`, then v6 `install.sh`; both done within
0.4 s; the `PATH` check accepted the machine. The installed wrapper equals
`login-screen-start`; all `MANIFEST` files match except the polkit rule
(root only). DrKonqi drop-in in place. The greeter running then had been
started by v5.

Install command used:

```bash
cd holder
old=~/.cache/plasma-logout-handoff/holder-bundle-vandal-5
new=~/.cache/plasma-logout-handoff/holder-bundle-vandal-6
BUNDLE_PACKAGES="$(cat $old/PACKAGES)" bash bundle.sh $new $old/greeter/plasma-login-wallpaper
sudo bash $old/install.sh --restore && sudo bash $new/install.sh
```

`backdrop/build` KWin matched v5's copy at the time. Read-only pre-check:
v5's pinned packages installed; systemd `PATH`
`/usr/local/sbin:/usr/local/bin:/usr/bin`; `plasmalogin.service` sets no
environment of its own.

### Greeter recovery after a failed sign-in, VM, 11-26/27 (88f7b46)

Goal: the second failure of 11-26 21:01 (restarted greeter refused, black
until reboot). Nothing installed on Vandal.

Method: `LOGOUT_VM_FAILED_RELOGIN` adds a 6 s `graphical-session.target`
stop, logs out, signs in 0.8 s after the greeter connects, so the desktop
start is refused. `stuck` passes if the greeter start is also refused, no
greeter connects within 20 s, no greeter UI process runs and no desktop
appears. `recover` passes if the desktop start is refused exactly once, the
greeter's never, a new greeter connects with a non-black screen, and a second
sign-in after the old stop reaches a desktop with `graphical-session.target`
active. `LOGOUT_VM_SLOW_GREETER_STOP` adds an `ExecStopPost` sleep to the
greeter KWin (in `/etc/systemd/user`; delivery runs use the greeter user's
configuration so the holder can be reinstalled).

All runs use `holder-bundle-vm-5` unless noted. Results in
`greeter-recovery/`; `summary` there has a line per run except
`stock-cold-stuck-1` (earlier lines lack the later columns). Guest: Plasma
6.8.3, Qt 6.12.1, Frameworks 6.32.0, systemd 262.2, same
`plasma-login-manager` 6.8.3-1 package as Vandal.

Packaged starter:

| Runs | Greeter KWin stop | Result |
| --- | --- | --- |
| `stock-cold-stuck-1…5` | as is | stuck 1 of 5 (`-4`) |
| `stock-warm-stuck-1…5` | as is | stuck 0 of 5 |
| `stock-slow1-cold-0…3`, `stock-slow1-warm-1…2` | 1 s slower | stuck 6 of 6; final screen fully black |
| `stock-slow6-cold-1` | 6 s slower | stuck |

Unslowed it is a race: the old greeter KWin stopped 26–38 ms after "Greeter
starting"; in 9 of 10 runs the new starter was not refused; in the
reproduced one it asked 3 ms too early. Vandal 21:01:36: refused 25 ms
before the old KWin finished. With 1 s slowdown it asked about 1 s too early
every time.

Compiled greeter patch
([patches/startplasma-login-wayland.patch](../patches/startplasma-login-wayland.patch),
`build-greeter-fix.sh`, from tag `v6.8.3` of
`../plasmalogin-theme/upstream`, startkde sources unmodified). The unpatched
build imports the same symbols and libraries as the packaged program; the
patched one differs only as the patch's calls would. Builds used: `build-2/`;
the 11-25 `stop-fix-2` was not used.

| Runs | Greeter KWin stop | Result |
| --- | --- | --- |
| `patch-slow1-cold-1…3`, `patch-slow1-warm-1…2` | 1 s slower | recovered 5 of 5 |
| `patch-cold-1…3`, `patch-warm-1…3` | as is | recovered 6 of 6 |
| `patch-slow6-cold-1` | 6 s slower | **stuck**: starter stops waiting after 4 s |
| `ctl-patch-cold`, `ctl-patch-warm` | normal logout and sign-in | passed |
| `ctl-patch-reboot`, `ctl-patch-halt` | restart, shutdown | "Restarting system", "Power down" |

In all 11 recovered runs the new greeter started 6–8 ms after the old KWin
stopped (packaged, slowed: about 1 s before). Unslowed, the new greeter
connected 0.3 s after the refused desktop start. The slowed runs are the
evidence that the patch matters.

On Vandal, 24 greeter teardowns in six boots (11-26/27) took 59–122 ms from
"Stopped target plasma-login-wayland.target" to greeter KWin stopped, well
inside 4 s. The longest was the 21:01 failure.

Delivered instead: [holder/login-screen-start](../holder/login-screen-start)
wrapper. PLM looks the greeter command up on its `PATH` at each greeter start.
The patch remains the candidate to report upstream.

| | Wrapper | Compiled patch |
| --- | --- | --- |
| Waits | before the new greeter starts | while the old one exits |
| Limit | 100 s | 4 s (PLM allows 5 s) |
| After a package update | stays in use | needs a rebuild; under `PACKAGES` it would fall back to the packaged starter and the black screen could return unnoticed |
| Tested as installed | yes | no (only copied over `/usr/bin` in the guest) |

`holder-bundle-vm-6` = v5 KWin, wallpaper and helper plus new installer and
wrapper.

| Runs | Installation | Result |
| --- | --- | --- |
| `upgrade-slow1-cold-1…3`, `upgrade-slow1-warm-1…2` | v5 → v6 from desktop, 1 s slower | recovered 5 of 5 |
| `upgrade-cold-1…3` | v5 → v6, as is | recovered 3 of 3 |
| `wrapper-slow6-cold-1…2` | v6, 6 s slower | recovered 2 of 2 |
| `theme-slow1-cold-1`, `theme-cold-1` | v6, Vandal theme | recovered 2 of 2 |
| `stale-slow1-cold-1` | v6, changed package simulated | recovered; packaged KWin ran (no backdrop), wrapper stayed in use |
| `restore-slow1-cold-1`, `upgrade-restore-slow1-cold-1` | v6 or v5 → v6, then `--restore` | stuck, as packaged; greeter from `/usr/bin` again |
| `ctl-upgrade-cold`, `ctl-upgrade-warm`, `ctl-upgrade-theme-cold` | normal logout and sign-in | passed |
| `ctl-upgrade-reboot`, `ctl-upgrade-halt` | restart, shutdown | "Restarting system", "Power down" |

- Recovery runs after an install logged the `/usr/local/bin` greeter
  command; none logged a failed stop.
- Median "Starting Wayland user session" → greeter KWin start after logout:
  34 ms packaged (cold, 10 runs), 48 ms wrapper (cold, 6 runs).
- Normal-logout controls with the holder (patched starter and wrapper): no
  black capture between logout and greeter; 12–13 after the password, as in
  `ctl-v5-cold`.
- `ctl-v5-cold`, and without a holder `ctl-plain-cold` and
  `ctl-stockfix-warm`, still passed.
- After a last `monitor.py` change (escaping line breaks in new commands),
  nine runs across the new modes were repeated as `final-*`; all passed.
- Limits: failure injected by slow stopping units, not the DrKonqi chain;
  second sign-in waited for the old stop (sooner not tested, expected to fail
  again); no message about the failed sign-in; assumes one seat; the
  installer's two new refusals not exercised (the `PATH` test only on sample
  strings), nor the wrapper's failed or timed-out stop;
  `interrupted-wrapper-slow6-cold-1` was cut off with the session, repeated,
  not counted.

### DrKonqi bug draft and unit-only reproduction (b95ce46, 72a9672, 7a473a4)

Draft and results: [drkonqi-report/](../drkonqi-report/README.md). Not
submitted. Unit-only reproduction, 3 runs: `stock` and `after` refuse the next
start; `no-requisite`, `socket-partof` and `irreversible` allow it.

An earlier claim that logout crashes are not lost and cost only a failed
processor unit was too optimistic. Journal since 11-26 21:00: 18 refused
reports (17 before the drop-in), all picked up at later sign-ins (22:15:22,
09:49:01), none with KCrash metadata, none notified; cores kept. See
[Crash reports at logout](../drkonqi-report/README.md#crash-reports-at-logout).

## 2026-11-26

### Vandal: Shut Down from the Plasma menu, 22:56:49 (7a473a4)

v5 and DrKonqi drop-in. Helper armed, copied display settings, did not
switch; `graphical-session.target` stopped normally; PC powered off. First
live check of Shutdown (VM only before).

### Vandal: first logout with the DrKonqi drop-in, 22:14 (07b94ea)

- Beeper dumped core (SIGTRAP), but the socket was already closed
  (22:14:13.584, 0.1 ms after `plasma-workspace-wayland.target` stopped; it
  used to close after the Plasma workspace target). The system processor
  logged `"Connection refused"`; no launcher started.
- `Stopped target Current graphical user session` 1 ms after Beeper stopped;
  no `Failed to enqueue`, no conflicting transaction.
- Sign-in 6.4 s after the session closed reached a desktop; socket listening
  again 22:14:22.
- One logout, no slow app: the trigger is gone; this does not prove the
  2-in-21 race cannot happen.
- The user reported Beeper's own crash to Beeper (in-app). A researcher found
  Chromium issue 580525223 (marked fixed upstream, November 2026): the browser
  process sits in its own scope, so stopping the launcher unit kills its zygote
  and GPU helpers and it hits "GPU process isn't usable". The journal's
  `app-Beeper-….scope` fits. The issue page could not be opened here.
- Unrelated: 2.4 s from greeter session start to its first user unit
  (22:14:15.50 → 17.90), 0.4 s at 21:01. Matches the
  `/etc/profile.d/nvidia-rtd3-workaround.sh` `lspci` delay with the GPU
  suspended. The holder kept the picture (backdrop first paint 22:14:18.58).

### Vandal: DrKonqi drop-in installed, 22:13 (07b94ea)

As the user, no sudo:
`~/.config/systemd/user/drkonqi-coredump-launcher.socket.d/stop-with-graphical-session.conf`
(`[Unit]` / `PartOf=graphical-session.target`), `daemon-reload`. Socket
`PartOf` then `plasma-core.target graphical-session.target`, still active.

### DrKonqi cause reproduced in the VM, `crash-batch.i7moFf` (07b94ea)

`LOGOUT_VM_CRASH_REPORT=stock|fixed` installs renamed copies of the two
coredump-launcher units (guest has no DrKonqi). The service activates the
portal, a11y bus and (40 times, 0.1 s apart) portal-kde, like the crash loop
on Vandal. A 2 s slow user unit stands in for NetBird. A root job sends the
"crash report" while it stops, logs pending jobs, and 3 s later the target
state. Re-login 5 s after greeter connect. Holder v5, cold greeter.

| Run | Report | `graphical-session.target` | Re-login |
| --- | --- | --- | --- |
| stock-1…4 | accepted with slow unit, `plasma-workspace.target` and target stop pending; `plasma-workspace.target` stopped < 0.1 ms after the report's unit was created, without the target stopping first | stock-1, -3, -4: not stopped during logout; stock-4 still `active`, no jobs, 3 s after the report. stock-2 (no portal-kde loop): stopped 1.7 s later, once the portal had started | passed |
| fixed-1, fixed-2 | refused: socket closed 0.6 s after the logout request | stopped when the slow unit finished (2.0 s) | passed |
| control-1 (no report) | — | stopped when the slow unit finished | passed |
| fixed-reboot, fixed-halt | — | — | guest went down |

Runs 1–2 predate the portal-kde loop and state log; stock-3 has the loop
only. The final failure did not reproduce: sign-in worked even with the stuck
target (on Vandal the re-activated portals were still running). Whether the
drop-in prevents the black screen on Vandal can only be shown there.

### Vandal: failed re-login after logout, 21:01 (07b94ea)

Holder v5. Sign-in about 8 s after logout: password accepted, black screen,
reboot needed. `journalctl -b -1`, boot `8e3c1363…`. Nothing changed during
the analysis.

| Time | Event |
| --- | --- |
| 21:01:28.24 | `plasma-workspace-wayland.target` stops; stop job for `graphical-session.target` queued behind apps ordered after it |
| 21:01:28.28 | holder switches to VT 1 (desktop KWin still has the card) |
| 21:01:28.25–30.62 | NetBird takes 2.4 s to stop (17 ms in the working 20:43 logout) |
| 21:01:29.73 | Beeper main process exits with core dump (SIGTRAP) |
| 21:01:30.046 | `plasma-workspace.target` stops without `graphical-session.target` stopping first |
| 21:01:30.047 | `drkonqi-coredump-launcher@…` starts for the crash |
| 21:01:30.63–30.75 | portal, document portal, a11y bus, `plasma-xdg-desktop-portal-kde` activated again |
| 21:01:30.766 | `graphical-session.target: Failed to enqueue stop job, ignoring: … destructive (plasma-xdg-desktop-portal-kde.service has 'start' job queued …)` |
| 21:01:30.79 | desktop KWin stops, session closes; portal-kde crash-loops until `start-limit-hit` |
| 21:01:31.70 | greeter KWin: `logout-holder backdrop: first paint` |
| 21:01:36.55 | new login: `startplasma-wayland` reloads the user manager; stop of the target queued |
| 21:01:36.65 | `Transaction for plasma-workspace-wayland.target/start is destructive (graphical-session.target has 'stop' job queued …)`; session ends |
| 21:01:36.76 | restarted greeter: `plasma-login-wayland.target/start is destructive (plasma-login-kwin_wayland.service has 'stop' job queued …)`; black until reboot |

- Same signature at 17:14:49 (v3, Restart from the menu): JetBrains Toolbox
  took 4 s to stop, Beeper crashed, `plasma-workspace.target` stopped 1 ms
  before the launcher started, target never stopped.
- 21 Plasma exits that day (boots −5 to 0): 19 stopped the target within
  0.2 s of Beeper stopping, 2 never did. Beeper dumped core at 18. The crash
  is routine; the difference is a slow app keeping the stop job pending.
- Explanation (journal and systemd job rules, not reproduced at this point):
  `drkonqi-coredump-launcher@.service` (6.8.3) has
  `Requisite=graphical-session.target` and its socket starts it in `replace`
  mode. The added "verify active" job cancels the pending stop, so
  `plasma-workspace.target` stops at once. The launcher activates portals and
  a11y bus (`PartOf=` the target). Their queued starts make the later
  `StopWhenUnneeded` stop destructive; systemd ignores it. The target stays
  active until the next login's reload queues its stop, which collides with
  the new session start. It was the only unit on Vandal with that
  `Requisite=`.
- Independent of the holder (17:14 was a restart, no VT involved), but the
  holder makes a fast re-login easy. The 11-25 source teardown patch would
  not have helped: its `--job-mode=fail` stop is refused once start jobs are
  queued. The greeter half of it addresses the second failure.

### Holder v4 and v5 (0eba4ea)

**Restart failure with v3, 17:14.** Plasma runs the shutdown hook for logout,
shutdown and restart alike (`runShutdownScripts()`,
`startkde/plasma-shutdown/shutdown.cpp`); only afterwards does
`logoutComplete()` stop `graphical-session.target` and then quit or call
logind `Reboot()`/`PowerOff()`. v1–v3 switched VT inside the hook. Restart
then failed: the desktop session was no longer in front, polkit treated
`org.freedesktop.login1.reboot` as `allow_inactive` (`auth_admin_keep`), the
password dialog had no screen, polkit logged "Operator of unix-session:18
FAILED to authenticate". Desktop stopped, no greeter, helper gave up after
15 s, text console. Shutdown fails the same way. VM `v3-reboot-*`
(`LOGOUT_VM_SHUTDOWN=reboot`) reproduced it: guest running 25 s later.

**v4** lets the hook return at once and switches only after plasma-shutdown
exits (wait up to 10 s) with no shutdown under way.

- VM `v4-batch.Qq8mgE`: restart and power-off (stock, restart also themed)
  went through; logout stock and themed: no black, re-login 2/2, switch
  11–13 ms after arming, desktop KWin still had the card.
- Vandal: logout 17:32:41 switched 35 ms after arming with KWin still on the
  card, backdrop painted, keyboard sign-in worked. Restart from the menu
  17:33:07 armed, did not switch, restarted normally.

**v5** copies `kwinoutputconfig.json` to the greeter at every Plasma exit.

- VM `v5b-batch.ArRYxo`, `v5c-batch.NIe0Wb`: copied 5–23 ms after arming,
  identical file, correct owner and mode, backup made, re-login 3/3, no
  logout black; restart and power-off copied after 5 ms and went down.
- A first version expected a JSON object (KWin writes a list); the VM caught
  it and the copy was skipped harmlessly.

### Holder v3: package guard (ab6c4c2)

`holder-bundle-vandal-3`: greeter units start `greeter-start`, which runs the
copies only while every package in `PACKAGES` (`kwin`, `qt6-base`,
`qt6-declarative`, `qt6-wayland`, `plasma-login-manager`) matches, else
`/usr/bin/kwin_wayland` and the previous wallpaper command. `LD_LIBRARY_PATH`
moved into the launcher so stock never sees it. Logic tested on Vandal with a
copy that prints instead of exec (current, stale, empty list).

VM: themed `v3-batch.HUQcYT` `t-1`, `t-2` and stock `v3b-batch.uBqClB` `s-1`,
`s-2`: no black at logout, re-login 4/4 (vmsum's black block in `s-*` is
after the password). Stale package `st-1`: stock KWin, no "first paint",
about 5 black captures, sign-in passed. The first `s-*` attempt failed in
setup: an unmatched glob under `pipefail` aborted the installer (fixed with
`nullglob`).

### Vandal: holder host trials, v1 and v2 (ab6c4c2)

Acer X28 on `HDMI-A-1` 3840x2160 at 60 Hz, lid closed, eDP-1 disabled.

**Trial 1, 15:51 (v1, `holder-bundle-vandal`, installed 15:49; filmed
`video_2026-11-26_15-52-47.mp4`, 30 fps, boot `1e8300cb…`).** Video zero from
the logout prompt closing (8.73 s ↔ 6306.6 s, ±0.1 s).

| Monotonic | Event | On film |
| ---: | --- | --- |
| 6306.71 | helper holds card1 from VT 3, switches to VT 1 | last desktop frame **including a terminal** (Alacritty closed 50 ms before; closing animation) |
| 6308.53 | greeter session `c3` | frozen frame |
| 6311.10 / .21 | greeter KWin (copy) starts / has the card | frozen until ≈6311.8 |
| ≈6311.8–6313.3 | | **≈1.5 s pure black** |
| 6312.34 | greeter Connect | |
| 6313.25 | helper exits | wallpaper and clock, **no password form** |
| 6312–6335 | user presses keys | nothing changes |
| 6335.67–6341.39 | suspend and resume (trigger not logged; BT wake) | |
| 6347.50 | sign-in succeeds | |

- Dead keys, cause (source and bug report, not re-tested then): the KWin copy
  was upstream v6.8.3; distro `kwin 6.8.3-3.1` has two backports: `47f03822`
  for [KDE 528936](https://bugs.kde.org/528936) (libinput switch events
  processed before KWin's filters, lid state lost) and `19404161` for KDE
  528824 (crash at logout/login), from Arch PKGBUILD 6.8.3-2/-3. Without the
  lid state, keyboard focus goes to the dark built-in screen. Fits: three
  "Input method is trying to show itself but without a context" lines (stock:
  one) and recovery after resume. The `GreeterState.qml:98` TypeError also
  appears with stock KWin at boot and in a working logout, so it is not the
  cause.
- Black 1.5 s, cause open then: backdrop not drawn or monitor re-sync. Film
  cannot tell (same image). With the lid bug KWin would also try to light
  eDP-1, which on i915 may force a full modeset. Settings differed: desktop
  `Broadcast RGB` Limited, `max bpc` 8; greeter defaults Automatic and 10.

**v2** (`holder-bundle-vandal-2`): both backports; bundle records
`KWIN_PACKAGE` (`kwin 6.8.3-3.1`) and the installer refuses another; backdrop
logs "first paint" and "desktop window covers it, stopped" once each (headless
smoke on Vandal with the 4K split image: logged, exit 0); hook calls KWin
`showDesktop(true)` and waits 0.5 s. VM with the Vandal theme
(`LOGOUT_VM_THEME`): v1 `theme-batch.pUUOHz` `th-1…3` and v2
`v2-batch.wMJrmJ` `v2-1…3`: no black at logout, re-login 6/6, "first paint"
in each v2 run (vmsum "partial" is the dark part of the split image). Theme
without helper (`tc-1`, `tc-2`): 18 black captures. The VM has no lid and no
open windows.

**Trial 2, ≈16:20** (journal only). Prompt closed 8183.41, Alacritty 8184.47,
switch 8185.02 (≈0.55 s, the
show-desktop wait), greeter session 8186.88, KWin start / card 8187.10 / .22,
first paint 8187.72, Connect 8187.98 (one input-method line, as stock),
Login 8192.14. Frozen frame → backdrop ≈2.7 s. Sign-in worked with the lid
closed, but the user touched the mouse, which activates the greeter window
(`Main.qml` `onPositionChanged`),
so keyboard focus was not yet proven.

**Trial 3, 16:25** (keyboard only, `video_2026-11-26_16-25-09.mp4`; prompt
gone 7.7 s ↔ 8298.38). Switch 8298.97, KWin card 8303.37, first paint
8303.86, Connect 8304.13, helper exit 8305.40, Login 8311.99.

- No terminal in the kept frame (show-desktop works).
- **Keyboard-only sign-in worked** with the lid closed: backport confirmed.
- **≈2.5 s black** (13.3–15.8 s ↔ ≈8304.0–8306.5), starting at the greeter's
  first frame, which already had the backdrop: read as a full modeset and
  monitor re-sync.

**Trial 4, 16:31** after `sudo bash holder/sync-greeter-outputs.sh`. Greeter
had `HDMI-A-1` rgbRange Automatic, maxBitsPerColor 0 (KWin asks 10), profile
sRGB; desktop Limited, 8, EDID. `video_2026-11-26_16-32-09.mp4`: desktop
wallpaper → themed greeter at 10.7 s in one step, **no dark frame** (the
brightness drop is the darker split image, then camera adjustment). Switch
8671.04, card 8675.63, first paint 8676.12, Connect 8676.46, Login 8681.46
(keyboard). Sign-in showed ≈2 dark frames (≈0.07 s). First time the goal was
met; one run.

### First installable holder, VM, `holder-batch.OEnXt1` (ab6c4c2)

Hook in `/etc/xdg/plasma-workspace/shutdown/` (run synchronously before
`StopUnit graphical-session.target`), polkit rule for `start` only, helper
keeps the card open and switches VT, patched greeter KWin and wallpaper.
Desktop compositor stock.

| Run | Logout black / partial | Re-login |
| --- | --- | --- |
| `h-3` (with `cap_sys_nice`) | 5 / 1 | passed |
| `h-4` … `h-9` | **0 / 0 in all six** | 6/6 |

- By eye (`h-4`, `h-5`, `h-9`): desktop with panel, same wallpaper without
  panel, greeter. Later black is after the password.
- `h-3`: `setcap cap_sys_nice` makes the loader ignore `LD_LIBRARY_PATH`, so
  stock `libkwin` loaded; the installer no longer sets it.
- `h-1`, `h-2` failed in setup (installer: `pacman -Q` in the VM, missing
  drop-in directory).
- On Vandal the patched KWin started headless (`--virtual`, private bus) and
  exited 0 with the same warnings as stock.

### Relay VM: switch only, no painting, `switch-batch.Umt8ha` (ab6c4c2)

Switch to VT 1 in graphics mode; never take DRM master or paint. "Greeter
changes" = KWin backdrop and transparent wallpaper window.

| Card held open | Greeter changes | Black captures per run | Re-login |
| --- | --- | --- | --- |
| yes (`switch`) | yes | 0, 0, 0, 0, 0, 0 (`full-*`) | 6/6 |
| no (`switch-nocard`) | yes | 9, 9, 8, 8, 9, 8 (`nocard/full-*`) | 6/6 |
| yes, alternating rerun | yes | 0, 0, 0 (`alt/switch/*`) | 3/3 |
| no, alternating rerun | yes | 7, 8, 10 (`alt/switch-nocard/*`) | 3/3 |
| yes | no | 6, 6, 6 (`stock-4..6`) | 3/3 |

- Card open: the last desktop frame, panel included, stayed to the greeter's
  first frame, 0.45–0.61 s from the trigger. With a stock greeter, 0.2–0.34 s
  of black followed.
- **The open file is required.** Without it the plane switched to `[fbcon]`
  about 0.11–0.13 s after the VT switch. Linux 7.0 `drm_release()` calls
  `drm_lastclose()` on the last close, restoring the console (inferred from
  source and A/B, not traced). `drm_fbdev_client_restore()` commits unforced,
  yielding to a master and ignoring KD mode. VM kernel 7.3.5-cachyos.
- Second pass counting near-black pixels in every capture: no capture over
  2 % black in any card-open run with greeter changes, nor in
  `clear-batch.Y2zacD`. The earlier `vmsum.py` missed partly black captures
  (one in `stock-4`); it now marks any over 2 % as partial. `[fbcon]` reached
  the plane in every card-closed run and no card-open run.
- `stock-1..3` failed in setup before logout (missing unit directory, fixed).
- Not tested: effect of the logout confirmation screen on the kept frame
  (logout over D-Bus), a missing greeter in this mode, physical GPUs.

### Relay VM: image relay (8c546ae, ab6c4c2)

Design (accepted for a VM prototype, later simplified to switch-only): keep a
trusted picture on screen in three stages: (1) the departing compositor keeps
painting the wallpaper; (2) a privileged relay takes DRM master when no one
has it, shows a prepared picture, drops master, repeats if the console
returns; (3) the greeter compositor paints the same picture until its UI is
ready. Rules: never take master while the greeter compositor exists (logind
would fail device activation), deadline, restore the console if nothing takes
over, no change to authentication or seat. Context: Vandal had gone from
about 5.5 s to 1.6 s of black (one run each).

**Gap stage alone** (`relay-batch.ic3YRW`, interleaved, orange picture; first
dark stretch):

| Condition | Black | Partly dark | Relay picture | Re-login |
| --- | --- | --- | --- | --- |
| Stock, 3 runs | 15, 17, 17 | 2, 0, 0 | none | 3/3 |
| Relay, 3 runs | 7, 7, 8 | 1, 2, 2 | 6, 6, 6 | 3/3 |
| Relay + greeter VT preset to graphics | 7, 7, 6 | 0, 1, 1 | 7, 6, 7 | 3/3 |

A further pair (`relay-ab-*-1795691939`) agreed: desktop KWin → relay →
fbcon → relay → fbcon → relay → greeter KWin. The relay painted 2–3 times per
logout, holding master 1–40 ms. The VT preset had no clear benefit and was
removed. Nine logouts cannot rule out the master race.

**All stages** (KWin backdrop patch, which also carries the login project's
marker and startup wallpaper; relay orange, backdrop cyan):

| Condition (`backdrop-smoke-*`, `backdrop-batch.qw5Vgp`) | Black | Partial | Re-login |
| --- | --- | --- | --- |
| Stock (above) | 15, 17, 17 | 2, 0, 0 | 3/3 |
| Backdrop only | 10, 10 | 0, 0 | 2/2 |
| Relay + backdrop | 3, 2, 2, 1 | 0, 1, 2, 2 | 4/4 |

Remaining black: departing desktop as the shell stops (cause not traced); a
console repaint before the relay replaced it; greeter UI drawing on black
before its wallpaper. Some "partial" captures are orange/cyan splits.

**Console switch and transparent wallpaper**:

| Condition | Black | Partial | Re-login |
| --- | --- | --- | --- |
| Hold master (`hold-smoke-*`) | 1 | 1 | 1/1 |
| Console switch (`vt-smoke-*`, `vt-batch.asHsds`) | 1, 0, 1, 1, 0, 0 | 1, 1, 0, 0, 1, 1 | 6/6 |
| + wallpaper window delayed (`ready-*`) | 0, 6 | 0, 0 | 2/2 |
| **+ transparent window** (`clear-batch.Y2zacD`) | **0 in all six** | **0** | 6/6 |

- Holding master does not stop the console: the kernel forces it back when
  its VT returns to text mode.
- `LOGOUT_VM_RELAY=vt`: a user unit's `ExecStop` touches `/tmp/relay-go`
  before plasmashell stops; the relay switches to VT 1 in graphics mode,
  paints, holds master until the greeter compositor appears. No console frame.
  In `vt-4` the shell took 4.1 s to stop and the picture stayed. `vt-2` exited
  2 only because the runner was edited mid-run.
- `plasma-login-wallpaper` cleared to black. Delaying the window fails:
  `TransientImage` loads only once exposed (3 s fallback seen). Fix: window
  transparent, and the backdrop stays 3 s after a desktop window appears.
- `clear-1` and `clear-6` checked by eye: desktop, orange, cyan, greeter.
  Black after the password remains.
- Open at the time, before any physical trial: one real wallpaper in all
  stages; stalled or failed greeter and relay timeout; cancelled logout; relay
  death while holding; who may trigger a root relay (the `/tmp` file is a
  prototype); an event instead of 1 ms polling for the greeter start; the
  backdrop's 3 s limit and direct scanout; multiple outputs and i915.

### Vandal: kept changes, second GPU lookup, after 14:05 (ab6c4c2)

`vandal-keep-handoff.sh` run 14:05, reboot. User reported lock/unlock still
works and asked to keep both changes. `HDMI-A-1` 4K 60 Hz, internal panel
off, so `video=DP-1:…` did not apply. One logout, journal only; not
comparable with the DP-1 runs.

| Interval | |
| --- | ---: |
| Greeter user-manager PAM opened → first target queued | 0.078 s |
| PLM greeter session started → Connect | 3.49 s |
| Desktop KWin ended → Connect | 3.62 s |

Re-login worked; the greeter was no faster. The override worked, but 2.4 s
passed from greeter session start to its first user unit: the greeter's shell
is `nologin`, so `wayland-session` sources `/etc/profile`, and
`/etc/profile.d/nvidia-rtd3-workaround.sh` runs the same `lspci` probe. It
took 2.322 s with the GPU `suspended`, 0.008 s awake. Probably the cause (GPU
state not captured at logout). The earlier 0.99 s and 1.05 s runs probably
found the GPU awake. The keep script does not cover this file.

### Vandal: console mode matching and generator override, filmed (8c546ae)

**Source reading** (upstream kernel v7.3.6, systemd v262; distro patches not
checked): logind's VT restore sets `KD_TEXT`; fbcon then force-restores the
console even while a compositor holds DRM master
(`drm_fb_helper_set_par`). Consistent with the 60 Hz switch while KWin was
still stopping; the trigger was not traced. `video=DP-1:3840x2160@100` marks
the first probed 100 Hz mode, CTA VIC 117 (1188 MHz) for this EDID, ahead of
DisplayID's 906 MHz timing. A search of local pi session logs found no
earlier `video=` trial.

**Console probe** (`vt-mode-probe.sh`): without the parameter, 100 Hz
(1188000) desktop, 60 Hz tty3, 100 Hz back; the console also lit the
lid-closed eDP-1 at 1920x1200. With it (boot 11:36, Limine one-boot edit;
built-in or USB keyboard, Bluetooth does not work there): desktop 4K 100 Hz
clock 1188000; DP-1 stayed 1188000 on tty3 and back; eDP-1 still lit. A rerun
gave the same; an added 1 s delay stopped stray newlines in Alacritty. Blink
inconclusive on a mostly black console. A white fill on tty3 covered only a
top-left rectangle (console 240x75 cells, 1920x1200 with 8x16 font, sized to
eDP-1). The rectangle appeared with no full-screen black transition (by eye),
so disabling eDP-1 was skipped.
(Planned step: `echo off | sudo tee /sys/class/drm/card1-eDP-1/status`,
restore with `detect`.) Pass criterion for the logout: only 1188000 and no
backlight-off phase on film; equal clocks alone do not prove i915 skipped a
full modeset.

A follow-up idea from the login project: paint the wallpaper in the greeter
KWin's first frames (`physical/kwin-6.8.3-on-lock-handoff.patch`). It was
untested in a greeter (`--no-lockscreen`, readable by `plasmalogin`), and the
marker suggested it covers only the tail. The holder backdrop replaced it.

**Mode matched, filmed** (`video_2026-11-26_11-57-30.mp4` with live
`/proc/uptime`; zero ≈1216.45 s ±0.2 s; no generator override;
`vandal-modematch.y2QmY5/`). Sampler: DP-1, pipe B, 1188000 on desktop VT,
greeter VT (1228.62) and new session VT (1236.59); no other state.

| Clip | Boot (≈) | Observation |
| ---: | ---: | --- |
| 9.19 s | 1225.64 | wallpaper goes black as the shell stops; cursor visible |
| | 1225.99 | desktop KWin stopped |
| 9.3–9.5 s | 1225.8–.9 | brightens to a blurred pattern, which holds |
| | 1228.53 | greeter user manager started (2.44 s); jump to VT 1 |
| 13.0 s | 1229.45 | cursor on black; Connect 1229.46 |
| 13.2 s | 1229.65 | greeter wallpaper |

About **4 s of black** (KWin end → Connect 3.48 s). The blurred pattern also
shows in the brightened first black frame, so it is read as camera exposure
on reflections; the user said it was pure dark. Stock clip
`video_2026-11-25_15-20-25.mp4` mean luma:
about 32 (13.9–15.8 s) → 63 → 30 (17.5–19.4 s) with sharp steps. Matched: 26
for 0.15 s, rise over 0.2 s, steady 66–67 until the greeter with one dip to
59. No backlight-off phase apparent; one run each, framing differs; says
nothing about backlight state or link training. New session on tty7, gettys
on tty2–6. Beeper dumped core before the black began.

**Both changes, filmed** (same boot, one-logout greeter generator override
added; `video_2026-11-26_12-07-08.mp4`; no sampler or clock; zero ≈1782.9 s
from the prompt dismissal; `vandal-combined.6ad2c2rf/`). Shell stopped
1801.61 / black at clip 18.70 s; KWin ended 1801.92; greeter user manager
started in 65 ms; Connect 1802.97; wallpaper 20.30 s; desktop after sign-in
≈31 s.

| One run each | Stock film (11-25) | Mode matched | Both |
| --- | ---: | ---: | ---: |
| Black on film | ≈5.5 s | ≈4.0 s | **≈1.6 s** |
| KWin end → Connect | not compared | 3.48 s | 1.05 s |

One dark level after the camera settles, room reflections visible, no
backlight-off phase. Mode not sampled. Override and staging file removed.
Sign-in at 1810.63 (8.7 s after KWin ended) reused the desktop user manager;
KWin, shell, ksmserver active, no failed units. One quick re-login, not
coverage of the race. Lock/unlock not tested. Beeper dumped core again.

### Vandal: RTD3 workaround files disabled, one logout (57b9466, 22d02ff, a71b256)

`vandal-rtd3-cleanup-trial.sh` moved both files aside.

| Interval | Stock | Fast probe, Mesa EGL kept | Both files disabled |
| --- | ---: | ---: | ---: |
| PAM opened → first target queued | 2.348 s | 0.058 s | 0.061 s |
| PLM session started → Connect | 0.810 s | 0.840 s | 3.458 s |
| KWin ended → Connect | 3.237 s | 0.987 s | 3.588 s |

- Not faster overall: greeter KWin took 2.94 s from Starting to Started;
  reason not established.
- New desktop session, locker ran and unlocked, NVIDIA `suspended` /
  `D3cold`. The desktop reused its user manager, which still had the Mesa EGL
  setting, so idle GPU behaviour and a fresh login without the workaround
  were not validated. No video. `vandal-rtd3-cleanup.w4pqL3/`.
- Decision: keep the original files. Only the fast probe with Mesa EGL kept
  was faster.
- The rollback timer fired but restored nothing: systemd expanded the inline
  shell's `$` expressions. Backups survived; manual `--restore` restored
  files, owners and modes. Script now passes `--expand-environment=no`,
  verified with a transient timer on temporary files.

### Vandal: greeter-only generator, one logout (da85952, 61f4795, 207bfba)

`vandal-greeter-generator-trial.sh`: runtime override for the greeter UID
only, others delegated to the installed probe. Probe 2.286 s standalone,
sysfs version 2 ms, same Mesa EGL output.

| Interval | Recent stock | Override |
| --- | ---: | ---: |
| PAM opened → first target queued | 2.348 s | 0.058 s |
| KWin ended → Connect | 3.237 s | 0.987 s |

Re-login worked; the timer removed override and staging file without
restarting PLM. One run; GPU state not captured before, so not a controlled
cold repeat; Connect is not first visible frame; not filmed, no immediate
re-login or lock test. It supports the cold PCI probe as a main cause of the
greeter delay. `vandal-generator.XyZwIj/`.

Upstream: CachyOS [replaced the probe](https://github.com/CachyOS/chwd/pull/282)
and [removed the workaround](https://github.com/CachyOS/chwd/pull/283).
`chwd 1.25.0-1`'s profile no longer references it, but
`/usr/lib/systemd/user-environment-generators/20-nvidia-rtd3-workaround` and
`/etc/profile.d/nvidia-rtd3-workaround.sh` remain, owned by no package: local
leftovers, no upstream patch needed.

## 2026-11-25

### loki: stock X11 with framebuffer attribution, 23:40 (88d7b1c, 8054180)

`video_2026-11-25_23-40-25.mp4`, `loki-fb.9WI2iP/`. Cues at clip 11 and 13 s
read 22493.29 and 22495.29; zero ≈22482.3 s.

| Clip (10 samples/s) | Panel |
| --- | --- |
| 17.6–19.0 s | apparently black |
| 19.1–24.6 s | dim visible field |
| 24.7–26.2 s | apparently black |
| ≈26.4 s | greeter artwork |

- Last sample before the gap (22499.92): DP-3 active, 4K 144 Hz at
  1328.800 MHz, KWin buffers. The next blocked from 22500.03 to 22506.17 and
  returned plane 64 on FB 854 `[fbcon]` at 4K 60 Hz (533.500 MHz), CRTC
  active on tty5. Two NVIDIA flip-event timeouts inside the blocked read.
  Console buffer and 60 Hz were there before Xorg launched (22506.23); the
  change cannot be timed inside the read, nor tied to a black interval or
  link retrain.
- 22507.13 (clip ≈24.8 s) tty1 still on console scanout; detach and DPMS off
  22507.15–.18, during the **second** dark interval. Connect 22508.11,
  artwork later. New Wayland session on re-login.
- This trace is lengthened by timeouts; do not generalize to the 23:31 run.
- Draft NVIDIA report (cf53c35): [NVIDIA-REPORT.md](../NVIDIA-REPORT.md).

### loki: stock X11 logout with filmed uptime, 23:31 (bf7522b, 619dbdc, 271d80a)

`video_2026-11-25_23-31-33.mp4` shows `/proc/uptime`; zero ≈21961.6 s (few
tenths; 0.2 s display cadence). Sampler uptime used (one journal line arrived
≈0.10 s late). Second sampler invocation. `loki-sync.MmjqHU/`.

| Boot s | Observation |
| ---: | --- |
| 21976.16 | tty5, CRTC active, DPMS On; refresh 144 → 60 Hz |
| ≈21976.2 | panel apparently black (clip ≈14.6 s) |
| 21976.27–.29 | desktop KWin ends; SDDM starts Xorg on tty1 |
| 21977.18–.21 | tty1 active at 60 Hz, then detached, DPMS Off |
| 21978.046 | greeter Connect; clip still dark |
| ≈21979.2 | greeter artwork (clip ≈17.6 s) |
| 21992.47 | sign-in starts a new Wayland session |

- ≈3 s from black to artwork. Black starts ≈1 s **before** the detach, so the
  detach cannot explain the whole gap. Onset is near the refresh change and
  teardown; neither established as cause. No link-training or signal data.
- `refresh.log`: both 23:31 runs reached 60 Hz on tty5 before Xorg launched.
  The unfilmed one had two head-0 flip-event timeouts and a warning during
  KWin teardown (60 Hz sample began 21871.99, returned 21878.14). The filmed
  one had none.
- fb0 is `nvidia-drmdrmfb`. The
  [NVIDIA 620.70.06 source](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/620.70.06/kernel-open/nvidia-drm/nvidia-drm-drv.c)
  sets up the DRM client/fbdev path, so console restore during teardown is a
  candidate. The earlier open-fd test covered the later detach, not this
  transition.

### Guest traces (SDDM Wayland, VM)

- **VT owner** `vt-owner-1795642476` (93dec45): Plasma VT → text VT 9 → back.
  DRM master: logind on VT 1, none on VT 9, same logind client again. KWin kept
  its PID, new DRM clients; logout/re-login passed. **A compositor parked on an
  inactive VT does not keep master.**
- **KMS trace** `kms-1795643272` (c52f9f8): desktop (KWin PID 547) on CRTC 38,
  FB 43; logout request 19.651031, greeter connect 20.192441. A kprobe on
  `drm_atomic_set_mode_for_crtc` saw only non-null modes, first `(sd-close)` at
  19.853173, then logind. Helper calls, not commits; no disable attributable.
- **State samples** `state-1795643557` (a3b75b9, 5 ms sleeps): plane 36 on CRTC
  38 FB 46 before the request (19.709867), FB 44 at 19.896950, FB 42 by
  19.931876, FB 47 by 20.283064, connect 20.301475. No disabled controller or
  detached plane sampled; short transitions could be missed.
- **Pixels, same run** (3fbbed9, 02e83cb): frames 006–018 (13; starts
  0.241–0.723 s) mean RGB ≤0.000011; 10 fully black (007, 010–018). Frame 005
  mean 0.285, 019 0.278: about 0.48 s of near-black samples. During re-login,
  048–058 (1.931–2.333 s) and 060–066 (2.414–2.655 s) fully black, 059 mean
  0.275291; separate intervals. Of 175: 31 near-black, 28 fully black.
- **Synchronized** `sync-1795644064` (cd14bfe): guest uptime 19.74 s at host
  0.000–0.002 s, 26.77 s at 7.031–7.033 s. Frames 010–013 black inside the FB
  42 interval, 016–017 black after FB 43; 014 straddles FB 47; connect 20.327
  s; 018 non-black.
- **Allocator** `owner-1795644184` (9b74977): after KWin FB 44 the plane used
  FB 42, allocated by `[fbcon]`, for about 0.34 s, then KWin FBs 47 and 41.
  Frames 006–012 black in the fbcon interval; 015–016 black in the following
  KWin interval; 017 non-black. Allocator is not the committer. All guest
  traces are time correlations: no frame can be assigned to a commit or
  process.
- **Console preload** `preload-1795644288` (ba8c220): the painted console
  appeared but did not last until the greeter.
- **Greeter background A/B** (50b01ac, same marker KWin, only color changed;
  re-login passed): black `sddm-early-0.f9yDCE`: near-black 006–018
  (0.244–0.727 s), greeter 019. Magenta `sddm-early-1.47enSy`: near-black
  007–017 (0.284–0.685 s), magenta 018–021, greeter 022. Controller stayed
  active in samples. Magenta appeared with the switch back to a KWin FB; it
  does not cover the console interval. One run each, no evidence of a speedup.

### loki: physical stock Wayland greeter (9f26686)

logind recorded Wayland greeter sessions and the helper started KWin; greeter
connected 22:26:11. `video_2026-11-25_22-28-48.mp4` (4 samples/s): ≈1.5 s
apparent black, then a dim frame before Breath appears near 10 s. Clip not
aligned to journal. Xorg back after the 22:26:31 restart; drop-in absent.
**Dropped:** no fix for the blackout.

### Superseded plan: single scanout owner (3383460 … fd623c4)

One compositor/KMS owner sleeps during the desktop session, presents a static
wallpaper (not a screenshot) at logout, and switches producers when the
greeter's first frame arrives, with a deadline and fallback to stock.
**Dropped:** needs seat and session redesign; the VT switch with an open card
did the job. Never integrated with SDDM or logind. Premise: a resident process
cannot present on an output while another compositor holds DRM master. Open
question: can one compositor stay seat owner and host isolated desktop and
greeter producers without changing authentication, exposing greeter input to
the old session, or breaking logind activation. Fallback preference: a visible
blink over an unusable seat.

- Stock SDDM VM baseline `holder-stock-1795640054`: 175 frames,
  password login and new session after logout.
- Synthetic probe (`holder_gate.py`, `holder-probe.qml`; one Qt window on a
  running compositor, no logout). The first run sampled before the first
  frame. Then: `holder-probe-stock-1795640613` black → fake greeter;
  `holder-probe-1795640578` holder → greeter, no black;
  `holder-probe-stall-1795640638` holder → timeout marker, no black. The
  timeout marker does not restart SDDM.
- SDDM facts: 0.21.0
  [`HelperStartWayland.cpp`](https://github.com/sddm/sddm/blob/v0.21.0/src/helper/HelperStartWayland.cpp)
  starts the configured compositor before the greeter and stops it with the
  helper; stock cannot attach to a resident compositor.
  `Seat::displayStopped()` evaluates `defaultDisplayServerType()` before
  `createDisplay()` reloads the config, so a staged drop-in may not apply at
  the next logout; deleting one does not replace a running greeter. The first
  trial script wrote the config before arming rollback and was replaced
  before use.
- Wayland greeter recovery, VM: `wayland-recovery-1795640971`
  (`SDDM_VM_GREETER_FAIL=1`): removing the drop-in and restarting SDDM
  restored Xorg; login, logout, re-login passed (verifies the procedure, not
  automatic fallback). `wayland-timer-1795641108`: the armed timer removed the
  config; a separate restart restored X11. The timer does not restart SDDM.

### loki: output state capture, 21:25 (5d73281)

`loki-logout-capture2.sh` (20 ms, root, read-only), two stock logouts; second
with `HOLD=1` (open `/dev/dri/card2`, no master).

| Event | Stock | fd held |
| --- | ---: | ---: |
| desktop KWin exited | 14478.52 | 14612.60 |
| VT 2 active, CRTC `active=1` 144 Hz | 14479.43 | 14613.52 |
| CRTC detached, `dpms=Off` | 14479.46 | 14613.54 |
| greeter Connect | 14480.32 | 14614.38 |

CRTC stayed active ≈0.9 s after KWin exit; detach 20–30 ms after VT 2.
**An open fd did not prevent it** (no VT graphics-mode switch in this test).
Not the 21:10 video run. Does not show when Xorg restored output, or a DP
retrain.

### loki: same-run video and telemetry, 21:10 (7565bc3)

One stock logout at 4K 144 Hz, root 50 ms sampler,
`video_2026-11-25_21-11-28.mp4`.

| Boot | Event |
| ---: | --- |
| 13557.059 | Plasma shutdown service started |
| 13557.775 | desktop KWin exited |
| 13557.792 | SDDM launched Xorg on VT 2 |
| ≤13558.72 | tty1 DRM state still 144 Hz |
| 13558.72 | VT 2 active, mode unavailable |
| 13559.31 | Xrandr: 4K 60 Hz in the greeter's Xorg |
| 13559.480 | greeter Connect |

| Clip | Visible |
| --- | --- |
| 17.1–17.7 s | logout dialog |
| 17.8–18.1 s | wallpaper, windows closed |
| 18.2–19.2 s | dark grey, backlight visibly on, cursor dot |
| 19.3 s | faint red at the bottom edge (one frame) |
| 19.4–20.8 s | fully black, backlight visibly off |
| 20.9 s | dark, backlight on |
| 21.0 s | Breath greeter |

Clocks not aligned; the sampler did not read CRTC active state between modes.
`nvidia_drm`: `modeset=Y fbdev=Y`.

### loki: SDDM wallpaper hook and timing (1712057 … 462896f)

| Xorg launch | Xsetup | shutdown service → KWin exit | KWin exit → Xorg | Xorg → Xsetup | Xsetup → Connect |
| --- | --- | ---: | ---: | ---: | ---: |
| 20:21:04 | wallpaper hook | 705 ms | 17 ms | 1546 ms | 309 ms |
| 20:25:41 | stock | 657 ms | 17 ms | 1582 ms | 169 ms |
| 20:41:39 | stock | 675 ms | 17 ms | 1550 ms | 163 ms |

| Outgoing desktop | Xorg launch | VT 2 active, mode unavailable | Xrandr 4K 60 Hz | Connect |
| --- | ---: | ---: | ---: | ---: |
| 4K 144 Hz | 9844.253 | 9845.22 | 9845.84 | 9845.979 |
| 4K 60 Hz | 10117.367 | 10118.30 | 10118.94 | 10119.138 |

(Sampler loop times; SDDM logs only the requested VT; the 60 Hz lines
reached the journal before Connect.)
An unreadable mode does not show that scanout stopped, an Xrandr mode does
not show a visible frame, and greeter Connect is not the first frame.

- Both stock Xorg logs: 886–887 ms gap after the NVIDIA OutputClass, before
  the autoconfigured driver list; mode set ≈1.14 s after launch. Operation not
  identified.
- Earlier journal reading: hook ran ≈1.59 s after Xorg launch, Connect
  ≈150 ms later. The one confirmed draw logged success 154 ms into Xsetup.
- Rollback done 20:23:44; later the helper was absent, `pacman -Qkk sddm` 0
  altered files. The confirmed trial ended in sign-in after a pause; no rapid
  re-login or lock test.
- `video_2026-11-25_20-26-33.mp4` and `…20-42-24.mp4`: ≈1.6 s black each
  (11.6–13.2 s, 8.4–10.0 s). The first was labelled hook-on, but its timestamp
  fits the 20:25 stock return: not a verified A/B.
- **Dropped:** the hook runs ≈1.55 s after Xorg starts, too late to cover
  startup. No evidence for changing session ordering, driver, mode or backend.

### loki: Manjaro comparison (623cd20 … fafaffc)

Monitor wired to the NVIDIA output. Normal logout: one brief black, no "No
signal" message (does not rule out an interruption), sign-in worked. Greeter
connected 1.757 s after KWin stopped. Connector stayed connected; enabled
flag went enabled → disabled (greeter VT) → enabled. No CachyOS generator.
Not a controlled comparison with Vandal. Nothing changed.

- Second capture: **4K 144 → 60 → 144 Hz** (desktop 1328.8 MHz; Xrandr 60 Hz
  in the greeter; mode unavailable in some samples). One uniform black.
- Desktop temporarily at 60 Hz (533.5 MHz before and after; Xrandr 60 Hz in
  the greeter, exact clock not captured): connect 1.789 s after KWin stopped
  vs 1.743 s on the preceding 144 Hz run; sign-in worked; 144 Hz restored and
  verified. Same black, "a little shorter" (subjective). The mismatch may
  contribute; matching did not remove the blackout.

### SDDM in the VM (3f4a014 … 1dcff40)

`SDDM_VM_PACKAGES=DIR bash run-vm.sh BASE NEW_RESULTS sddm`: networkless
snapshot, signed SDDM and Xorg versions as on loki, CachyOS/Arch Plasma 6.8.3
base, built-in theme. It matches the X11 greeter → Wayland session path, not
the full Manjaro install or GPU.

| Run | Result |
| --- | --- |
| `sddm-baseline-1795632543` (stock) | rapid re-login passed; Xorg 58 ms after KWin stop; connect 337 ms |
| `sddm-delay-1795632579` (6 s desktop stop) | password accepted, Plasma start collided with the queued stop; SDDM returned the greeter, no own transaction error |
| `sddm-delay-fixed-1795632626` (+ desktop teardown patch only) | rapid re-login passed; connect 6.23 s after KWin stop |

So the desktop ordering race exists on SDDM too under slow teardown; the
PLM greeter patch is not needed there.

| Run | Result |
| --- | --- |
| `sddm-continuous-1795632701` | Xorg ready 241 ms after KWin stop, connect +99 ms; 011 dark console-like, 012–015 black, 016 greeter |
| `sddm-retro-1795632745` (`SDDM_VM_RETRO=1`) | earlier black stayed; Xorg stipple 013–019, greeter 020; Xorg ready 238 ms, connect +112 ms |
| `sddm-root-color-1795632820` (`xsetroot`) | hook ran on both starts; magenta 013–016, greeter 017; earlier black stayed |
| `sddm-backend-{0,1}-1795632902` | X11 vs Wayland: connect 382 vs 351 ms; greeter at 020 vs 021; black before both |
| `sddm-combined-wallpaper-{0,1}-1795632992` (`xwallpaper --zoom`, 1 s limit) | wallpaper at 014 (≈0.56 s after request), control black then; greeter 019 control, 020 wallpaper; connect 343 vs 405 ms; re-login and lock/unlock passed with the combined setup and teardown patch |

All passed re-login. An Xsetup hook covers only the tail after Xorg starts.
The VM theme used a different photo, so continuity into a matching greeter
was not shown. QEMU cannot model NVIDIA Xorg startup.

### Vandal: slow greeter user manager (7c7b0ad, 49e4ad5)

≈2.35 s between the greeter manager's PAM session opening and the default
target queuing; the target then takes ≈12 ms. Same gap for the desktop
manager after boot. `probe-generator.sh`: installed
`20-nvidia-rtd3-workaround` ([chwd PR 149](https://github.com/CachyOS/chwd/pull/149),
runs `lspci -d '10de:*:0302'` to pick Mesa EGL) takes 2.28–2.32 s cold (three
runs, wakes the GPU where checked), 8 ms warm. Sysfs version: same output,
<1 ms; follow-up 2 ms with the GPU suspended before and after. A same-named
file in `/run/systemd/user-environment-generators/` overrides it
([manual](https://www.freedesktop.org/software/systemd/man/latest/systemd.environment-generator.html));
it applies to all user managers unless it checks the UID. The probe time
matches the gap closely; a controlled manager-start A/B was still needed.

### Vandal: refresh mode across logout (bacefde … e5844bf)

`sample-dp.sh` (≈50 ms, read-only), DP-1:

| Boot s | State |
| ---: | --- |
| 173.544 | desktop KWin stopping |
| 173.570 | 4K 100 Hz (1188 MHz) → 60 Hz (533.25 MHz), desktop VT |
| 173.895 | KWin stopped |
| 176.370 | greeter VT active, 60 Hz |
| 176.890 | greeter sets 100 Hz, same clock as desktop |
| 177.268 | greeter Connect |
| 183.850 | new desktop VT, 100 Hz |

User saw pitch black → dark gray (backlight on) → pitch black. Consistent
with two mode changes around ≈3.3 s at 60 Hz; no frame timestamps; sampled
CRTC stayed enabled and active; no link loss confirmed.

A/B with the desktop at 533.25 MHz 60 Hz throughout (59.997 Hz preferred
timing, not the 594 MHz one): Connect 3.237 s after KWin stop (3.372 s at
100 Hz); re-login worked; 100 Hz (1188 MHz) restored, greeter config restored
byte for byte. User saw **one kind of black**. Suggests the mode change adds
to the flicker; one comparison. Holding 60 Hz was diagnostic only.

### CachyOS: combined login and lock regression, VM (8ec76fd)

`warm-combined-1795618921`: patched starters with the combined desktop KWin,
private locker, wallpaper producer and splash (synthetic wallpaper, stock VM
theme). With the 6 s stop: re-login, D-Bus lock active, password unlock via
QMP. Functional only.

### CachyOS: greeter first-frame marker, VM (0d7db65)

`greeter-marker-{0,1}-1795618717` (teardown patch, greeter-only instrumented
KWin): re-login passed. VT 1 requested ≈74 ms after KWin stop; first non-test
atomic ioctl 248 ms (black) and 234 ms (magenta) after the request. Black run:
black 007–015. Magenta: black 006, 008–013; magenta before the wallpaper
at 015. Covers some black, not the earlier interval.

### CachyOS: source teardown patches (be8c11a)

`patches/startplasma-{wayland,login-wayland}.patch` wait on
`systemctl --user --job-mode=fail stop` (desktop:
`graphical-session.target`, 15 s limit; greeter: target and KWin, 4 s, inside
the helper's 5 s). Timeout logged; no recovery guarantee. Never installed.

- `warm-source-1795618465` (6 s delay): re-login worked, no conflicting
  starts; greeter launched 5.895 s after KWin stopped: longer without a
  desktop compositor.
- Controls `*-source-control-1795618518`: passed, greeter 58 ms (cold) and
  42 ms (warm) after KWin stop.
- **Superseded** by the DrKonqi drop-in and the greeter wrapper.

### CachyOS: re-login race in the VM (de2ce86, 8cde191, 0c23753)

Desktop logout queues `StopUnit(graphical-session.target, fail)`; the starter
exits when KWinWrapper and Shutdown release their bus names, which can be
before the stop completes. The greeter starter queues stops (including KWin)
without waiting. Both incoming starters use `StartUnit(…, fail)`.

- `cold-roundtrip-1795617733`, `warm-roundtrip-1795617733` (runner now signs
  back in, 800 ms pacing; one pass each): two authentications each, new
  desktop, no conflict. Stock guest does not reproduce the physical failure.
- `warm-delay-1795618054` (6 s stop): **both** physical errors reproduced.
  Shows overlapping shutdown can cause it, not that Vandal had that service.
- `vm-start-barrier.sh`, `both`: `warm-barrier-1795618225` waited 4.18 s, new
  desktop. Greeter only: `warm-greeter-barrier-1795618242` desktop race still
  hit; greeter waited 58 ms and connected a third time (retry possible).
  Isolation probe, not installable (check and start are separate).

### Vandal: warm greeter start, failed re-login (1cdf89a)

One-off physical test: KWin exit 7455.137 s, greeter session 7455.197 s
(60 ms vs ≈2.51 s cold). **User could not sign back in and rebooted.**
Authentication succeeded; `plasma-workspace-wayland.target` start rejected
(stop job queued on `graphical-session.target`), then the greeter restart
rejected (its KWin stop queued). Shorter startup, no visual result; unclear
whether prewarming triggered it. After reboot sign-in normal, greeter user
manager inactive, patched desktop KWin selected, nothing persisted.
**Dropped:** do not pre-start the greeter user manager.

### Cold vs warm greeter, VM (5a49ad7)

`cold-1795616876`, `warm-1795616876`, from desktop KWin exit:

| Event | Cold | Warm |
| --- | ---: | ---: |
| VT switch requested | 135 ms | 70 ms |
| greeter KWin ready | 340 ms | 250 ms |
| greeter Connect | 413 ms | 321 ms |

Cold user manager 56 ms (physical ≈2.45 s). **Both sampled 13 black of
175.** Does not reproduce the DP flicker.

### Vandal: filmed stock logout (79d8187, ba63a8b)

Setup then: DP-1 4K 100 Hz (60 Hz preferred). Logout dialog to ≈6.5 s, then
desktop.

| Clip (0.25 s sampling) | Visible |
| --- | --- |
| 13.75 s | desktop wallpaper |
| 14.00–15.50 s | very dark, faint shapes |
| 15.75–17.25 s | brighter blue/blurred, no controls |
| 17.50–19.25 s | very dark, faint shapes |
| 19.50 s on | greeter |

No "No signal" banner seen. User: the blue interval looks backlit, the dark
ones backlight off. The clip does not establish that. Journal: 3.25 s from
Plasma shutdown service start to KWin exit, 2.45 s to VT switch, 0.88 s to
greeter Connect. Journal and clip clocks are not aligned.

### Vandal: baseline journal timing (84c924b)

Three sign-outs, same order: PLM starts a greeter after the session exits,
then waits for the greeter user manager: 2.42–2.45 s (≈0.10 s at boot).

| From desktop KWin exit | Offset |
| --- | ---: |
| PLM begins greeter | 0.02 s |
| greeter user manager starting | 0.04 s |
| switch to VT 1 logged | 2.47 s |
| greeter KWin ready | 2.91 s |
| greeter Connect | 3.36 s |

Journal events, not scanout. Much of the gap precedes the greeter compositor,
so a wallpaper behind its first frame cannot cover it alone. The greeter's
live mode was not yet measured.

## Dropped approaches

| Approach | Why dropped |
| --- | --- |
| Pre-start the greeter user manager | re-login failed on Vandal (its role not established) |
| Wait in the outgoing starters (source patches) | longer time without compositor; DrKonqi drop-in and wrapper cover the observed failures |
| Compiled greeter-exit patch | 4 s limit, lost on package update; wrapper shipped (patch still a candidate for upstream) |
| Open GPU fd only (loki) | did not stop the controller detach |
| Compositor parked on another VT (VM) | loses DRM master |
| Preload the console image (VM) | did not last until the greeter |
| Greeter-only background paint (VM) | covers only the tail |
| SDDM Wayland greeter (loki) | still ≈1.5 s black |
| SDDM Xsetup wallpaper (loki) | runs ≈1.55 s after Xorg starts |
| Resident compositor for both sessions | seat and session redesign; never integrated |
| Image relay that paints | painting unnecessary; open card plus VT switch gave 6/6 without black |
| Console switch inside the hook (v1–v3) | broke Restart and Shutdown |
| Matching 60 Hz as a fix | diagnostic only |
