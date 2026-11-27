# Prior work on a logout without black (searched 2026-11-26)

No upstream feature found that covers the whole logout-to-greeter wallpaper
handoff. A kernel primitive and several partial patterns exist. "Not found"
means not found in this survey.

## Checked by hand

| Source | Finding |
| --- | --- |
| Linux v7.0 `drm_fb_helper.c` | `drm_fb_helper_set_par()` sets `force` for `FB_ACTIVATE_KD_TEXT`, committing the console even with a DRM master. The comment says this keeps a userspace ABI. Matches the failed "hold master" run |
| Local `drm.h` | `DRM_IOCTL_MODE_CLOSEFB` closes a framebuffer without disabling planes, "useful to implement flicker-free transitions between two processes"; the next master can read the contents |
| Local KWin 6.8.3 `drm_buffer.cpp` | already calls `drmModeCloseFB`, falling back to `drmModeRmFB` |

Idea from these, tested in the VM: switch to the greeter VT in graphics mode
before KWin exits, with a process keeping the card open. KWin's last frame
stays ([result](docs/LOG.md#relay-vm-switch-only-no-painting-switch-batchumt8ha-ab6c4c2)).

## Researcher report

Collected by Codex `gpt-6-luna`, low reasoning, web search. **Not verified**
unless also listed above. It took our VM findings as given. Version links are
those the researcher opened.

### Logout and session switching

| Project | Finding | Evidence and fit |
| --- | --- | --- |
| Plasma Login Manager | 6.8.0 fixes taking over a stale VT handler and ignoring switch signals during handoff. KWin and PLM 6.8.3 released 2026-11-10 ([changelog](https://kde.org/announcements/changelogs/plasma/6/6.7.5-6.8.0/), [release](https://kde.org/info/plasma-6.8.3/)) | release notes; a VT race, not a wallpaper handoff |
| GNOME / GDM | [Bug 694062](https://bugzilla.gnome.org/show_bug.cgi?id=694062) (2013, fixed): cross-fades and "fade out before starting session" | login direction; animation only |
| COSMIC | [cosmic-comp 1643](https://github.com/pop-os/cosmic-comp/issues/1643) (2024) asks for smooth greeter/desktop transitions; closed as duplicate | login analogy; no implementation shown |
| ChromeOS frecon | can wait for `LoginScreenVisible` before exiting, and delay dropping DRM master ([README](https://chromium.googlesource.com/chromiumos/platform/frecon/)) | persistent owner plus ready signal; boot and login, not Plasma logout |
| Gamescope / SteamOS | standalone DRM/KMS compositor ([gamescope](https://github.com/ValveSoftware/gamescope)); [SteamOS 2666](https://github.com/ValveSoftware/SteamOS/issues/2666) reports a blank screen on mode switch | user report, anecdotal; no handoff solution |
| SDDM | closed [PR 2174](https://github.com/sddm/sddm/pull/2174) fixes a VT signal race at login | not a logout hold |
| greetd / Cage, Android | no logout behaviour found | not proof none exists |

### Kernel and KMS

| Topic | Finding | Limit |
| --- | --- | --- |
| `DRM_IOCTL_MODE_CLOSEFB` (Linux 6.8) | closes a framebuffer "without disabling planes and CRTCs" ([6.10 docs](https://www.kernel.org/doc/html/v6.10/gpu/drm-uapi.html), [6.8 docs](https://kernel.org/doc/html/v6.8/gpu/drm-uapi.html)) | does not stop fbdev restore or coordinate the greeter's first frame; the next master may read the content |
| Compositor use of CLOSEFB | search results say wlroots moved from RMFB, and KWin uses it where available | commit pages not opened; unconfirmed there (KWin checked by hand above) |
| fbdev restore | forced when a process enters `KD_TEXT` while logind holds a DRM fd ([commit](https://cgit.freedesktop.org/drm-tip/commit/?id=dc5bdb68b5b369d5bc7d1de96fa64cc1737a6320)) | fbdev emulation path; not every driver |
| Deferred fbcon takeover | keeps boot framebuffer until console output ([fbcon docs](https://origin.kernel.org/doc/html/v5.19/fb/fbcon.html)); a [KDE post](https://planet.kde.org/kai-uwe-broulik-2025-10-24-ksplash-bgrt/) still notes black frames before KSplash | boot only |

CLOSEFB can keep a plane through one client's cleanup while a console restore
still changes the scanout. The two facts are compatible.

### systemd and logind

| Topic | Finding |
| --- | --- |
| VT restore race | [systemd 42091](https://github.com/systemd/systemd/issues/42091): `Session.ReleaseControl()` restores `VT_AUTO` before a pending switch signal, causing delay (systemd 258.7, Linux 6.19.11, SDDM 0.21, Plasma 6.6.3). Login handoff, not this problem |
| DRM master release | [systemd 3938](https://github.com/systemd/systemd/issues/3938) (closed): logind cannot assume clients release master synchronously |
| `PrepareForShutdown` | poweroff, reboot, halt, kexec, soft reboot only; cannot identify a logout ([API](https://www.freedesktop.org/software/systemd/man/256/org.freedesktop.login1.html)) |
| Shutdown ordering | `Conflicts=` plus `Before=shutdown.target` stops a service at shutdown; no logout-start signal ([systemd.special](https://www.freedesktop.org/software/systemd/man/261/systemd.special.html)) |
| FD store | keeps a service's descriptors across its own restart; no master or ownership transfer ([doc](https://systemd.io/FILE_DESCRIPTOR_STORE/)) |

### Authorization and safety

- A polkit rule for one unit and verb looks feasible
  ([dbus-util.c](https://github.com/systemd/systemd/blob/main/src/core/dbus-util.c),
  [systemd 38992](https://github.com/systemd/systemd/issues/38992)). Check
  against installed versions. It is unsafe if the caller can change the
  executable or configuration.
- Recommendation (not an upstream design): fixed start/stop only, no
  caller-supplied executable or properties, limited device access, independent
  timeout that restores VT control. No DRM-specific hardening profile was
  verified ([systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)).
- The retained framebuffer may hold sensitive desktop content.
- `plymouth quit --retain-splash` keeps splash and VT state; shutdown has its
  own splash path
  ([source](https://cgit.freedesktop.org/plymouth/tree/src/main.c?id=6814c3f7429c69cc0affd06ac5e69cd6a482619b),
  [unit](https://sources.debian.org/src/plymouth/26.134.222-1/systemd-units/plymouth-poweroff.service.in)).
  Shutdown analogy only.

### Greeter readiness

| Signal | Finding |
| --- | --- |
| Wayland [presentation-time](https://wayland.app/protocols/presentation-time) | reports when a surface update was presented; not a global "wallpaper ready" signal, and cannot tell a black placeholder from the image |
| Mutter [`first-frame`](https://mutter.gnome.org/meta/signal.WindowActor.first-frame.html) | content drawn; may fire while obscured or on another workspace |
| Layer-shell background (KWin, wlroots) | lives in one compositor; no promise across two |

A greeter should load the image before showing its wallpaper surface, and
report ready only after that frame is presented.

### Limits of the survey

- Nothing opened validates the whole prototype on Intel, virtio-gpu, kernel
  7.3 and Plasma 6.8.3.
- Some wlroots and KWin commit pages were inaccessible. Search snippets are not
  counted as release evidence.
- No usable bugs.kde.org report for logout wallpaper was found.
- Forum and user reports are anecdotes.

### Suggested tests

| Idea | Test |
| --- | --- |
| CLOSEFB | client A scans out a dumb buffer and closes it with CLOSEFB; client B becomes master and sets a mode; record per driver whether the image stays until then |
| fbdev restore | trace `KDSETMODE`, VT switches, master changes and restore events; compare `KD_TEXT` with `KD_GRAPHICS` on the greeter VT |
| frecon-style relay | release only on a greeter-ready message; test success and a forced greeter crash; the timeout must leave a usable VT |
| Presented-frame readiness | load the wallpaper before mapping, use presentation-time, report per output; delay the image decode on purpose |
| Logout vs shutdown | run logout, session switch, reboot and poweroff, logging helper start/stop and `PrepareForShutdown`; only logout may use the holder, shutdown must stop it |
