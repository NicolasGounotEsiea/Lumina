"""App-profile rules engine.

Handles foreground-process detection, rule matching, value application and
state restore.  Fully decoupled from the UI — all state changes are reported
via callbacks provided at construction time.
"""
import logging
import re
from typing import Callable

from lumina_control.app_rules import AppRule
from lumina_control.utils import (
    get_foreground_process,
    get_foreground_window_title,
    get_foreground_window_monitor,
)

log = logging.getLogger(__name__)

# Number of consecutive 500 ms ticks with the same (process, rule) before firing.
# Avoids flicker on fast alt-tab and title transitions.
_STABILITY_TICKS = 2


def _title_matches(rule: AppRule, title: str | None) -> bool:
    """Return True if the rule's window_title pattern matches *title*.

    When ``rule.window_title`` is None the rule matches any window of that
    process.  An invalid regex falls back to case-insensitive substring match.
    """
    if not rule.window_title:
        return True
    if title is None:
        return False
    try:
        return bool(re.search(rule.window_title, title, re.IGNORECASE))
    except re.error:
        return rule.window_title.lower() in title.lower()


class RulesEngine:
    """Detect the foreground application and apply the first matching AppRule.

    Parameters
    ----------
    rules:
        Initial list of AppRule objects.
    enabled:
        Whether detection is active at startup.
    get_cards:
        Callable that returns the current list of MonitorCard widgets.
    on_rule_active:
        Called with the matched AppRule when a rule becomes active.
    on_rule_inactive:
        Called (no arguments) when the active rule is cleared.
    on_proc_detect:
        Called every poll tick with (process_name: str | None, has_match: bool)
        so the UI can display the detected process.
    """

    def __init__(
        self,
        rules: list,
        enabled: bool,
        get_cards: Callable,
        on_rule_active: Callable,
        on_rule_inactive: Callable,
        on_proc_detect: Callable,
    ) -> None:
        self._rules: list[AppRule] = rules
        self._enabled: bool = enabled
        self._get_cards = get_cards
        self._on_rule_active = on_rule_active
        self._on_rule_inactive = on_rule_inactive
        self._on_proc_detect = on_proc_detect

        # Detection state
        self._active_rule: AppRule | None = None
        # Candidate key = (process_name, id(matched_rule)) for stability guard
        self._candidate_key: tuple | None = None
        self._ticks: int = 0

        # Pre-rule snapshot (restored when the rule ends)
        self._pre_bri: dict[str, int] = {}
        self._pre_con: dict[str, int] = {}
        self._pre_gamma: dict[str, float] = {}
        self._pre_rgb: dict[str, tuple] = {}
        # Saved (custom_luts, custom_curve_points) snapshot per device, for curve restore.
        self._pre_curves: dict[str, tuple] = {}
        self._pre_device: str | None = None

    # ── Public properties ─────────────────────────────────────────────────────

    @property
    def rules(self) -> list:
        return self._rules

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def active_rule(self) -> AppRule | None:
        return self._active_rule

    # ── Public interface ──────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable rule detection."""
        self._enabled = enabled
        if not enabled:
            self.suspend()
            self._candidate_key = None
            self._ticks = 0

    def update_rules(self, rules: list) -> None:
        """Replace the rule list (e.g. after the user edits them).
        Forces re-evaluation on the next poll tick.
        """
        self._rules = rules
        self._active_rule = None
        self._candidate_key = None
        self._ticks = 0

    def poll(self) -> None:
        """Called every 500 ms by the main poll timer.

        Detects the foreground process and window title, matches them against
        rules, and applies / restores values as needed.  No-op when disabled.
        """
        if not self._enabled:
            return

        proc = get_foreground_process()
        title = get_foreground_window_title() if proc else None

        # Find first matching enabled rule (process + optional title regex)
        matched: AppRule | None = None
        if proc:
            for rule in self._rules:
                if (rule.enabled
                        and rule.process.lower() == proc
                        and _title_matches(rule, title)):
                    matched = rule
                    break

        has_match = matched is not None
        self._on_proc_detect(proc, has_match)

        # Stability guard — require _STABILITY_TICKS consecutive ticks with the
        # same (process, rule) pair before firing.  id(matched) differentiates
        # between rules for the same process (window-title variants).
        candidate_key = (proc, id(matched))
        if candidate_key != self._candidate_key:
            self._candidate_key = candidate_key
            self._ticks = 0
            return
        self._ticks += 1
        if self._ticks < _STABILITY_TICKS:
            return

        prev = self._active_rule
        # Same rule still active → nothing to do
        if matched is prev:
            return

        # Leaving a rule → restore
        if matched is None:
            self.suspend()
            return

        # Entering a rule (or switching to a different one)
        device = get_foreground_window_monitor()
        if not self._pre_bri:
            self._snapshot(matched, device)

        self._apply(matched, device)
        self._active_rule = matched
        self._on_rule_active(matched)

    def suspend(self) -> None:
        """Restore the pre-rule state and clear the active rule.

        Safe to call when no rule is active (no-op).
        Called by MainWindow when a higher-priority mode (Focus, Gaming) activates.
        """
        self._restore()
        if self._active_rule is not None:
            self._active_rule = None
            self._on_rule_inactive()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _snapshot(self, rule: AppRule, device: str | None) -> None:
        """Save current monitor state before applying a rule."""
        cards = self._get_cards()
        target = [c for c in cards
                  if c.available and (not device or c.device_name == device)]
        self._pre_bri = {c.device_name: c.sl_bri.value() for c in target}
        self._pre_con = {c.device_name: c.sl_con.value() for c in target}
        if rule.gamma is not None:
            self._pre_gamma = {c.device_name: c.gamma_value for c in target}
        if rule.red is not None or rule.green is not None or rule.blue is not None:
            for c in target:
                rgb = c.read_rgb()
                if rgb is not None:
                    self._pre_rgb[c.device_name] = rgb
        if rule.curve_points:
            for c in target:
                self._pre_curves[c.device_name] = (
                    c._custom_luts,
                    (dict(c._custom_curve_points)
                     if c._custom_curve_points is not None else None),
                )
        self._pre_device = device

    def _apply(self, rule: AppRule, device: str | None) -> None:
        """Push rule values onto the target monitor card(s)."""
        log.debug(
            "Applying rule '%s' on %s: bri=%s con=%s gamma=%s rgb=(%s,%s,%s)"
            " title_pattern=%r",
            rule.label, device or "all",
            rule.brightness, rule.contrast, rule.gamma,
            rule.red, rule.green, rule.blue,
            rule.window_title,
        )
        for c in self._get_cards():
            if not c.available:
                continue
            if device and c.device_name != device:
                continue
            c.apply_rule_values(rule.brightness, rule.contrast)
            c.apply_rule_rgb(rule.red, rule.green, rule.blue)
        if rule.gamma is not None:
            for c in self._get_cards():
                if c.available and (not device or c.device_name == device):
                    c.set_gamma_value(rule.gamma)
        if rule.curve_points:
            from lumina_control.curve_editor import monotone_lut
            pts = {
                ch: [tuple(p) for p in rule.curve_points.get(
                    ch, [(0.0, 0.0), (1.0, 1.0)])]
                for ch in ("R", "G", "B")
            }
            r_lut = monotone_lut(pts["R"])
            g_lut = monotone_lut(pts["G"])
            b_lut = monotone_lut(pts["B"])
            for c in self._get_cards():
                if c.available and (not device or c.device_name == device):
                    # Direct state set — avoid MonitorCard._on_curves_applied because
                    # it triggers save_hook, which would persist the rule's transient
                    # curves as the user's baseline in settings.json.
                    c._ramp_fail_count = 0
                    c._ramp_unsupported = False
                    c._custom_luts = (r_lut, g_lut, b_lut)
                    c._custom_curve_points = pts
                    c._apply_ramp(user_triggered=True)

    def _restore(self) -> None:
        """Restore the snapshot saved before the last rule was applied."""
        if not self._pre_bri:
            return
        for c in self._get_cards():
            if not c.available:
                continue
            bri = self._pre_bri.get(c.device_name)
            con = self._pre_con.get(c.device_name)
            if bri is not None or con is not None:
                c.apply_rule_values(bri, con)
        for device, gamma in self._pre_gamma.items():
            for c in self._get_cards():
                if c.device_name == device and c.available:
                    c.set_gamma_value(gamma)
        for device, rgb in self._pre_rgb.items():
            for c in self._get_cards():
                if c.device_name == device and c.available:
                    c.apply_rule_rgb(*rgb)
        for device, (luts, pts) in self._pre_curves.items():
            for c in self._get_cards():
                if c.device_name == device and c.available:
                    c._ramp_fail_count = 0
                    c._ramp_unsupported = False
                    c._custom_luts = luts
                    c._custom_curve_points = pts
                    c._apply_ramp(user_triggered=True)
        self._pre_bri.clear()
        self._pre_con.clear()
        self._pre_gamma.clear()
        self._pre_rgb.clear()
        self._pre_curves.clear()
        self._pre_device = None
