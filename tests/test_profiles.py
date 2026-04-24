"""Tests for lumina_control.profiles — ProfileManager and DEFAULT_SETTINGS."""
import json
import os

import pytest

from lumina_control.profiles import ProfileManager, DEFAULT_SETTINGS


class TestDefaultSettings:
    def test_is_dict(self):
        assert isinstance(DEFAULT_SETTINGS, dict)

    def test_has_sync_enabled(self):
        assert "sync_enabled" in DEFAULT_SETTINGS

    def test_has_gamma_value(self):
        assert "gamma_value" in DEFAULT_SETTINGS

    def test_has_focus_enabled(self):
        assert "focus_enabled" in DEFAULT_SETTINGS

    def test_has_gaming_enabled(self):
        assert "gaming_enabled" in DEFAULT_SETTINGS

    def test_has_circadian_keys(self):
        for key in ("circadian_enabled", "circadian_lat", "circadian_lon",
                    "circadian_bri_min", "circadian_bri_max",
                    "circadian_warmth_enabled", "circadian_warmth_max"):
            assert key in DEFAULT_SETTINGS, f"Missing key: {key}"

    def test_has_curve_points(self):
        assert "curve_points" in DEFAULT_SETTINGS

    def test_gamma_default_is_1(self):
        assert DEFAULT_SETTINGS["gamma_value"] == 1.0

    def test_focus_default_is_false(self):
        assert DEFAULT_SETTINGS["focus_enabled"] is False

    def test_paris_default_coords(self):
        assert abs(DEFAULT_SETTINGS["circadian_lat"] - 48.85) < 0.1
        assert abs(DEFAULT_SETTINGS["circadian_lon"] - 2.35) < 0.1


class TestProfileManagerSnapshot:
    def _mgr(self, tmp_path):
        return ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )

    def test_load_snapshot_missing_returns_none(self, tmp_path):
        mgr = self._mgr(tmp_path)
        assert mgr.load_snapshot() is None

    def test_save_and_load_snapshot(self, tmp_path):
        mgr = self._mgr(tmp_path)
        monitors = [{"device_name": r"\\.\DISPLAY1", "index": 0, "brightness": 75, "contrast": 50}]
        saved_at = mgr.save_snapshot(monitors)
        snap = mgr.load_snapshot()
        assert snap is not None
        assert snap["monitors"][0]["brightness"] == 75
        assert snap["saved_at"] == saved_at

    def test_snapshot_saved_at_format(self, tmp_path):
        mgr = self._mgr(tmp_path)
        ts = mgr.save_snapshot([{"device_name": r"\\.\DISPLAY1", "index": 0}])
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", ts)


class TestProfileManagerSettings:
    def _mgr(self, tmp_path):
        return ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )

    def test_load_settings_missing_file_returns_defaults(self, tmp_path):
        mgr = self._mgr(tmp_path)
        settings = mgr.load_settings()
        assert settings["sync_enabled"] == DEFAULT_SETTINGS["sync_enabled"]
        assert settings["gamma_value"] == DEFAULT_SETTINGS["gamma_value"]

    def test_load_settings_merges_with_defaults(self, tmp_path):
        mgr = self._mgr(tmp_path)
        partial = {"sync_enabled": True}
        mgr.save_settings(partial)
        settings = mgr.load_settings()
        # Saved key overridden
        assert settings["sync_enabled"] is True
        # Missing key filled from defaults
        assert "focus_enabled" in settings
        assert settings["focus_enabled"] == DEFAULT_SETTINGS["focus_enabled"]

    def test_load_settings_ignores_unknown_keys(self, tmp_path):
        settings_path = str(tmp_path / "settings.json")
        with open(settings_path, "w") as f:
            json.dump({"sync_enabled": True, "future_unknown_key": 42}, f)
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            settings_path,
            str(tmp_path / "named.json"),
        )
        settings = mgr.load_settings()
        assert "future_unknown_key" not in settings

    def test_save_and_load_settings_round_trip(self, tmp_path):
        mgr = self._mgr(tmp_path)
        data = {
            "sync_enabled": True,
            "gamma_value": 1.2,
            "focus_enabled": True,
            "focus_dim": 35,
        }
        mgr.save_settings(data)
        loaded = mgr.load_settings()
        assert loaded["sync_enabled"] is True
        assert abs(loaded["gamma_value"] - 1.2) < 0.001
        assert loaded["focus_dim"] == 35

    def test_corrupt_settings_returns_defaults(self, tmp_path):
        settings_path = str(tmp_path / "settings.json")
        with open(settings_path, "w") as f:
            f.write("NOT JSON {{{{")
        mgr = ProfileManager(
            str(tmp_path / "profiles.json"),
            settings_path,
            str(tmp_path / "named.json"),
        )
        settings = mgr.load_settings()
        assert settings["gamma_value"] == DEFAULT_SETTINGS["gamma_value"]

    def test_all_default_keys_present_on_fresh_load(self, tmp_path):
        mgr = self._mgr(tmp_path)
        settings = mgr.load_settings()
        for key in DEFAULT_SETTINGS:
            assert key in settings, f"Missing key: {key}"


