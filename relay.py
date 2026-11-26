"""VM research prototype: keep a picture on screen between desktop and greeter.

Prepare a framebuffer while the desktop still owns the display. Whenever the
display has no owner and shows something else, take DRM master, show the
picture and drop master at once. Never take master while the greeter's
compositor process exists: logind needs it for that compositor.

Disposable guest only. The picture is a solid colour so captures can identify it.
"""
import ctypes as c
import glob
import mmap
import os
import pwd
import sys
import time

COLOR = 0x00FF8000  # orange
u8, u16, u32, u64 = c.c_uint8, c.c_uint16, c.c_uint32, c.c_uint64
P = c.POINTER


class Mode(c.Structure):
    _fields_ = [("clock", u32)] + [(n, u16) for n in (
        "hdisplay", "hsync_start", "hsync_end", "htotal", "hskew",
        "vdisplay", "vsync_start", "vsync_end", "vtotal", "vscan")] + [
        ("vrefresh", u32), ("flags", u32), ("type", u32), ("name", c.c_char * 32)]


class Resources(c.Structure):
    _fields_ = [("count_fbs", c.c_int), ("fbs", P(u32)),
                ("count_crtcs", c.c_int), ("crtcs", P(u32)),
                ("count_connectors", c.c_int), ("connectors", P(u32)),
                ("count_encoders", c.c_int), ("encoders", P(u32)),
                ("min_width", u32), ("max_width", u32),
                ("min_height", u32), ("max_height", u32)]


class Crtc(c.Structure):
    _fields_ = [("crtc_id", u32), ("buffer_id", u32), ("x", u32), ("y", u32),
                ("width", u32), ("height", u32), ("mode_valid", c.c_int),
                ("mode", Mode), ("gamma_size", c.c_int)]


class Connector(c.Structure):
    # Leading fields of drmModeConnector; the rest is not read.
    _fields_ = [("connector_id", u32), ("encoder_id", u32)]


class Encoder(c.Structure):
    _fields_ = [("encoder_id", u32), ("encoder_type", u32), ("crtc_id", u32)]


drm = c.CDLL("libdrm.so.2", use_errno=True)
for name, result, args in (
        ("drmModeGetResources", P(Resources), [c.c_int]),
        ("drmModeFreeResources", None, [P(Resources)]),
        ("drmModeGetCrtc", P(Crtc), [c.c_int, u32]),
        ("drmModeFreeCrtc", None, [P(Crtc)]),
        ("drmModeGetConnectorCurrent", P(Connector), [c.c_int, u32]),
        ("drmModeFreeConnector", None, [P(Connector)]),
        ("drmModeGetEncoder", P(Encoder), [c.c_int, u32]),
        ("drmModeFreeEncoder", None, [P(Encoder)]),
        ("drmModeCreateDumbBuffer", c.c_int,
         [c.c_int, u32, u32, u32, u32, P(u32), P(u32), P(u64)]),
        ("drmModeMapDumbBuffer", c.c_int, [c.c_int, u32, P(u64)]),
        ("drmModeAddFB", c.c_int, [c.c_int, u32, u32, u8, u8, u32, u32, P(u32)]),
        ("drmModeSetCrtc", c.c_int,
         [c.c_int, u32, u32, u32, u32, P(u32), c.c_int, P(Mode)]),
        ("drmSetMaster", c.c_int, [c.c_int]),
        ("drmDropMaster", c.c_int, [c.c_int])):
    function = getattr(drm, name)
    function.restype, function.argtypes = result, args


def log(*words):
    print(f"{time.monotonic():.6f}", *words, flush=True)


def check(code, what):
    if code:
        raise OSError(c.get_errno(), what)


def read_crtc(fd, crtc_id):
    pointer = drm.drmModeGetCrtc(fd, crtc_id)
    if not pointer:
        raise OSError(c.get_errno(), "drmModeGetCrtc")
    copy = Crtc.from_buffer_copy(pointer.contents)
    drm.drmModeFreeCrtc(pointer)
    return copy


