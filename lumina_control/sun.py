"""Astronomical sunrise / sunset calculation.

Pure Python, zero external dependencies.  Implements the standard
NOAA solar position algorithm (Spencer 1971 / Almanac approximation).

Usage::

    from lumina_control.sun import sun_times
    from datetime import date

    rise, sett = sun_times(48.8566, 2.3522, date.today())
    # rise and sett are decimal hours in *local solar time*
    # e.g. rise=6.52  → 06h31 local solar time
"""
from __future__ import annotations

import math
import datetime as _datetime
from datetime import date as _date


def _day_of_year(d: _date) -> int:
    return d.timetuple().tm_yday


def _eq_of_time(doy: int) -> float:
    """Equation of time in minutes (Spencer 1971)."""
    b = math.radians((360 / 365) * (doy - 81))
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def _declination(doy: int) -> float:
    """Solar declination in radians."""
    return math.radians(23.45 * math.sin(math.radians((360 / 365) * (doy - 81))))


def _resolve_utc_offset(tz_name: str | None, lon: float) -> float:
    """Return the UTC offset in hours for *tz_name*, falling back to lon/15."""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            return _datetime.datetime.now(tz=ZoneInfo(tz_name)).utcoffset().total_seconds() / 3600.0
        except Exception:
            pass
    # Solar time fallback (used for "Personnalisé" or if tzdata is not installed)
    return lon / 15.0


def sun_times(
    lat: float,
    lon: float,
    d: _date | None = None,
    tz_name: str | None = None,
) -> tuple[float, float]:
    """Return (sunrise, sunset) as decimal hours in the city's local clock time.

    Parameters
    ----------
    lat:
        Latitude in decimal degrees (north positive).
    lon:
        Longitude in decimal degrees (east positive).
    d:
        Date to compute for. Defaults to today.
    tz_name:
        IANA timezone name for the target city (e.g. ``"America/New_York"``).
        When provided, sunrise/sunset are expressed in that city's local time,
        regardless of the machine's own timezone.  When ``None``, falls back to
        the machine's civil UTC offset (original behaviour, used for
        "Personnalisé" where the user is assumed to be in their own timezone).

    Returns
    -------
    (sunrise, sunset) in local clock time decimal hours, e.g. (6.52, 20.13).
    Returns (6.0, 20.0) as a safe fallback on any arithmetic error (e.g. polar
    night or midnight sun at extreme latitudes).
    """
    if d is None:
        d = _date.today()

    try:
        doy = _day_of_year(d)
        decl = _declination(doy)
        lat_r = math.radians(lat)

        # Hour angle at sunrise / sunset
        cos_ha = (-math.sin(math.radians(-0.83))  # -0.83° = refraction + disc radius
                  - math.sin(lat_r) * math.sin(decl)) / (math.cos(lat_r) * math.cos(decl))

        # Clamp to avoid domain errors at extreme latitudes (polar day/night)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha = math.degrees(math.acos(cos_ha))        # in degrees

        # Solar noon in local solar time (hours)
        eot = _eq_of_time(doy)                      # minutes

        # Use the city's UTC offset, not necessarily the machine's
        if tz_name is None:
            # "Personnalisé": use machine civil time (user is presumably there)
            utc_offset = _datetime.datetime.now().astimezone().utcoffset().total_seconds() / 3600.0
        else:
            utc_offset = _resolve_utc_offset(tz_name, lon)

        # Solar noon in UTC, then shifted to wall-clock time
        solar_noon_utc   = 12.0 - eot / 60.0 - lon / 15.0
        solar_noon_local = solar_noon_utc + utc_offset

        sunrise = solar_noon_local - ha / 15.0
        sunset  = solar_noon_local + ha / 15.0
        return (sunrise, sunset)

    except (ValueError, ZeroDivisionError):
        # Polar night or midnight sun — fall back to a neutral 14-hour day
        return (6.0, 20.0)


def solar_noon(lat: float, lon: float, d: _date | None = None) -> float:
    """Return solar noon as decimal hours in local clock time."""
    rise, sett = sun_times(lat, lon, d)
    return (rise + sett) / 2.0
