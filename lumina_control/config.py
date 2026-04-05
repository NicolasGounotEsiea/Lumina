"""Application-wide constants, colour palette and path helpers."""
import os
import sys

APP_NAME = "Lumina Control"
APP_VERSION = "1.0.0"
APP_WIDTH = 420
SINGLE_INSTANCE_SERVER = "LuminaControl_SingleInstance"

# ── Colour palette  (Windows 11 dark Fluent Design) ──────────────────────────
ACCENT_COLOR  = "#60CDFF"              # Windows 11 blue (light variant)
ACCENT_DIM    = "#4AB8F0"
ACCENT_SUBTLE = "rgba(96,205,255,0.12)"

BG_COLOR      = "#202020"             # Window background (Win 11 dark)
CARD_COLOR    = "#2B2B2B"             # Elevated surface / card
CARD_HOVER    = "#363636"             # Card hover
BORDER_COLOR  = "#282828"             # Very subtle dividers
BORDER_ACCENT = "#484848"             # Card / control borders

TEXT_COLOR    = "#F0F0F0"             # Primary text
TEXT_MUTED    = "#8A8A8A"             # Secondary / disabled text

DANGER_COLOR  = "#FF6F6F"             # Destructive / error
WARM_COLOR    = "#FCB900"             # Warning / warm preset
SUCCESS_COLOR = "#6CCB5F"             # Success / on-state

# ── Paths ─────────────────────────────────────────────────────────────────────

def resource_path(rel_path: str) -> str:
    """Return absolute path to a bundled resource (PyInstaller-aware)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", rel_path))


ICON_PATH = resource_path("icon.png")

_app_data_dir: str | None = None


def get_app_data_dir() -> str:
    global _app_data_dir
    if _app_data_dir:
        return _app_data_dir
    from PySide6.QtCore import QStandardPaths
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
