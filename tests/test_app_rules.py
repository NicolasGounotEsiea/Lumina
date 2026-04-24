"""Tests for lumina_control.app_rules — AppRule dataclass and AppRuleManager."""
import json
import os
import tempfile

import pytest

from lumina_control.app_rules import AppRule, AppRuleManager, DEFAULT_RULES


class TestAppRuleDataclass:
    def test_required_fields(self):
        rule = AppRule(
            process="vlc.exe",
            label="VLC",
            brightness=25,
            contrast=50,
            gamma=None,
        )
        assert rule.process == "vlc.exe"
        assert rule.label == "VLC"
        assert rule.brightness == 25
        assert rule.contrast == 50
        assert rule.gamma is None

    def test_optional_fields_default_to_none(self):
        rule = AppRule("app.exe", "App", 50, 50, 1.0)
        assert rule.red is None
        assert rule.green is None
        assert rule.blue is None
        assert rule.window_title is None
        assert rule.curve_points is None

    def test_enabled_defaults_to_true(self):
        rule = AppRule("app.exe", "App", 50, 50, 1.0)
        assert rule.enabled is True

    def test_can_disable(self):
        rule = AppRule("app.exe", "App", 50, 50, 1.0, enabled=False)
        assert rule.enabled is False

    def test_curve_points_field(self):
        cp = {"R": [[0, 0], [1, 1]], "G": [[0, 0], [1, 1]], "B": [[0, 0], [1, 1]]}
        rule = AppRule("app.exe", "App", 50, 50, 1.0, curve_points=cp)
        assert rule.curve_points == cp


class TestDefaultRules:
    def test_is_list(self):
        assert isinstance(DEFAULT_RULES, list)

    def test_not_empty(self):
        assert len(DEFAULT_RULES) > 0

    def test_all_are_approle(self):
        for r in DEFAULT_RULES:
            assert isinstance(r, AppRule)

    def test_vlc_rule_exists(self):
        procs = [r.process for r in DEFAULT_RULES]
        assert "vlc.exe" in procs

    def test_all_processes_lowercase(self):
        for r in DEFAULT_RULES:
            assert r.process == r.process.lower(), f"{r.process} is not lowercase"

    def test_brightness_in_range_or_none(self):
        for r in DEFAULT_RULES:
            if r.brightness is not None:
                assert 0 <= r.brightness <= 100

    def test_contrast_in_range_or_none(self):
        for r in DEFAULT_RULES:
            if r.contrast is not None:
                assert 0 <= r.contrast <= 100


class TestAppRuleManagerLoad:
    def test_missing_file_returns_defaults(self, tmp_path):
        mgr = AppRuleManager(str(tmp_path / "nonexistent.json"))
        rules = mgr.load()
        assert len(rules) == len(DEFAULT_RULES)

    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        original = [
            AppRule("vlc.exe", "VLC", 25, 50, None),
            AppRule("zoom.exe", "Zoom", 90, 60, None, enabled=True),
        ]
        mgr.save(original)
        loaded = mgr.load()
        assert len(loaded) == 2
        assert loaded[0].process == "vlc.exe"
        assert loaded[0].brightness == 25
        assert loaded[1].process == "zoom.exe"

    def test_process_name_lowercased_on_load(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            json.dump([{
                "process": "VLC.EXE",
                "label": "VLC",
                "brightness": 25,
                "contrast": 50,
                "gamma": None,
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].process == "vlc.exe"

    def test_optional_rgb_loaded_as_none(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            json.dump([{
                "process": "vlc.exe",
                "label": "VLC",
                "brightness": 25,
                "contrast": 50,
                "gamma": None,
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].red is None
        assert rules[0].green is None
        assert rules[0].blue is None

    def test_rgb_values_loaded(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            json.dump([{
                "process": "photoshop.exe",
                "label": "PS",
                "brightness": 75,
                "contrast": 55,
                "gamma": 1.0,
                "red": 80,
                "green": 70,
                "blue": 90,
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].red == 80
        assert rules[0].green == 70
        assert rules[0].blue == 90

    def test_corrupt_file_returns_defaults(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            f.write("INVALID JSON {{{")
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert len(rules) == len(DEFAULT_RULES)

    def test_curve_points_loaded(self, tmp_path):
        path = str(tmp_path / "rules.json")
        cp = {"R": [[0, 0], [0.5, 0.7], [1, 1]], "G": [[0, 0], [1, 1]], "B": [[0, 0], [1, 1]]}
        with open(path, "w") as f:
            json.dump([{
                "process": "app.exe",
                "label": "App",
                "brightness": 50,
                "contrast": 50,
                "gamma": None,
                "curve_points": cp,
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].curve_points is not None
        assert "R" in rules[0].curve_points

    def test_curve_points_empty_dict_becomes_none(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            json.dump([{
                "process": "app.exe",
                "label": "App",
                "brightness": 50,
                "contrast": 50,
                "gamma": None,
                "curve_points": {},
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].curve_points is None

    def test_window_title_loaded(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            json.dump([{
                "process": "app.exe",
                "label": "App",
                "brightness": 50,
                "contrast": 50,
                "gamma": None,
                "window_title": "Netflix.*",
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].window_title == "Netflix.*"

    def test_enabled_false_preserved(self, tmp_path):
        path = str(tmp_path / "rules.json")
        with open(path, "w") as f:
            json.dump([{
                "process": "app.exe",
                "label": "App",
                "brightness": 50,
                "contrast": 50,
                "gamma": None,
                "enabled": False,
            }], f)
        mgr = AppRuleManager(path)
        rules = mgr.load()
        assert rules[0].enabled is False


class TestAppRuleManagerSave:
    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        mgr.save([AppRule("vlc.exe", "VLC", 25, 50, None)])
        assert os.path.exists(path)

    def test_save_valid_json(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        mgr.save([AppRule("vlc.exe", "VLC", 25, 50, None)])
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert data[0]["process"] == "vlc.exe"

    def test_save_empty_list(self, tmp_path):
        path = str(tmp_path / "rules.json")
        mgr = AppRuleManager(path)
        mgr.save([])
        with open(path) as f:
            data = json.load(f)
        assert data == []
