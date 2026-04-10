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
    hz:            float | None = None
    ddc_handle:    Any          = None  # monitorcontrol Monitor, or None if no DDC-CI
    position_hint: str          = ""    # e.g. "Gauche  ·  Principal" — set by enumerate_monitors

    @property
    def label(self) -> str:
        base = _("Écran {}").format(self.index + 1)
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

        g   = geo.get(dev, {})
        hz  = _get_hz(dev)

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
        ))

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
