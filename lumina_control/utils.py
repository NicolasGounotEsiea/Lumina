"""Low-level utilities: monitor wake, active screen detection, gamma ramp."""
import ctypes
import ctypes.wintypes
import logging
import os

import win32api
import win32con
import win32gui
import win32process
from PySide6.QtGui import QCursor

log = logging.getLogger(__name__)


def wake_all_monitors() -> None:
    """Simulate a tiny mouse movement to wake sleeping monitors."""
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 1, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, -1, -1, 0, 0)


def get_active_screen_index() -> int:
    """Return the index of the screen that currently contains the cursor."""
    from screeninfo import get_monitors
    pos = QCursor.pos()
    for i, m in enumerate(get_monitors()):
        if m.x <= pos.x() < m.x + m.width and m.y <= pos.y() < m.y + m.height:
            return i
    return 0


# ── Gamma correction (Windows GDI32) ─────────────────────────────────────────

def _build_gamma_ramp(gamma: float):
    gamma = max(0.5, min(3.0, float(gamma)))
    ramp = (ctypes.c_ushort * (256 * 3))()
    for i in range(256):
        v = min(65535, int(pow(i / 255.0, 1.0 / gamma) * 65535 + 0.5))
        ramp[i] = v
        ramp[256 + i] = v
        ramp[512 + i] = v
    return ramp


def set_device_gamma(device_name: str | None, gamma: float) -> bool:
    """Apply gamma ramp to *device_name* via SetDeviceGammaRamp. Returns success."""
    if not device_name:
        return False
    hdc = ctypes.windll.gdi32.CreateDCW("DISPLAY", device_name, None, None)
    if not hdc:
        return False
    ramp = _build_gamma_ramp(gamma)
    ok = bool(ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)))
    ctypes.windll.gdi32.DeleteDC(hdc)
    return ok


def reset_gamma_all() -> None:
    """Reset all monitors to gamma 1.0 (linear)."""
    from screeninfo import get_monitors
    for m in get_monitors():
        device = getattr(m, "name", None) or getattr(m, "device", None)
        set_device_gamma(device, 1.0)


def set_gamma_all(gamma: float) -> None:
    """Apply *gamma* to all monitors."""
    from screeninfo import get_monitors
    for m in get_monitors():
        device = getattr(m, "name", None) or getattr(m, "device", None)
        set_device_gamma(device, gamma)


# ── Foreground process detection ──────────────────────────────────────────────

def get_user_processes() -> list[tuple[str, str]]:
    """Return ``[(exe_name, window_title)]`` for all user-visible windows.

    Deduplicated by exe name (longest window title kept as representative).
    Sorted alphabetically by exe name.  Never raises.
    """
    results: dict[str, str] = {}

    def _cb(hwnd, _) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid:
                return True
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not h:
                return True
            buf  = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            ctypes.windll.kernel32.CloseHandle(h)
            if buf.value:
                exe = os.path.basename(buf.value).lower()
                if exe not in results or len(title) > len(results[exe]):
                    results[exe] = title
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    return sorted(results.items())


def get_foreground_window_monitor() -> str | None:
    """Return the device name (e.g. r'\\\\.\\DISPLAY1') of the monitor that
    contains the current foreground window.  Returns None on any failure."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        MONITOR_DEFAULTTONEAREST = 2
        hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None

        class _MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize",    ctypes.c_ulong),
                ("rcMonitor", ctypes.wintypes.RECT),
                ("rcWork",    ctypes.wintypes.RECT),
                ("dwFlags",   ctypes.c_ulong),
                ("szDevice",  ctypes.c_wchar * 32),
            ]

        info = _MONITORINFOEX()
        info.cbSize = ctypes.sizeof(_MONITORINFOEX)
        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return info.szDevice
        return None
    except Exception:
        return None


def get_foreground_process() -> str | None:
    """Return the exe filename (lowercase) of the current foreground window.

    Uses ``QueryFullProcessImageNameW`` to avoid needing PROCESS_VM_READ
    rights; returns ``None`` on any failure.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return None
        PROCESS_QUERY_LIMITED = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            return None
        buf  = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(1024)
        ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        ctypes.windll.kernel32.CloseHandle(h)
        return os.path.basename(buf.value).lower() if buf.value else None
    except Exception:
        return None
