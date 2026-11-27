# Logout holder

The holder keeps the desktop's wallpaper on screen from Log Out until the login
screen appears over its own wallpaper. Restart and shutdown look as they did
before. Design: [HOLDER-DESIGN.md](../HOLDER-DESIGN.md). Status:
[README.md](../README.md#status-2026-11-27).

## What happens

At logout, restart or shutdown:

1. Plasma runs `/etc/xdg/plasma-workspace/shutdown/logout-holder` before it
   stops the desktop. The hook hides windows (KWin "show desktop", 0.5 s) and
   starts `logout-holder.service`. It returns once the helper holds the screen,
   after at most about 6.5 s.
2. The helper opens each card that drives a screen, without taking control.
3. It copies `~/.config/kwinoutputconfig.json` to
   `/var/lib/plasmalogin/.config/`.
4. It waits for Plasma's logout program to exit. On a plain logout it switches
   to VT 1 in graphics mode. On restart or shutdown it does nothing more.
5. The greeter's patched KWin draws the login wallpaper from its first frame,
   with no window-open animation.
6. The helper exits 2 s after that KWin has the card. If none appears within
   15 s, or the service is stopped, the console returns to text mode.

## Build

You need:

- the KWin 6.8.3 build with the distro backports
  (`../patches/kwin-6.8.3-arch-backport-{528824,528936}.patch`, as in Arch
  `kwin 6.8.3-3`) plus `../patches/kwin-6.8.3-logout-vm-backdrop.patch`, in
  `~/.cache/plasma-logout-handoff/backdrop/build` or `KWIN_BUILD`;
- `plasma-login-wallpaper` built with
  `../patches/plasma-login-manager-6.8.3-logout-vm-wallpaper.patch`.

The backports are required. Without the fix for KDE bug 528936, the login
prompt went to the closed built-in screen and the keyboard did nothing.

```bash
bash bundle.sh NEW_DIR PATCHED_PLASMA_LOGIN_WALLPAPER
```

This creates `NEW_DIR` with the helper, hook, unit, polkit rule,
`greeter-start`, `login-screen-start`, both copies, `PACKAGES` and
`SHA256SUMS`. `BUNDLE_PACKAGES` overrides the derived package list.

## Install

```bash
sudo bash NEW_DIR/install.sh
```

It takes effect at the next logout. The installer changes nothing if:

- a target file already exists, or a bundle file is missing;
- KWin or the login manager is not 6.8.3;
- a package in `PACKAGES` is not installed, or a copy does not load;
- the greeter KWin has local overrides (the unchanged
  `greeter-animation-test.sh` files are accepted and then removed);
- the stock greeter or wallpaper command is unexpected, or
  `/etc/plasmalogin.conf` names no wallpaper image;
- the running login manager does not search `/usr/local/bin` before
  `/usr/bin`, or sets `PLASMALOGIN_GREETER_EXEC`.

## Upgrade

Remove the old version with its own bundle, then install the new one:

```bash
sudo bash OLD_DIR/install.sh --restore && sudo bash NEW_DIR/install.sh
```

To return from v7 to v6, swap the directories. The scale-in then returns unless
you run `sudo bash ../greeter-animation-test.sh apply`.

## Undo

```bash
sudo bash NEW_DIR/install.sh --restore
```

This removes the installed files and restores the login screen's display
settings. A file changed since install is left in place, with a message.

**If the login screen does not appear:** Ctrl+Alt+F3, sign in, run the restore
command, then `sudo systemctl restart plasmalogin`.

## Display settings

Different colour range or bit depth on the greeter forces a modeset, and the
monitor shows black for a few seconds. Step 3 prevents that. It runs at every
logout, restart and shutdown from Plasma. The greeter reads the copy at once or
at the next boot. It also spares a modeset when the desktop takes over at
sign-in.

- The first copy keeps the greeter's own file as `.before-logout-holder`.
- `systemctl reboot`, Ctrl+Alt+Del or a crash leave the previous copy in place
  until the next exit from Plasma.
- To copy by hand: `sudo bash sync-greeter-outputs.sh` (`--restore` undoes it).

## Login screen after a failed sign-in

If the desktop fails to start, the login manager starts a new greeter while the
old KWin may still be stopping. systemd refuses, and the screen stays black
until a reboot. The bundle installs [login-screen-start](login-screen-start) as
`/usr/local/bin/startplasma-login-wayland`. It waits for the pending stop, then
runs the packaged program.

- Tested in the VM only. Installed since v6
  ([results](../docs/LOG.md#greeter-recovery-after-a-failed-sign-in-vm-11-2627-88f7b46)).
- Shell script using only `systemctl`: it stays in use after package updates.
- Takes effect at the next login screen. No restart needed.
- It stops running greeter units first, which assumes one seat.
- After 100 s, or if the stop fails, it logs that
  (`journalctl -t logout-holder`) and starts the packaged program anyway.
- It does not stop the desktop start from failing. The new greeter shows no
  error.

## When the copies are not used

`greeter-start` runs the stock program and logs why
(`journalctl -b -g logout-holder`) if:

- a package in `PACKAGES` is no longer installed at that version: `kwin`
  (plugins load into the copy), `qt6-wayland` (loaded at run time),
  `plasma-login-manager`, and the packages supplying private symbols (on the
  test PC `qt6-base`, `qt6-declarative`, `kdecoration`, `kwindowsystem`);
- or `ldd -r` reports a missing library or symbol (0.05 s for KWin, 0.03 s for
  the wallpaper program).

The backdrop is then gone until you install a rebuilt bundle. Sign-in works.
Expect this after each KDE Frameworks release (`kwindowsystem`). A copy that
loads and then fails is not detected.

## Check the re-login workaround

DrKonqi can cancel the session stop at logout and break a quick re-login. The
fix is a user drop-in, not part of the bundle
([report](../drkonqi-report/README.md)). After a logout:

```bash
journalctl --since -10min -o short-precise --no-pager \
  -g 'Socket to launch DrKonqi|Launch DrKonqi|Current graphical user session|Failed to enqueue|contradicts existing jobs|destructive|startplasma-login-wayland'
```

Good:

- `Closed Socket to launch DrKonqi for a systemd-coredump crash` at the start
  of teardown;
- no `Started Launch DrKonqi …` during teardown;
- `Stopped target Current graphical user session`;
- no `Failed to enqueue` or `destructive`.

## Test in the VM

Options are in [docs/VM.md](../docs/VM.md#logout-holder). Test restart and
shutdown after every change.

## Limits

- Restart and shutdown show what they showed before (the screen may go black
  before the boot splash).
- The greeter KWin copy has no real-time priority (`cap_sys_nice`): a file
  capability would make the loader ignore `LD_LIBRARY_PATH`.
- The kept frame is readable by the next program that controls the display. The
  hook shows the desktop first, so open windows are not in it.
- One seat (`seat0`), login screen on console 1.
- Live tests: Intel graphics, HDMI 4K at 60 Hz, lid closed. Other setups are
  not tested.
