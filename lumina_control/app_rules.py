"""Automatic brightness/contrast/gamma profiles triggered by foreground application."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

log = logging.getLogger(__name__)


@dataclass
class AppRule:
    process:      str            # exe name matched case-insensitively, e.g. "vlc.exe"
    label:        str            # display name
    brightness:   int | None     # 0-100, or None = don't touch
    contrast:     int | None     # 0-100, or None = don't touch
    gamma:        float | None   # e.g. 1.0, or None = don't touch
    red:          int | None = None   # DDC VCP 0x16, 0-100, or None = don't touch
    green:        int | None = None   # DDC VCP 0x18, 0-100, or None = don't touch
    blue:         int | None = None   # DDC VCP 0x1A, 0-100, or None = don't touch
    enabled:      bool = True
    window_title: str | None = None   # regex matched on foreground window title; None = any


# ── Built-in defaults ─────────────────────────────────────────────────────────

DEFAULT_RULES: list[AppRule] = [
    # Media players — dim for comfortable viewing
    AppRule("vlc.exe",         "VLC",               25,   50,  None),
    AppRule("mpv.exe",         "mpv",               25,   50,  None),
    AppRule("mpc-hc64.exe",    "MPC-HC",            25,   50,  None),
    AppRule("mpc-be64.exe",    "MPC-BE",            25,   50,  None),
    # Video calls — boost brightness so the other party sees you correctly
    AppRule("teams.exe",       "Microsoft Teams",   90,   60,  None),
    AppRule("ms-teams.exe",    "Teams (nouveau)",   90,   60,  None),
    AppRule("zoom.exe",        "Zoom",              90,   60,  None),
    AppRule("webex.exe",       "Cisco Webex",       90,   60,  None),
    # Creative apps — accurate gamma is critical
    AppRule("photoshop.exe",   "Photoshop",         75,   55,   1.0),
    AppRule("lightroom.exe",   "Lightroom",         70,   55,   1.0),
    AppRule("afterfx.exe",     "After Effects",     80,   55,   1.0),
    AppRule("blender.exe",     "Blender",           80,   55,  None),
    # Gaming — higher brightness + slight contrast boost
    AppRule("steam.exe",       "Steam",             80,   65,  None),
    AppRule("obs64.exe",       "OBS Studio",        80,   55,  None),
    AppRule("discord.exe",     "Discord",           65,  None, None),
]


# ── Persistence ───────────────────────────────────────────────────────────────

class AppRuleManager:
    def __init__(self, path: str) -> None:
        self._path = path

    def load(self) -> list[AppRule]:
        if not os.path.exists(self._path):
            return list(DEFAULT_RULES)
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rules: list[AppRule] = []
            for d in data:
                bri = d.get("brightness")
                con = d.get("contrast")
                gam = d.get("gamma")
                r   = d.get("red")
                g   = d.get("green")
                b   = d.get("blue")
                wt = d.get("window_title")
                rules.append(AppRule(
                    process      = str(d.get("process", "")).lower(),
                    label        = str(d.get("label", d.get("process", ""))),
                    brightness   = int(bri) if bri is not None else None,
                    contrast     = int(con) if con is not None else None,
                    gamma        = float(gam) if gam is not None else None,
                    red          = int(r) if r is not None else None,
                    green        = int(g) if g is not None else None,
                    blue         = int(b) if b is not None else None,
                    enabled      = bool(d.get("enabled", True)),
                    window_title = str(wt) if wt else None,
                ))
            return rules
        except Exception as e:
            log.warning("Cannot load app rules: %s", e)
            return list(DEFAULT_RULES)

    def save(self, rules: list[AppRule]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in rules], f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.warning("Cannot save app rules: %s", e)
