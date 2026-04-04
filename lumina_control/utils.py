"""Low-level utilities: monitor wake, active screen detection, gamma ramp."""
import ctypes
import logging

import win32api
import win32con
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
