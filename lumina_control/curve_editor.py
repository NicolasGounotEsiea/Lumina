"""RGB tone curve utilities: spline interpolation → GDI32 gamma ramp + ICC v2 writer.

Public API
----------
    monotone_lut(points)                      → list[int]  (256 × 0-65535)
    set_device_gamma_ramp(dev, r, g, b)       → bool
    build_icc_bytes(r_lut, g_lut, b_lut)      → bytes
    write_icc_profile(r_lut, g_lut, b_lut, p) → bool
"""
from __future__ import annotations

import ctypes
import datetime
import logging
import struct
from pathlib import Path

log = logging.getLogger(__name__)


# ── Monotone cubic spline (Fritsch-Carlson 1980) ──────────────────────────────

def monotone_lut(points: list[tuple[float, float]], out_max: int = 65535) -> list[int]:
    """Return a 256-entry LUT (0…*out_max*) from control points in [0,1]².

    Uses Fritsch-Carlson monotone cubic interpolation — no ringing/overshoot,
    guaranteed monotone between consecutive control points.  Points are sorted
    by x; endpoints at x=0 and x=1 are enforced automatically.
    """
    if not points:
        return [int(round(i / 255 * out_max)) for i in range(256)]

    # Sort and clamp to [0, 1]
    pts: list[tuple[float, float]] = sorted(
        (max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y))))
        for x, y in points
    )

    # Remove duplicate x values (keep first)
    seen: set[float] = set()
    clean: list[tuple[float, float]] = []
    for x, y in pts:
        if x not in seen:
            clean.append((x, y))
            seen.add(x)
    pts = clean

    # Enforce boundary control points
    if pts[0][0] > 0.0:
        pts.insert(0, (0.0, pts[0][1]))
    if pts[-1][0] < 1.0:
        pts.append((1.0, pts[-1][1]))

    n = len(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    if n < 2:
        v = int(round(ys[0] * out_max))
        return [v] * 256

    # Secant slopes between adjacent points
    delta = [
        (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])
        if xs[i + 1] > xs[i] else 0.0
        for i in range(n - 1)
    ]

    # Initial tangents: mean of adjacent secant slopes
    m = [0.0] * n
    m[0] = delta[0]
    for i in range(1, n - 1):
        m[i] = (delta[i - 1] + delta[i]) / 2.0
    m[-1] = delta[-1]

    # Fritsch-Carlson monotonicity correction
    for i in range(n - 1):
        if abs(delta[i]) < 1e-12:
            m[i] = m[i + 1] = 0.0
        else:
            alpha = m[i] / delta[i]
            beta  = m[i + 1] / delta[i]
            if alpha < 0.0:
                m[i] = 0.0
            if beta < 0.0:
                m[i + 1] = 0.0
            sq = alpha ** 2 + beta ** 2
            if sq > 9.0:
                tau = 3.0 / sq ** 0.5
                m[i]     = tau * alpha * delta[i]
                m[i + 1] = tau * beta  * delta[i]

    def _eval(t: float) -> float:
        t = max(xs[0], min(xs[-1], t))
        seg = n - 2
        for k in range(n - 1):
            if t <= xs[k + 1]:
                seg = k
                break
        hk = xs[seg + 1] - xs[seg]
        if abs(hk) < 1e-14:
            return ys[seg]
        tau = (t - xs[seg]) / hk
        h00 =  2 * tau ** 3 - 3 * tau ** 2 + 1
        h10 =      tau ** 3 - 2 * tau ** 2 + tau
        h01 = -2 * tau ** 3 + 3 * tau ** 2
        h11 =      tau ** 3 -     tau ** 2
        return (h00 * ys[seg] + h10 * hk * m[seg]
                + h01 * ys[seg + 1] + h11 * hk * m[seg + 1])

    return [
        int(round(max(0.0, min(1.0, _eval(i / 255.0))) * out_max))
        for i in range(256)
    ]


# ── GDI32 gamma ramp ──────────────────────────────────────────────────────────

