"""Regression tests — one test per named bug from the CHANGELOG.

Each test is named after the version and the bug it guards against.
All tests use pure-Python modules only (no Qt, no DDC-CI, no Win32).
"""
import json
import math
import re
import tempfile
import os
from datetime import date
from unittest.mock import patch

import pytest

from lumina_control.circadian import CircadianEngine
from lumina_control.curve_editor import monotone_lut, build_icc_bytes, compose_ramp
from lumina_control.sun import sun_times, solar_noon
from lumina_control.app_rules import AppRule, AppRuleManager, DEFAULT_RULES
from lumina_control.profiles import ProfileManager, DEFAULT_SETTINGS
from lumina_control.i18n import _EN


# ── v1.2.4 bugs ──────────────────────────────────────────────────────────────

class TestV124CircadianPeakAtNoon:
    """BUG: (1−cos(π·t))/2 formula peaked at sunset, not solar noon.
    FIX: sin(π·t) peaks exactly at the midpoint of the day interval.
    """

    def _engine_with_fixed_sun(self, sunrise=6.0, sunset=20.0):
        eng = CircadianEngine(bri_min=0, bri_max=100)
        eng._cache_date = object()
        eng._sunrise = sunrise
        eng._sunset = sunset
        return eng

    def test_peak_at_noon_not_at_sunset(self):
        eng = self._engine_with_fixed_sun(6.0, 20.0)
        noon = 13.0
        pre_sunset = 19.0
        f_noon = eng._day_factor(noon)
        f_pre_sunset = eng._day_factor(pre_sunset)
        assert f_noon > f_pre_sunset, (
            "Brightness factor should peak at solar noon, not near sunset. "
            "If this fails, the old cosine formula has regressed."
        )

    def test_noon_factor_is_exactly_one(self):
        eng = self._engine_with_fixed_sun(6.0, 20.0)
        noon = 13.0  # midpoint of 6.0–20.0
        assert abs(eng._day_factor(noon) - 1.0) < 0.001

    def test_sin_shape_not_cosine(self):
        """sin(π·t) is symmetric; old cosine formula was not."""
        eng = self._engine_with_fixed_sun(6.0, 20.0)
        noon = 13.0
        offset = 4.0
        f_before = eng._day_factor(noon - offset)
        f_after  = eng._day_factor(noon + offset)
        assert abs(f_before - f_after) < 0.01


class TestV124CircadianUTCOffset:
    """BUG: sun_times used lon/15 (solar time) instead of civil UTC offset.
    FIX: zoneinfo used when tz_name is provided.
    """

    def test_paris_tz_offset_differs_from_solar_time_offset(self):
        # Paris lon=2.35 → solar time offset = 2.35/15 ≈ 0.157 h
        # Paris "Europe/Paris" winter → UTC+1 = 1.0 h
        # These should differ by ~0.84h
        from lumina_control.sun import _resolve_utc_offset
        solar_offset = 2.35 / 15.0
        paris_offset = _resolve_utc_offset("Europe/Paris", 2.35)
        assert abs(paris_offset - solar_offset) > 0.5, (
            f"Paris civil offset ({paris_offset:.3f}h) should differ from solar "
            f"time offset ({solar_offset:.3f}h) by > 0.5h"
        )

    def test_new_york_uses_city_timezone(self):
        d = date(2024, 6, 21)
        rise, sett = sun_times(40.71, -74.01, d, "America/New_York")
        # New York summer sunrise ≈ 05:25 EDT (UTC-4) → ~5.4h
        assert 4.0 < rise < 7.0, f"NY summer sunrise {rise:.2f}h outside expected range"

    def test_resolve_utc_offset_returns_float(self):
        from lumina_control.sun import _resolve_utc_offset
        offset = _resolve_utc_offset("Europe/Paris", 2.35)
        assert isinstance(offset, float)

    def test_resolve_utc_offset_fallback_uses_lon(self):
        from lumina_control.sun import _resolve_utc_offset
        offset = _resolve_utc_offset(None, 30.0)
        # lon/15 = 30/15 = 2.0
        assert abs(offset - 2.0) < 0.1


