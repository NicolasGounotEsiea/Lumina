"""Persistence layer: brightness snapshots and application settings."""
import json
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

# Default values used when no saved settings file is found
DEFAULT_SETTINGS: dict = {
    "sync_enabled": False,
    "sync_rgb_enabled": False,
    "sync_master_index": 0,
    "sync_master_device": "",   # stable device name, e.g. r"\\.\DISPLAY1"
    "sync_relative_enabled": False,
    "sync_offset_bri": 0,
    "sync_offset_con": 0,
    "gamma_value": 1.0,
    "gamma_values": {},         # per-monitor gamma: {device_name: float}
    "focus_enabled": False,
    "focus_dim": 20,
    "app_rules_enabled": False,
    "night_mode_enabled": False,
    "night_warmth": 50,         # 0-100
}


class ProfileManager:
    """Handles reading and writing snapshots and persistent app settings."""

    def __init__(self, profile_path: str, settings_path: str,
                 named_profiles_path: str = "") -> None:
        self._profile_path = profile_path
        self._settings_path = settings_path
        self._named_path = named_profiles_path

    # ── Brightness / contrast snapshots ──────────────────────────────────────

    def save_snapshot(self, monitors: list[dict]) -> str:
        """Persist a brightness/contrast snapshot. Returns the saved_at string."""
        saved_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._write(self._profile_path, {"saved_at": saved_at, "monitors": monitors})
        return saved_at

    def load_snapshot(self) -> dict | None:
        """Return the saved snapshot dict, or None if not found."""
        return self._read(self._profile_path)

    # ── Application settings ──────────────────────────────────────────────────

    def save_settings(self, settings: dict) -> None:
        """Persist application settings (sync, gamma, focus…)."""
        self._write(self._settings_path, settings)

    def load_settings(self) -> dict:
        """Return settings dict merged with defaults (safe against missing keys)."""
        data = self._read(self._settings_path) or {}
        result = DEFAULT_SETTINGS.copy()
        # Only update keys we actually know about (ignore unknown saved keys)
        result.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        return result

    # ── Named profiles ────────────────────────────────────────────────────────

    def list_named_profiles(self) -> list[str]:
        """Return sorted list of saved named profile names."""
        return sorted((self._read(self._named_path) or {}).keys())

    def save_named_profile(self, name: str, monitors: list[dict],
                           gamma_values: dict) -> None:
        """Save/overwrite a named profile."""
        data = self._read(self._named_path) or {}
        data[name] = {"monitors": monitors, "gamma_values": gamma_values}
        self._write(self._named_path, data)

    def load_named_profile(self, name: str) -> dict | None:
        """Return the named profile dict, or None if not found."""
        return (self._read(self._named_path) or {}).get(name)

    def delete_named_profile(self, name: str) -> None:
        """Delete a named profile (no-op if not found)."""
        data = self._read(self._named_path) or {}
        data.pop(name, None)
        self._write(self._named_path, data)

    # ── I/O helpers ───────────────────────────────────────────────────────────

    def _write(self, path: str, data: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            log.warning("Cannot write %s: %s", path, e)

    def _read(self, path: str) -> dict | None:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("Cannot read %s: %s", path, e)
            return None