class TestNamedProfiles:
    def _mgr(self, tmp_path):
        return ProfileManager(
            str(tmp_path / "profiles.json"),
            str(tmp_path / "settings.json"),
            str(tmp_path / "named.json"),
        )

    def test_list_named_profiles_empty(self, tmp_path):
        mgr = self._mgr(tmp_path)
        assert mgr.list_named_profiles() == []

    def test_save_and_list(self, tmp_path):
        mgr = self._mgr(tmp_path)
        monitors = [{"device_name": r"\\.\DISPLAY1", "brightness": 75}]
        mgr.save_named_profile("Work", monitors, {})
        mgr.save_named_profile("Cinema", monitors, {})
        names = mgr.list_named_profiles()
        assert sorted(names) == ["Cinema", "Work"]

    def test_list_is_sorted(self, tmp_path):
        mgr = self._mgr(tmp_path)
        monitors = []
        mgr.save_named_profile("Zebra", monitors, {})
        mgr.save_named_profile("Alpha", monitors, {})
        assert mgr.list_named_profiles() == ["Alpha", "Zebra"]

    def test_load_named_profile(self, tmp_path):
        mgr = self._mgr(tmp_path)
        monitors = [{"device_name": r"\\.\DISPLAY1", "brightness": 55}]
        gamma = {r"\\.\DISPLAY1": 1.1}
        mgr.save_named_profile("Work", monitors, gamma)
        profile = mgr.load_named_profile("Work")
        assert profile is not None
        assert profile["monitors"][0]["brightness"] == 55
        assert abs(profile["gamma_values"][r"\\.\DISPLAY1"] - 1.1) < 0.001

    def test_load_missing_profile_returns_none(self, tmp_path):
        mgr = self._mgr(tmp_path)
        assert mgr.load_named_profile("DoesNotExist") is None

    def test_overwrite_named_profile(self, tmp_path):
        mgr = self._mgr(tmp_path)
        mgr.save_named_profile("Work", [{"brightness": 50}], {})
        mgr.save_named_profile("Work", [{"brightness": 80}], {})
        profile = mgr.load_named_profile("Work")
        assert profile["monitors"][0]["brightness"] == 80

    def test_delete_named_profile(self, tmp_path):
        mgr = self._mgr(tmp_path)
        mgr.save_named_profile("Temp", [], {})
        mgr.delete_named_profile("Temp")
        assert mgr.load_named_profile("Temp") is None
        assert "Temp" not in mgr.list_named_profiles()

    def test_delete_missing_profile_no_error(self, tmp_path):
        mgr = self._mgr(tmp_path)
        mgr.delete_named_profile("NoSuchProfile")  # should not raise

    def test_curve_points_saved_in_named_profile(self, tmp_path):
        mgr = self._mgr(tmp_path)
        cp = {r"\\.\DISPLAY1": {"R": [[0, 0], [1, 1]]}}
        mgr.save_named_profile("Curves", [], {}, curve_points=cp)
        profile = mgr.load_named_profile("Curves")
        assert profile["curve_points"] == cp

    def test_multiple_monitors_in_named_profile(self, tmp_path):
        mgr = self._mgr(tmp_path)
        monitors = [
            {"device_name": r"\\.\DISPLAY1", "brightness": 75},
            {"device_name": r"\\.\DISPLAY2", "brightness": 60},
        ]
        mgr.save_named_profile("Dual", monitors, {})
        profile = mgr.load_named_profile("Dual")
        assert len(profile["monitors"]) == 2
