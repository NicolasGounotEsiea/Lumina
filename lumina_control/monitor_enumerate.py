"""Stable monitor enumeration using Windows API.

Matches DDC-CI handles from ``monitorcontrol`` to display geometry from
``screeninfo`` via the Windows HMONITOR device name, avoiding the fragile
zip-by-index approach that silently misaligns monitors when one display lacks
DDC-CI support.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from dataclasses import dataclass
from typing import Any

from lumina_control.i18n import _

log = logging.getLogger(__name__)

# ── Windows structs ───────────────────────────────────────────────────────────

class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize",    ctypes.c_ulong),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork",    ctypes.wintypes.RECT),
        ("dwFlags",   ctypes.c_ulong),
        ("szDevice",  ctypes.c_wchar * 32),
    ]

_MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool,
    ctypes.wintypes.HMONITOR,
    ctypes.wintypes.HDC,
    ctypes.POINTER(ctypes.wintypes.RECT),
    ctypes.wintypes.LPARAM,
)

_user32 = ctypes.windll.user32
_dxva2  = ctypes.windll.dxva2

# ── Public dataclass ──────────────────────────────────────────────────────────

@dataclass
class MonitorDescriptor:
    """One logical display with geometry and optional DDC-CI handle."""
    index:         int
    device_name:   str         # e.g. r"\\.\DISPLAY1"
    x:             int
    y:             int
    width:         int
    height:        int
    is_primary:    bool
    hz:                float | None = None
    ddc_handle:        Any          = None  # monitorcontrol Monitor, or None if no DDC-CI
    position_hint:     str          = ""    # e.g. "Gauche  ·  Principal" — set by enumerate_monitors
    model_name:        str | None   = None  # e.g. "Dell U2722D" — from EnumDisplayDevices EDID
    brightness_backend: str         = "none"  # "ddc" | "wmi" | "none"
    wmi_index:         int | None   = None   # index into WmiMonitorBrightnessMethods()
    hdr_info:          Any          = None   # HdrInfo | None — populated after enumeration

    @property
    def label(self) -> str:
        base = self.model_name if self.model_name else _("Écran {}").format(self.index + 1)
        if self.position_hint:
            return f"{base}  —  {self.position_hint}"
        return base

    @property
    def details(self) -> str:
        parts: list[str] = []
        if self.width and self.height:
            parts.append(f"{self.width}×{self.height}")
        if self.hz:
            try:
                parts.append(f"{int(round(self.hz))} Hz")
            except (ValueError, TypeError):
                parts.append(f"{self.hz} Hz")
        return "  ·  ".join(parts) if parts else _("Écran détecté")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _enum_hmonitors() -> list[tuple[int, str, bool]]:
    """Return ``(hmonitor, device_name, is_primary)`` in Windows enumeration order."""
    results: list[tuple[int, str, bool]] = []

    def _cb(hmon: int, _hdc, _rect, _lparam) -> bool:
        info = _MONITORINFOEX()
        info.cbSize = ctypes.sizeof(_MONITORINFOEX)
        if _user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            is_primary = bool(info.dwFlags & 1)
            results.append((hmon, info.szDevice, is_primary))
        return True

    _user32.EnumDisplayMonitors(None, None, _MONITORENUMPROC(_cb), 0)
    return results


def _ddc_count(hmonitor: int) -> int:
    """Return how many physical DDC-CI monitors are behind *hmonitor*."""
    n = ctypes.c_ulong(0)
    try:
        if _dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, ctypes.byref(n)):
            return n.value
    except Exception:
        pass
    return 0


def _get_hz(device_name: str) -> float | None:
    """Return the current refresh rate for *device_name* (best-effort)."""
    try:
        import win32api
        import win32con
        dm = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)
        return float(dm.DisplayFrequency)
    except Exception:
        return None


def _count_wmi_brightness_monitors() -> int:
    """Return the number of WMI-controllable brightness monitors (laptop screens).

    Returns 0 if WMI is unavailable or no brightness-capable monitors exist.
    """
    try:
        import wmi as _wmi
        c = _wmi.WMI(namespace="wmi")
        return len(c.WmiMonitorBrightness())
    except Exception:
        return 0


def _parse_edid_name(edid: bytes) -> str | None:
    """Extract the monitor name from an EDID blob (128+ bytes).

    Scans the four 18-byte descriptor blocks starting at offset 54 for a
    'Monitor Name' descriptor (tag byte 0xFC) and returns its ASCII content.
    """
    if len(edid) < 128:
        return None
    for offset in range(54, 126, 18):
        block = edid[offset: offset + 18]
        if len(block) < 18:
            break
        # Monitor Name descriptor: header bytes 0x00 0x00 0x00 0xFC 0x00
        if block[0] == 0 and block[1] == 0 and block[2] == 0 and block[3] == 0xFC and block[4] == 0:
            raw = block[5:18].decode("ascii", errors="replace")
            name = raw.split("\n")[0].strip()
            if name:
                return name
    return None


def _get_name_from_edid_registry(monitor_class: str) -> str | None:
    """Return the monitor name by reading EDID from the Windows registry.

    Looks up ``HKLM\\SYSTEM\\CurrentControlSet\\Enum\\DISPLAY\\<monitor_class>``
    and parses the first EDID found.  Works for monitors reported as
    'Generic PnP Monitor' by the GDI driver.
    """
    try:
        import winreg
        base = fr"SYSTEM\CurrentControlSet\Enum\DISPLAY\{monitor_class}"
        key  = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
        n_instances = winreg.QueryInfoKey(key)[0]
        for i in range(n_instances):
            try:
                inst = winreg.EnumKey(key, i)
                dp   = winreg.OpenKey(key, inst + r"\Device Parameters")
                edid, _ = winreg.QueryValueEx(dp, "EDID")
                name = _parse_edid_name(bytes(edid))
                if name:
                    return name
            except (FileNotFoundError, OSError, PermissionError):
                continue
    except Exception:
        pass
    return None


def _get_model_name(device_name: str) -> str | None:
    """Return the monitor model name for *device_name* (e.g. 'LG ULTRAWIDE').

    Strategy:
    1. ``EnumDisplayDevices`` — fast, works when the driver exposes the name.
    2. EDID registry fallback — reads the raw EDID from
       ``HKLM\\SYSTEM\\CurrentControlSet\\Enum\\DISPLAY\\<model>`` and parses
       the 'Monitor Name' descriptor.  Covers virtually all PnP monitors even
       when GDI only reports 'Generic PnP Monitor'.
    """
    try:
        import win32api
        dd = win32api.EnumDisplayDevices(device_name, 0, 0)
        # Path 1: driver reports a non-generic name directly
        name = (dd.DeviceString or "").strip()
        if name and name.lower() not in ("plug and play monitor", "generic pnp monitor", ""):
            return name
        # Path 2: EDID registry lookup via the hardware DeviceID
        # DeviceID format: MONITOR\<ModelClass>\{...}\NNN
        device_id = getattr(dd, "DeviceID", "") or ""
        parts = device_id.split("\\")
        if len(parts) >= 2:
            monitor_class = parts[1]
            return _get_name_from_edid_registry(monitor_class)
    except Exception:
        pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def enumerate_monitors() -> list[MonitorDescriptor]:
    """Return one :class:`MonitorDescriptor` per logical display.

    DDC-CI handles from ``monitorcontrol.get_monitors()`` are assigned in
    Windows enumeration order, skipping HMONITORs that report zero physical
    monitors (no DDC-CI).  Geometry comes from ``screeninfo``, matched by
    device name so no positional alignment is required.
    """
    # ── Gather DDC-CI handles ─────────────────────────────────────────────────
    try:
        from monitorcontrol import get_monitors as mc_monitors
        ddc_handles = list(mc_monitors())
    except Exception as e:
        log.warning("monitorcontrol unavailable: %s", e)
        ddc_handles = []

    # ── Gather geometry from screeninfo (indexed by device name) ─────────────
    geo: dict[str, dict] = {}
    try:
        from screeninfo import get_monitors as si_monitors
        for m in si_monitors():
            name = getattr(m, "name", None) or getattr(m, "device", None) or ""
            geo[name] = {
                "x":      getattr(m, "x", 0),
                "y":      getattr(m, "y", 0),
                "width":  getattr(m, "width", 0),
                "height": getattr(m, "height", 0),
            }
    except Exception as e:
        log.warning("screeninfo unavailable: %s", e)

    # ── Enumerate HMONITORs and correlate ────────────────────────────────────
    hmons = _enum_hmonitors()
    descriptors: list[MonitorDescriptor] = []
    ddc_idx = 0

    for idx, (hmon, dev, is_primary) in enumerate(hmons):
        n_phys = _ddc_count(hmon)

        # Consume one DDC handle per physical monitor behind this HMONITOR.
        # Typically n_phys is 0 (no DDC-CI) or 1; rarely 2+ (e.g. a splitter).
        assigned: Any = None
        for _i in range(n_phys):
            if ddc_idx < len(ddc_handles):
                if assigned is None:
                    assigned = ddc_handles[ddc_idx]
                ddc_idx += 1

        g          = geo.get(dev, {})
        hz         = _get_hz(dev)
        model_name = _get_model_name(dev)

        descriptors.append(MonitorDescriptor(
            index       = idx,
            device_name = dev,
            x           = g.get("x", 0),
            y           = g.get("y", 0),
            width       = g.get("width", 0),
            height      = g.get("height", 0),
            is_primary  = is_primary,
            hz          = hz,
            ddc_handle  = assigned,
            model_name  = model_name,
        ))

    # ── Assign brightness backends ────────────────────────────────────────────
    # DDC monitors get the 'ddc' backend immediately.
    # DDC-less monitors (laptop panels, unsupported external) are matched to
    # WMI brightness instances positionally — first DDC-less → WMI index 0, etc.
    wmi_count = _count_wmi_brightness_monitors()
    wmi_idx   = 0
    for d in descriptors:
        if d.ddc_handle is not None:
            d.brightness_backend = "ddc"
        elif wmi_idx < wmi_count:
            d.brightness_backend = "wmi"
            d.wmi_index = wmi_idx
            wmi_idx += 1
        else:
            d.brightness_backend = "none"

    # ── HDR info (best-effort, swallows all errors) ───────────────────────────
    try:
        from lumina_control.hdr import get_hdr_info
        for d in descriptors:
            d.hdr_info = get_hdr_info(d.device_name)
    except Exception as e:
        log.warning("HDR detection failed: %s", e)

    # ── Compute position hints (Gauche / Droite / Principal …) ───────────────
    _attach_position_hints(descriptors)

    return descriptors


def _attach_position_hints(descriptors: list[MonitorDescriptor]) -> None:
    """Set ``position_hint`` on each descriptor based on physical layout.

    For a single monitor no hint is added.
    For two or more, monitors are sorted by their dominant axis (horizontal
    spread → Gauche/Droite, vertical spread → Haut/Bas) and labelled
    accordingly.  The primary monitor gets an extra "Principal" tag.
    """
    if len(descriptors) < 2:
        if descriptors and descriptors[0].is_primary:
            descriptors[0].position_hint = _("Principal")
        return

    xs = [d.x for d in descriptors]
    ys = [d.y for d in descriptors]
    horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))

    if horizontal:
        ordered = sorted(descriptors, key=lambda d: d.x)
        edge_names = {0: _("Gauche"), len(descriptors) - 1: _("Droite")}
        middle_name = _("Centre")
    else:
        ordered = sorted(descriptors, key=lambda d: d.y)
        edge_names = {0: _("Haut"), len(descriptors) - 1: _("Bas")}
        middle_name = _("Centre")

    for rank, d in enumerate(ordered):
        parts = [edge_names.get(rank, middle_name)]
        if d.is_primary:
            parts.append(_("Principal"))
        d.position_hint = "  ·  ".join(parts)
