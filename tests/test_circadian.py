"""Tests for lumina_control.circadian — CircadianEngine."""
import math
from unittest.mock import patch

import pytest

from lumina_control.circadian import CircadianEngine, PRESET_CITIES


class TestCircadianPresetCities:
    def test_preset_cities_is_list(self):
        assert isinstance(PRESET_CITIES, list)
        assert len(PRESET_CITIES) > 0

    def test_each_entry_has_four_fields(self):
        for entry in PRESET_CITIES:
            assert len(entry) == 4, f"Entry should have 4 fields: {entry}"

    def test_personnalise_is_last(self):
        assert PRESET_CITIES[-1][0] == "Personnalisé"

    def test_personnalise_has_none_tz(self):
        assert PRESET_CITIES[-1][3] is None

    def test_paris_coords(self):
        paris = next(c for c in PRESET_CITIES if c[0] == "Paris")
        lat, lon = paris[1], paris[2]
        assert 47.0 < lat < 50.0
        assert 1.0 < lon < 4.0


class TestDayFactor:
    """Test _day_factor through the engine internals."""

    def _engine_with_sun(self, sunrise=6.0, sunset=20.0):
        eng = CircadianEngine(bri_min=0, bri_max=100)
        eng._cache_date = object()   # prevent refresh
        eng._sunrise = sunrise
        eng._sunset = sunset
        return eng

    def test_before_sunrise_is_zero(self):
        eng = self._engine_with_sun(6.0, 20.0)
        assert eng._day_factor(5.0) == 0.0
        assert eng._day_factor(6.0) == 0.0

    def test_after_sunset_is_zero(self):
        eng = self._engine_with_sun(6.0, 20.0)
        assert eng._day_factor(20.0) == 0.0
        assert eng._day_factor(21.0) == 0.0

    def test_solar_noon_is_one(self):
        sunrise, sunset = 6.0, 20.0
        noon = (sunrise + sunset) / 2.0   # 13.0
        eng = self._engine_with_sun(sunrise, sunset)
        factor = eng._day_factor(noon)
        assert abs(factor - 1.0) < 0.001, f"Expected ~1.0 at noon, got {factor}"

    def test_peak_is_at_midpoint_not_sunset(self):
        eng = self._engine_with_sun(6.0, 20.0)
        f_noon = eng._day_factor(13.0)
        f_sunset_minus_1 = eng._day_factor(19.0)
        assert f_noon > f_sunset_minus_1

    def test_uses_sin_not_cosine_shape(self):
        eng = self._engine_with_sun(6.0, 20.0)
        # At t=0.5 (solar noon) sin(π·0.5) = 1.0
        # At t=0.25 sin(π·0.25) = sin(π/4) ≈ 0.707
        t = 0.25
        hour = 6.0 + t * (20.0 - 6.0)
        factor = eng._day_factor(hour)
        expected = math.sin(math.pi * t)
        assert abs(factor - expected) < 0.001

    def test_symmetric_around_noon(self):
        eng = self._engine_with_sun(6.0, 20.0)
        noon = 13.0
        offset = 3.0
        f_before = eng._day_factor(noon - offset)
        f_after  = eng._day_factor(noon + offset)
        assert abs(f_before - f_after) < 0.001


class TestTargetBrightness:
    def _engine_at_hour(self, hour, bri_min=20, bri_max=100, sunrise=6.0, sunset=20.0):
        eng = CircadianEngine(bri_min=bri_min, bri_max=bri_max)
        eng._cache_date = object()
        eng._sunrise = sunrise
        eng._sunset = sunset
        with patch.object(eng, '_current_hour', return_value=hour):
            return eng.target_brightness()

    def test_nighttime_returns_bri_min(self):
        bri = self._engine_at_hour(3.0, bri_min=20, bri_max=100)
        assert bri == 20

    def test_noon_returns_bri_max(self):
        bri = self._engine_at_hour(13.0, bri_min=20, bri_max=100)
        assert abs(bri - 100) <= 1  # sin(π·0.5) ≈ 1.0 but rounding may give 99

    def test_returns_int(self):
        bri = self._engine_at_hour(13.0)
        assert isinstance(bri, int)

    def test_interpolation_midpoint(self):
        # At t=0.25, factor=sin(π/4)≈0.707 → bri ≈ 20 + 80*0.707 ≈ 77
        bri = self._engine_at_hour(9.5, bri_min=20, bri_max=100)
        assert 55 < bri < 85

    def test_clamped_to_range(self):
        for hour in [1.0, 13.0, 23.0]:
            bri = self._engine_at_hour(hour, bri_min=20, bri_max=100)
            assert 20 <= bri <= 100


