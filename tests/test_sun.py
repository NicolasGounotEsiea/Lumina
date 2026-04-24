"""Tests for lumina_control.sun — NOAA sunrise/sunset algorithm."""
import math
from datetime import date

import pytest

from lumina_control.sun import sun_times, solar_noon, _day_of_year, _declination, _eq_of_time


class TestDayOfYear:
    def test_jan_1(self):
        assert _day_of_year(date(2024, 1, 1)) == 1

    def test_dec_31_leap(self):
        assert _day_of_year(date(2024, 12, 31)) == 366

    def test_dec_31_common(self):
        assert _day_of_year(date(2023, 12, 31)) == 365

    def test_mar_1_leap(self):
        assert _day_of_year(date(2024, 3, 1)) == 61

    def test_mar_1_common(self):
        assert _day_of_year(date(2023, 3, 1)) == 60


class TestDeclination:
    def test_summer_solstice_positive(self):
        doy = _day_of_year(date(2024, 6, 21))
        decl = math.degrees(_declination(doy))
        assert 22.0 < decl < 24.0

    def test_winter_solstice_negative(self):
        doy = _day_of_year(date(2024, 12, 21))
        decl = math.degrees(_declination(doy))
        assert -24.0 < decl < -22.0

    def test_equinox_near_zero(self):
        doy = _day_of_year(date(2024, 3, 21))
        decl = math.degrees(_declination(doy))
        assert abs(decl) < 2.0


class TestEquationOfTime:
    def test_returns_minutes(self):
        eot = _eq_of_time(1)
        assert isinstance(eot, float)

    def test_magnitude_reasonable(self):
        for doy in [1, 91, 181, 271]:
            eot = _eq_of_time(doy)
            assert abs(eot) < 20, f"EoT out of range at doy={doy}: {eot}"


class TestSunTimes:
    PARIS_LAT, PARIS_LON = 48.85, 2.35
    PARIS_TZ = "Europe/Paris"
    SYDNEY_LAT, SYDNEY_LON = -33.87, 151.21
    SYDNEY_TZ = "Australia/Sydney"

    def test_paris_summer_returns_two_floats(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 6, 21), self.PARIS_TZ)
        assert isinstance(rise, float) and isinstance(sett, float)

    def test_paris_summer_sunrise_before_sunset(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 6, 21), self.PARIS_TZ)
        assert rise < sett

    def test_paris_summer_long_day(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 6, 21), self.PARIS_TZ)
        assert (sett - rise) > 14.0, "Paris summer should have > 14 h of daylight"

    def test_paris_winter_short_day(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 12, 21), self.PARIS_TZ)
        assert (sett - rise) < 9.0, "Paris winter should have < 9 h of daylight"

    def test_paris_summer_sunrise_in_range(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 6, 21), self.PARIS_TZ)
        # Paris summer: ~05:30–21:30 local
        assert 4.0 < rise < 7.0
        assert 20.0 < sett < 23.0

    def test_paris_winter_sunrise_in_range(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 12, 21), self.PARIS_TZ)
        # Paris winter: ~08:40–16:55 local
        assert 7.5 < rise < 10.0
        assert 15.0 < sett < 18.0

    def test_southern_hemisphere_summer(self):
        rise, sett = sun_times(self.SYDNEY_LAT, self.SYDNEY_LON,
                               date(2024, 12, 21), self.SYDNEY_TZ)
        assert (sett - rise) > 13.0

    def test_southern_hemisphere_winter(self):
        rise, sett = sun_times(self.SYDNEY_LAT, self.SYDNEY_LON,
                               date(2024, 6, 21), self.SYDNEY_TZ)
        assert (sett - rise) < 11.0

    def test_polar_night_gives_degenerate_or_fallback(self):
        # At lat=89.9 in polar night, cos_ha is clamped to ±1 (no ValueError raised).
        # ha → 0, so sunrise ≈ sunset ≈ solar noon. Either that or fallback (6.0,20.0).
        rise, sett = sun_times(89.9, 0.0, date(2024, 12, 21), None)
        # Either the fallback or a valid result where the day has zero length
        if rise == 6.0 and sett == 20.0:
            pass  # classic fallback
        else:
            assert abs(sett - rise) < 1.0, "Polar night should give near-zero day length"

    def test_none_date_uses_today(self):
        rise, sett = sun_times(48.85, 2.35, None, "Europe/Paris")
        assert isinstance(rise, float) and isinstance(sett, float)
        assert rise < sett

    def test_result_in_24h_range(self):
        rise, sett = sun_times(self.PARIS_LAT, self.PARIS_LON,
                               date(2024, 6, 21), self.PARIS_TZ)
        assert 0.0 <= rise <= 24.0
        assert 0.0 <= sett <= 24.0

    def test_without_tz_returns_floats(self):
        rise, sett = sun_times(48.85, 2.35, date(2024, 6, 21), None)
        assert isinstance(rise, float) and isinstance(sett, float)


class TestSolarNoon:
    def test_equals_midpoint(self):
        d = date(2024, 6, 21)
        rise, sett = sun_times(48.85, 2.35, d, "Europe/Paris")
        noon = solar_noon(48.85, 2.35, d)
        assert abs(noon - (rise + sett) / 2.0) < 0.001

    def test_noon_around_midday(self):
        noon = solar_noon(48.85, 2.35, date(2024, 6, 21))
        assert 11.0 < noon < 15.0