def set_device_gamma_ramp(device_name: str,
                          r_lut: list[int],
                          g_lut: list[int],
                          b_lut: list[int]) -> bool:
    """Apply explicit 256-entry LUTs (0-65535) to *device_name* via SetDeviceGammaRamp."""
    try:
        hdc = ctypes.windll.gdi32.CreateDCW("DISPLAY", device_name, None, None)
        if not hdc:
            return False
        ramp = (ctypes.c_ushort * 768)()
        for i in range(256):
            ramp[i]         = min(65535, max(0, int(r_lut[i])))
            ramp[256 + i]   = min(65535, max(0, int(g_lut[i])))
            ramp[512 + i]   = min(65535, max(0, int(b_lut[i])))
        ok = bool(ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)))
        ctypes.windll.gdi32.DeleteDC(hdc)
        return ok
    except Exception as e:
        log.debug("set_device_gamma_ramp failed for %s: %s", device_name, e)
        return False


# ── ICC v2 profile builder ────────────────────────────────────────────────────

def _s15f16(v: float) -> bytes:
    """Encode a float as ICC s15Fixed16Number (big-endian signed 16.16)."""
    return struct.pack(">i", int(round(v * 65536)))


def _pad4(data: bytes) -> bytes:
    while len(data) % 4:
        data += b"\x00"
    return data


def _tag_xyz(x: float, y: float, z: float) -> bytes:
    return _pad4(b"XYZ " + b"\x00" * 4 + _s15f16(x) + _s15f16(y) + _s15f16(z))


def _tag_text(text: str) -> bytes:
    return _pad4(b"text" + b"\x00" * 4 + text.encode("ascii") + b"\x00")


def _tag_desc(text: str) -> bytes:
    """ICC v2 profileDescriptionTag (type 'desc')."""
    ascii_b = text.encode("ascii") + b"\x00"
    n = len(ascii_b)
    data = (
        b"desc" + b"\x00" * 4        # type + reserved
        + struct.pack(">I", n)         # invariantDescLength
        + ascii_b                      # ASCII string
        + struct.pack(">I", 0)         # unicodeLanguageCode
        + struct.pack(">I", 0)         # unicodeCount (0 = no unicode string)
        + b"\x00\x00"                  # scriptcodeCode
        + bytes([0])                   # macintoshDescLength
        + b"\x00" * 67                 # macintoshDesc (always 67 bytes, ICC spec §10.14)
    )
    return _pad4(data)


def _tag_curv(lut: list[int]) -> bytes:
    """ICC 'curv' tone response curve tag with *len(lut)* entries (uint16 each)."""
    data = b"curv" + b"\x00" * 4 + struct.pack(">I", len(lut))
    for v in lut:
        data += struct.pack(">H", min(65535, max(0, int(v))))
    return _pad4(data)


