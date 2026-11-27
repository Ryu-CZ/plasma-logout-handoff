# Draft KDE bug report (not submitted)

Product `drkonqi`, component `general`, version 6.8.3, severity major.
Attach: `drkonqi-repro.sh`.

## Title

Crash during logout: socket-activated drkonqi-coredump-launcher cancels the
pending stop of graphical-session.target; a quick re-login then fails

## Versions

drkonqi / plasma-workspace / plasma-login-manager 6.8.3, Frameworks 6.32.0,
Qt 6.12.1, systemd 262.2, dbus-broker 37, xdg-desktop-portal 1.22.1 (distro
build, no `Requisite=` in its unit), CachyOS, kernel 7.3.6, Wayland.

`Requisite=` on the launcher comes from
[b2971200](https://invent.kde.org/plasma/drkonqi/-/commit/b2971200bf34d370cf4fd5011fee1d3821f48dc4)
(bug 522477; backported to 6.6 and 6.7). Launcher units are unchanged between
v6.8.3 and master 984607999 / Plasma/6.8 bd89fbb8e (2026-11-26).

Local modifications on the affected machine: a logout helper run from
`plasma-workspace/shutdown` (keeps the last frame on screen, switches VT after
plasma-shutdown exits) and patched KWin + wallpaper binaries for the login
screen only. The unit-only reproduction below involves none of this.

## Steps

1. Run an app that crashes while quitting (here an Electron app, SIGTRAP).
2. Have something `After=graphical-session.target` that takes longer to stop
   than the crash takes to reach DrKonqi (here a tray app, 2.4 s; core dump to
   socket connection took 1.7 s).
3. Log out. Sign in again within a few seconds (same user manager).

Timing dependent: 2 of 21 session exits in one day (one logout, one restart).
The failed login was seen once; the other occurrence was the restart.

## Observed

- `graphical-session.target` is not stopped at logout and stays active.
- Next sign-in: password accepted, then
  `Transaction for plasma-workspace-wayland.target/start is destructive
  (graphical-session.target has 'stop' job queued, ...)`. No desktop; black
  screen until reboot.

## Expected

The session stop cannot be undone by a crash report; re-login works.

## Journal (failed logout, trimmed, app names replaced)

Times are seconds within one minute; 36.x is the new sign-in.

```
28.244 systemd[user]: Stopped target plasma-workspace-wayland.target.
28.244 systemd[user]: Stopping <crashing-app>...
28.245 systemd[user]: Stopping <slow-app>...
28.302 systemd-coredump: Process N (<crashing-app>) ... signal 5/TRAP, processing...
29.735 systemd[user]: Stopped <crashing-app>.
30.045 drkonqi-coredump-processor: "<crashing-app>" ...
30.046 systemd[user]: Stopped target KDE Plasma Workspace.        # graphical-session.target did not stop first
30.047 systemd[user]: Started Launch DrKonqi for a systemd-coredump crash (...).
30.621 systemd[user]: Stopped <slow-app>.
30.623 systemd[user]: Closed Socket to launch DrKonqi for a systemd-coredump crash.
30.626 systemd[user]: Starting Portal service...
30.700 systemd[user]: Starting Accessibility services bus...
30.745 systemd[user]: Starting Xdg Desktop Portal For KDE...
30.765 systemd[user]: drkonqi-coredump-launcher@....service: Failed with result 'exit-code'.
30.765 systemd[user]: graphical-session.target: Failed to enqueue stop job, ignoring: Transaction for
       graphical-session.target/stop is destructive (plasma-xdg-desktop-portal-kde.service has 'start'
       job queued, but 'stop' is included in transaction).
31.396 systemd[user]: plasma-xdg-desktop-portal-kde.service: Failed with result 'start-limit-hit'.
       --- sign-in, 5 s later ---
36.545 systemd[user]: Reload requested from client PID N ('startplasma-way')...
36.639 systemd[user]: Stopping Portal service...
36.648 systemd[user]: Requested transaction contradicts existing jobs: Transaction for
       plasma-workspace-wayland.target/start is destructive (graphical-session.target has 'stop' job
       queued, but 'start' is included in transaction).
36.650 systemd[user]: Stopped target Current graphical user session.
36.761 systemd[greeter]: Transaction for plasma-login-wayland.target/start is destructive
       (plasma-login-kwin_wayland.service has 'stop' job queued, ...).   # restarted greeter fails too
```

## Mechanism (source: systemd v262.2, Plasma v6.8.3)

Units:
[launcher@.service](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/drkonqi-coredump-launcher%40.service.cmake)
has `PartOf=` + `Requisite=graphical-session.target`, no `After=`.
[The socket](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/drkonqi-coredump-launcher.socket)
is `Accept=yes`, `PartOf=plasma-core.target`, so it keeps listening while
graphical-session.target is waiting to stop.

1. plasma-shutdown calls `StopUnit(graphical-session.target, "fail")`
   ([`Shutdown::logoutComplete`](https://invent.kde.org/plasma/plasma-workspace/-/blob/v6.8.3/startkde/plasma-shutdown/shutdown.cpp#L164)).
   The stop job waits for units ordered after the target.
2. A crash report connects. For `Accept=yes` the instance is always started in
   `replace` mode
   ([`socket.c:socket_enter_running`](https://github.com/systemd/systemd/blob/v262.2/src/core/socket.c#L2573)).
3. `Requisite=` adds a `verify-active` job on the target to that transaction
   ([`unit-dependency-atom.c`](https://github.com/systemd/systemd/blob/v262.2/src/core/unit-dependency-atom.c#L22),
   [`transaction.c:transaction_add_job_and_dependencies`](https://github.com/systemd/systemd/blob/v262.2/src/core/transaction.c#L1172)).
   The target is active, but the job is not dropped as redundant because it
   conflicts with an installed job
   ([`transaction_drop_redundant`](https://github.com/systemd/systemd/blob/v262.2/src/core/transaction.c#L383)).
4. Neither guard applies:
   [`transaction_minimize_impact`](https://github.com/systemd/systemd/blob/v262.2/src/core/transaction.c#L662)
   acts only in `fail`/`lenient` mode;
   [`transaction_is_destructive`](https://github.com/systemd/systemd/blob/v262.2/src/core/transaction.c#L622)
   only in those modes or against an irreversible job.
5. `verify-active` and `stop` are not mergeable
   ([`job.c:job_merging_table`](https://github.com/systemd/systemd/blob/v262.2/src/core/job.c#L416)), so
   [`job_install`](https://github.com/systemd/systemd/blob/v262.2/src/core/job.c#L254)
   finishes the stop job with `JOB_CANCELED`.
   `verify-active` then
   [succeeds](https://github.com/systemd/systemd/blob/v262.2/src/core/job.c#L939).
   plasma-workspace.target (`Before=` the target) stops without waiting.
6. D-Bus activation queues portal start jobs. xdg-desktop-portal.service
   (`After=` the target) waits behind `verify-active`, which waits for the slow
   unit's stop
   ([`job_compare`](https://github.com/systemd/systemd/blob/v262.2/src/core/job.c#L1725):
   stops go first); here it started 5 ms after that. The a11y bus and the other
   portals (all `PartOf=` the target) follow. The journal does not name the
   caller; presumably the launcher's Qt start-up.
7. The launcher exits. That re-checks `StopWhenUnneeded=` on the target, which
   enqueues a stop in `fail` mode
   ([`manager.c:manager_dispatch_stop_when_unneeded_queue`](https://github.com/systemd/systemd/blob/v262.2/src/core/manager.c#L1557)).
   It propagates to the portals, whose start jobs are queued: refused as
   destructive. `PartOf=` units
   [do not trigger another check](https://github.com/systemd/systemd/blob/v262.2/src/core/unit-dependency-atom.c#L85),
   so the target stays active.
8. Next login,
   [`startPlasmaSession`](https://invent.kde.org/plasma/plasma-workspace/-/blob/v6.8.3/startkde/startplasma.cpp#L696)
   reloads systemd. Restoring the active target
   ([`target.c:target_coldplug`](https://github.com/systemd/systemd/blob/v262.2/src/core/target.c#L85))
   queues the unneeded check again; the stop is now accepted and waits for the
   leftover units. The
   [`StartUnit(plasma-workspace-wayland.target, "fail")`](https://invent.kde.org/plasma/plasma-workspace/-/blob/v6.8.3/startkde/startplasma.cpp#L746)
   that follows is refused.

## Reproduction without Plasma

`bash drkonqi-repro.sh [variant]`, in a disposable VM or test account. It
creates only `repro-*` runtime units:

| Unit | Stands for | Relevant settings |
| --- | --- | --- |
| session.target | graphical-session.target | `StopWhenUnneeded=yes` |
| workspace.target | plasma-workspace.target | `BindsTo=` + `Before=` session |
| slow.service | slow app | `PartOf=` + `After=` session, stop takes 4 s |
| portal.service | portals | `PartOf=` + `After=` session, start and stop 3 s |
| crash.socket | launcher socket | `Accept=yes` |
| crash@.service | launcher | `PartOf=` + `Requisite=` session; starts portal, exits |

Sequence: stop session.target with `--job-mode=fail`; connect to the socket
while that job waits; `daemon-reload`; start workspace.target with
`--job-mode=fail`.

`stock` output (systemd 262.2):

```
jobs:
  repro-workspace.target stop waiting
  repro-session.target stop waiting
  repro-slow.service stop running
=== crash report: connect to the socket
Job for repro-session.target canceled.
...
Failed to start repro-workspace.target: Transaction for repro-workspace.target/start is destructive
(repro-session.target has 'stop' job queued, but 'start' is included in transaction).
```

Variants, same result in 3 runs:

| Variant | Pending stop | session.target after logout | Next start |
| --- | --- | --- | --- |
| `stock` | canceled | active | refused |
| `after` (adds `After=` to the service) | canceled | active | refused |
| `no-requisite` | kept | inactive; activated portal left running | ok |
| `socket-partof` (`PartOf=` session on the socket) | kept; connection refused | inactive | ok |
| `irreversible` (stop with `replace-irreversibly`) | kept; activation refused, socket `failed` | inactive | ok |

Plasma 6.8.3 VM (same local helper, no DrKonqi package): copies of the two
launcher units with a shell stand-in as the service, report sent while a 2 s
unit was stopping. In 3 of 4 runs the target did not stop during logout; in the
other it stopped 1.7 s later, once the portal had started. Re-login still
succeeded in that VM, so of the two setups only the script reproduces the
refused start.

## Proposed fixes

1. **Socket: add `PartOf=graphical-session.target`** (keep the existing one).
   The socket's stop job is created in the same transaction as the target's,
   and a socket with a pending stop
   [refuses connections](https://github.com/systemd/systemd/blob/v262.2/src/core/socket.c#L2456).
   Tested (script, Plasma VM, one real logout).
   Side effect: crashes during teardown get `Connection refused`, and
   [the processor](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/processor/main.cpp)
   exits 1. `RemoveOnStop=yes` on the socket, or treating `ECONNREFUSED` like a
   [missing socket](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/processor/main.cpp#L110),
   would avoid the failed unit (untested).
   The stock socket already refuses reports that arrive after it closes: on
   the affected machine 17 refused reports in one evening predate the
   workaround and 1 followed it. At a later login the pickup service resent all
   18. None had KCrash metadata; on the first resend the launcher logged
   `Nothing handled the dump` and
   [`GlobalNotifierTruck`](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/GlobalNotifierTruck.cpp#L56)
   skips pickups, so no crash notification for these; the cores stay with
   systemd-coredump. With KCrash metadata the source would start DrKonqi (not
   observed).

   ```diff
    PartOf=plasma-core.target
   +# Activating the launcher while the session is stopping cancels the stop.
   +PartOf=graphical-session.target
   ```

2. **Drop `Requisite=` from the launcher.** Removes this `verify-active` job,
   but is not enough alone: the launcher still starts during teardown and what
   it activates can outlive the session; an activated unit with its own
   `Requisite=` cancels the stop the same way (upstream
   xdg-desktop-portal.service 1.22.1 has one); and bug 522477 needs another
   guard (with fix 1 and the socket tied to plasma-core.target, the
   no-session window should be closed; untested). `After=` does not help. A
   check such as `ExecCondition=systemctl --user is-active
   graphical-session.target` would pass during teardown: the target is still
   `active` while its stop job waits.
3. **plasma-shutdown: stop the session with `replace-irreversibly`** instead of
   `fail`. No later activation can cancel it, whichever unit has `Requisite=`
   or `Requires=`. Conflicting activations then fail, and an `Accept=yes`
   socket that hits this enters `failed` (startplasma resets failed units at
   login). Tested only in the script.
4. **startplasma:** wait for a leftover graphical-session.target to be inactive
   before starting the new session. Only covers the re-login (untested).
5. **systemd:** `verify-active` should not cancel a `stop` job
   ([systemd#39409](https://github.com/systemd/systemd/issues/39409), open;
   the merging table is the same on main 8634c420).

## Workaround

```sh
d=~/.config/systemd/user/drkonqi-coredump-launcher.socket.d
mkdir -p "$d"
printf '[Unit]\nPartOf=graphical-session.target\n' >"$d/stop-with-graphical-session.conf"
systemctl --user daemon-reload
```

Plasma VM: with it, 2 logout runs refused the report and stopped the target;
reboot and halt went through. Real machine: one logout, app crashed again,
socket already closed, target stopped, re-login worked (no slow app that time).
Undo: delete the file, `daemon-reload`.

## Related

Same mechanism, other unit:

- [systemd#39409](https://github.com/systemd/systemd/issues/39409): start of a
  `Requisite=` unit cancels the stop (xdg-desktop-portal).
- [xdg-desktop-portal#2215](https://github.com/flatpak/xdg-desktop-portal/issues/2215):
  portal activation at logout leaves graphical-session.target active on Plasma;
  closed as duplicate.

No report of this through DrKonqi found (bugs.kde.org, invent.kde.org merge
requests, drkonqi history; 2026-11-26).

Background and analogies, not duplicates:

- [522477](https://bugs.kde.org/show_bug.cgi?id=522477): added the `Requisite=`.
- [524048](https://bugs.kde.org/show_bug.cgi?id=524048): that guard is
  incomplete; own-binary crashes now filtered.
- [524490](https://bugs.kde.org/show_bug.cgi?id=524490),
  [drkonqi!419](https://invent.kde.org/plasma/drkonqi/-/merge_requests/419):
  socket moved under plasma-core.target, its own `Requisite=` removed.
- [484864](https://bugs.kde.org/show_bug.cgi?id=484864),
  [485011](https://bugs.kde.org/show_bug.cgi?id=485011): DrKonqi pickup service
  blocked logout (fixed 6.0.4).
- [461475](https://bugs.kde.org/show_bug.cgi?id=461475): same re-login error
  from a slow-stopping unit (2022, closed fixed).
- [plasma-workspace!7012](https://invent.kde.org/plasma/plasma-workspace/-/merge_requests/7012),
  [!7336](https://invent.kde.org/plasma/plasma-workspace/-/merge_requests/7336)
  (open): session stop handling in plasma-shutdown and startplasma.
- [bazzite#4869](https://github.com/ublue-os/bazzite/issues/4869): same
  re-login error, different cause.
