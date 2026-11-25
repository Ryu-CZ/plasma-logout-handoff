# NVIDIA 620.70.06: intermittent head-0 flip timeouts during Plasma Wayland logout

**Status:** Draft for the [NVIDIA Linux forum](https://forums.developer.nvidia.com/c/gpu-graphics/linux/148), not filed. The running module is proprietary, so the open-kernel-module issue tracker is not the right venue.

## Environment

- Manjaro, kernel `7.3.4-3-MANJARO`, proprietary NVIDIA module `620.70.06`.
- GeForce RTX 4090; DisplayPort output at 3840×2160, 144 Hz on the desktop.
- KWin `6.8.2-2` (Plasma Wayland), SDDM `0.21.0-7` with its stock X11 greeter.
- `nvidia_drm` modesetting and fbdev enabled.

## Steps and results

1. Sign in to Plasma Wayland and use the 4K 144 Hz DisplayPort mode.
2. Use Plasma’s normal **Log Out** action and wait for the SDDM greeter.
3. Check the kernel journal around teardown. Sign back in normally.

In two of three instrumented logout traces, the driver logged two head-0 flip timeouts roughly three seconds apart during teardown. A DRM debugfs sample took about six seconds to complete in each of those runs. SDDM eventually returned and re-login worked. The third trace returned without these warnings, despite a visible blackout. This report is about the **intermittent stalls and kernel warnings**, not the ordinary logout blink.

Representative kernel lines, with host metadata omitted:

```text
22503.165 [drm:nv_drm_atomic_commit [nvidia_drm]] *ERROR* [nvidia-drm] [GPU ID 0x00000100] Flip event timeout on head 0
22506.173 [drm:nv_drm_atomic_commit [nvidia_drm]] *ERROR* [nvidia-drm] [GPU ID 0x00000100] Flip event timeout on head 0
```

The other affected run also logged `WARNING: nvidia-drm/nvidia-drm-crtc.h:371 at __nv_drm_handle_flip_event`. In the affected run with framebuffer attribution, the last completed sample showed KWin buffers at 4K 144 Hz. The blocked sample returned with an active 4K 60 Hz CRTC and a framebuffer allocated by `[fbcon]`, still on the outgoing VT. Xorg launched afterward. This brackets the transition but does not identify the commit caller, prove DisplayPort retraining, or establish what caused the timeouts.

**Expected:** Logout completes and the greeter returns without flip-event timeouts or kernel warnings.

Related but different: [NVIDIA issue #1553](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1553) reports a similar warning on the same driver version during cold boot with four displays and the open module. This report does not assume a common cause.

## Before posting

NVIDIA’s [Linux reporting instructions](https://forums.developer.nvidia.com/t/if-you-have-a-problem-please-read-this-first/27131) request an `nvidia-bug-report.log.gz`. No diagnostic bundle is attached. Review any bundle for private system or session details before sharing; do not put it, raw journals, or video in the public repository. The [investigation record](README.md#stock-x11-with-framebuffer-attribution-2340) documents the measurements separately.
