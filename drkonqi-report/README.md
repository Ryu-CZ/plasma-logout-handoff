# DrKonqi upstream bug report

Status: draft, not submitted. Background: the 2026-11-26 21:01 section of
[../README.md](../README.md).

| File | Contents |
| --- | --- |
| [drkonqi-kde-bug.md](drkonqi-kde-bug.md) | the report: steps, journal, mechanism, fixes, workaround, related reports |
| [drkonqi-repro.sh](drkonqi-repro.sh) | reproduction with plain systemd user units; attach to the report |
| [drkonqi-repro-vm.py](drkonqi-repro-vm.py) | runs every variant in a throwaway VM boot |
| [results/](results/) | output per variant, systemd 262.2, run of 2026-11-27 |

Rerun, from this directory (needs the VM cache that `../run-vm.sh` uses; the
log must not exist yet; do not run the `.sh` on a live session):

```sh
python3 -I drkonqi-repro-vm.py ~/.cache/plasma-handoff-6.8.3/vm /tmp/drkonqi-repro.log
```

## Result

The mechanism holds against systemd v262.2 source. In the unit-only
reproduction (3 runs):

| Variant | Next start |
| --- | --- |
| `stock`, `after` | refused |
| `no-requisite` | ok, activated portal left running |
| `socket-partof` (the workaround) | ok |
| `irreversible` | ok, socket `failed` |

No report of this through DrKonqi found (2026-11-26). Same mechanism with
another unit: [systemd#39409](https://github.com/systemd/systemd/issues/39409).

## Check before submitting

- The draft discloses the local logout helper and patched login-screen
  binaries, and replaces application names.
- On the real machine the cancellation is inferred from event order; the VM
  runs show it directly. The journal does not say what activated the portals.
- Fixes 2–4, and `RemoveOnStop=yes` under fix 1, are untested or tested only in
  the script, as marked.

## Correction to the main README

`main` (5c7378a) says crashes during logout are not lost and the refused
connection costs only a failed processor unit. The journal since 2026-11-26
21:00 shows less:

- 18 refused reports; all 18 handed to a launcher by a later pickup run.
  17 predate the drop-in (installed 22:13:01): the stock socket also refuses
  reports that arrive after it closes. One (22:14:15) came after it.
- All 18: no KCrash metadata, first hand-over ends in
  `Nothing handled the dump`. The launcher does not notify for pickups
  ([source](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/GlobalNotifierTruck.cpp#L56)),
  and later pickups treat the dump as already handled
  ([source](https://invent.kde.org/plasma/drkonqi/-/blob/v6.8.3/src/coredump/launcher/main.cpp#L168)).

So the core dump is kept, but no crash notification appears for these. Whether
one would have been visible without the drop-in, during teardown, was not
tested.
