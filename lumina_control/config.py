"""Application-wide constants, colour palette and path helpers."""
import os
import sys

APP_NAME = "Lumina Control"
APP_VERSION = "1.0.0"
APP_WIDTH = 400
SINGLE_INSTANCE_SERVER = "LuminaControl_SingleInstance"

# ── Colour palette ────────────────────────────────────────────────────────────
ACCENT_COLOR  = "#38bdf8"
ACCENT_DIM    = "#0ea5e9"
ACCENT_SUBTLE = "rgba(56,189,248,0.12)"
BG_COLOR      = "#0d1117"
CARD_COLOR    = "#161b27"
CARD_HOVER    = "#1d2336"
BORDER_COLOR  = "#1f2535"
BORDER_ACCENT = "#2d3756"
TEXT_COLOR    = "#e2e8f0"
TEXT_MUTED    = "#4e5d78"
DANGER_COLOR  = "#f87171"
WARM_COLOR    = "#fbbf24"
SUCCESS_COLOR = "#34d399"

# ── Paths ─────────────────────────────────────────────────────────────────────

def resource_path(rel_path: str) -> str:
    """Return absolute path to a bundled resource (PyInstaller-aware)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    # config.py lives in lumina_control/; resources are in the project root
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", rel_path))


ICON_PATH = resource_path("icon.png")

_app_data_dir: str | None = None


def get_app_data_dir() -> str:
    global _app_data_dir
    if _app_data_dir:
        return _app_data_dir
    from PySide6.QtCore import QStandardPaths  # deferred: needs QApplication
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not base:
        base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", APP_NAME)
    os.makedirs(base, exist_ok=True)
    _app_data_dir = base
    return base


def get_profile_path() -> str:
    return os.path.join(get_app_data_dir(), "profiles.json")


def get_settings_path() -> str:
    return os.path.join(get_app_data_dir(), "settings.json")