def build_icc_bytes(r_lut: list[int], g_lut: list[int], b_lut: list[int]) -> bytes:
    """Build a minimal ICC v2 monitor profile from three 256-point LUTs (0-65535).

    The profile encodes sRGB primaries (Bradford-adapted to D50) so that
    colour-managed applications (Photoshop, Lightroom, DaVinci Resolve…)
    interpret the display in a well-defined colour space while applying the
    custom tone response curves.
    """
    tags_data = [
        (b"desc", _tag_desc("LuminaControl Custom Profile")),
        (b"cprt", _tag_text("Generated by LuminaControl")),
        # D50 PCS white point
        (b"wtpt", _tag_xyz(0.96420288, 1.00000000, 0.82490540)),
        # sRGB primaries adapted to D50 via Bradford transform
        (b"rXYZ", _tag_xyz(0.43607, 0.22249, 0.01393)),
        (b"gXYZ", _tag_xyz(0.38515, 0.71687, 0.09708)),
        (b"bXYZ", _tag_xyz(0.14307, 0.06061, 0.71393)),
        # Per-channel tone response curves (custom)
        (b"rTRC", _tag_curv(r_lut)),
        (b"gTRC", _tag_curv(g_lut)),
        (b"bTRC", _tag_curv(b_lut)),
    ]

    n_tags = len(tags_data)
    header_size   = 128
    tag_table_size = 4 + n_tags * 12   # tagCount(4) + (sig + offset + size) * n

    # Calculate tag data offsets
    offset = header_size + tag_table_size
    offsets: list[int] = []
    for _sig, data in tags_data:
        offsets.append(offset)
        offset += len(data)
    total_size = offset

    # ── Header (exactly 128 bytes) ─────────────────────────────────────────────
    now = datetime.datetime.utcnow()
    header = (
        struct.pack(">I", total_size)          # profile size
        + b"\x00" * 4                          # preferred CMM type
        + b"\x02\x10\x00\x00"                  # ICC version 2.1.0
        + b"mntr"                               # profile class: display device
        + b"RGB "                               # colour space of data
        + b"XYZ "                               # PCS
        + struct.pack(">6H", now.year, now.month, now.day,
                      now.hour, now.minute, now.second)  # creation date/time
        + b"acsp"                               # file signature
        + b"MSFT"                               # primary platform
        + b"\x00" * 4                          # profile flags
        + b"\x00" * 4                          # device manufacturer
        + b"\x00" * 4                          # device model
        + b"\x00" * 8                          # device attributes
        + b"\x00" * 4                          # rendering intent (perceptual = 0)
        + _s15f16(0.96420288) + _s15f16(1.0) + _s15f16(0.82490540)  # D50 illuminant
        + b"LMNA"                               # profile creator signature
        + b"\x00" * 16                         # profile ID (MD5 not computed)
        + b"\x00" * 28                         # reserved
    )
    assert len(header) == 128, f"ICC header must be 128 bytes, got {len(header)}"

    # ── Tag table ──────────────────────────────────────────────────────────────
    tag_table = struct.pack(">I", n_tags)
    for i, (sig, data) in enumerate(tags_data):
        tag_table += sig + struct.pack(">II", offsets[i], len(data))

    # ── Assemble ───────────────────────────────────────────────────────────────
    profile = header + tag_table
    for _sig, data in tags_data:
        profile += data

    return profile


def compose_ramp(r_lut: list[int], g_lut: list[int], b_lut: list[int],
                 gamma: float = 1.0, warmth: float = 0.0,
                 ) -> tuple[list[int], list[int], list[int]]:
    """Apply *gamma* and *warmth* on top of existing per-channel LUTs.

    This lets the gamma slider and Night Mode warm-tint compose with custom
    curves rather than overwriting them.

    *gamma*   — same semantics as ``_build_combined_ramp``: 1.0 = neutral,
                > 1.0 = brighter mid-tones, < 1.0 = darker.
    *warmth*  — 0.0 = neutral, 1.0 = maximum warm (+5 % R, −70 % B).

    With *gamma*=1.0 and *warmth*=0.0 the output is identical to the input.
    With identity LUTs the output is identical to ``_build_combined_ramp``.
    """
    gamma   = max(0.5, min(3.0, float(gamma)))
    warmth  = max(0.0, min(1.0, float(warmth)))
    r_mult  = 1.0 + warmth * 0.05
    g_mult  = 1.0 - warmth * 0.05
    b_mult  = 1.0 - warmth * 0.70

    out_r: list[int] = []
    out_g: list[int] = []
    out_b: list[int] = []
    for i in range(256):
        cr = r_lut[i] / 65535.0
        cg = g_lut[i] / 65535.0
        cb = b_lut[i] / 65535.0
        if gamma != 1.0:
            cr = pow(cr, 1.0 / gamma) if cr > 0.0 else 0.0
            cg = pow(cg, 1.0 / gamma) if cg > 0.0 else 0.0
            cb = pow(cb, 1.0 / gamma) if cb > 0.0 else 0.0
        out_r.append(min(65535, max(0, int(round(cr * r_mult * 65535)))))
        out_g.append(min(65535, max(0, int(round(cg * g_mult * 65535)))))
        out_b.append(min(65535, max(0, int(round(cb * b_mult * 65535)))))
    return out_r, out_g, out_b


def write_icc_profile(r_lut: list[int], g_lut: list[int], b_lut: list[int],
                      path: str) -> bool:
    """Write an ICC v2 profile to *path*. Returns True on success."""
    try:
        data = build_icc_bytes(r_lut, g_lut, b_lut)
        Path(path).write_bytes(data)
        return True
    except Exception as e:
        log.debug("write_icc_profile failed: %s", e)
        return False