# ── v1.2.5 bugs ──────────────────────────────────────────────────────────────

class TestV125CircadianCityTimezones:
    """BUG: Cities like New York showed shifted times (e.g. 'sunrise 12:31')
    because machine UTC offset was used instead of the city's own IANA timezone.
    """

    def test_preset_cities_have_iana_tz(self):
        from lumina_control.circadian import PRESET_CITIES
        for name, lat, lon, tz in PRESET_CITIES:
            if name == "Personnalisé":
                assert tz is None
            else:
                assert tz is not None, f"City {name!r} missing IANA timezone"
                assert "/" in tz, f"City {name!r} has invalid IANA timezone: {tz!r}"

    def test_tokyo_sunrise_in_reasonable_range(self):
        d = date(2024, 6, 21)
        rise, sett = sun_times(35.68, 139.69, d, "Asia/Tokyo")
        # Tokyo summer: rise ≈ 04:26 JST
        assert 3.0 < rise < 6.0, f"Tokyo summer sunrise {rise:.2f}h unreasonable"

    def test_sydney_winter_sunrise(self):
        d = date(2024, 6, 21)
        rise, sett = sun_times(-33.87, 151.21, d, "Australia/Sydney")
        # Sydney winter: rise ≈ 07:01 AEST
        assert 6.0 < rise < 9.0, f"Sydney winter sunrise {rise:.2f}h unreasonable"


# ── v1.2.7 bugs ──────────────────────────────────────────────────────────────

class TestV127CurveLeakToSettings:
    """BUG: App Rules applying curves triggered save_hook via _on_curves_applied,
    persisting transient rule curves into settings.json as the user baseline.
    FIX: rules_engine._apply sets _custom_luts directly without save_hook.
    This test verifies the ProfileManager never saves curve_points from an
    external caller without explicit intent.
    """

    def test_save_settings_without_curves_preserves_empty_dict(self, tmp_path):
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )
        settings = DEFAULT_SETTINGS.copy()
        settings["curve_points"] = {}
        mgr.save_settings(settings)
        loaded = mgr.load_settings()
        assert loaded["curve_points"] == {}

    def test_explicit_curve_points_are_saved(self, tmp_path):
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )
        cp = {r"\\.\DISPLAY1": {"R": [[0, 0], [1, 1]]}}
        settings = DEFAULT_SETTINGS.copy()
        settings["curve_points"] = cp
        mgr.save_settings(settings)
        loaded = mgr.load_settings()
        assert loaded["curve_points"] == cp


class TestV127CurvesInNamedProfiles:
    """BUG: Named profiles did not save/restore per-channel tone curves.
    FIX: save_named_profile() accepts curve_points param.
    """

    def test_curves_round_trip_in_named_profile(self, tmp_path):
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )
        cp = {r"\\.\DISPLAY1": {"R": [[0.0, 0.0], [0.5, 0.7], [1.0, 1.0]]}}
        mgr.save_named_profile("Cinema", [{"brightness": 60}], {}, curve_points=cp)
        profile = mgr.load_named_profile("Cinema")
        assert profile is not None
        assert r"\\.\DISPLAY1" in profile["curve_points"]
        assert profile["curve_points"][r"\\.\DISPLAY1"]["R"][1] == [0.5, 0.7]

    def test_profile_without_curves_has_empty_dict(self, tmp_path):
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )
        mgr.save_named_profile("Work", [{"brightness": 80}], {})
        profile = mgr.load_named_profile("Work")
        assert profile["curve_points"] == {}


# ── v1.2.8 bugs ──────────────────────────────────────────────────────────────

