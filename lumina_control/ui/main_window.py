"""Main floating control panel."""
import logging
import math
from functools import partial

from PySide6.QtCore import Qt, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSlider, QToolTip, QVBoxLayout, QWidget,
)

from lumina_control.circadian import CircadianEngine, PRESET_CITIES
from lumina_control.config import (
    ACCENT_COLOR, APP_NAME, APP_WIDTH, WARM_COLOR,
    get_named_profiles_path, get_profile_path, get_rules_path, get_settings_path,
)
from lumina_control.i18n import _
from lumina_control.profiles import ProfileManager
from lumina_control.app_rules import AppRule, AppRuleManager
from lumina_control.rules_engine import RulesEngine
from lumina_control import startup as _startup
from lumina_control.updater import UpdateChecker
from lumina_control.utils import (
    get_active_screen_index, get_foreground_process, get_foreground_window_monitor,
    invalidate_monitors_cache, is_fullscreen_foreground, wake_all_monitors,
)
from lumina_control.monitor_enumerate import enumerate_monitors
from lumina_control.ui.monitor_card import MonitorCard
from lumina_control.ui.patterns import PatternWindow
from lumina_control.ui.calibration import CalibrationWizard

log = logging.getLogger(__name__)


class _CircadianCurveWidget(QWidget):
    """24-h circadian curve — cohesive with the app card style.

    Draws on the app's dark palette:
    - Card-style background (#2B2B2B) with rounded corners + border
    - Subtle warm day-zone band, darker night zones
    - Filled sin-curve in warm amber
    - Dashed sunrise / sunset markers with HH:MM
    - Hour grid: 00 / 06 / 12 / 18
    - Accent (#60CDFF) vertical line + dot for the current time
    - Geometric sun (circle + rays) or crescent moon above the cursor
    """

    _H = 108

    def __init__(self, engine: "CircadianEngine", parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self.setFixedHeight(self._H)

    def refresh(self) -> None:
        self.update()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _draw_sun(p: QPainter, cx: float, cy: float, r: float) -> None:
        """Geometric sun: filled circle + 8 short rays."""
        p.save()
        p.setBrush(QColor(255, 200, 50))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)
        ray_pen = QPen(QColor(255, 200, 50, 180), 1.2, Qt.SolidLine, Qt.RoundCap)
        p.setPen(ray_pen)
        p.setBrush(Qt.NoBrush)
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = cx + math.cos(angle) * (r + 2.5)
            y1 = cy + math.sin(angle) * (r + 2.5)
            x2 = cx + math.cos(angle) * (r + 5.5)
            y2 = cy + math.sin(angle) * (r + 5.5)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.restore()

    @staticmethod
    def _draw_moon(p: QPainter, cx: float, cy: float, r: float) -> None:
        """Geometric crescent moon using path clipping."""
        p.save()
        p.setBrush(QColor(180, 200, 230))
        p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), r, r)
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx + r * 0.55, cy - r * 0.1), r * 0.82, r * 0.82)
        crescent = path.subtracted(clip)
        p.drawPath(crescent)
        p.restore()

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        eng = self._engine
        eng._refresh_sun_cache()

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W, H = float(self.width()), float(self.height())
        radius   = 10.0
        pad_l    = 2.0
        pad_r    = 2.0
        pad_top  = 18.0   # icon zone
        pad_bot  = 16.0   # label zone
        curve_h  = H - pad_top - pad_bot

        rise = eng._sunrise
        sett = eng._sunset

        def _x(hour: float) -> float:
            return pad_l + (hour / 24.0) * (W - pad_l - pad_r)

        def _y(bri: int) -> float:
            t = (bri - eng.bri_min) / max(1, eng.bri_max - eng.bri_min)
            return pad_top + curve_h * (1.0 - t)

        # ── Card background ───────────────────────────────────────────────────
        card_path = QPainterPath()
        card_path.addRoundedRect(QRectF(0, 0, W, H), radius, radius)
        p.fillPath(card_path, QColor("#2B2B2B"))

        # ── Night overlay (before sunrise + after sunset) ─────────────────────
        night_color = QColor(0, 0, 0, 55)
        sx, ex = _x(rise), _x(sett)

        left_night = QPainterPath()
        left_night.addRoundedRect(QRectF(0, 0, sx, H), radius, radius)
        left_night = left_night.intersected(card_path)
        p.fillPath(left_night, night_color)

        right_night = QPainterPath()
        right_night.addRoundedRect(QRectF(ex, 0, W - ex, H), radius, radius)
        right_night = right_night.intersected(card_path)
        p.fillPath(right_night, night_color)

        # Soft warm day-zone horizontal gradient
        if ex > sx:
            day_grad = QLinearGradient(QPointF(sx, 0), QPointF(ex, 0))
            day_grad.setColorAt(0.0,  QColor(255, 160, 30,  0))
            day_grad.setColorAt(0.25, QColor(255, 160, 30, 18))
            day_grad.setColorAt(0.75, QColor(255, 160, 30, 18))
            day_grad.setColorAt(1.0,  QColor(255, 160, 30,  0))
            day_path = QPainterPath()
            day_path.addRect(QRectF(sx, 0, ex - sx, H))
            day_path = day_path.intersected(card_path)
            p.fillPath(day_path, day_grad)

        # ── Hour grid (00 / 06 / 12 / 18) ────────────────────────────────────
        grid_font = QFont("Segoe UI Variable", 7)
        p.setFont(grid_font)
        fm = p.fontMetrics()
        for hour, label in ((0, "00"), (6, "06"), (12, "12"), (18, "18")):
            gx = _x(float(hour))
            p.setPen(QPen(QColor(255, 255, 255, 18), 1))
            p.drawLine(QPointF(gx, pad_top), QPointF(gx, H - pad_bot))
            tw = fm.horizontalAdvance(label)
            lx = max(2.0, min(gx - tw / 2, W - tw - 2))
            p.setPen(QColor(255, 255, 255, 35))
            p.drawText(QPointF(lx, H - 3), label)

        # ── Curve fill + line ─────────────────────────────────────────────────
        N = max(int(W), 200)
        fill = QPainterPath()
        line = QPainterPath()
        fill.moveTo(_x(0), H - pad_bot)
        for i in range(N + 1):
            hour = (i / N) * 24.0
            bri  = eng._bri_curve(hour)
            px, py = _x(hour), _y(bri)
            fill.lineTo(px, py)
            if i == 0:
                line.moveTo(px, py)
            else:
                line.lineTo(px, py)
        fill.lineTo(_x(24), H - pad_bot)
        fill.closeSubpath()

        fill_clip = fill.intersected(card_path)
        fill_grad = QLinearGradient(QPointF(0, pad_top), QPointF(0, H - pad_bot))
        fill_grad.setColorAt(0.0, QColor(255, 170, 30, 90))
        fill_grad.setColorAt(1.0, QColor(255, 110, 0,   8))
        p.fillPath(fill_clip, fill_grad)

        pen_curve = QPen(QColor(255, 185, 45, 200), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen_curve)
        p.drawPath(line)

        # ── Sunrise / sunset dashed markers + labels ──────────────────────────
        pen_dash = QPen(QColor(255, 255, 255, 38), 1, Qt.DashLine)
        pen_dash.setDashPattern([3, 4])
        p.setPen(pen_dash)
        for x in (sx, ex):
            p.drawLine(QPointF(x, pad_top), QPointF(x, H - pad_bot))

        lbl_font = QFont("Segoe UI Variable", 8)
        lbl_font.setWeight(QFont.Medium)
        p.setFont(lbl_font)
        fm2 = p.fontMetrics()
        p.setPen(QColor(255, 255, 255, 100))

        rise_txt = eng._fmt(rise)
        sett_txt = eng._fmt(sett)
        rtw = fm2.horizontalAdvance(rise_txt)
        stw = fm2.horizontalAdvance(sett_txt)
        lbl_y = H - 3
        p.drawText(QPointF(max(pad_l, min(sx + 3, W - rtw - 4)), lbl_y), rise_txt)
        p.drawText(QPointF(max(pad_l, min(ex - stw - 3, W - stw - 4)), lbl_y), sett_txt)

        # ── Current-time accent line + dot ────────────────────────────────────
        now_h   = eng._current_hour()
        nx      = _x(now_h)
        is_day  = rise < now_h < sett
        bri_now = eng._bri_curve(now_h)
        ny      = _y(bri_now)

        accent = QColor("#60CDFF")
        p.setPen(QPen(QColor(96, 205, 255, 70), 1))
        p.drawLine(QPointF(nx, pad_top), QPointF(nx, H - pad_bot))

        p.setBrush(accent)
        p.setPen(QPen(QColor("#2B2B2B"), 1.5))
        p.drawEllipse(QPointF(nx, ny), 4.0, 4.0)

        # ── Sun or moon icon above / below cursor ─────────────────────────────
        icon_r  = 5.5
        icon_cx = max(icon_r + 8, min(nx, W - icon_r - 8))
        if is_day:
            icon_cy = max(icon_r + 6, ny - 13)
            self._draw_sun(p, icon_cx, icon_cy, icon_r)
        else:
            icon_cy = min(H - pad_bot - icon_r - 2, ny + 13)
            icon_cy = max(icon_r + 4, icon_cy)
            self._draw_moon(p, icon_cx, icon_cy, icon_r)

        # ── Border ────────────────────────────────────────────────────────────
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#484848"), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), radius, radius)

        p.end()


