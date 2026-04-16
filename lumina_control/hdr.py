"""HDR / advanced-colour control via Win32 DisplayConfig API.

Public API
----------
    get_hdr_info(device_name)          -> HdrInfo | None
    set_hdr(device_name, enabled)      -> bool
    set_auto_hdr(device_name, enabled) -> bool   (Windows 11 22H2+ only)
    get_sdr_white_level(device_name)   -> int | None   (0-100 %)
    set_sdr_white_level(device_name, pct)              (0-100 %)

All functions are best-effort: they swallow errors and return None / False
so callers never need to handle DisplayConfig exceptions.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

_user32 = ctypes.windll.user32

# ── Constants ─────────────────────────────────────────────────────────────────

QDC_ONLY_ACTIVE_PATHS = 0x00000002

DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME          = 1
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO  = 9
DISPLAYCONFIG_DEVICE_INFO_SET_ADVANCED_COLOR_STATE = 10
DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL      = 11
DISPLAYCONFIG_DEVICE_INFO_SET_SDR_WHITE_LEVEL      = 12
# Windows 11 22H2+ Auto HDR
DISPLAYCONFIG_DEVICE_INFO_GET_AUTO_COLOR_STATE     = 17
DISPLAYCONFIG_DEVICE_INFO_SET_AUTO_COLOR_STATE     = 18

# SDR white level: unit = 1/1000 * 80 nits  →  1000 = 80 nits (baseline)
_SDR_WL_MIN  = 1000   # 80 nits
_SDR_WL_MAX  = 6250   # 500 nits (safe upper bound recognised by Windows UI)


# ── Win32 structures ──────────────────────────────────────────────────────────

class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_ulong), ("HighPart", ctypes.c_long)]


class _DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type",       ctypes.c_int32),
        ("size",       ctypes.c_uint32),
        ("adapterId",  _LUID),
        ("id",         ctypes.c_uint32),
    ]


class _DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId",   _LUID),
        ("id",          ctypes.c_uint32),
        ("modeInfoIdx", ctypes.c_uint32),
        ("statusFlags", ctypes.c_uint32),
    ]


class _DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", ctypes.c_uint32), ("Denominator", ctypes.c_uint32)]


class _DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId",       _LUID),
        ("id",              ctypes.c_uint32),
        ("modeInfoIdx",     ctypes.c_uint32),
        ("outputTechnology",ctypes.c_int32),
        ("rotation",        ctypes.c_int32),
        ("scaling",         ctypes.c_int32),
        ("refreshRate",     _DISPLAYCONFIG_RATIONAL),
        ("scanLineOrdering",ctypes.c_int32),
        ("targetAvailable", ctypes.wintypes.BOOL),
        ("statusFlags",     ctypes.c_uint32),
    ]


class _DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", _DISPLAYCONFIG_PATH_SOURCE_INFO),
        ("targetInfo", _DISPLAYCONFIG_PATH_TARGET_INFO),
        ("flags",      ctypes.c_uint32),
    ]


# Opaque placeholder — we allocate mode-info arrays but never inspect them
_DISPLAYCONFIG_MODE_INFO = ctypes.c_byte * 64


class _DISPLAYCONFIG_SOURCE_NAME(ctypes.Structure):
    _fields_ = [
        ("header",           _DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", ctypes.c_wchar * 32),
    ]


class _DISPLAYCONFIG_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [
        ("header",              _DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("value",               ctypes.c_uint32),  # bit 0 = supported, bit 1 = enabled
        ("colorEncoding",       ctypes.c_int32),
        ("bitsPerColorChannel", ctypes.c_uint32),
    ]


class _DISPLAYCONFIG_SET_ADVANCED_COLOR(ctypes.Structure):
    _fields_ = [
        ("header", _DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("value",  ctypes.c_uint32),   # bit 0 = enableAdvancedColor
    ]


class _DISPLAYCONFIG_SDR_WHITE_LEVEL(ctypes.Structure):
    _fields_ = [
        ("header",        _DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("SDRWhiteLevel", ctypes.c_ulong),
    ]


class _DISPLAYCONFIG_AUTO_COLOR_STATE(ctypes.Structure):
    _fields_ = [
        ("header", _DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("value",  ctypes.c_uint32),   # bit 0 = supported, bit 1 = enabled (GET)
                                        # bit 0 = enableAutoColor          (SET)
    ]


# ── Public dataclass ──────────────────────────────────────────────────────────

@dataclass
class HdrInfo:
    """HDR capability and state snapshot for one monitor."""
    hdr_supported:        bool = False
    hdr_enabled:          bool = False
    auto_hdr_supported:   bool = False
    auto_hdr_enabled:     bool = False
    sdr_white_level_pct:  int  = 0      # 0-100 %, meaningful only when hdr_enabled


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_target(device_name: str) -> tuple[_LUID, int] | None:
    """Return (adapterId, targetId) for the GDI device name, or None."""
    n_paths = ctypes.c_uint32(0)
    n_modes = ctypes.c_uint32(0)
    if _user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,
                                            ctypes.byref(n_paths),
                                            ctypes.byref(n_modes)) != 0:
        return None

    PathArray = _DISPLAYCONFIG_PATH_INFO * n_paths.value
    ModeArray = _DISPLAYCONFIG_MODE_INFO  * n_modes.value
    paths = PathArray()
    modes = ModeArray()

    if _user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,
                                   ctypes.byref(n_paths), paths,
                                   ctypes.byref(n_modes), modes,
                                   None) != 0:
        return None

    for path in paths:
        src = _DISPLAYCONFIG_SOURCE_NAME()
        src.header.type      = DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
        src.header.size      = ctypes.sizeof(_DISPLAYCONFIG_SOURCE_NAME)
        src.header.adapterId = path.sourceInfo.adapterId
        src.header.id        = path.sourceInfo.id
        if _user32.DisplayConfigGetDeviceInfo(ctypes.byref(src.header)) == 0:
            if src.viewGdiDeviceName.lower() == device_name.lower():
                return (path.targetInfo.adapterId, path.targetInfo.id)
    return None


def _make_header(type_id: int, struct_type, adapter: _LUID, target_id: int
                 ) -> _DISPLAYCONFIG_DEVICE_INFO_HEADER:
    h = _DISPLAYCONFIG_DEVICE_INFO_HEADER()
    h.type      = type_id
    h.size      = ctypes.sizeof(struct_type)
    h.adapterId = adapter
    h.id        = target_id
    return h


def _sdr_wl_to_pct(wl: int) -> int:
    """Convert raw SDRWhiteLevel to 0-100 %."""
    pct = (wl - _SDR_WL_MIN) / (_SDR_WL_MAX - _SDR_WL_MIN) * 100
    return max(0, min(100, int(round(pct))))


def _pct_to_sdr_wl(pct: int) -> int:
    """Convert 0-100 % to raw SDRWhiteLevel."""
    return int(_SDR_WL_MIN + (pct / 100) * (_SDR_WL_MAX - _SDR_WL_MIN))


# ── Public API ────────────────────────────────────────────────────────────────

def get_hdr_info(device_name: str) -> HdrInfo | None:
    """Return the HDR capability/state for *device_name*, or None on error."""
    target = _find_target(device_name)
    if target is None:
        return None
    adapter, tid = target
    info = HdrInfo()

    # ── Advanced colour (HDR) ─────────────────────────────────────────────────
    try:
        aci = _DISPLAYCONFIG_ADVANCED_COLOR_INFO()
        aci.header = _make_header(DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO,
                                   _DISPLAYCONFIG_ADVANCED_COLOR_INFO, adapter, tid)
        if _user32.DisplayConfigGetDeviceInfo(ctypes.byref(aci.header)) == 0:
            info.hdr_supported = bool(aci.value & 0x1)
            info.hdr_enabled   = bool(aci.value & 0x2)
    except Exception as e:
        log.debug("HDR color info failed for %s: %s", device_name, e)

    # ── SDR white level (only meaningful when HDR on) ─────────────────────────
    if info.hdr_enabled:
        try:
            swl = _DISPLAYCONFIG_SDR_WHITE_LEVEL()
            swl.header = _make_header(DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL,
                                       _DISPLAYCONFIG_SDR_WHITE_LEVEL, adapter, tid)
            if _user32.DisplayConfigGetDeviceInfo(ctypes.byref(swl.header)) == 0:
                info.sdr_white_level_pct = _sdr_wl_to_pct(swl.SDRWhiteLevel)
        except Exception as e:
            log.debug("SDR white level get failed for %s: %s", device_name, e)

    # ── Auto HDR (Windows 11 22H2+, best-effort) ──────────────────────────────
    try:
        acs = _DISPLAYCONFIG_AUTO_COLOR_STATE()
        acs.header = _make_header(DISPLAYCONFIG_DEVICE_INFO_GET_AUTO_COLOR_STATE,
                                   _DISPLAYCONFIG_AUTO_COLOR_STATE, adapter, tid)
        if _user32.DisplayConfigGetDeviceInfo(ctypes.byref(acs.header)) == 0:
            info.auto_hdr_supported = bool(acs.value & 0x1)
            info.auto_hdr_enabled   = bool(acs.value & 0x2)
    except Exception as e:
        log.debug("Auto HDR info failed for %s (may not be Win11 22H2+): %s",
                  device_name, e)

    return info


def set_hdr(device_name: str, enabled: bool) -> bool:
    """Toggle HDR on/off for *device_name*. Returns True on success."""
    target = _find_target(device_name)
    if target is None:
        return False
    adapter, tid = target
    try:
        s = _DISPLAYCONFIG_SET_ADVANCED_COLOR()
        s.header = _make_header(DISPLAYCONFIG_DEVICE_INFO_SET_ADVANCED_COLOR_STATE,
                                 _DISPLAYCONFIG_SET_ADVANCED_COLOR, adapter, tid)
        s.value  = 1 if enabled else 0
        return _user32.DisplayConfigSetDeviceInfo(ctypes.byref(s.header)) == 0
    except Exception as e:
        log.debug("set_hdr failed for %s: %s", device_name, e)
        return False


def set_auto_hdr(device_name: str, enabled: bool) -> bool:
    """Toggle Auto HDR on/off (Windows 11 22H2+). Returns True on success."""
    target = _find_target(device_name)
    if target is None:
        return False
    adapter, tid = target
    try:
        s = _DISPLAYCONFIG_AUTO_COLOR_STATE()
        s.header = _make_header(DISPLAYCONFIG_DEVICE_INFO_SET_AUTO_COLOR_STATE,
                                 _DISPLAYCONFIG_AUTO_COLOR_STATE, adapter, tid)
        s.value  = 1 if enabled else 0
        return _user32.DisplayConfigSetDeviceInfo(ctypes.byref(s.header)) == 0
    except Exception as e:
        log.debug("set_auto_hdr failed for %s: %s", device_name, e)
        return False


def get_sdr_white_level(device_name: str) -> int | None:
    """Return SDR white level as 0-100 %, or None on error / HDR inactive."""
    target = _find_target(device_name)
    if target is None:
        return None
    adapter, tid = target
    try:
        swl = _DISPLAYCONFIG_SDR_WHITE_LEVEL()
        swl.header = _make_header(DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL,
                                   _DISPLAYCONFIG_SDR_WHITE_LEVEL, adapter, tid)
        if _user32.DisplayConfigGetDeviceInfo(ctypes.byref(swl.header)) == 0:
            return _sdr_wl_to_pct(swl.SDRWhiteLevel)
    except Exception as e:
        log.debug("get_sdr_white_level failed for %s: %s", device_name, e)
    return None


def set_sdr_white_level(device_name: str, pct: int) -> None:
    """Set SDR white level from 0-100 % (only effective when HDR is active)."""
    target = _find_target(device_name)
    if target is None:
        return
    adapter, tid = target
    try:
        swl = _DISPLAYCONFIG_SDR_WHITE_LEVEL()
        swl.header       = _make_header(DISPLAYCONFIG_DEVICE_INFO_SET_SDR_WHITE_LEVEL,
                                         _DISPLAYCONFIG_SDR_WHITE_LEVEL, adapter, tid)
        swl.SDRWhiteLevel = _pct_to_sdr_wl(max(0, min(100, pct)))
        _user32.DisplayConfigSetDeviceInfo(ctypes.byref(swl.header))
    except Exception as e:
        log.debug("set_sdr_white_level failed for %s: %s", device_name, e)
