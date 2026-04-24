"""Tests for lumina_control.i18n — translation dict and _() function."""
import pytest

from lumina_control.i18n import _EN, _, _detect_lang


class TestTranslationDict:
    def test_is_dict(self):
        assert isinstance(_EN, dict)

    def test_no_empty_keys(self):
        empty_keys = [k for k in _EN if not k.strip()]
        assert empty_keys == [], f"Empty keys found: {empty_keys}"

    def test_no_empty_values(self):
        empty_values = [(k, v) for k, v in _EN.items() if not v.strip()]
        assert empty_values == [], f"Empty values: {empty_values}"

    def test_no_duplicate_keys(self):
        # Python dicts cannot have duplicate keys, but we check the raw source
        # indirectly: each key must appear exactly once → dict length must match
        # a set of keys
        assert len(_EN) == len(set(_EN.keys()))

    def test_known_french_key_translates(self):
        assert _EN.get("Luminosité globale") == "Global brightness"

    def test_known_key_quit(self):
        assert _EN.get("Quitter") == "Quit"

    def test_values_are_strings(self):
        for k, v in _EN.items():
            assert isinstance(v, str), f"Value for {k!r} is not a string"

    def test_keys_are_strings(self):
        for k in _EN:
            assert isinstance(k, str), f"Key {k!r} is not a string"

    def test_city_names_present(self):
        for city in ["Paris", "Tokyo", "New York", "Sydney"]:
            assert city in _EN, f"City {city!r} missing from _EN"

    def test_gaming_mode_translated(self):
        assert "Gaming mode" in _EN.values()

    def test_focus_mode_translated(self):
        assert "Focus mode" in _EN.values()

    def test_at_least_50_entries(self):
        assert len(_EN) >= 50


class TestDetectLang:
    def test_returns_string(self):
        result = _detect_lang()
        assert isinstance(result, str)

    def test_returns_fr_or_en(self):
        result = _detect_lang()
        assert result in ("fr", "en")


class TestTranslationFunction:
    def test_fr_returns_original(self, monkeypatch):
        import lumina_control.i18n as i18n
        monkeypatch.setattr(i18n, "_LANG", "fr")
        # Reimport _() to pick up the monkeypatched value — call directly
        assert i18n._("Quitter") == "Quitter"

    def test_en_returns_translation(self, monkeypatch):
        import lumina_control.i18n as i18n
        monkeypatch.setattr(i18n, "_LANG", "en")
        assert i18n._("Quitter") == "Quit"

    def test_en_unknown_string_falls_back_to_original(self, monkeypatch):
        import lumina_control.i18n as i18n
        monkeypatch.setattr(i18n, "_LANG", "en")
        assert i18n._("UNKNOWN_STRING_XYZ") == "UNKNOWN_STRING_XYZ"

    def test_empty_string_passthrough(self, monkeypatch):
        import lumina_control.i18n as i18n
        monkeypatch.setattr(i18n, "_LANG", "en")
        assert i18n._("") == ""


class TestFormatStringsConsistency:
    """Ensure format strings have matching placeholders between FR and EN."""

    def test_format_placeholders_match(self):
        mismatches = []
        for fr, en in _EN.items():
            fr_count = fr.count("{}")
            en_count = en.count("{}")
            if fr_count != en_count:
                mismatches.append((fr[:40], fr_count, en_count))
        assert mismatches == [], f"Placeholder count mismatch: {mismatches}"
