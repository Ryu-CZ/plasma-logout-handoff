# Logout holder (first working version)

Keeps a picture on screen from Log Out until the login screen appears,
instead of black. Design and VM evidence:
[HOLDER-DESIGN.md](../HOLDER-DESIGN.md#switch-only-no-painting).

What happens at logout:

1. Plasma's logout program runs `/etc/xdg/plasma-workspace/shutdown/logout-holder`
   just before it stops the desktop. It hides the remaining windows (KWin
   "show desktop", 0.5 s), then starts `logout-holder.service`
   (allowed by a polkit rule for that unit and verb only) and waits until it
   has switched consoles, at most 5 s.
2. The helper keeps each graphics card that drives a screen open, without
   controlling it, and switches to the login screen's console in graphics
   mode. The desktop's last frame (wallpaper and panel) stays on screen.
3. The login screen's compositor (patched KWin 6.8.3) draws the login
   wallpaper underneath from its first frame; the wallpaper window
   (patched `plasma-login-wallpaper`) is transparent instead of black
   until its picture has loaded.
4. The helper exits 2 s after that compositor has the card. If none starts
   within 15 s, or the service is stopped, the console returns to text mode
   as without this helper.

Install and undo (bundle made by `bundle.sh`, which also writes `SHA256SUMS`):

    sudo bash install.sh
    sudo bash install.sh --restore

Monitor re-sync: if the login screen's display settings differ from the
desktop's (colour range, bits per colour), its first frame forces a full
modeset and the monitor shows black for a few seconds.
`sudo bash sync-greeter-outputs.sh` copies the desktop's
`kwinoutputconfig.json` to the login screen (`--restore` undoes it); re-run
after changing display settings.

If the login screen does not appear: Ctrl+Alt+F3, sign in, run the restore
line, then `sudo systemctl restart plasmalogin`.

Known limits of this first version:

- Also starts on shutdown and restart (the hook cannot tell them apart); the
  service is stopped as soon as shutdown begins.
- The login screen compositor copy runs without real-time priority
  (`cap_sys_nice`); see the comment in `install.sh`.
- After a KWin, Qt or Plasma Login Manager update, `greeter-start` runs the
  stock programs instead of the copies (no backdrop, sign-in unaffected)
  until a rebuilt bundle is installed. Built for KWin and Plasma Login
  Manager 6.8.3 only; the installer refuses other versions. The KWin copy must carry the same distribution backports
  as the installed package (`KWIN_PACKAGE` in the bundle; the first host
  trial lacked KDE bug 528936's fix, and with the lid closed the login
  prompt went to the dark built-in screen). Package updates need a rebuild.
- The frozen frame stays readable by the next program that controls the
  display (the login screen compositor).
- Only one seat (`seat0`) and the login screen on console 1.
