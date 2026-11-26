# Prior work on a seamless logout (searched 2026-11-26)

## Checked by hand

- Kernel (v7.0 source), `drm_fb_helper.c`: `drm_fb_helper_set_par()` sets
  `force` for `FB_ACTIVATE_KD_TEXT`, which commits the console even while
  a DRM master exists. The comment says this keeps a userspace ABI. This
  matches the failed "hold master" run.
- Local `drm.h`: `DRM_IOCTL_MODE_CLOSEFB` closes a framebuffer without
  disabling planes, "useful to implement flicker-free transitions between
  two processes"; the next DRM master can read the retained contents.
- Local KWin 6.8.3 work tree, `drm_buffer.cpp`: already calls
  `drmModeCloseFB`, falling back to `drmModeRmFB`.

## Idea from the above, tested in the VM

Switching to the greeter VT in graphics mode before KWin exits keeps
KWin's last frame without painting, provided a process keeps the card
open. [Results](HOLDER-DESIGN.md#switch-only-no-painting).

## Researcher report (not verified unless listed above)

Collected by Codex `gpt-6-luna`, low reasoning, web search. Several commit
pages were inaccessible; "not found" means not found in this survey. Kernel
version links are those the researcher opened.

```text
• ## Findings as of 2026-11-26

I found no upstream feature that solves the full logout-to-greeter wallpaper handoff. I did find a
kernel primitive and several useful handoff patterns, but none covers Plasma teardown, fbcon’s
restore, and greeter wallpaper readiness together. The prototype observations below are your VM
findings; I treat them as supplied evidence, not independently verified results.

### 1. Seamless logout or session switching

• KDE / Plasma Login Manager — partial fix merged and released; whole transition not found. Plasma
  6.8.0’s changelog records a Plasma Login Manager fix to take over a stale VT handler and ignore
  switch signals during session handoff. That is evidence of a specific greeter-to-session VT race
  fix, not of preserving a wallpaper on logout. Plasma 6.8.3 was released on 2026-11-10; its release
  page lists both KWin and Plasma Login Manager 6.8.3. 6.8.0 changelog
  (https://kde.org/announcements/changelogs/plasma/6/6.7.5-6.8.0/) · 6.8.3 release
  (https://kde.org/info/plasma-6.8.3/). Evidence: upstream release notes; close VT-handoff analogy,
  not an exact match.

• GNOME/GDM — an older transition animation was merged and marked fixed; it is not a logout scanout
  handoff. GNOME Bug 694062, filed in 2013 and marked “RESOLVED FIXED,” records cross-fades and a
  “fade out before starting session.” Its scope is the GDM-to-session transition. I found no
  corresponding upstream evidence of continuous wallpaper scanout across logout. Bug 694062
  (https://bugzilla.gnome.org/show_bug.cgi?id=694062). Evidence: upstream bug record; animation
  analogy only.

• COSMIC — discussed, closed as duplicate. A 2024 feature request asks for “smooth transitions
  between greeter and desktop without flickers or black screens,” illustrated for login. The issue
  does not establish an implemented transition or logout support. cosmic-comp issue 1643
  (https://github.com/pop-os/cosmic-comp/issues/1643). Evidence: project issue; login analogy.

• ChromeOS frecon — implemented handoff pattern, but a different system and lifecycle. The official
  README says frecon can wait for Chrome’s LoginScreenVisible signal before exiting and has an option
  to wait before dropping DRM master. That is a strong analogue for a persistent display owner plus
  an explicit greeter-ready signal, but it documents ChromeOS startup/login, not Plasma logout.
  frecon README (https://chromium.googlesource.com/chromiumos/platform/frecon/). Evidence: upstream
  project documentation; architecture analogue, not a direct Linux desktop solution.

• Gamescope/SteamOS — compositor exists; seamless desktop/game-mode handoff not established. Valve
  describes gamescope as a standalone DRM/KMS session compositor. I found a SteamOS issue reporting a
  blank screen while switching modes, not a handoff solution. gamescope
  (https://github.com/ValveSoftware/gamescope) · SteamOS issue 2666
  (https://github.com/ValveSoftware/SteamOS/issues/2666). Evidence: upstream project description plus
  user report; the report is anecdotal.

• SDDM, greetd/Cage, Android — no whole-transition solution found in the opened upstream material. A
  closed SDDM pull request addresses a VT signal race during the SDDM/Plasma login handoff; it is not
  evidence of a logout wallpaper hold. SDDM PR 2174 (https://github.com/sddm/sddm/pull/2174). For
  greetd/Cage and Android, I found no opened upstream source establishing the requested logout
  behavior. These are “not found in this survey,” not proof that no implementation exists.

### 2. Kernel/KMS handoff

• DRM_IOCTL_MODE_CLOSEFB — merged and released in Linux 6.8. Kernel documentation says it closes a
  framebuffer ID “without disabling planes and CRTCs,” specifically noting it is useful for
  “flicker-free transitions between two processes.” That makes it a strong fit for keeping the old
  scanout alive while another DRM client takes over. It does not retain the old image by itself,
  prevent a separate fbdev restore, or coordinate the greeter’s first wallpaper frame. The kernel
  also warns that the next DRM master may read the retained framebuffer’s contents. Linux 6.10 DRM
  UAPI documentation (https://www.kernel.org/doc/html/v6.10/gpu/drm-uapi.html) · Linux 6.8 DRM UAPI
  documentation (https://kernel.org/doc/html/v6.8/gpu/drm-uapi.html). Evidence: upstream kernel docs;
  exact primitive, partial solution.

• Compositor use is real, but I could not open the upstream commit pages. Search results point to
  wlroots switching from RMFB to CLOSEFB to avoid disabling the CRTC, and to KWin using CLOSEFB where
  available. The corresponding GitLab/Invent commit URLs were inaccessible to the browser, so I
  cannot confirm details or release versions from opened sources. Status: use is indicated, but not
  verified here to the requested standard.

• Kernel fbdev restore can be forced independently of DRM master. The DRM fb-helper restore fix
  describes the case where a process enters KD_TEXT while logind still holds a DRM FD and explains
  that the kernel must force fbdev restore. This is highly relevant to your reported mechanism, but
  it refers to the DRM fbdev emulation helper path; it is not a claim that every KMS driver behaves
  identically. Upstream DRM fb-helper commit
  (https://cgit.freedesktop.org/drm-tip/commit/?id=dc5bdb68b5b369d5bc7d1de96fa64cc1737a6320).
  Evidence: upstream kernel commit; strong mechanism match, driver/path dependent.

• Deferred fbcon takeover and flicker-free boot are boot solutions, not logout solutions. Deferred
  takeover can preserve boot framebuffer contents until console output. KDE maintainer Kai Uwe
  Broulik’s 2025 post describes boot work involving the kernel, drivers, and desktop stack, while
  still noting black frames before KSplash. Neither addresses an explicit logout-time KD_TEXT
  restore. fbcon documentation (https://origin.kernel.org/doc/html/v5.19/fb/fbcon.html) · KSplash and
  BGRT maintainer post (https://planet.kde.org/kai-uwe-broulik-2025-10-24-ksplash-bgrt/). Evidence:
  kernel docs and maintainer post; boot analogy.

### 3. systemd/logind

• VT restore races are documented, but the surfaced issue is login handoff. systemd issue 42091
  describes Session.ReleaseControl() restoring VT_AUTO before a pending switch signal is processed,
  with a resulting delay; it was reported with systemd 258.7, Linux 6.19.11, SDDM 0.21 and Plasma
  6.6.3. That is a useful timing analogue, not the reported logout/KD_TEXT problem. systemd issue
  42091 (https://github.com/systemd/systemd/issues/42091). Status: issue discussion; version-specific
  report, not a fix for this case.

• DRM-master handoff is a consumer coordination problem. systemd issue 3938 records a completed
  discussion that logind cannot assume all clients release DRM master synchronously. systemd issue
  3938 (https://github.com/systemd/systemd/issues/3938). Status: closed discussion; strong warning
  against treating logind’s device-FD lifecycle as a ready-made framebuffer handoff.

• PrepareForShutdown means system shutdown, not user logout. The login1 API defines it for poweroff,
  reboot, halt, kexec, and soft reboot. It cannot by itself distinguish logout from other session
  endings. systemd-logind API documentation
  (https://www.freedesktop.org/software/systemd/man/256/org.freedesktop.login1.html).
  Conflicts=shutdown.target plus Before=shutdown.target is a documented way for a service to stop
  during shutdown, but it does not supply a logout-start signal. systemd.special
  (https://www.freedesktop.org/software/systemd/man/261/systemd.special.html).

• The FD store preserves a service’s descriptors across its own restart; it is not a compositor
  handoff. systemd File Descriptor Store (https://systemd.io/FILE_DESCRIPTOR_STORE/). It does not
  transfer DRM master or ownership to the greeter.

### 4. Ownership, authorization, shutdown, recovery

• A narrow polkit rule appears feasible for one fixed unit and verb. systemd’s current D-Bus utility
  source shows authorization details passed for unit operations, and issue 38992 discusses
  manage-units details including unit and verb. That supports matching an exact unit and start action
  in principle; it does not make that unit safe if the caller can alter its executable or
  configuration. Keep the privileged helper fixed and tightly bounded. systemd dbus-util.c
  (https://github.com/systemd/systemd/blob/main/src/core/dbus-util.c) · systemd issue 38992
  (https://github.com/systemd/systemd/issues/38992). Evidence: upstream source plus issue discussion;
  the exact rule should be checked against the installed polkit/systemd versions.

• Keep the privileged screen holder small and time-bounded. This is an architectural recommendation,
  not a reviewed upstream “safe screen holder” design: expose a fixed start/stop operation, accept no
  caller-supplied executable or arbitrary unit properties, constrain device access and service
  privileges, and have an independent timeout that restores normal VT/display control if no greeter
  arrives. systemd documents service execution restrictions, but I did not verify a complete
  DRM-specific hardening profile. systemd.exec
  (https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html). The DRM docs’ warning
  about retained framebuffer contents also means the outgoing desktop image may contain sensitive
  data; account for that during handoff.

• Plymouth retention is for splash ownership, not greeter wallpaper readiness. plymouth quit
  --retain-splash retains the splash/VT state; Plymouth’s code distinguishes that from hiding the
  splash and switching the terminal to text. Its poweroff service is a separate shutdown-splash path.
  Plymouth source
  (https://cgit.freedesktop.org/plymouth/tree/src/main.c?id=6814c3f7429c69cc0affd06ac5e69cd6a482619b)
  · Plymouth poweroff unit
  (https://sources.debian.org/src/plymouth/26.134.222-1/systemd-units/plymouth-poweroff.service.in).
  Evidence: source and unit file; useful shutdown analogy, not a logout contract.

### 5. Greeter readiness

• Wayland presentation-time is the most reusable protocol-level signal I found. It reports when a
  committed surface update was presented, with timing tied to display presentation. That can tell a
  cooperating greeter client its surface was shown; it does not make the greeter publish a global
  “wallpaper ready” signal, and it cannot tell whether the committed content is the final image or a
  black placeholder. presentation-time protocol (https://wayland.app/protocols/presentation-time).
  Evidence: protocol documentation; strong building block, not a greeter API.

• Mutter has a first-frame signal, with important limits. Meta.WindowActor::first-frame indicates
  that initial window content was drawn and could be put on screen, but may fire when the window is
  obscured or not on the active workspace. Mutter API
  (https://mutter.gnome.org/meta/signal.WindowActor.first-frame.html). Evidence: official API docs;
  compositor-specific analogy, not proof of visibility.

• KWin/wlroots backdrop support does not solve cross-compositor handoff. A layer-shell background
  layer is a client surface within one compositor; I found no opened upstream documentation promising
  a persistent backdrop across two compositor processes. The KDE maintainer’s boot post also records
  black frames before KSplash. A greeter should therefore avoid mapping a black placeholder: load the
  image before exposing the wallpaper surface, then signal readiness only after its first presented
  frame.

## Contradictions and limits

The kernel primitive explicitly supports a two-process flicker-free transition, while the fbdev
helper has a separate forced-restore path on KD_TEXT. Those facts are compatible: CLOSEFB may
preserve an active plane through one DRM client’s framebuffer cleanup, yet another console/fbdev
action can still change what is scanned out.

The frecon pattern demonstrates persistent display ownership and explicit readiness, but it is not
evidence that a desktop greeter or logind offers the same lifecycle hooks. Likewise, GNOME’s resolved
cross-fade and Plasma’s released VT fix solve narrower animation or VT problems. I did not find an
opened upstream source validating the complete VM prototype on Intel, virtio-gpu, kernel 7.3, and
Plasma 6.8.3.

Some direct commit pages for wlroots and KWin were inaccessible; I have not treated their search-
result snippets as confirmed release evidence. I also did not obtain a usable direct bugs.kde.org
page for an exact logout-wallpaper report. Forum/user reports, including the SteamOS blank-screen
report, are anecdotes and are labeled as such above.

## Five reusable items and a small test for each

1. CLOSEFB: make a minimal two-DRM-client experiment: client A scans out a dumb buffer, closes its FB
   with CLOSEFB, then client B becomes master and sets its own mode. Record whether the old image
   remains until B’s modeset on each target driver.

2. KD_TEXT/fbdev restore: repeat the handoff while tracing KDSETMODE, VT switches, DRM master
   changes, and fbdev restore events. Compare KD_TEXT with leaving the greeter VT in KD_GRAPHICS.

3. Frecon-style ownership: keep a fixed relay alive and release it only on an explicit greeter-ready
   message. Test both successful greeter startup and a forced greeter crash; verify the timeout
   returns the VT to a usable state.

4. Presented-frame readiness: have the greeter load the real wallpaper before mapping it, request
   presentation-time feedback, and report readiness only after the wallpaper-bearing commit is
   presented. Confirm the signal per output and test a deliberately delayed image decode.

5. Logout versus shutdown authorization: trigger logout, session switch, reboot, and poweroff
   separately while logging the helper’s start/stop and PrepareForShutdown events. Verify only logout
   starts the holder, and shutdown ordering always stops it.

```
