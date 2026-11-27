# DrKonqi upstream bug report

Draft, **not submitted**. A crash during logout makes DrKonqi's launcher socket
cancel the pending stop of `graphical-session.target`, and a quick re-login can
then fail. Background:
[failed re-login, 2026-11-26](../docs/LOG.md#vandal-failed-re-login-after-logout-2101-07b94ea).

| File | Contents |
| --- | --- |
| [drkonqi-kde-bug.md](drkonqi-kde-bug.md) | the report: steps, journal, mechanism, fixes, workaround, related reports |
| [drkonqi-repro.sh](drkonqi-repro.sh) | reproduction with plain systemd user units; attach to the report |
| [drkonqi-repro-vm.py](drkonqi-repro-vm.py) | runs every variant in a throwaway VM boot |
| [results/](results/) | output per variant, systemd 262.2, run of 2026-11-27 |

Rerun from this directory. It needs the VM cache that `../run-vm.sh` uses, and
the log file must not exist. Do not run the `.sh` on a live session.

```sh
python3 -I drkonqi-repro-vm.py ~/.cache/plasma-handoff-6.8.3/vm /tmp/drkonqi-repro.log
```

## Result

The mechanism holds against systemd v262.2 source. Unit-only reproduction,
3 runs:

| Variant | Next start |
| --- | --- |
| `stock`, `after` | refused |
| `no-requisite` | ok, activated portal left running |
| `socket-partof` (the workaround) | ok |
| `irreversible` | ok, socket `failed` |

No report of this through DrKonqi found (2026-11-26). Same mechanism with
another unit: [systemd#39409](https://github.com/systemd/systemd/issues/39409).

## Check before submitting

- The draft discloses the local logout helper and patched login screen
  binaries, and replaces application names.
- On the real machine the cancellation is inferred from event order. The VM
  runs show it directly. The journal does not say what activated the portals.
- Fixes 2–4, and `RemoveOnStop=yes` under fix 1, are untested or tested only in
  the script, as marked.

## Crash reports at logout

The core dump is kept (`coredumpctl`), but no crash notification appeared for
logout crashes. Journal of the live PC since 2026-11-26 21:00:

- 18 refused reports (`"Connection refused"`), all handed to a launcher by a
  later pickup run (for example at the 22:15:22 and 09:49:01 sign-ins).
- 17 predate the drop-in (installed 22:13:01): the stock socket also refuses
  reports that arrive after it closes. One (22:14:15) came after it.
- All 18 lack KCrash metadata (`Unable to find file for pid …`). The first
  hand-over ends in `Nothing handled the dump`.
- The 6.8.3 launcher does not notify for pickups
  ([source](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/GlobalNotifierTruck.cpp#L56)),
  and later pickups treat the dump as handled
  ([source](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/main.cpp#L168)).

Not tested: whether an app with KCrash metadata gets a notification at the next
sign-in, and whether a notification would have been visible during teardown
without the drop-in.
