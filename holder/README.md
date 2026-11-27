# Logout holder

Keeps a picture on screen from Log Out until the login screen appears,
instead of black: the desktop's wallpaper stays up, then the login screen
appears over its own wallpaper. Restart and shutdown are left as they were.
Design, VM and host evidence: [HOLDER-DESIGN.md](../HOLDER-DESIGN.md).

Status (2026-11-27): v6 installed on Vandal (Intel, HDMI 4K@60, lid closed)
on 2026-11-27 12:35. With v5, logout showed no black, keyboard sign-in worked,
and Restart and Shutdown from the Plasma menu worked (Shutdown 2026-11-26
22:56); v6 differs only in the installer and the login-screen wrapper, and has
been through normal logouts and sign-ins on Vandal.
v7 (the animation setting and the new package guard) is built and VM-tested,
not yet installed ([results](../README.md#holder-v7-animation-setting-and-package-guard-vm)).

## What happens

When Plasma ends the session (logout, restart or shutdown):

1. Plasma's logout program runs `/etc/xdg/plasma-workspace/shutdown/logout-holder`
   just before it stops the desktop. The hook hides the remaining windows
   (KWin "show desktop", then 0.5 s for animations), starts
   `logout-holder.service` (a polkit rule allows only `start` of that unit)
   and returns once the helper holds the screen (at most about 6.5 s).
2. The helper keeps each graphics card that drives a screen open, without
   controlling it, so the desktop's last frame stays on screen when its
   compositor exits.
3. It copies the departing user's display settings
   (`~/.config/kwinoutputconfig.json`) to the login screen
   (`/var/lib/plasmalogin/.config/`). See "Display settings" below.
4. It waits for Plasma's logout program to exit. Only if that program has
   exited and no restart or shutdown is under way (a plain logout) does it
   switch to the login screen's console (VT 1) in graphics mode. Plasma
   gives the hook no other way to tell a logout from a restart. Switching
   earlier would make logind refuse a restart or shutdown, because the
   desktop would no longer be the session in front. v3 did that.
5. The login screen's compositor (a patched copy of KWin 6.8.3) draws the
   login wallpaper underneath from its first frame. The wallpaper window
   (a patched copy of `plasma-login-wallpaper`) stays transparent until its
   picture has loaded.
   The login screen compositor also runs without KWin's window-open
   animation (v7): over the backdrop, the login screen would visibly dim and
   scale in from the centre. The setting is
   `/usr/local/lib/logout-holder/xdg/kwinrc`, seen by that compositor only.
6. The helper exits 2 s after that compositor has the card. If none starts
   within 15 s, or the service is stopped, the console returns to text mode,
   as without the helper.

## Display settings

If the login screen's display settings differ from the desktop's (colour
range, bits per colour), its first frame forces a full modeset and the
monitor shows black for a few seconds while it re-syncs. On Vandal the
desktop uses Broadcast RGB Limited and 8 bits per colour; the login
screen's defaults differ.

So step 3 runs at every logout, restart and shutdown from Plasma. The login
screen uses the copied settings right away, or at the next boot. Matching
settings also spare a modeset when the desktop takes over at sign-in. How
the copy is made:

- The file is read as the departing user, so a link cannot point the helper
  at a file that user could not read.
- It must be in KWin's format and at most 1 MiB.
- It is written as a new file, owned by plasmalogin, then renamed into place.
- The first copy keeps the login screen's own file as
  `.before-logout-holder`, and `install.sh --restore` puts it back.

After a restart that bypassed Plasma (`systemctl reboot`, Ctrl+Alt+Del, a
crash), the login screen keeps the previous copy until the next exit from
Plasma. To copy by hand: `sudo bash sync-greeter-outputs.sh` (`--restore`
undoes it).

## Login screen after a failed sign-in

Installed on Vandal with v6 (2026-11-27 12:35); the greeter starts through it.
Recovery tested in the VM only (no failed sign-in on Vandal since).

If the desktop fails to start at sign-in, the login manager starts a new login
screen at once. The old one's compositor may still be stopping, systemd
refuses the new start, and the screen stays black until a reboot. The bundle
installs [login-screen-start](login-screen-start) as
`/usr/local/bin/startplasma-login-wayland`. The login manager finds it ahead of
the packaged program, it waits for the pending stop, then it runs the packaged
program. Evidence: [the main README](../README.md#greeter-recovery-after-a-failed-sign-in-vm).

- It is a shell script that uses only `systemctl`, so it is not tied to
  `PACKAGES` and stays in use after package updates.
- It takes effect at the next login screen; no restart or reboot is needed.
- The installer refuses if the running login manager would not find it.
- It stops any login screen units still running before starting new ones, which
  assumes one seat.
- If the stop fails or takes 100 s, it logs that (`journalctl -t logout-holder`)
  and starts the packaged program anyway.
- It does not stop the desktop start from failing; it only gets the login screen
  back so that you can sign in again. The new login screen shows no error.

## When the copies are not used

`greeter-start` starts the stock program instead of a copy, and logs why
(`journalctl -b -g logout-holder`), in either case:

- A package in `PACKAGES` is no longer installed at that version. The list
  holds the packages whose private code the copies depend on. `bundle.sh`
  asks the dynamic loader which libraries supply private symbols to the copies
  (on Vandal `qt6-base`, `qt6-declarative`, `kdecoration`, `kwindowsystem`)
  and adds `kwin`, whose plugins load into the copy, `qt6-wayland`, a plugin
  loaded at run time, and `plasma-login-manager`.
- The copy does not load: `ldd -r` reports a library not found or a symbol
  missing, whichever package caused it. This costs about 0.05 s for KWin and
  0.03 s for the wallpaper program (measured on Vandal).

Either way the backdrop is gone until a rebuilt bundle is installed, and
sign-in works. A copy that loads but fails while running is not detected.
`kwindowsystem` is a KDE Frameworks package, so expect this after each
Frameworks release.

## Build, install, upgrade, undo

The bundle holds the helper, the hook, the unit, the polkit rule,
`greeter-start`, `login-screen-start` and the two patched programs. `bundle.sh`
writes `PACKAGES` (see above) and `SHA256SUMS`. The installer refuses a
bundle whose packages are not installed or whose copies do not load:

    bash bundle.sh NEW_DIR PATCHED_PLASMA_LOGIN_WALLPAPER
    sudo bash NEW_DIR/install.sh

To upgrade, remove the installed version with its own bundle, then install
the new one:

    sudo bash OLD_DIR/install.sh --restore && sudo bash NEW_DIR/install.sh

The v7 installer also accepts, and then removes, the unchanged test files of
`../greeter-animation-test.sh`.

`install.sh --restore` removes everything it installed. If the login screen
does not appear: Ctrl+Alt+F3, sign in, run the restore line, then
`sudo systemctl restart plasmalogin`.

The KWin copy is built from 6.8.3 with the distribution's backports
(`../patches/kwin-6.8.3-arch-backport-*.patch`, as in Arch kwin 6.8.3-3)
plus `../patches/kwin-6.8.3-logout-vm-backdrop.patch`. The backports are
required. Without the fix for KDE bug 528936, the first host trial sent the
login prompt to the closed built-in screen and the keyboard did nothing.

## Testing in the VM

From the project directory (see [the main README](../README.md)):

- `LOGOUT_VM_HOLDER_BUNDLE=DIR bash run-vm.sh BASE NEW_RESULTS cold`: one
  logout and sign-in, with captured frames.
- With `LOGOUT_VM_THEME=DIR` added, the Vandal login theme is injected.
- With `LOGOUT_VM_HOLDER_STALE=1` added, a changed package is simulated.
- With `LOGOUT_VM_HOLDER_BROKEN=library|symbol` added, the installed KWin copy
  loses a library, or the wallpaper copy a symbol.
- `LOGOUT_VM_GREETER_FORCE_ANIMATIONS=1` turns greeter animations on (the VM's
  software renderer disables them); `LOGOUT_VM_GREETER_NO_SCALE=1` adds the
  no-animation override; `LOGOUT_VM_EFFECTS_PROBE=1` logs the effects the
  returned greeter loaded, after `LOGOUT_VM_EFFECTS_PROBE_DELAY` seconds.
- With `LOGOUT_VM_HOLDER_UPGRADE=NEW_DIR` added, the bundle above is removed
  and `NEW_DIR` installed from the desktop, with the login manager running.
- With `LOGOUT_VM_HOLDER_RESTORE=1` added, the last installed bundle is removed
  again from the desktop.
- With `LOGOUT_VM_FAILED_RELOGIN=stuck|recover` added, the first sign-in after
  logout is made to fail. `stuck` passes if no login screen follows; `recover`
  passes if one does and a second sign-in reaches a desktop.
  `LOGOUT_VM_SLOW_GREETER_STOP=SECONDS` makes the old login screen compositor
  slow to stop, so that stock fails every time.
- With `LOGOUT_VM_SHUTDOWN=reboot|halt` added, the run restarts or shuts
  down from the desktop instead. It passes only if the guest actually goes
  down.

`python3 vmsum.py RESULTS...` summarises the captured frames. Its "first
gap" also counts the black after the password (sign-in), so check by eye
which side of the login screen it is on.

## Known limits

- Restart and shutdown show what they showed without the helper (the
  screen may go black before the boot splash).
- After an update of a package in `PACKAGES`, the backdrop is gone until a
  rebuilt bundle is installed ([above](#when-the-copies-are-not-used)).
- The login screen's KWin copy runs without real-time priority
  (`cap_sys_nice`); see the comment in `install.sh`.
- The frozen frame stays readable by the next program that controls the
  display (the login screen compositor). The hook shows the desktop first,
  so open windows are not in it.
- Only one seat (`seat0`), with the login screen on console 1.