class TestV128ComposeRampBackwardCompat:
    """BUG: compose_ramp did not have contrast/gain params — adding them
    must not change output when using default values.
    """

    def test_new_defaults_are_identity(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        r1, g1, b1 = compose_ramp(lut, lut, lut, gamma=1.0, warmth=0.0)
        r2, g2, b2 = compose_ramp(lut, lut, lut, gamma=1.0, warmth=0.0,
                                   contrast=0.5, r_gain=1.0, g_gain=1.0, b_gain=1.0)
        assert r1 == r2
        assert g1 == g2
        assert b1 == b2

    def test_contrast_50_is_identity(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        r_id, _, _ = compose_ramp(lut, lut, lut, contrast=0.5)
        r_no, _, _ = compose_ramp(lut, lut, lut)
        assert r_id == r_no

    def test_gains_1_is_identity(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        r1, g1, b1 = compose_ramp(lut, lut, lut, r_gain=1.0, g_gain=1.0, b_gain=1.0)
        r2, g2, b2 = compose_ramp(lut, lut, lut)
        assert r1 == r2 and g1 == g2 and b1 == b2


class TestV128ContrastLinearStretch:
    """BUG: contrast was not implemented.
    FIX: y = clamp(0.5 + (x − 0.5) × factor, 0, 1) where factor = contrast × 2.
    """

    def test_max_contrast_expands_range(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        r, _, _ = compose_ramp(lut, lut, lut, contrast=1.0)
        # At max contrast: anything below 0.5 goes to 0, above 0.5 goes to max
        assert r[50] == 0
        assert r[200] == 65535

    def test_zero_contrast_flattens_to_grey(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        r, _, _ = compose_ramp(lut, lut, lut, contrast=0.0)
        mid = 32767
        assert all(abs(v - mid) <= 1 for v in r)


# ── v1.2.9 bugs ──────────────────────────────────────────────────────────────

class TestV129MonotonicGammaRamp:
    """BUG: Non-monotone custom curves could cause SetDeviceGammaRamp to fail.
    The monotone_lut function must always produce a non-decreasing output
    for monotone input control points.
    """

    def test_monotone_lut_output_is_nondecreasing(self):
        # Various curve shapes
        test_cases = [
            [(0, 0), (1, 1)],
            [(0, 0), (0.3, 0.1), (0.7, 0.9), (1, 1)],
            [(0, 0.2), (0.5, 0.5), (1, 0.8)],
            [(0, 0), (0.5, 0.8), (1, 1)],
        ]
        for pts in test_cases:
            lut = monotone_lut(pts)
            for i in range(len(lut) - 1):
                assert lut[i + 1] >= lut[i], (
                    f"Non-monotone at index {i} with points {pts}: "
                    f"{lut[i]} > {lut[i+1]}"
                )


# ── v1.3.0 bugs ──────────────────────────────────────────────────────────────

class TestV130AppRulesSuspendBeforeClear:
    """BUG: update_rules() set _active_rule = None without restoring pre-rule values.
    FIX: suspend() called first to restore state.
    This test verifies the data layer: AppRuleManager.load() returns fresh rules
    without contaminating old state.
    """

    def test_load_always_returns_independent_list(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        rules1 = mgr.load()
        rules2 = mgr.load()
        # Mutating one list should not affect the other
        rules1.clear()
        assert len(rules2) > 0

    def test_modify_and_reload(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        original = mgr.load()
        original[0] = AppRule("new.exe", "New", 50, 50, None)
        mgr.save(original)
        reloaded = mgr.load()
        assert reloaded[0].process == "new.exe"


class TestV130ApplyRgbDictUserColourUnlock:
    """BUG: apply_rgb_dict did not send VCP 0x14 = 0x0B before RGB writes,
    silently failing on monitors in Gaming/Cinema preset mode.
    FIX: User Colour unlock sent before each RGB sequence.
    This test verifies the AppRule correctly stores RGB gains that will be used.
    """

    def test_rgb_gains_in_rule_round_trip(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        rule = AppRule("photoshop.exe", "PS", 75, 55, 1.0,
                       red=85, green=75, blue=90)
        mgr.save([rule])
        loaded = mgr.load()
        assert loaded[0].red == 85
        assert loaded[0].green == 75
        assert loaded[0].blue == 90


class TestV130SettingsMergeOnLoad:
    """BUG: Unknown saved keys were being kept, cluttering settings.
    FIX: load_settings only merges known DEFAULT_SETTINGS keys.
    """

    def test_unknown_key_not_in_result(self, tmp_path):
        settings_path = str(tmp_path / "settings.json")
        with open(settings_path, "w") as f:
            json.dump({"sync_enabled": True, "__future__": "value"}, f)
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            settings_path,
            str(tmp_path / "named.json"),
        )
        result = mgr.load_settings()
        assert "__future__" not in result

    def test_all_default_keys_always_present(self, tmp_path):
        settings_path = str(tmp_path / "settings.json")
        with open(settings_path, "w") as f:
            json.dump({"sync_enabled": True}, f)
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            settings_path,
            str(tmp_path / "named.json"),
        )
        result = mgr.load_settings()
        for key in DEFAULT_SETTINGS:
            assert key in result


# ── i18n regressions ─────────────────────────────────────────────────────────

class TestI18nRegressions:
    """BUG: _ shadowing in list comprehensions (using _ as throwaway variable
    conflicted with the i18n _() function in the same scope).
    Guard: ensure _EN is importable and no key is a bare underscore.
    """

    def test_underscore_not_a_key(self):
        assert "_" not in _EN

    def test_import_does_not_break_i18n(self):
        from lumina_control.i18n import _
        result = _("Quitter")
        assert isinstance(result, str)

    def test_format_string_keys_have_matching_braces(self):
        for fr, en in _EN.items():
            assert fr.count("{") == fr.count("}"), f"Unmatched braces in FR key: {fr[:50]!r}"
            assert en.count("{") == en.count("}"), f"Unmatched braces in EN val: {en[:50]!r}"


# ── Circadian step smoothing regression ──────────────────────────────────────

class TestCircadianStepSmoothingRegression:
    """Guard against large brightness jumps when circadian is first enabled.
    step() must never move more than step_pct in one call.
    """

    def test_step_never_exceeds_step_pct(self):
        eng = CircadianEngine(bri_min=20, bri_max=100, step_pct=2)
        eng.enabled = True
        eng._cache_date = object()
        eng._sunrise = 6.0
        eng._sunset = 20.0

        with patch.object(eng, 'target_brightness', return_value=100):
            result = eng.step(20)
            assert result is not None
            assert abs(result - 20) <= 2

    def test_step_converges_to_target(self):
        eng = CircadianEngine(bri_min=20, bri_max=100, step_pct=5)
        eng.enabled = True
        eng._cache_date = object()
        eng._sunrise = 6.0
        eng._sunset = 20.0

        target = 80
        current = 20
        with patch.object(eng, 'target_brightness', return_value=target):
            for _ in range(20):
                result = eng.step(current)
                if result is None:
                    break
                current = result
        assert current == target


# ── ICC v2 structure regression ───────────────────────────────────────────────

class TestIccStructureRegression:
    """Guard ICC v2 profile structure (header offsets, tag count, size consistency)."""

    def test_tag_count_is_9(self):
        import struct
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        data = build_icc_bytes(lut, lut, lut)
        # Tag count is at offset 128 (after header)
        tag_count = struct.unpack(">I", data[128:132])[0]
        assert tag_count == 9

    def test_all_tag_offsets_within_file(self):
        import struct
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        data = build_icc_bytes(lut, lut, lut)
        n_tags = struct.unpack(">I", data[128:132])[0]
        total = len(data)
        for i in range(n_tags):
            base = 132 + i * 12
            offset = struct.unpack(">I", data[base + 4:base + 8])[0]
            size   = struct.unpack(">I", data[base + 8:base + 12])[0]
            assert offset + size <= total, (
                f"Tag {i} data extends beyond file end: offset={offset} size={size} total={total}"
            )

    def test_rtrc_gtrc_btrc_tags_present(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        data = build_icc_bytes(lut, lut, lut)
        for sig in (b"rTRC", b"gTRC", b"bTRC"):
            assert sig in data, f"Tag {sig!r} missing from ICC profile"