class _CollapsibleSection(QWidget):
    """Expandable / collapsible labelled panel used inside MainWindow."""

    def __init__(self, title: str, expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._title = title

        vbox = QVBoxLayout(self)
        vbox.setSpacing(0)
        vbox.setContentsMargins(0, 0, 0, 0)

        self._btn = QPushButton()
        self._btn.setObjectName("CollapsibleHeader")
        self._btn.setCheckable(True)
        self._btn.setChecked(expanded)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setFocusPolicy(Qt.NoFocus)
        self._btn.clicked.connect(self._toggle)
        self._set_btn_text(expanded)
        vbox.addWidget(self._btn)

        self._body = QWidget()
        body_l = QVBoxLayout(self._body)
        body_l.setContentsMargins(2, 6, 2, 10)
        body_l.setSpacing(10)
        self._body_layout = body_l
        self._body.setVisible(expanded)
        vbox.addWidget(self._body)

    def _set_btn_text(self, expanded: bool) -> None:
        arrow = "▾" if expanded else "▸"
        self._btn.setText(f"  {arrow}   {self._title}")

    def _toggle(self, checked: bool) -> None:
        self._set_btn_text(checked)
        self._body.setVisible(checked)

    def add_widget(self, w: QWidget) -> None:
        self._body_layout.addWidget(w)

    def add_layout(self, layout) -> None:
        self._body_layout.addLayout(layout)


class MainWindow(QWidget):

    brightness_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setObjectName("MainWindow")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)  # prevent WM_ERASEBKGND fill
        self.setFixedWidth(APP_WIDTH)

        self._profile = ProfileManager(
            get_profile_path(), get_settings_path(), get_named_profiles_path()
        )

        # Load persisted settings (defaults if no file)
        s = self._profile.load_settings()
        self.sync_enabled          = s["sync_enabled"]
        self.sync_rgb_enabled      = s["sync_rgb_enabled"]
        self.sync_master_index     = s["sync_master_index"]   # fallback when device not found
        self.sync_master_device    = s["sync_master_device"]  # stable device name
        self.sync_relative_enabled = s["sync_relative_enabled"]
        self.sync_offset_bri       = s["sync_offset_bri"]
        self.sync_offset_con       = s["sync_offset_con"]
        self.gamma_value           = s["gamma_value"]
        self.gamma_values:  dict   = s["gamma_values"]
        self.focus_enabled         = s["focus_enabled"]
        self.focus_dim             = s["focus_dim"]
        self.night_mode_enabled    = s["night_mode_enabled"]
        self.night_warmth          = s["night_warmth"]
        self.gaming_enabled        = s["gaming_enabled"]
        self.gaming_brightness     = s["gaming_brightness"]
        self.gaming_contrast       = s["gaming_contrast"]
        self.focus_delay           = int(s["focus_delay"])

        # Circadian engine
        self._circadian = CircadianEngine(
            lat             = float(s["circadian_lat"]),
            lon             = float(s["circadian_lon"]),
            bri_min         = int(s["circadian_bri_min"]),
            bri_max         = int(s["circadian_bri_max"]),
            warmth_enabled  = bool(s["circadian_warmth_enabled"]),
            warmth_max      = int(s["circadian_warmth_max"]),
        )
        self._circadian.enabled      = bool(s["circadian_enabled"])
        self._circadian_city         = str(s["circadian_city"])
        self._circadian_bri_before: int | None = None  # snapshot taken at enable time
        # Exclusion set — processes that never trigger gaming mode (matched lowercase)
        self._gaming_exclusions: set[str] = {
            p.strip().lower() for p in s["gaming_exclusions"] if p.strip()
        }

        # App rules engine
        self._rule_mgr = AppRuleManager(get_rules_path())
        self._rules_engine = RulesEngine(
            rules=self._rule_mgr.load(),
            enabled=s["app_rules_enabled"],
            get_cards=lambda: self.cards,
            on_rule_active=self._update_rule_status,
            on_rule_inactive=lambda: self._update_rule_status(None),
            on_proc_detect=self._on_proc_detect,
        )

        # Transient runtime state
        self.cards:               list[MonitorCard] = []
        self._sync_guard:         bool              = False
        self.pattern_window:      PatternWindow | None     = None
        self.calibration_wizard:  CalibrationWizard | None = None
        self.pre_focus_values:    dict = {}
        self.last_active:         int | None = None
        self._last_focus_target:  int | None = None
        self._last_focus_dim:     int | None = None
        self.focus_action                    = None  # QAction from tray
        self.gaming_action                   = None  # QAction from tray
        self._gaming_active:      bool              = False
        self._gaming_fs_ticks:    int               = 0
        self._gaming_device:      str | None        = None   # device_name of the game screen
        self._pre_gaming_bri:     dict[int, int]    = {}
        self._pre_gaming_con:     dict[int, int]    = {}
        self._gaming_exit_timer                     = QTimer(self)
        self._gaming_exit_timer.setSingleShot(True)
        self._gaming_exit_timer.setInterval(2000)
        self._gaming_exit_timer.timeout.connect(self._exit_gaming_mode)

        self._focus_delay_timer                     = QTimer(self)
        self._focus_delay_timer.setSingleShot(True)
        self._focus_delay_timer.timeout.connect(lambda: self._apply_focus(force=True))

        self._drag_pos = None  # QPoint | None — set while dragging from title bar

        self._build_ui()
        self._apply_loaded_settings()
        self.refresh()
        self._refresh_snapshot_label()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(500)

        # Non-blocking update check (B10)
        self._updater = UpdateChecker(self)
        self._updater.update_available.connect(self._on_update_available)
        QTimer.singleShot(3000, self._updater.start)   # delay 3 s after launch

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer_l = QVBoxLayout(self)
        outer_l.setContentsMargins(10, 10, 10, 10)

        # Container with drop shadow
        self.container = QWidget()
        self.container.setObjectName("Container")
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(28)
        eff.setColor(QColor(0, 0, 0, 160))
        eff.setOffset(0, 4)
        self.container.setGraphicsEffect(eff)
        outer_l.addWidget(self.container)

        container_l = QVBoxLayout(self.container)
        container_l.setSpacing(0)
        container_l.setContentsMargins(0, 0, 0, 0)

        # ── Title bar ─────────────────────────────────
        header = QWidget()
        header.setObjectName("TitleBar")
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(14, 10, 10, 10)
        header_l.setSpacing(6)

        icon_lbl = QLabel("◈")
        icon_lbl.setObjectName("AccentIcon")
        title_lbl = QLabel(APP_NAME)
        title_lbl.setObjectName("AppTitle")

        btn_refresh = QPushButton("↻")
        btn_refresh.setProperty("class", "icon-btn")
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip(_("Rafraîchir les écrans"))
        btn_refresh.clicked.connect(self.refresh)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseWinBtn")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip(_("Masquer"))
        btn_close.clicked.connect(self.hide)

        header_l.addWidget(icon_lbl)
        header_l.addSpacing(4)
        header_l.addWidget(title_lbl)
        header_l.addStretch()
        header_l.addWidget(btn_refresh)
        header_l.addWidget(btn_close)
        container_l.addWidget(header)
        self._title_bar = header  # reference used for drag-to-move hit testing

        sep_top = QFrame()
        sep_top.setObjectName("Separator")
        sep_top.setFrameShape(QFrame.HLine)
        container_l.addWidget(sep_top)

        # ── Scrollable content ────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # AlwaysOn reserves the 6 px scrollbar track permanently.
        # With AsNeeded the bar pops in when a section expands past the viewport
        # height, stealing viewport width and triggering a full layout reflow —
        # that's the visible "jump".  Our scrollbar is styled to 6 px and
        # nearly invisible when inactive, so the reserved space is unnoticeable.
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # Fixed height: prevents the window from resizing when sections are
        # expanded/collapsed, which caused the visible "jump".  Content scrolls
        # inside the panel just like any OS tray panel (volume, bluetooth…).
        _avail_h = (QApplication.primaryScreen().availableGeometry().height()
                    if QApplication.primaryScreen() else 1080)
        scroll.setFixedHeight(min(560, max(420, int(_avail_h * 0.52))))

        content_w = QWidget()
        self.main_l = QVBoxLayout(content_w)
        self.main_l.setSpacing(8)
        self.main_l.setContentsMargins(12, 12, 12, 14)
        scroll.setWidget(content_w)
        container_l.addWidget(scroll)

        # ── Content sections ──────────────────────────
        self._build_brightness_strip()
        self._build_quick_section()

        self.main_l.addWidget(self._sep())

        # Monitor cards (primary content)
        screens_hdr = QHBoxLayout()
        screens_hdr.addWidget(self._section_label(_("ÉCRANS")))
        screens_hdr.addStretch()
        self.main_l.addLayout(screens_hdr)
        # DDC-CI warning banner (hidden until a N/A monitor is detected)
        self._lbl_ddc_banner = QLabel("")
        self._lbl_ddc_banner.setObjectName("DDCBanner")
        self._lbl_ddc_banner.setWordWrap(True)
        self._lbl_ddc_banner.setVisible(False)
        self.main_l.addWidget(self._lbl_ddc_banner)

        self.mon_l = QVBoxLayout()
        self.mon_l.setSpacing(8)
        self.main_l.addLayout(self.mon_l)

        self.main_l.addWidget(self._group_sep(_("RÉGLAGES")))

        self._build_sync_section()
        self._build_gamma_section()
        self._build_focus_section()
        self._build_gaming_section()
        self._build_snapshot_section()

        self.main_l.addWidget(self._group_sep(_("AUTOMATISATION")))
        self._build_circadian_section()
        self._build_app_rules_section()
        self._build_named_profiles_section()

        self.main_l.addWidget(self._group_sep(_("APPLICATION")))
        self._build_tools_section()
        self._build_settings_section()

        # Update banner — hidden until a newer release is detected
        self._update_banner = self._make_update_banner()
        self.main_l.addWidget(self._update_banner)

        self.main_l.addStretch()

        btn_quit = QPushButton(_("Quitter l'application"))
        btn_quit.setObjectName("QuitBtn")
        btn_quit.setCursor(Qt.PointingHandCursor)
        btn_quit.clicked.connect(QApplication.quit)
        self.main_l.addWidget(btn_quit, alignment=Qt.AlignCenter)

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_brightness_strip(self) -> None:
        """Global brightness — always visible, visually prominent."""
        strip = QWidget()
        strip.setObjectName("BrightnessStrip")
        sl = QVBoxLayout(strip)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setSpacing(8)

        h = QHBoxLayout()
        lbl = QLabel(_("Luminosité globale"))
        lbl.setObjectName("Subtle")
        self.lbl_glob_val = QLabel("50%")
        self.lbl_glob_val.setObjectName("ValueBadge")
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(self.lbl_glob_val)
        sl.addLayout(h)

        self.sl_glob = QSlider(Qt.Horizontal)
        self.sl_glob.setRange(0, 100)
        self.sl_glob.setValue(50)
        # Apply on every value change (not just release) so cards track the
        # global slider in real time.  Each card's 150 ms debounce timer
        # absorbs the rapid events — DDC-CI writes only fire after the user
        # stops dragging, keeping the UI perfectly responsive.
        self.sl_glob.valueChanged.connect(lambda v: self.lbl_glob_val.setText(f"{v}%"))
        self.sl_glob.valueChanged.connect(self.brightness_changed)
        self.sl_glob.valueChanged.connect(lambda _: self._apply_glob())
        sl.addWidget(self.sl_glob)

        self._brightness_strip = strip
        self.main_l.addWidget(strip)

    def _build_quick_section(self) -> None:
        # Preset pills
        h_pre = QHBoxLayout()
        h_pre.setSpacing(6)
        btn_day = QPushButton(_("☀  Jour  80%"))
        btn_day.setProperty("class", "pill")
        btn_day.setStyleSheet(
            f"color:{WARM_COLOR}; border-color:rgba(252,185,0,0.35);"
            f" background:rgba(252,185,0,0.08);"
        )
        btn_day.setCursor(Qt.PointingHandCursor)
        btn_day.clicked.connect(self._preset_day)
        btn_night = QPushButton(_("☾  Nuit  25%"))
        btn_night.setProperty("class", "pill")
        btn_night.setCursor(Qt.PointingHandCursor)
        btn_night.clicked.connect(self._preset_night)
        h_pre.addWidget(btn_day)
        h_pre.addWidget(btn_night)
        self.main_l.addLayout(h_pre)

        # Power row
        h_pow = QHBoxLayout()
        h_pow.setSpacing(6)
        for label, slot, cls in [
            (_("⏻  Allumer"),   partial(self._set_all_power, True),  "pill"),
            (_("⭘  Éteindre"),  partial(self._set_all_power, False), "pill-muted"),
            (_("⏵  Réveiller"), wake_all_monitors,                   "pill-muted"),
        ]:
            btn = QPushButton(label)
            btn.setProperty("class", cls)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            h_pow.addWidget(btn)
        self.main_l.addLayout(h_pow)

    def _build_sync_section(self) -> None:
        sec = _CollapsibleSection(_("SYNCHRONISATION"), expanded=False)

        # ── Row 1 : toggle + master picker ───────────────────────────────────
        h_sync = QHBoxLayout()
        self.chk_sync = QCheckBox(_("Lier les écrans"))
        self.chk_sync.toggled.connect(self._set_sync_enabled)
        lbl_master = QLabel(_("Maître"))
        lbl_master.setObjectName("Subtle")
        self.cmb_master = QComboBox()
        self.cmb_master.setFixedWidth(120)
        self.cmb_master.setToolTip(_("L'écran maître pilote les autres"))
        self.cmb_master.currentIndexChanged.connect(self._set_sync_master)
        h_sync.addWidget(self.chk_sync)
        h_sync.addStretch()
        h_sync.addWidget(lbl_master)
        h_sync.addWidget(self.cmb_master)
        sec.add_layout(h_sync)

        # ── Status badge ──────────────────────────────────────────────────────
        self._lbl_sync_status = QLabel("")
        self._lbl_sync_status.setObjectName("SyncStatus")
        sec.add_widget(self._lbl_sync_status)

        # ── Row 2 : options (RGB + sync now) ─────────────────────────────────
        h2 = QHBoxLayout()
        self.chk_sync_rgb = QCheckBox(_("Couleurs RGB"))
        self.chk_sync_rgb.toggled.connect(self._set_sync_rgb_enabled)
        self.btn_sync_now = QPushButton(_("Sync maintenant"))
        self.btn_sync_now.setProperty("class", "pill-muted")
        self.btn_sync_now.setCursor(Qt.PointingHandCursor)
        self.btn_sync_now.clicked.connect(self.sync_now)
        h2.addWidget(self.chk_sync_rgb)
        h2.addStretch()
        h2.addWidget(self.btn_sync_now)
        sec.add_layout(h2)

        # ── Row 3 : relative offset toggle ───────────────────────────────────
        h3 = QHBoxLayout()
        self.chk_sync_relative = QCheckBox(_("Décalage permanent"))
        self.chk_sync_relative.setToolTip(
            _("Maintient un écart fixe de luminosité et contraste entre le maître et les autres écrans")
        )
        self.chk_sync_relative.toggled.connect(self._set_sync_relative_enabled)
        h3.addWidget(self.chk_sync_relative)
        h3.addStretch()
        sec.add_layout(h3)

        # ── Offset sliders ────────────────────────────────────────────────────
        for attr, label, lo, hi, lbl_attr, slot_fn in [
            ("sl_sync_bri", _("Lum. secondaires"), -40, 40,
             "lbl_sync_bri_val", self._update_sync_bri_label),
            ("sl_sync_con", _("Con. secondaires"), -40, 40,
             "lbl_sync_con_val", self._update_sync_con_label),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("Subtle")
            lbl.setFixedWidth(104)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(0)
            sl.valueChanged.connect(slot_fn)
            sl.sliderReleased.connect(self._apply_sync_offsets)
            val_lbl = QLabel("+0%")
            val_lbl.setObjectName("ValueBadge")
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(val_lbl)
            sec.add_layout(row)
            setattr(self, attr, sl)
            setattr(self, lbl_attr, val_lbl)

        self.main_l.addWidget(sec)

    def _build_gamma_section(self) -> None:
        sec = _CollapsibleSection(_("GAMMA GPU"), expanded=False)

        row = QHBoxLayout()
        lbl = QLabel(_("Gamma"))
        lbl.setObjectName("Subtle")
        lbl.setFixedWidth(60)
        self.sl_gamma = QSlider(Qt.Horizontal)
        self.sl_gamma.setRange(60, 240)
        self.sl_gamma.setValue(100)
        self.sl_gamma.valueChanged.connect(self._update_gamma_label)
        self.sl_gamma.sliderReleased.connect(self._apply_gamma)
        self.lbl_gamma_val = QLabel("1.00")
        self.lbl_gamma_val.setObjectName("ValueBadge")
        self.lbl_gamma_val.setFixedWidth(40)
        self.lbl_gamma_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)
        row.addWidget(self.sl_gamma)
        row.addWidget(self.lbl_gamma_val)
        row.addWidget(self._help_btn(_(
            "Applique un gamma identique à tous les écrans via la carte graphique. "
            "Pour régler chaque écran indépendamment, utilisez le slider γ sur sa carte."
        )))
        sec.add_layout(row)

        h_btn = QHBoxLayout()
        h_btn.setSpacing(6)
        self.btn_gamma_import = QPushButton(_("Importer"))
        self.btn_gamma_import.setProperty("class", "pill-muted")
        self.btn_gamma_import.setCursor(Qt.PointingHandCursor)
        self.btn_gamma_import.clicked.connect(self._import_gamma)
        self.btn_gamma_export = QPushButton(_("Exporter"))
        self.btn_gamma_export.setProperty("class", "pill-muted")
        self.btn_gamma_export.setCursor(Qt.PointingHandCursor)
        self.btn_gamma_export.clicked.connect(self._export_gamma)
        btn_reset = QPushButton(_("Reset"))
        btn_reset.setProperty("class", "pill-muted")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.reset_gamma)
        h_btn.addWidget(self.btn_gamma_import)
        h_btn.addWidget(self.btn_gamma_export)
        h_btn.addStretch()
        h_btn.addWidget(btn_reset)
        sec.add_layout(h_btn)

        self.main_l.addWidget(sec)

    def _build_focus_section(self) -> None:
        sec = _CollapsibleSection(_("MODE FOCUS"), expanded=False)

        h = QHBoxLayout()
        lbl_help = QLabel(_("Écran actif lumineux, autres atténués."))
        lbl_help.setObjectName("Subtle")
        self.btn_focus = QPushButton(_("Désactivé"))
        self.btn_focus.setObjectName("FocusToggle")
        self.btn_focus.setCheckable(True)
        self.btn_focus.setCursor(Qt.PointingHandCursor)
        self.btn_focus.setToolTip(_("Suspendu automatiquement quand le Mode Jeu détecte un plein écran."))
        self.btn_focus.toggled.connect(lambda v: self.set_focus_enabled(v, source="ui"))

        h.addWidget(lbl_help)
        h.addStretch()
        h.addWidget(self.btn_focus)
        sec.add_layout(h)

        row = QHBoxLayout()
        lbl_dim = QLabel(_("Atténuation"))
        lbl_dim.setObjectName("Subtle")
        lbl_dim.setFixedWidth(76)
        self.sl_focus_dim = QSlider(Qt.Horizontal)
        self.sl_focus_dim.setRange(0, 60)
        self.sl_focus_dim.setValue(self.focus_dim)
        self.sl_focus_dim.valueChanged.connect(self._update_focus_dim_label)
        self.sl_focus_dim.sliderReleased.connect(self._apply_focus)
        self.lbl_focus_dim = QLabel(f"{self.focus_dim}%")
        self.lbl_focus_dim.setObjectName("ValueBadge")
        self.lbl_focus_dim.setFixedWidth(40)
        self.lbl_focus_dim.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl_dim)
        row.addWidget(self.sl_focus_dim)
        row.addWidget(self.lbl_focus_dim)
        sec.add_layout(row)

        # Focus delay — debounce before dimming (avoids flicker on rapid alt-tab)
        delay_row = QHBoxLayout()
        lbl_delay = QLabel(_("Délai Focus"))
        lbl_delay.setObjectName("Subtle")
        lbl_delay.setFixedWidth(76)
        lbl_delay.setToolTip(_("Délai avant d'atténuer les écrans inactifs — évite le flickering lors d'un Alt+Tab rapide."))
        self.sl_focus_delay = QSlider(Qt.Horizontal)
        self.sl_focus_delay.setRange(0, 5)
        self.sl_focus_delay.setValue(self.focus_delay)
        self.lbl_focus_delay_val = QLabel(f"{self.focus_delay}s")
        self.lbl_focus_delay_val.setObjectName("ValueBadge")
        self.lbl_focus_delay_val.setFixedWidth(40)
        self.lbl_focus_delay_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sl_focus_delay.valueChanged.connect(self._update_focus_delay)
        delay_row.addWidget(lbl_delay)
        delay_row.addWidget(self.sl_focus_delay)
        delay_row.addWidget(self.lbl_focus_delay_val)
        sec.add_layout(delay_row)

        # Conflict badge — visible when Gaming mode overrides Focus mode
        self._lbl_focus_conflict = QLabel("")
        self._lbl_focus_conflict.setObjectName("SyncStatus")
        sec.add_widget(self._lbl_focus_conflict)

        self.main_l.addWidget(sec)

    def _build_gaming_section(self) -> None:
        sec = _CollapsibleSection(_("MODE JEU"), expanded=False)

        h = QHBoxLayout()
        lbl_help = QLabel(_("Préréglage auto quand un jeu est en plein écran."))
        lbl_help.setObjectName("Subtle")
        self.btn_gaming = QPushButton(_("Désactivé"))
        self.btn_gaming.setObjectName("GamingToggle")
        self.btn_gaming.setCheckable(True)
        self.btn_gaming.setCursor(Qt.PointingHandCursor)
        self.btn_gaming.setToolTip(_(
            "Priorité maximale : suspend le Mode Focus et les Profils Automatiques "
            "dès qu'un jeu passe en plein écran.\n\n"
            "Détecte le plein écran → applique le préréglage sur l'écran du jeu → "
            "suspend le DDC-CI de cet écran pour éviter tout artefact visuel. "
            "Les autres écrans restent librement ajustables. Tout est restauré à la sortie."
        ))
        self.btn_gaming.toggled.connect(lambda v: self.set_gaming_mode_enabled(v, source="ui"))

        h.addWidget(lbl_help)
        h.addStretch()
        h.addWidget(self.btn_gaming)
        sec.add_layout(h)

        # Exclusion list — processes that never trigger gaming mode
        excl_row = QHBoxLayout()
        lbl_excl = QLabel(_("Exclusions"))
        lbl_excl.setObjectName("Subtle")
        lbl_excl.setFixedWidth(76)
        lbl_excl.setToolTip(_("Processus qui ne déclenchent jamais le mode jeu (ex : afterfx.exe, resolve.exe)"))
        self._gaming_excl_edit = QLineEdit()
        self._gaming_excl_edit.setPlaceholderText("afterfx.exe, premiere.exe …")
        self._gaming_excl_edit.setToolTip(_("Processus qui ne déclenchent jamais le mode jeu (ex : afterfx.exe, resolve.exe)"))
        self._gaming_excl_edit.setText(", ".join(sorted(self._gaming_exclusions)))
        self._gaming_excl_edit.editingFinished.connect(self._on_gaming_exclusions_changed)
        excl_row.addWidget(lbl_excl)
        excl_row.addWidget(self._gaming_excl_edit)
        excl_row.addSpacing(4)
        excl_row.addWidget(self._help_btn(_(
            "Processus qui ne déclenchent jamais le mode jeu (ex : afterfx.exe, resolve.exe)"
        )))
        sec.add_layout(excl_row)

        for attr, label, default, slot in [
            ("sl_gaming_bri", _("Lum. jeu"), self.gaming_brightness, self._on_gaming_bri_changed),
            ("sl_gaming_con", _("Con. jeu"), self.gaming_contrast,   self._on_gaming_con_changed),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("Subtle")
            lbl.setFixedWidth(76)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 100)
            sl.setValue(default)
            sl.sliderReleased.connect(slot)
            val_lbl = QLabel(f"{default}%")
            val_lbl.setObjectName("ValueBadge")
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sl.valueChanged.connect(lambda v, lbl=val_lbl: lbl.setText(f"{v}%"))
            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(val_lbl)
            sec.add_layout(row)
            setattr(self, attr, sl)

        self.main_l.addWidget(sec)

    def _build_snapshot_section(self) -> None:
        sec = _CollapsibleSection(_("SAUVEGARDE RAPIDE"), expanded=True)

        desc = QLabel(_("Mémorise l'état actuel en 1 clic — utile avant d'expérimenter."))
        desc.setObjectName("Subtle")
        desc.setWordWrap(True)
        sec.add_widget(desc)

        h = QHBoxLayout()
        h.setSpacing(6)
        btn_save = QPushButton(_("Sauver"))
        btn_save.setProperty("class", "pill")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save_snapshot)
        btn_restore = QPushButton(_("Restaurer"))
        btn_restore.setProperty("class", "pill-muted")
        btn_restore.setCursor(Qt.PointingHandCursor)
        btn_restore.clicked.connect(self.restore_snapshot)
        self.lbl_snapshot = QLabel(_("Aucun instantané"))
        self.lbl_snapshot.setObjectName("Subtle")
        h.addWidget(btn_save)
        h.addWidget(btn_restore)
        h.addStretch()
        h.addWidget(self.lbl_snapshot)
        sec.add_layout(h)

        self.main_l.addWidget(sec)

    def _build_circadian_section(self) -> None:
        sec = _CollapsibleSection(_("LUMINOSITÉ CIRCADIENNE"), expanded=False)

        # ── Toggle row ────────────────────────────────────────────────────────
        h_top = QHBoxLayout()
        lbl_desc = QLabel(_("Suit le soleil — luminosité automatique lever/coucher."))
        lbl_desc.setObjectName("Subtle")
        lbl_desc.setWordWrap(True)
        self._btn_circadian = QPushButton(_("Désactivé"))
        self._btn_circadian.setObjectName("FocusToggle")
        self._btn_circadian.setCheckable(True)
        self._btn_circadian.setCursor(Qt.PointingHandCursor)
        self._btn_circadian.toggled.connect(self._set_circadian_enabled)

        h_top.addWidget(lbl_desc)
        h_top.addStretch()
        h_top.addWidget(self._btn_circadian)
        sec.add_layout(h_top)

        # ── Curve widget ──────────────────────────────────────────────────────
        self._curve_widget = _CircadianCurveWidget(self._circadian)
        self._curve_widget.setContentsMargins(0, 4, 0, 4)
        sec.add_widget(self._curve_widget)

        # ── Sun info label (kept for accessible text / screen readers) ────────
        self._lbl_sun_times = QLabel("")
        self._lbl_sun_times.setObjectName("Subtle")
        self._lbl_sun_times.setVisible(False)   # info is shown on the curve
        sec.add_widget(self._lbl_sun_times)

        # ── City picker ───────────────────────────────────────────────────────
        city_row = QHBoxLayout()
        lbl_city = QLabel(_("Ville"))
        lbl_city.setObjectName("Subtle")
        lbl_city.setFixedWidth(76)
        self._cmb_city = QComboBox()
        for _cname, _clat, _clon in PRESET_CITIES:
            self._cmb_city.addItem(_(_cname))
        # Select saved city
        city_names = [_(n) for n, _la, _lo in PRESET_CITIES]
        saved = _(self._circadian_city)
        idx = city_names.index(saved) if saved in city_names else 0
        self._cmb_city.setCurrentIndex(idx)
        self._cmb_city.currentIndexChanged.connect(self._on_city_changed)
        city_row.addWidget(lbl_city)
        city_row.addWidget(self._cmb_city, stretch=1)
        city_row.addSpacing(4)
        city_row.addWidget(self._help_btn(_(
            "La luminosité suit une courbe cosinus entre le lever et le coucher du soleil, "
            "avec un pic au zénith.\n\n"
            "Avant le lever et après le coucher : luminosité minimale.\n"
            "Compatible avec le Mode Focus (atténue les écrans inactifs par rapport à la cible).\n"
            "Suspendu automatiquement en Mode Jeu."
        )))
        sec.add_layout(city_row)

        # ── Custom lat / lon (shown only when "Personnalisé" is selected) ─────
        self._custom_coords_widget = QWidget()
        coords_l = QVBoxLayout(self._custom_coords_widget)
        coords_l.setContentsMargins(0, 0, 0, 0)
        coords_l.setSpacing(4)

        for attr, label, val, lo, hi in [
            ("_spin_lat", _("Latitude"),  self._circadian.lat, -90.0,  90.0),
            ("_spin_lon", _("Longitude"), self._circadian.lon, -180.0, 180.0),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("Subtle")
            lbl.setFixedWidth(76)
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(4)
            spin.setSingleStep(0.1)
            spin.setValue(val)
            spin.valueChanged.connect(self._on_coords_changed)
            row.addWidget(lbl)
            row.addWidget(spin, stretch=1)
            coords_l.addLayout(row)
            setattr(self, attr, spin)

        self._custom_coords_widget.setVisible(
            self._cmb_city.currentIndex() == len(PRESET_CITIES) - 1
        )
        sec.add_widget(self._custom_coords_widget)

        # ── Min / max brightness sliders ──────────────────────────────────────
        for attr, label, default, lbl_attr in [
            ("_sl_circ_min", _("Lum. min"),  self._circadian.bri_min, "_lbl_circ_min"),
            ("_sl_circ_max", _("Lum. max"),  self._circadian.bri_max, "_lbl_circ_max"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("Subtle")
            lbl.setFixedWidth(76)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 100)
            sl.setValue(default)
            val_lbl = QLabel(f"{default}%")
            val_lbl.setObjectName("ValueBadge")
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sl.valueChanged.connect(lambda v, l=val_lbl: l.setText(f"{v}%"))
            sl.sliderReleased.connect(self._on_circadian_range_changed)
            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(val_lbl)
            sec.add_layout(row)
            setattr(self, attr, sl)
            setattr(self, lbl_attr, val_lbl)

        # ── Warmth (circadian colour temperature) ────────────────────────────
        warmth_toggle_row = QHBoxLayout()
        lbl_warmth_toggle = QLabel(_("Chaleur circadienne"))
        lbl_warmth_toggle.setObjectName("Subtle")
        self._chk_circ_warmth = QPushButton(_("Désactivé"))
        self._chk_circ_warmth.setObjectName("FocusToggle")
        self._chk_circ_warmth.setCheckable(True)
        self._chk_circ_warmth.setChecked(self._circadian.warmth_enabled)
        self._chk_circ_warmth.setText(
            _("Activé") if self._circadian.warmth_enabled else _("Désactivé"))
        self._chk_circ_warmth.setCursor(Qt.PointingHandCursor)
        self._chk_circ_warmth.toggled.connect(self._set_circadian_warmth_enabled)

        warmth_toggle_row.addWidget(lbl_warmth_toggle)
        warmth_toggle_row.addStretch()
        warmth_toggle_row.addWidget(self._chk_circ_warmth)
        sec.add_layout(warmth_toggle_row)

        warmth_max_row = QHBoxLayout()
        lbl_warmth_max = QLabel(_("Chaleur max"))
        lbl_warmth_max.setObjectName("Subtle")
        lbl_warmth_max.setFixedWidth(76)
        self._sl_circ_warmth = QSlider(Qt.Horizontal)
        self._sl_circ_warmth.setObjectName("SliderWarmth")
        self._sl_circ_warmth.setRange(0, 100)
        self._sl_circ_warmth.setValue(self._circadian.warmth_max)
        self._lbl_circ_warmth_val = QLabel(f"{self._circadian.warmth_max}%")
        self._lbl_circ_warmth_val.setObjectName("ValueBadge")
        self._lbl_circ_warmth_val.setFixedWidth(40)
        self._lbl_circ_warmth_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._sl_circ_warmth.valueChanged.connect(self._on_circadian_warmth_max_changed)
        warmth_max_row.addWidget(lbl_warmth_max)
        warmth_max_row.addWidget(self._sl_circ_warmth)
        warmth_max_row.addWidget(self._lbl_circ_warmth_val)
        self._warmth_max_widget = QWidget()
        _wml = QVBoxLayout(self._warmth_max_widget)
        _wml.setContentsMargins(0, 0, 0, 0)
        _wml.addLayout(warmth_max_row)
        self._warmth_max_widget.setVisible(self._circadian.warmth_enabled)
        sec.add_widget(self._warmth_max_widget)

        # ── Current target preview ────────────────────────────────────────────
        self._lbl_circ_target = QLabel("")
        self._lbl_circ_target.setObjectName("Subtle")
        sec.add_widget(self._lbl_circ_target)

        self.main_l.addWidget(sec)
        self._update_circadian_labels()

    def _build_app_rules_section(self) -> None:
        sec = _CollapsibleSection(_("PROFILS AUTOMATIQUES"), expanded=False)

        # Toggle + status
        h_top = QHBoxLayout()
        self._chk_app_rules = QCheckBox(_("Activer les profils par application"))
        self._chk_app_rules.setChecked(self._rules_engine.enabled)
        self._chk_app_rules.toggled.connect(self._set_app_rules_enabled)
        h_top.addWidget(self._chk_app_rules, stretch=1)
        sec.add_layout(h_top)

        # Active rule status indicator
        self._lbl_rule_status = QLabel(_("Aucune règle active"))
        self._lbl_rule_status.setObjectName("RuleStatus")
        sec.add_widget(self._lbl_rule_status)

        # Conflict badge (shown when a higher-priority mode is active)
        self._lbl_rules_conflict = QLabel("")
        self._lbl_rules_conflict.setObjectName("SyncStatus")
        sec.add_widget(self._lbl_rules_conflict)

        # Real-time process display (visible when enabled)
        self._lbl_proc_detect = QLabel("")
        self._lbl_proc_detect.setObjectName("ProcDetect")
        sec.add_widget(self._lbl_proc_detect)

        # Manage button
        btn_manage = QPushButton(_("Gérer les règles…"))
        btn_manage.setProperty("class", "pill-muted")
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.clicked.connect(self._open_app_rules_dialog)
        sec.add_widget(btn_manage)

        self.main_l.addWidget(sec)

    def _build_tools_section(self) -> None:
        h = QHBoxLayout()
        h.setSpacing(6)
        btn_patterns = QPushButton(_("Patterns plein écran"))
        btn_patterns.setProperty("class", "pill")
        btn_patterns.setCursor(Qt.PointingHandCursor)
        btn_patterns.clicked.connect(self.show_patterns)
        btn_wizard = QPushButton(_("Calibrage guidé"))
        btn_wizard.setProperty("class", "pill-muted")
        btn_wizard.setCursor(Qt.PointingHandCursor)
        btn_wizard.clicked.connect(self.show_calibration_wizard)
        h.addWidget(btn_patterns)
        h.addWidget(btn_wizard)
        self.main_l.addLayout(h)

    def _build_named_profiles_section(self) -> None:
        sec = _CollapsibleSection(_("PROFILS NOMMÉS"), expanded=False)

        desc = QLabel(_("Préréglages permanents nommés — luminosité, contraste et gamma par écran."))
        desc.setObjectName("Subtle")
        desc.setWordWrap(True)
        sec.add_widget(desc)

        # Save row
        h = QHBoxLayout()
        h.setSpacing(6)
        self._profile_name_edit = QLineEdit()
        self._profile_name_edit.setPlaceholderText(_("Nom du profil"))
        btn_save_profile = QPushButton(_("Sauver le profil"))
        btn_save_profile.setProperty("class", "pill")
        btn_save_profile.setCursor(Qt.PointingHandCursor)
        btn_save_profile.clicked.connect(self._save_named_profile)
        h.addWidget(self._profile_name_edit, stretch=1)
        h.addWidget(btn_save_profile)
        sec.add_layout(h)

        # Profile list container (rebuilt on save/delete)
        self._named_profiles_container = QWidget()
        self._named_profiles_layout = QVBoxLayout(self._named_profiles_container)
        self._named_profiles_layout.setSpacing(4)
        self._named_profiles_layout.setContentsMargins(0, 4, 0, 0)
        sec.add_widget(self._named_profiles_container)
        self._refresh_named_profiles_list()

        self.main_l.addWidget(sec)

    def _refresh_named_profiles_list(self) -> None:
        lay = self._named_profiles_layout
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        names = self._profile.list_named_profiles()
        if not names:
            lbl = QLabel(_("Aucun profil sauvegardé"))
            lbl.setObjectName("Subtle")
            lay.addWidget(lbl)
            return

        for name in names:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(10, 5, 6, 5)
            lbl = QLabel(name)
            lbl.setObjectName("Title")
            btn_load = QPushButton(_("Charger"))
            btn_load.setProperty("class", "pill-muted")
            btn_load.setCursor(Qt.PointingHandCursor)
            btn_load.setFixedWidth(72)
            btn_load.clicked.connect(lambda _, n=name: self._load_named_profile(n))
            btn_del = QPushButton("×")
            btn_del.setProperty("class", "icon-btn")
            btn_del.setProperty("danger", "true")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setFixedSize(28, 28)
            btn_del.clicked.connect(lambda _, n=name: self._delete_named_profile(n))
            row.addWidget(lbl, stretch=1)
            row.addWidget(btn_load)
            row.addWidget(btn_del)
            container = QWidget()
            container.setObjectName("ProfileRow")
            container.setLayout(row)
            lay.addWidget(container)

    def _save_named_profile(self) -> None:
        name = self._profile_name_edit.text().strip()
        if not name:
            return
        monitors = [
            {"device_name": c.device_name,
             "brightness":  c.sl_bri.value(),
             "contrast":    c.sl_con.value()}
            for c in self.cards
        ]
        gamma_values = {c.device_name: c.gamma_value for c in self.cards}
        self._profile.save_named_profile(name, monitors, gamma_values)
        self._profile_name_edit.clear()
        self._refresh_named_profiles_list()

    def _load_named_profile(self, name: str) -> None:
        data = self._profile.load_named_profile(name)
        if not data:
            return
        warmth = (self.night_warmth / 100.0) if self.night_mode_enabled else 0.0
        for entry in data.get("monitors", []):
            dev = entry.get("device_name")
            bri = entry.get("brightness")
            con = entry.get("contrast")
            for c in self.cards:
                if c.device_name == dev:
                    self._sync_guard = True
                    if bri is not None:
                        c.sl_bri.setValue(bri)
                    if con is not None:
                        c.sl_con.setValue(con)
                    self._sync_guard = False
        for dev, gamma in data.get("gamma_values", {}).items():
            for c in self.cards:
                if c.device_name == dev:
                    c.set_gamma_value(float(gamma))
                    c.current_warmth = warmth

    def _delete_named_profile(self, name: str) -> None:
        self._profile.delete_named_profile(name)
        self._refresh_named_profiles_list()

    def _build_settings_section(self) -> None:
        sec = _CollapsibleSection(_("PARAMÈTRES"), expanded=False)

        # F6 — Launch at Windows startup
        self._chk_startup = QCheckBox(_("Lancer au démarrage de Windows"))
        self._chk_startup.setChecked(_startup.is_enabled())
        self._chk_startup.toggled.connect(
            lambda v: _startup.set_enabled(v)
        )
        sec.add_widget(self._chk_startup)

        # B6 — Night mode
        self._chk_night = QCheckBox(_("Activer le mode nuit"))
        self._chk_night.setChecked(self.night_mode_enabled)
        self._chk_night.toggled.connect(self._set_night_mode)
        sec.add_widget(self._chk_night)

        warmth_row = QHBoxLayout()
        warmth_row.setSpacing(8)
        lbl_warmth = QLabel(_("Chaleur"))
        lbl_warmth.setObjectName("Subtle")
        self.sl_warmth = QSlider(Qt.Horizontal)
        self.sl_warmth.setObjectName("SliderWarmth")
        self.sl_warmth.setRange(0, 100)
        self.sl_warmth.setValue(self.night_warmth)
        self.sl_warmth.setEnabled(self.night_mode_enabled)
        self.lbl_warmth_val = QLabel(f"{self.night_warmth}%")
        self.lbl_warmth_val.setObjectName("ValueBadge")
        self.lbl_warmth_val.setFixedWidth(40)
        self.lbl_warmth_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sl_warmth.valueChanged.connect(self._set_night_warmth)
        warmth_row.addWidget(lbl_warmth)
        warmth_row.addWidget(self.sl_warmth, stretch=1)
        warmth_row.addWidget(self.lbl_warmth_val)
        sec.add_layout(warmth_row)

        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        sec.add_widget(sep)

        btn_onboarding = QPushButton(_("Assistant de démarrage…"))
        btn_onboarding.setProperty("class", "pill-muted")
        btn_onboarding.setCursor(Qt.PointingHandCursor)
        btn_onboarding.clicked.connect(self._show_onboarding)
        sec.add_widget(btn_onboarding)

        self.main_l.addWidget(sec)

    def _show_onboarding(self) -> None:
        from lumina_control.ui.onboarding import OnboardingDialog
        OnboardingDialog(self).exec()

    def _make_update_banner(self) -> QWidget:
        """Create the update-available banner (hidden by default)."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        banner = QWidget()
        banner.setObjectName("UpdateBanner")
        banner.setStyleSheet(
            "QWidget#UpdateBanner{"
            "background:rgba(96,205,255,0.10);"
            "border:1px solid rgba(96,205,255,0.35);"
            "border-radius:6px;}"
        )
        hl = QHBoxLayout(banner)
        hl.setContentsMargins(10, 8, 10, 8)
        hl.setSpacing(8)

        self._lbl_update = QLabel("")
        self._lbl_update.setStyleSheet(
            f"font-size:11px; color:{ACCENT_COLOR}; font-weight:600;"
        )
        hl.addWidget(self._lbl_update, stretch=1)

        btn_dl = QPushButton(_("Télécharger"))
        btn_dl.setProperty("class", "pill")
        btn_dl.setFixedHeight(26)
        btn_dl.setCursor(Qt.PointingHandCursor)
        btn_dl.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self._updater.releases_url))
        )
        hl.addWidget(btn_dl)

        banner.setVisible(False)
        return banner

    # ── B10 — Update available ────────────────────────────────────────────────

    def _on_update_available(self, version: str) -> None:
        self._lbl_update.setText(_("Mise à jour disponible : {}").format(version))
        self._update_banner.setVisible(True)
        self.adjustSize()

    # ── Window events ─────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        pass  # Fully transparent root; Container handles its own background

    # ── Drag-to-move (title bar only) ────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            title_pos = self._title_bar.mapFrom(self, pos)
            if self._title_bar.rect().contains(title_pos):
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            else:
                self._drag_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Remove the 1-px DWM border glow Windows 11 adds to non-Tool windows
        try:
            import ctypes
            _DWMWA_BORDER_COLOR = 34
            _DWMWA_COLOR_NONE   = 0xFFFFFFFE
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()), _DWMWA_BORDER_COLOR,
                ctypes.byref(ctypes.c_int(_DWMWA_COLOR_NONE)),
                ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(160)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start()

    # ── Helper widgets ────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        return lbl

    def _group_sep(self, text: str) -> QWidget:
        """Labeled group separator — accent title + thin line, creates visual hierarchy."""
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        lbl = QLabel(text)
        lbl.setObjectName("GroupTitle")
        vl.addWidget(lbl)
        line = QFrame()
        line.setObjectName("Separator")
        line.setFrameShape(QFrame.HLine)
        vl.addWidget(line)
        return w

    def _help_btn(self, tooltip: str) -> QPushButton:
        """Small circular '?' button that shows *tooltip* on hover and on click."""
        btn = QPushButton("?")
        btn.setObjectName("HelpBtn")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.WhatsThisCursor)
        btn.setToolTip(tooltip)
        # Also show on click — hover alone is easy to miss
        btn.clicked.connect(lambda _checked, b=btn, t=tooltip:
            QToolTip.showText(b.mapToGlobal(b.rect().bottomLeft()), t, b))
        return btn

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Separator")
        line.setFrameShape(QFrame.HLine)
        return line

    # ─────────────────────────────────────────────────────────────────────────
    # Settings persistence
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_loaded_settings(self) -> None:
        """Push persisted settings to UI controls (block signals to avoid side effects)."""
        widgets = [
            self.chk_sync, self.chk_sync_rgb, self.chk_sync_relative,
            self.sl_sync_bri, self.sl_sync_con, self.sl_gamma,
            self._chk_app_rules,
        ]
        for w in widgets:
            w.blockSignals(True)

        self.chk_sync.setChecked(self.sync_enabled)
        self.chk_sync_rgb.setChecked(self.sync_rgb_enabled)
        self.chk_sync_relative.setChecked(self.sync_relative_enabled)
        self.sl_sync_bri.setValue(self.sync_offset_bri)
        self.sl_sync_con.setValue(self.sync_offset_con)
        self.sl_gamma.setValue(int(round(self.gamma_value * 100)))
        self._chk_app_rules.setChecked(self._rules_engine.enabled)

        for w in widgets:
            w.blockSignals(False)

        # Update value labels
        self._update_sync_bri_label(self.sync_offset_bri)
        self._update_sync_con_label(self.sync_offset_con)
        self._update_gamma_label(int(round(self.gamma_value * 100)))
        self._update_sync_ui()

        if self.focus_enabled:
            self.btn_focus.blockSignals(True)
            self.btn_focus.setChecked(True)
            self.btn_focus.setText(_("Activé"))
            self.btn_focus.blockSignals(False)

        self.sl_focus_delay.blockSignals(True)
        self.sl_focus_delay.setValue(self.focus_delay)
        self.sl_focus_delay.blockSignals(False)
        self.lbl_focus_delay_val.setText(f"{self.focus_delay}s")

        if self._circadian.enabled:
            self._btn_circadian.blockSignals(True)
            self._btn_circadian.setChecked(True)
            self._btn_circadian.setText(_("Activé"))
            self._btn_circadian.blockSignals(False)

        if self.gaming_enabled:
            self.btn_gaming.blockSignals(True)
            self.btn_gaming.setChecked(True)
            self.btn_gaming.setText(_("Activé"))
            self.btn_gaming.blockSignals(False)
            self._apply_gaming_visual(True)
            self._update_gaming_ui()

    def save_settings(self) -> None:
        """Persist current UI state to disk (called on app exit)."""
        self._profile.save_settings({
            "sync_enabled":          self.sync_enabled,
            "sync_rgb_enabled":      self.sync_rgb_enabled,
            "sync_master_index":     self.sync_master_index,
            "sync_master_device":    self.sync_master_device,
            "sync_relative_enabled": self.sync_relative_enabled,
            "sync_offset_bri":       self.sync_offset_bri,
            "sync_offset_con":       self.sync_offset_con,
            "gamma_value":           self.gamma_value,
            "gamma_values":          {c.device_name: c.gamma_value for c in self.cards},
            "focus_enabled":         self.focus_enabled,
            "focus_dim":             self.focus_dim,
            "app_rules_enabled":     self._rules_engine.enabled,
            "night_mode_enabled":    self.night_mode_enabled,
            "night_warmth":          self.night_warmth,
            "gaming_enabled":        self.gaming_enabled,
            "gaming_brightness":     self.gaming_brightness,
            "gaming_contrast":       self.gaming_contrast,
            "gaming_exclusions":     sorted(self._gaming_exclusions),
            "focus_delay":           self.focus_delay,
            "circadian_enabled":        self._circadian.enabled,
            "circadian_lat":            self._circadian.lat,
            "circadian_lon":            self._circadian.lon,
            "circadian_bri_min":        self._circadian.bri_min,
            "circadian_bri_max":        self._circadian.bri_max,
            "circadian_city":           self._circadian_city,
            "circadian_warmth_enabled": self._circadian.warmth_enabled,
            "circadian_warmth_max":     self._circadian.warmth_max,
        })
        self._rule_mgr.save(self._rules_engine.rules)
        log.debug("Settings saved.")

    # ─────────────────────────────────────────────────────────────────────────
    # Monitor management
    # ─────────────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        invalidate_monitors_cache()
        while self.mon_l.count():
            w = self.mon_l.takeAt(0).widget()
            if w:
                w.cleanup()
                w.deleteLater()
        self.cards.clear()

        try:
            for desc in enumerate_monitors():
                card = MonitorCard(
                    desc,
                    sync_hook=self._on_monitor_changed,
                    sync_rgb_hook=self._on_rgb_changed,
                )
                self.mon_l.addWidget(card)
                self.cards.append(card)
        except Exception as e:
            log.warning("Monitor scan failed: %s", e)
            self.mon_l.addWidget(QLabel(_("Erreur lors du scan des écrans")))

        # Apply saved per-monitor gamma values (with night warmth if active)
        warmth = (self.night_warmth / 100.0) if self.night_mode_enabled else 0.0
        for c in self.cards:
            c.current_warmth = warmth
            if c.device_name in self.gamma_values:
                c.set_gamma_value(float(self.gamma_values[c.device_name]))

        # DDC-CI banner: show when at least one monitor has no DDC handle
        na_count = sum(1 for c in self.cards if not c.available)
        if na_count:
            self._lbl_ddc_banner.setText(
                _("{} écran(s) sans DDC-CI — écran intégré (laptop) ou DDC/CI désactivé dans le menu OSD du moniteur.").format(na_count)
            )
            self._lbl_ddc_banner.setVisible(True)
        else:
            self._lbl_ddc_banner.setVisible(False)

        self.adjustSize()
        self._refresh_sync_combo()
        self._update_sync_ui()
        if self.sync_enabled:
            self.sync_now()
        if self.focus_enabled:
            self._apply_focus(force=True)

    def _poll(self) -> None:
        need_idx = self.isVisible() or self.focus_enabled
        idx = get_active_screen_index() if need_idx else -1
        if self.isVisible():
            for c in self.cards:
                c.set_active(c.index == idx)
        self._apply_focus(active_idx=idx)
        if self.gaming_enabled or self._gaming_active:
            self._check_gaming_mode()
        # Suppress app rules while gaming is active OR while the 2-s exit debounce
        # is still running — prevents brightness flickering when alt-tabbing in a game.
        gaming_active_or_pending = self._gaming_active or self._gaming_exit_timer.isActive()
        if self._circadian.enabled and not gaming_active_or_pending:
            self._apply_circadian()
        if not self.focus_enabled and not gaming_active_or_pending:
            self._rules_engine.poll()

    # ─────────────────────────────────────────────────────────────────────────
    # App rules — UI callbacks (logic lives in RulesEngine)
    # ─────────────────────────────────────────────────────────────────────────

    def _on_proc_detect(self, proc: str | None, has_rule: bool) -> None:
        """Update the real-time process label. Called by RulesEngine every poll tick."""
        if not hasattr(self, "_lbl_proc_detect"):
            return
        if proc:
            self._lbl_proc_detect.setText(_("Détecté : {}").format(proc))
            self._lbl_proc_detect.setProperty("matched", "true" if has_rule else "false")
            self._lbl_proc_detect.style().unpolish(self._lbl_proc_detect)
            self._lbl_proc_detect.style().polish(self._lbl_proc_detect)
        else:
            self._lbl_proc_detect.setText("")

    def _update_rule_status(self, rule: AppRule | None) -> None:
        """Update the status label in the app-rules section."""
        if not hasattr(self, "_lbl_rule_status"):
            return
        if rule:
            self._lbl_rule_status.setText(_("● {}").format(rule.label))
            self._lbl_rule_status.setProperty("active", "true")
        else:
            self._lbl_rule_status.setText(_("Aucune règle active"))
            self._lbl_rule_status.setProperty("active", "false")
        self._lbl_rule_status.style().unpolish(self._lbl_rule_status)
        self._lbl_rule_status.style().polish(self._lbl_rule_status)

    def _set_app_rules_enabled(self, enabled: bool) -> None:
        self._rules_engine.set_enabled(enabled)

    def _open_app_rules_dialog(self) -> None:
        from lumina_control.ui.app_rules_dialog import AppRulesDialog
        dlg = AppRulesDialog(
            rules=self._rules_engine.rules,
            detection_active=self._rules_engine.enabled,
            parent=self,
        )
        dlg.rules_changed.connect(self._on_rules_changed)
        dlg.exec()

    def _on_rules_changed(self, rules: list) -> None:
        self._rule_mgr.save(rules)
        self._rules_engine.update_rules(rules)

    # ─────────────────────────────────────────────────────────────────────────
    # Gaming mode
    # ─────────────────────────────────────────────────────────────────────────

    def register_gaming_action(self, action) -> None:
        self.gaming_action = action

    def set_gaming_mode_enabled(self, enabled: bool, source: str = "ui") -> None:
        self.gaming_enabled = enabled
        if source != "ui":
            self.btn_gaming.blockSignals(True)
            self.btn_gaming.setChecked(enabled)
            self.btn_gaming.blockSignals(False)
        self.btn_gaming.setText(_("Activé") if enabled else _("Désactivé"))
        if self.gaming_action and self.gaming_action.isChecked() != enabled:
            self.gaming_action.blockSignals(True)
            self.gaming_action.setChecked(enabled)
            self.gaming_action.blockSignals(False)
        self._apply_gaming_visual(enabled)
        self._update_gaming_ui()
        if not enabled:
            self._gaming_fs_ticks = 0
            self._gaming_exit_timer.stop()
            if self._gaming_active:
                self._exit_gaming_mode()

    def _update_gaming_ui(self) -> None:
        """Grey out controls only while a game is actively running in fullscreen.

        Gaming mode can be *enabled* without a game running — app rules still
        work in that state, so the checkbox must stay interactive.
        """
        self._chk_app_rules.setEnabled(not self._gaming_active)
        if self._gaming_active:
            self._chk_app_rules.setToolTip(_("Désactivé pendant le mode jeu"))
        else:
            self._chk_app_rules.setToolTip("")

    _GAMING_ENTRY_TICKS = 2  # ~1 s at 500 ms poll before entering

    def _check_gaming_mode(self) -> None:
        fullscreen = is_fullscreen_foreground()
        if fullscreen:
            # Skip excluded processes (e.g. After Effects full-screen renders)
            proc = get_foreground_process()
            if proc and proc in self._gaming_exclusions:
                self._gaming_fs_ticks = 0
                return
            self._gaming_exit_timer.stop()       # cancel any pending exit
            if not self._gaming_active:
                self._gaming_fs_ticks += 1
                if self._gaming_fs_ticks >= self._GAMING_ENTRY_TICKS:
                    self._enter_gaming_mode()
        else:
            self._gaming_fs_ticks = 0
            if self._gaming_active and not self._gaming_exit_timer.isActive():
                self._gaming_exit_timer.start()  # exit after 2 s of non-fullscreen

    def _apply_gaming_visual(self, active: bool) -> None:
        from lumina_control.style import get_stylesheet
        from lumina_control.utils import is_windows_dark_mode
        QApplication.instance().setStyleSheet(
            get_stylesheet(dark=is_windows_dark_mode(), gaming=active)
        )

    def _enter_gaming_mode(self) -> None:
        self._gaming_active = True
        # Identify the screen that contains the game — preset and DDC suspension
        # are scoped to this screen only.  Other screens remain fully usable.
        self._gaming_device = get_foreground_window_monitor()
        self._update_gaming_ui()
        self._update_modes_conflict_ui()
        # Hide the panel so it doesn't appear on top of windowed-fullscreen games.
        if self.isVisible():
            self.hide()
        # Exit any active app rule first — restores pre-rule values so the
        # snapshot below captures the user's actual brightness, not a rule's.
        self._rules_engine.suspend()
        # Snapshot + apply preset only on the game screen (fallback: all screens
        # if the monitor cannot be identified — e.g. exclusive fullscreen on a
        # single-monitor setup where GetMonitorInfoW may return None).
        targets = [c for c in self.cards if c.available
                   and (self._gaming_device is None
                        or c.device_name == self._gaming_device)]
        self._pre_gaming_bri = {c.index: c.sl_bri.value() for c in targets}
        self._pre_gaming_con = {c.index: c.sl_con.value() for c in targets}
        for c in targets:
            c.apply_rule_values(self.gaming_brightness, self.gaming_contrast)
        # Suspend DDC on the game screen only — avoids I²C bus artefacts (OSD
        # flash, micro-flicker) on that monitor.  Other screens stay live so the
        # user can adjust them freely during the session.
        QTimer.singleShot(300, self._suspend_ddc_game_screen)
        log.debug("Gaming mode: entered on %s (bri=%d con=%d)",
                  self._gaming_device or "all", self.gaming_brightness, self.gaming_contrast)

    def _suspend_ddc_game_screen(self) -> None:
        for c in self.cards:
            if c.available and (self._gaming_device is None
                                or c.device_name == self._gaming_device):
                c.set_ddc_suspended(True)

    def _exit_gaming_mode(self) -> None:
        self._gaming_active = False
        self._update_gaming_ui()
        self._update_modes_conflict_ui()
        # Resume DDC on the game screen first so restore writes go through
        for c in self.cards:
            if c.available and (self._gaming_device is None
                                or c.device_name == self._gaming_device):
                c.set_ddc_suspended(False)
        # Restore pre-gaming values (only the cards that were snapshotted)
        for c in self.cards:
            if c.available:
                bri = self._pre_gaming_bri.get(c.index)
                con = self._pre_gaming_con.get(c.index)
                if bri is not None or con is not None:
                    c.apply_rule_values(bri, con)
        self._pre_gaming_bri.clear()
        self._pre_gaming_con.clear()
        self._gaming_device = None
        log.debug("Gaming mode: exited, restored game screen brightness/contrast")

    # ─────────────────────────────────────────────────────────────────────────
    # Circadian brightness
    # ─────────────────────────────────────────────────────────────────────────

    def _set_circadian_enabled(self, enabled: bool) -> None:
        if enabled:
            # Snapshot current brightness before circadian takes over
            self._circadian_bri_before = self.sl_glob.value()
            self._circadian.enabled = True
            # Jump immediately to the target (no slow step on first enable)
            t = self._circadian.target_brightness()
            self._set_glob(t)
            if self._circadian.warmth_enabled and not self.night_mode_enabled:
                self._set_warmth_all(self._circadian.target_warmth())
        else:
            self._circadian.enabled = False
            # Restore the pre-circadian brightness instantly
            if self._circadian_bri_before is not None:
                self._set_glob(self._circadian_bri_before)
            # Reset warmth unless night mode is controlling it
            if self._circadian.warmth_enabled and not self.night_mode_enabled:
                self._set_warmth_all(0.0)
        self._btn_circadian.setText(_("Activé") if enabled else _("Désactivé"))
        self._update_circadian_labels()

    def _on_city_changed(self, idx: int) -> None:
        name, lat, lon = PRESET_CITIES[idx]
        self._circadian_city = name
        is_custom = (idx == len(PRESET_CITIES) - 1)
        self._custom_coords_widget.setVisible(is_custom)
        if not is_custom:
            self._circadian.lat = lat
            self._circadian.lon = lon
            self._circadian._cache_date = None  # force sun recalculation
        self._update_circadian_labels()

    def _on_coords_changed(self) -> None:
        self._circadian.lat = self._spin_lat.value()
        self._circadian.lon = self._spin_lon.value()
        self._circadian._cache_date = None
        self._update_circadian_labels()

    def _on_circadian_range_changed(self) -> None:
        min_v = self._sl_circ_min.value()
        max_v = self._sl_circ_max.value()
        # Enforce min < max
        if min_v >= max_v:
            if self.sender() is self._sl_circ_min:
                self._sl_circ_min.setValue(max_v - 1)
            else:
                self._sl_circ_max.setValue(min_v + 1)
        self._circadian.bri_min = self._sl_circ_min.value()
        self._circadian.bri_max = self._sl_circ_max.value()
        self._update_circadian_labels()

    def _set_warmth_all(self, warmth: float) -> None:
        """Apply warmth to every card (GDI32 — fast, no DDC-CI)."""
        for c in self.cards:
            c.set_warmth(warmth)

    def _set_circadian_warmth_enabled(self, enabled: bool) -> None:
        self._circadian.warmth_enabled = enabled
        self._chk_circ_warmth.setText(_("Activé") if enabled else _("Désactivé"))
        self._warmth_max_widget.setVisible(enabled)
        if not self.night_mode_enabled:
            # Apply target immediately; the poll will keep it in sync every 500 ms
            if enabled and self._circadian.enabled:
                self._set_warmth_all(self._circadian.target_warmth())
            elif not enabled:
                self._set_warmth_all(0.0)

    def _on_circadian_warmth_max_changed(self, value: int) -> None:
        self._circadian.warmth_max = value
        self._lbl_circ_warmth_val.setText(f"{value}%")

    def _update_circadian_labels(self) -> None:
        """Refresh the curve widget and the current target preview."""
        if not hasattr(self, "_lbl_sun_times"):
            return
        self._lbl_sun_times.setText(self._circadian.sun_label())
        if hasattr(self, "_curve_widget"):
            self._curve_widget.refresh()
        if self._circadian.enabled:
            t = self._circadian.target()
            if self._circadian.warmth_enabled:
                w = int(round(self._circadian.target_warmth() * 100))
                self._lbl_circ_target.setText(
                    _("Cible : {}%  ·  chaleur {}%").format(t, w))
            else:
                self._lbl_circ_target.setText(_("Cible actuelle : {}%").format(t))
        else:
            self._lbl_circ_target.setText("")

    def _apply_circadian(self) -> None:
        """Called from _poll — moves global brightness one step toward the target."""
        current = self.sl_glob.value()
        nxt = self._circadian.step(current)
        if nxt is not None and nxt != current:
            self._set_glob(nxt)
        # Apply warmth curve (defers to night mode if both are active)
        if self._circadian.warmth_enabled and not self.night_mode_enabled:
            self._set_warmth_all(self._circadian.target_warmth())
        # Refresh label every poll tick so it stays current
        self._update_circadian_labels()

    def _on_gaming_bri_changed(self) -> None:
        self.gaming_brightness = self.sl_gaming_bri.value()

    def _on_gaming_con_changed(self) -> None:
        self.gaming_contrast = self.sl_gaming_con.value()

    def _on_gaming_exclusions_changed(self) -> None:
        """Parse the comma-separated exclusion field and update the in-memory set."""
        raw = self._gaming_excl_edit.text()
        self._gaming_exclusions = {
            p.strip().lower() for p in raw.split(",") if p.strip()
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Global brightness
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_glob(self) -> None:
        if self.focus_enabled:
            self._apply_focus(force=True)
            return
        v = self.sl_glob.value()
        self._sync_guard = True
        for c in self.cards:
            if c.available:
                c.sl_bri.setValue(v)
        self._sync_guard = False

    def _set_glob(self, v: int) -> None:
        self.sl_glob.setValue(v)
        self._apply_glob()

    def _set_all_power(self, on: bool) -> None:
        for c in self.cards:
            if c.available:
                c.set_power(on)

    def update_glob_label(self, v: int) -> None:
        self.lbl_glob_val.setText(f"{v}%")

    # ─────────────────────────────────────────────────────────────────────────
    # Snapshot
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_snapshot_label(self) -> None:
        snap = self._profile.load_snapshot()
        if snap and snap.get("saved_at"):
            self.lbl_snapshot.setText(_("Dernier : {}").format(snap["saved_at"]))
        else:
            self.lbl_snapshot.setText(_("Aucun instantané"))

    def save_snapshot(self) -> None:
        monitors = [
            {
                "device_name": c.device_name,
                "index":       c.index,
                "brightness":  c.sl_bri.value(),
                "contrast":    c.sl_con.value(),
            }
            for c in self.cards if c.available
        ]
        saved_at = self._profile.save_snapshot(monitors)
        self.lbl_snapshot.setText(_("Dernier : {}").format(saved_at))

    def restore_snapshot(self) -> None:
        snap = self._profile.load_snapshot()
        if not snap or not snap.get("monitors"):
            self.lbl_snapshot.setText(_("Instantané introuvable"))
            return
        # Prefer matching by device_name; fall back to index for old snapshots.
        card_by_device = {c.device_name: c for c in self.cards}
        card_by_index  = {c.index: c for c in self.cards}
        self._sync_guard = True
        for item in snap["monitors"]:
            card = card_by_device.get(item.get("device_name")) \
                or card_by_index.get(item.get("index"))
            if card and card.available:
                if "brightness" in item:
                    card.sl_bri.setValue(int(item["brightness"]))
                if "contrast" in item:
                    card.sl_con.setValue(int(item["contrast"]))
        self._sync_guard = False
        if snap.get("saved_at"):
            self.lbl_snapshot.setText(_("Dernier : {}").format(snap["saved_at"]))

    # ─────────────────────────────────────────────────────────────────────────
    # Sync
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_sync_combo(self) -> None:
        self.cmb_master.blockSignals(True)
        self.cmb_master.clear()
        for c in self.cards:
            self.cmb_master.addItem(c.descriptor.label, c.device_name)

        if self.cards:
            # Prefer restoring by stable device name; fall back to saved index.
            combo_idx = 0
            if self.sync_master_device:
                for i, c in enumerate(self.cards):
                    if c.device_name == self.sync_master_device:
                        combo_idx = i
                        break
            else:
                combo_idx = min(self.sync_master_index, len(self.cards) - 1)

            self.cmb_master.setCurrentIndex(combo_idx)
            self.sync_master_device = self.cards[combo_idx].device_name
            self.sync_master_index  = combo_idx

        self.cmb_master.blockSignals(False)

    def _update_sync_ui(self) -> None:
        enabled = self.sync_enabled
        self.cmb_master.setEnabled(enabled)
        self.chk_sync_rgb.setEnabled(enabled)
        self.btn_sync_now.setEnabled(enabled)
        self.chk_sync_relative.setEnabled(enabled)
        rel = enabled and self.sync_relative_enabled
        self.sl_sync_bri.setEnabled(rel)
        self.sl_sync_con.setEnabled(rel)

        # Status badge
        if not enabled:
            self._lbl_sync_status.setText("")
            self._lbl_sync_status.setProperty("state", "")
        elif self._gaming_active:
            self._lbl_sync_status.setText(_("⚠ Suspendu — Mode Jeu actif"))
            self._lbl_sync_status.setProperty("state", "warning")
        elif self.focus_enabled:
            self._lbl_sync_status.setText(_("⚠ Suspendu — Mode Focus actif"))
            self._lbl_sync_status.setProperty("state", "warning")
        else:
            n = sum(1 for c in self.cards
                    if c.device_name != self.sync_master_device and c.available)
            self._lbl_sync_status.setText(_("Actif — {} écran(s) lié(s)").format(n))
            self._lbl_sync_status.setProperty("state", "active")
        self._lbl_sync_status.style().unpolish(self._lbl_sync_status)
        self._lbl_sync_status.style().polish(self._lbl_sync_status)

    def _update_modes_conflict_ui(self) -> None:
        """Refresh conflict badges in sections that can be suspended by a higher-priority mode."""
        # Sync section badge (also checks gaming mode)
        if hasattr(self, "_lbl_sync_status"):
            self._update_sync_ui()

        # Focus section: show when Gaming mode is actively overriding it
        if hasattr(self, "_lbl_focus_conflict"):
            if self._gaming_active and self.focus_enabled:
                f_text  = _("⚠ Suspendu — Mode Jeu actif")
                f_state = "warning"
            else:
                f_text  = ""
                f_state = ""
            self._lbl_focus_conflict.setText(f_text)
            self._lbl_focus_conflict.setProperty("state", f_state)
            self._lbl_focus_conflict.style().unpolish(self._lbl_focus_conflict)
            self._lbl_focus_conflict.style().polish(self._lbl_focus_conflict)

        # App rules conflict badge
        if not hasattr(self, "_lbl_rules_conflict"):
            return
        if self._gaming_active:
            text  = _("⚠ Suspendu — Mode Jeu actif")
            state = "warning"
        elif self.focus_enabled:
            text  = _("⚠ Suspendu — Mode Focus actif")
            state = "warning"
        else:
            text  = ""
            state = ""
        self._lbl_rules_conflict.setText(text)
        self._lbl_rules_conflict.setProperty("state", state)
        self._lbl_rules_conflict.style().unpolish(self._lbl_rules_conflict)
        self._lbl_rules_conflict.style().polish(self._lbl_rules_conflict)

    def _set_sync_enabled(self, enabled: bool) -> None:
        self.sync_enabled = enabled
        self._update_sync_ui()
        if enabled:
            self.sync_now()

    def _set_sync_rgb_enabled(self, enabled: bool) -> None:
        self.sync_rgb_enabled = enabled
        if self.sync_enabled and enabled:
            self.sync_now()

    def _set_sync_relative_enabled(self, enabled: bool) -> None:
        self.sync_relative_enabled = enabled
        self._update_sync_ui()
        if self.sync_enabled:
            self.sync_now()

    def _set_sync_master(self, idx: int) -> None:
        if idx < 0:
            return
        self.sync_master_index  = idx
        self.sync_master_device = self.cmb_master.itemData(idx) or ""
        if self.sync_enabled:
            self.sync_now()

    def _update_sync_bri_label(self, v: int) -> None:
        self.sync_offset_bri = v
        self.lbl_sync_bri_val.setText(f"{v:+d}%")

    def _update_sync_con_label(self, v: int) -> None:
        self.sync_offset_con = v
        self.lbl_sync_con_val.setText(f"{v:+d}%")

    def _apply_sync_offsets(self) -> None:
        if self.sync_enabled and self.sync_relative_enabled:
            self.sync_now()

    def sync_now(self) -> None:
        if not self.sync_enabled or not self.cards or self.focus_enabled:
            return
        if self._rules_engine.active_rule is not None:
            return
        master = next(
            (c for c in self.cards if c.device_name == self.sync_master_device),
            None,
        )
        if not master or not master.available:
            return
        bri = self._clamp(master.sl_bri.value() + self.sync_offset_bri
                          if self.sync_relative_enabled else master.sl_bri.value())
        con = self._clamp(master.sl_con.value() + self.sync_offset_con
                          if self.sync_relative_enabled else master.sl_con.value())
        self._sync_guard = True
        for c in self.cards:
            if c.device_name != master.device_name and c.available:
                c.sl_bri.setValue(bri)
                c.sl_con.setValue(con)
        self._sync_guard = False
        if self.sync_rgb_enabled:
            self._sync_rgb_from_master(master)

    def _on_monitor_changed(self, device_name: str, brightness, contrast) -> None:
        if self._sync_guard or not self.sync_enabled or self.focus_enabled:
            return
        if self._rules_engine.active_rule is not None:
            return
        if device_name != self.sync_master_device:
            return
        master = next(
            (c for c in self.cards if c.device_name == self.sync_master_device),
            None,
        )
        if not master:
            return
        bri = self._clamp((brightness if brightness is not None else master.sl_bri.value())
                          + (self.sync_offset_bri if self.sync_relative_enabled else 0))
        con = self._clamp((contrast if contrast is not None else master.sl_con.value())
                          + (self.sync_offset_con if self.sync_relative_enabled else 0))
        self._sync_guard = True
        for c in self.cards:
            if c.device_name != device_name and c.available:
                c.sl_bri.setValue(bri)
                c.sl_con.setValue(con)
        self._sync_guard = False

    def _on_rgb_changed(self, device_name: str, rgb: dict) -> None:
        if not self.sync_enabled or not self.sync_rgb_enabled:
            return
        if device_name != self.sync_master_device:
            return
        for c in self.cards:
            if c.device_name != device_name and c.available:
                c.set_rgb_values(rgb)

    def _sync_rgb_from_master(self, master: MonitorCard) -> None:
        try:
            with master.monitor:
                rgb = {
                    0x16: master.monitor.vcp.get_vcp_feature(0x16)[0],
                    0x18: master.monitor.vcp.get_vcp_feature(0x18)[0],
                    0x1A: master.monitor.vcp.get_vcp_feature(0x1A)[0],
                }
        except Exception as e:
            log.debug("RGB read from master failed: %s", e)
            return
        for c in self.cards:
            if c.device_name != master.device_name and c.available:
                c.set_rgb_values(rgb)

    @staticmethod
    def _clamp(v: int) -> int:
        return max(0, min(100, int(v)))

    # ─────────────────────────────────────────────────────────────────────────
    # Gamma
    # ─────────────────────────────────────────────────────────────────────────

    def _update_gamma_label(self, v: int) -> None:
        g = v / 100.0
        self.gamma_value = g
        self.lbl_gamma_val.setText(f"{g:.2f}")

    def _apply_gamma(self) -> None:
        for c in self.cards:
            c.set_gamma_value(self.gamma_value)

    def reset_gamma(self) -> None:
        self.sl_gamma.setValue(100)
        self.gamma_value = 1.0
        for c in self.cards:
            c.set_gamma_value(1.0)

    def _preset_day(self) -> None:
        self._set_glob(80)
        if self.night_mode_enabled:
            self._chk_night.setChecked(False)

    def _preset_night(self) -> None:
        self._set_glob(25)
        if not self.night_mode_enabled:
            self._chk_night.setChecked(True)

    # ── Night mode ────────────────────────────────────────────────────────────

    def _set_night_mode(self, enabled: bool) -> None:
        self.night_mode_enabled = enabled
        self.sl_warmth.setEnabled(enabled)
        warmth = (self.night_warmth / 100.0) if enabled else 0.0
        for c in self.cards:
            c.set_warmth(warmth)

    def _set_night_warmth(self, value: int) -> None:
        self.night_warmth = value
        self.lbl_warmth_val.setText(f"{value}%")
        if self.night_mode_enabled:
            warmth = value / 100.0
            for c in self.cards:
                c.set_warmth(warmth)

    def _export_gamma(self) -> None:
        from datetime import datetime
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter gamma", "gamma_preset.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            import json as _json
            with open(path, "w", encoding="utf-8") as f:
                _json.dump({"gamma": round(self.gamma_value, 4),
                            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M")}, f, indent=2)
        except OSError as e:
            log.warning("Export gamma failed: %s", e)

    def _import_gamma(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer gamma", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            import json as _json
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            gamma = max(0.5, min(3.0, float(data.get("gamma", 1.0))))
        except (OSError, ValueError, KeyError) as e:
            log.warning("Import gamma failed: %s", e)
            return
        self.gamma_value = gamma
        self.sl_gamma.setValue(int(round(gamma * 100)))
        for c in self.cards:
            c.set_gamma_value(gamma)

    # ─────────────────────────────────────────────────────────────────────────
    # Focus mode
    # ─────────────────────────────────────────────────────────────────────────

    def register_focus_action(self, action) -> None:
        self.focus_action = action
        self.focus_action.setChecked(self.focus_enabled)

    def set_focus_enabled(self, enabled: bool, source: str | None = None) -> None:
        if self.focus_enabled == enabled:
            if source == "menu" and self.btn_focus.isChecked() != enabled:
                self.btn_focus.setChecked(enabled)
            if source == "ui" and self.focus_action:
                self.focus_action.setChecked(enabled)
            return
        self.focus_enabled = enabled
        if source != "ui":
            self.btn_focus.blockSignals(True)
            self.btn_focus.setChecked(enabled)
            self.btn_focus.blockSignals(False)
        if self.focus_action and source != "menu":
            self.focus_action.setChecked(enabled)
        self.btn_focus.setText(_("Activé") if enabled else _("Désactivé"))
        if enabled:
            # Cleanly exit any active app rule before focus takes over
            self._rules_engine.suspend()
            self.pre_focus_values = {
                c.index: c.sl_bri.value() for c in self.cards if c.available
            }
            self.last_active = None
            self._apply_focus(force=True)
        else:
            self._restore_pre_focus()
        self._update_sync_ui()
        self._update_modes_conflict_ui()

    def _restore_pre_focus(self) -> None:
        if not self.pre_focus_values:
            return
        self._sync_guard = True
        for c in self.cards:
            if c.index in self.pre_focus_values and c.available:
                c.sl_bri.setValue(self.pre_focus_values[c.index])
        self.pre_focus_values.clear()
        self._sync_guard = False

    def _apply_focus(self, force: bool = False, active_idx: int = -1) -> None:
        if not self.focus_enabled or not self.cards:
            return
        if active_idx < 0:
            active_idx = get_active_screen_index()
        target = self.sl_glob.value()
        dim = self.sl_focus_dim.value()
        bg = max(0, target - dim)

        # When the active screen changes and a delay is configured, debounce the
        # dim: restart the timer.  force=True bypasses the delay (used on enable,
        # refresh, or when the timer itself fires).
        if not force and active_idx != self.last_active and self.focus_delay > 0:
            self._focus_delay_timer.start(self.focus_delay * 1000)
            return

        self._focus_delay_timer.stop()
        if (not force and self.last_active == active_idx
                and self._last_focus_target == target
                and self._last_focus_dim == dim):
            return
        self.last_active = active_idx
        self._last_focus_target = target
        self._last_focus_dim = dim
        self._sync_guard = True
        for c in self.cards:
            if not c.available:
                continue
            desired = target if c.index == active_idx else bg
            if c.sl_bri.value() != desired:
                c.sl_bri.setValue(desired)
        self._sync_guard = False

    def _update_focus_dim_label(self, v: int) -> None:
        self.focus_dim = v
        self.lbl_focus_dim.setText(f"{v}%")

    def _update_focus_delay(self, v: int) -> None:
        self.focus_delay = v
        self.lbl_focus_delay_val.setText(f"{v}s")

    # ─────────────────────────────────────────────────────────────────────────
    # Tools
    # ─────────────────────────────────────────────────────────────────────────

    def show_patterns(self) -> None:
        if self.pattern_window and self.pattern_window.isVisible():
            self.pattern_window.activateWindow()
            return
        idx = get_active_screen_index()
        self.pattern_window = PatternWindow(start_screen_idx=idx)
        self.pattern_window.destroyed.connect(
            lambda: setattr(self, "pattern_window", None)
        )
        self.pattern_window.showFullScreen()

    def show_calibration_wizard(self) -> None:
        if self.calibration_wizard and self.calibration_wizard.isVisible():
            self.calibration_wizard.activateWindow()
            return
        self.calibration_wizard = CalibrationWizard(parent=self)
        self.calibration_wizard.destroyed.connect(
            lambda: setattr(self, "calibration_wizard", None)
        )
        self.calibration_wizard.show()

    # ─────────────────────────────────────────────────────────────────────────
    # Window positioning
    # ─────────────────────────────────────────────────────────────────────────

    def move_to_tray(self) -> None:
        from PySide6.QtGui import QCursor
        p = QCursor.pos()
        screen = QApplication.screenAt(p) or QApplication.primaryScreen()
        s = screen.availableGeometry()
        self.adjustSize()
        x = max(s.left() + 5, min(p.x() - self.width() // 2, s.right() - self.width() - 5))
        y = p.y() - self.height() - 15
        if y < s.top():
            y = p.y() + 15
        if y + self.height() > s.bottom():
            y = s.bottom() - self.height() - 5
        self.move(x, y)

    def toggle(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.move_to_tray()
            self.show()
            self.activateWindow()

    def show_and_activate(self) -> None:
        self.move_to_tray()
        self.show()
        self.raise_()
        self.activateWindow()

    def focusOutEvent(self, event) -> None:
        if not QApplication.activeModalWidget():
            fw = QApplication.focusWidget()
            if fw is None or not self.isAncestorOf(fw):
                self.hide()
        super().focusOutEvent(event)
