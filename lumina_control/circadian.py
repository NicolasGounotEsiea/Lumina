"""Circadian brightness engine.

Maps the current time of day to a DDC-CI brightness target using a smooth
cosine curve anchored to real sunrise / sunset times.

Curve shape
-----------
  bri_max  ─────────────·─────────────
                       / \\
                      /   \\
  bri_min  ──────────/     \\──────────
           ^sunrise       ^sunset

The curve is a half-cosine (0 → π) between sunrise and sunset, peaking at
solar noon.  Before sunrise and after sunset the output is *bri_min*.

Smoothing
---------
``step()`` is meant to be called every 500 ms (main poll timer).  It returns
the next brightness value, moving toward the computed target by at most
*step_pct* percentage points per call.  This ensures no visible jump when the
feature is first enabled or when sunrise/sunset transitions happen.

Usage::

    engine = CircadianEngine(lat=48.85, lon=2.35, bri_min=20, bri_max=100)
    engine.enabled = True

    # In the 500 ms poll:
    new_bri = engine.step(current_bri)
    if new_bri is not None:
        window._set_glob(new_bri)
"""
from __future__ import annotations

import math
from datetime import date

from lumina_control.sun import sun_times


# Predefined cities for the UI picker (name, lat, lon)
PRESET_CITIES: list[tuple[str, float, float]] = [
    ("Paris",         48.85,   2.35),
    ("Londres",       51.51,  -0.13),
    ("Berlin",        52.52,  13.41),
    ("Madrid",        40.42,  -3.70),
    ("Rome",          41.90,  12.50),
    ("Amsterdam",     52.37,   4.90),
    ("Bruxelles",     50.85,   4.35),
    ("Zurich",        47.38,   8.54),
    ("New York",      40.71, -74.01),
    ("Los Angeles",   34.05,-118.24),
    ("Chicago",       41.88, -87.63),
    ("Toronto",       43.65, -79.38),
    ("Montréal",      45.50, -73.57),
    ("Tokyo",         35.68, 139.69),
    ("Seoul",         37.57, 126.98),
    ("Sydney",       -33.87, 151.21),
    ("Dubaï",         25.20,  55.27),
    ("Singapore",      1.35, 103.82),
    ("São Paulo",    -23.55, -46.63),
    ("Personnalisé",   0.0,    0.0),   # always last — triggers lat/lon inputs
]


class CircadianEngine:
    """Computes and tracks the circadian brightness and warmth targets.

    Attributes
    ----------
    enabled:
        Whether the engine should produce brightness/warmth updates.
    lat, lon:
        Geographic coordinates used for sunrise/sunset computation.
    bri_min, bri_max:
        Brightness boundaries (0–100).
    warmth_enabled:
        Whether the engine also drives night-warmth (warm tint).
        Warmth follows the *inverse* of the brightness curve:
        maximum warmth (warmth_max) at night, zero at solar noon.
    warmth_max:
        Maximum warmth level (0–100) applied at night.
    step_pct:
        Maximum brightness change per ``step()`` call (smoothing).
    """

    def __init__(
        self,
        lat: float = 48.85,
        lon: float = 2.35,
        bri_min: int = 20,
        bri_max: int = 100,
        warmth_enabled: bool = False,
        warmth_max: int = 60,
        step_pct: int = 2,
    ) -> None:
        self.enabled        = False
        self.lat            = lat
        self.lon            = lon
        self.bri_min        = bri_min
        self.bri_max        = bri_max
        self.warmth_enabled = warmth_enabled
        self.warmth_max     = warmth_max
        self.step_pct       = step_pct

        # Cache sunrise/sunset per calendar day — recomputed when date changes
        self._cache_date: date | None = None
        self._sunrise:    float = 6.0
        self._sunset:     float = 20.0

    # ── Public API ────────────────────────────────────────────────────────────

    def target_brightness(self) -> int:
        """Return the ideal brightness (0–100) for the current moment."""
        self._refresh_sun_cache()
        return self._bri_curve(self._current_hour())

    def target_warmth(self) -> float:
        """Return the ideal warmth (0.0–1.0) for the current moment.

        The warmth is the *inverse* of the brightness factor:
        0.0 at solar noon (full daylight), warmth_max/100 at night.
        """
        self._refresh_sun_cache()
        hour   = self._current_hour()
        factor = self._day_factor(hour)            # 0.0 at night, 1.0 at noon
        night  = 1.0 - factor                      # 1.0 at night, 0.0 at noon
        return night * (self.warmth_max / 100.0)

    # Convenience alias used by the poll loop
    def target(self) -> int:
        return self.target_brightness()

    def step(self, current_bri: int) -> int | None:
        """Return the next brightness value, or None if the engine is disabled.

        Moves *current_bri* toward ``target_brightness()`` by at most
        *step_pct* per call, ensuring smooth transitions.
        """
        if not self.enabled:
            return None
        t = self.target_brightness()
        if current_bri == t:
            return None
        delta = t - current_bri
        move  = max(-self.step_pct, min(self.step_pct, delta))
        return current_bri + move

    def sun_label(self) -> str:
        """Human-readable 'HH:MM ↑  ·  HH:MM ↓' string for the UI."""
        self._refresh_sun_cache()
        return "{} ↑  ·  {} ↓".format(
            self._fmt(self._sunrise),
            self._fmt(self._sunset),
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _refresh_sun_cache(self) -> None:
        today = date.today()
        if self._cache_date != today:
            self._cache_date = today
            self._sunrise, self._sunset = sun_times(self.lat, self.lon, today)

    def _current_hour(self) -> float:
        import datetime as _dt
        now = _dt.datetime.now()
        return now.hour + now.minute / 60.0 + now.second / 3600.0

    def _day_factor(self, hour: float) -> float:
        """0.0 before sunrise / after sunset, rises to 1.0 at solar noon."""
        if hour <= self._sunrise or hour >= self._sunset:
            return 0.0
        t = (hour - self._sunrise) / (self._sunset - self._sunrise)
        return math.sin(math.pi * t)

    def _bri_curve(self, hour: float) -> int:
        """Cosine brightness curve clamped to [bri_min, bri_max]."""
        factor = self._day_factor(hour)
        return int(round(self.bri_min + (self.bri_max - self.bri_min) * factor))

    @staticmethod
    def _fmt(h: float) -> str:
        hh = int(h)
        mm = int((h - hh) * 60)
        return f"{hh:02d}:{mm:02d}"