class TestTargetWarmth:
    def _engine_at_hour(self, hour, warmth_max=60, sunrise=6.0, sunset=20.0):
        eng = CircadianEngine(warmth_max=warmth_max)
        eng._cache_date = object()
        eng._sunrise = sunrise
        eng._sunset = sunset
        with patch.object(eng, '_current_hour', return_value=hour):
            return eng.target_warmth()

    def test_noon_warmth_is_zero(self):
        w = self._engine_at_hour(13.0, warmth_max=60)
        assert abs(w) < 0.02  # sin(π·0.5) very close to 1 → warmth very close to 0

    def test_nighttime_warmth_is_max(self):
        w = self._engine_at_hour(2.0, warmth_max=60)
        assert abs(w - 0.60) < 0.01

    def test_warmth_inverse_of_brightness_factor(self):
        w_noon  = self._engine_at_hour(13.0)
        w_night = self._engine_at_hour(2.0)
        assert w_noon < w_night


class TestStep:
    def _engine(self, enabled=True, bri_min=20, bri_max=100, step_pct=2):
        eng = CircadianEngine(bri_min=bri_min, bri_max=bri_max, step_pct=step_pct)
        eng.enabled = enabled
        eng._cache_date = object()
        eng._sunrise = 6.0
        eng._sunset = 20.0
        return eng

    def test_disabled_returns_none(self):
        eng = self._engine(enabled=False)
        with patch.object(eng, '_current_hour', return_value=13.0):
            assert eng.step(50) is None

    def test_at_target_returns_none(self):
        eng = self._engine()
        with patch.object(eng, 'target_brightness', return_value=50):
            assert eng.step(50) is None

    def test_moves_toward_target(self):
        eng = self._engine(step_pct=2)
        with patch.object(eng, 'target_brightness', return_value=80):
            result = eng.step(50)
            assert result == 52

    def test_moves_down_toward_target(self):
        eng = self._engine(step_pct=2)
        with patch.object(eng, 'target_brightness', return_value=40):
            result = eng.step(50)
            assert result == 48

    def test_max_step_per_call(self):
        eng = self._engine(step_pct=2)
        with patch.object(eng, 'target_brightness', return_value=100):
            result = eng.step(10)
            assert result == 12

    def test_exactly_step_pct_away(self):
        eng = self._engine(step_pct=5)
        with patch.object(eng, 'target_brightness', return_value=55):
            result = eng.step(50)
            assert result == 55

    def test_returns_int(self):
        eng = self._engine()
        with patch.object(eng, 'target_brightness', return_value=80):
            result = eng.step(50)
            assert isinstance(result, int)


class TestSunLabel:
    def test_format(self):
        eng = CircadianEngine()
        # Mock _refresh_sun_cache to avoid overwriting our test values
        with patch.object(eng, '_refresh_sun_cache'):
            eng._sunrise = 6.5     # 06:30
            eng._sunset  = 20.25   # 20:15
            label = eng.sun_label()
        assert "06:30" in label
        assert "20:15" in label
        assert "↑" in label
        assert "↓" in label

    def test_midnight_normalization(self):
        eng = CircadianEngine()
        with patch.object(eng, '_refresh_sun_cache'):
            eng._sunrise = 25.0    # > 24 — should normalise to 01:00
            eng._sunset  = 30.0    # → 06:00
            label = eng.sun_label()
        assert "01:00" in label