def find_output():
    for path in sorted(glob.glob("/dev/dri/card*")):
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
        # An unowned card grants master to whoever opens it: give it back.
        drm.drmDropMaster(fd)
        resources = drm.drmModeGetResources(fd)
        if resources:
            res = resources.contents
            for index in range(res.count_connectors):
                connector = drm.drmModeGetConnectorCurrent(fd, res.connectors[index])
                if not connector:
                    continue
                connector_id = connector.contents.connector_id
                encoder_id = connector.contents.encoder_id
                drm.drmModeFreeConnector(connector)
                encoder = drm.drmModeGetEncoder(fd, encoder_id) if encoder_id else None
                if not encoder:
                    continue
                crtc_id = encoder.contents.crtc_id
                drm.drmModeFreeEncoder(encoder)
                if crtc_id and read_crtc(fd, crtc_id).mode_valid:
                    drm.drmModeFreeResources(resources)
                    return path, fd, crtc_id, connector_id
            drm.drmModeFreeResources(resources)
        os.close(fd)
    raise RuntimeError("no active output")


def make_picture(fd, width, height):
    handle, pitch, size, offset, fb = u32(), u32(), u64(), u64(), u32()
    check(drm.drmModeCreateDumbBuffer(fd, width, height, 32, 0, handle, pitch, size), "create")
    check(drm.drmModeAddFB(fd, width, height, 24, 32, pitch, handle, fb), "addfb")
    check(drm.drmModeMapDumbBuffer(fd, handle, offset), "map")
    with mmap.mmap(fd, size.value, offset=offset.value) as pixels:
        row = COLOR.to_bytes(4, "little") * (pitch.value // 4)
        pixels.write(row * height)
    return fb.value


def greeter_compositor(uid):
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            with open(f"/proc/{entry.name}/comm") as comm:
                if comm.read().startswith("kwin_wayland"):
                    return True
        except OSError:
            pass  # The process exited while we looked.
    return False


def main():
    uid = pwd.getpwnam(sys.argv[1] if len(sys.argv) > 1 else "plasmalogin").pw_uid
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 30
    if greeter_compositor(uid):
        raise RuntimeError("a greeter compositor is already running")
    path, fd, crtc_id, connector_id = find_output()
    mode = read_crtc(fd, crtc_id).mode
    picture = make_picture(fd, mode.hdisplay, mode.vdisplay)
    connectors = (u32 * 1)(connector_id)
    log("READY", path, f"crtc={crtc_id}", f"fb={picture}",
        f"{mode.hdisplay}x{mode.vdisplay}")
    replaced = set()
    seen = None
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        current = read_crtc(fd, crtc_id).buffer_id
        if current != seen:
            log("SCANOUT", f"fb={current}")
            seen = current
        # Check for the greeter immediately before any attempt to take master.
        if current != picture:
            if greeter_compositor(uid):
                if replaced and current and current not in replaced:
                    log("DONE greeter owns the output")
                    return
            elif drm.drmSetMaster(fd) == 0:
                start = time.monotonic()
                try:
                    before = read_crtc(fd, crtc_id).buffer_id
                    code = drm.drmModeSetCrtc(fd, crtc_id, picture, 0, 0,
                                              connectors, 1, c.byref(mode))
                    error = c.get_errno()
                finally:
                    check(drm.drmDropMaster(fd), "drop master")
                held = (time.monotonic() - start) * 1000
                log("PAINT" if code == 0 else f"PAINT_FAILED errno={error}",
                    f"over={before}", f"held_ms={held:.2f}")
                if code == 0:
                    replaced.add(before)
        time.sleep(.001)
    log("TIMEOUT")
    # Nobody took over: put the console's buffer back if the display is free.
    if replaced and read_crtc(fd, crtc_id).buffer_id == picture \
            and not greeter_compositor(uid) and drm.drmSetMaster(fd) == 0:
        console = max(replaced - {0}, default=0)
        if console:
            drm.drmModeSetCrtc(fd, crtc_id, console, 0, 0, connectors, 1, c.byref(mode))
        drm.drmDropMaster(fd)
        log("RESTORED", f"fb={console}")


if __name__ == "__main__":
    main()
