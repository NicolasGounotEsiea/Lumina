"""Main floating control panel."""
import logging
from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog,
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from lumina_control.config import (
    ACCENT_COLOR, APP_NAME, APP_WIDTH,
    BORDER_COLOR, WARM_COLOR,
    get_profile_path, get_rules_path, get_settings_path,
)
from lumina_control.i18n import _
from lumina_control.profiles import ProfileManager
from lumina_control.app_rules import AppRule, AppRuleManager
from lumina_control import startup as _startup
from lumina_control.updater import UpdateChecker
from lumina_control.utils import (
    get_active_screen_index, get_foreground_process,
    get_foreground_window_monitor, invalidate_monitors_cache, wake_all_monitors,
)
from lumina_control.monitor_enumerate import enumerate_monitors
from lumina_control.ui.monitor_card import MonitorCard
from lumina_control.ui.patterns import PatternWindow
from lumina_control.ui.calibration import CalibrationWizard

log = logging.getLogger(__name__)


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

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(APP_WIDTH)

        self._profile = ProfileManager(get_profile_path(), get_settings_path())

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
        self.app_rules_enabled     = s["app_rules_enabled"]

        # App rules engine
        self._rule_mgr        = AppRuleManager(get_rules_path())
        self._rules:            list[AppRule]    = self._rule_mgr.load()
        self._active_rule:      AppRule | None   = None
        self._pre_rule_bri:     dict[str, int]               = {}
        self._pre_rule_con:     dict[str, int]               = {}
        self._pre_rule_gamma:   dict[str, float]             = {}
        self._pre_rule_rgb:     dict[str, tuple[int,int,int]] = {}
        self._active_rule_device: str | None                 = None
        self._rule_candidate:   str | None       = None  # process being watched for stability
        self._rule_ticks:       int              = 0     # consecutive polls with same process

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
        icon_lbl.setStyleSheet(f"color:{ACCENT_COLOR}; font-size:17px; padding:0;")
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

        sep_top = QFrame()
        sep_top.setFrameShape(QFrame.HLine)
        sep_top.setStyleSheet(f"background:{BORDER_COLOR}; max-height:1px; border:none;")
        container_l.addWidget(sep_top)

        # ── Scrollable content ────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(600)

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
        self.mon_l = QVBoxLayout()
        self.mon_l.setSpacing(8)
        self.main_l.addLayout(self.mon_l)

        self.main_l.addWidget(self._sep())

        # Advanced settings as collapsible panels
        self._build_sync_section()
        self._build_gamma_section()
        self._build_focus_section()
        self._build_snapshot_section()

        self.main_l.addWidget(self._sep())
        self._build_app_rules_section()
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
        self.sl_glob.sliderReleased.connect(self._apply_glob)
        self.sl_glob.valueChanged.connect(lambda v: self.lbl_glob_val.setText(f"{v}%"))
        sl.addWidget(self.sl_glob)

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
        btn_day.clicked.connect(partial(self._set_glob, 80))
        btn_night = QPushButton(_("☾  Nuit  25%"))
        btn_night.setProperty("class", "pill")
        btn_night.setCursor(Qt.PointingHandCursor)
        btn_night.clicked.connect(partial(self._set_glob, 25))
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

        h_sync = QHBoxLayout()
        self.chk_sync = QCheckBox(_("Synchroniser les écrans"))
        self.chk_sync.toggled.connect(self._set_sync_enabled)
        lbl_master = QLabel(_("Maître"))
        lbl_master.setObjectName("Subtle")
        self.cmb_master = QComboBox()
        self.cmb_master.setFixedWidth(120)
        self.cmb_master.currentIndexChanged.connect(self._set_sync_master)
        h_sync.addWidget(self.chk_sync)
        h_sync.addStretch()
        h_sync.addWidget(lbl_master)
        h_sync.addWidget(self.cmb_master)
        sec.add_layout(h_sync)

        h2 = QHBoxLayout()
        self.chk_sync_rgb = QCheckBox(_("Gains RGB"))
        self.chk_sync_rgb.toggled.connect(self._set_sync_rgb_enabled)
        self.btn_sync_now = QPushButton(_("Sync maintenant"))
        self.btn_sync_now.setProperty("class", "pill-muted")
        self.btn_sync_now.setCursor(Qt.PointingHandCursor)
        self.btn_sync_now.clicked.connect(self.sync_now)
        h2.addWidget(self.chk_sync_rgb)
        h2.addStretch()
        h2.addWidget(self.btn_sync_now)
        sec.add_layout(h2)

        h3 = QHBoxLayout()
        self.chk_sync_relative = QCheckBox(_("Décalages relatifs"))
        self.chk_sync_relative.toggled.connect(self._set_sync_relative_enabled)
        h3.addWidget(self.chk_sync_relative)
        h3.addStretch()
        sec.add_layout(h3)

        for attr, label, lo, hi, lbl_attr, slot_fn in [
            ("sl_sync_bri", _("Offset lum."), -40, 40,
             "lbl_sync_bri_val", self._update_sync_bri_label),
            ("sl_sync_con", _("Offset con."), -40, 40,
             "lbl_sync_con_val", self._update_sync_con_label),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("Subtle")
            lbl.setFixedWidth(72)
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

        self.main_l.addWidget(sec)

    def _build_snapshot_section(self) -> None:
        sec = _CollapsibleSection(_("INSTANTANÉ"), expanded=True)

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

    def _build_app_rules_section(self) -> None:
        sec = _CollapsibleSection(_("PROFILS AUTOMATIQUES"), expanded=False)

        # Toggle + status
        h_top = QHBoxLayout()
        self._chk_app_rules = QCheckBox(_("Activer les profils par application"))
        self._chk_app_rules.setChecked(self.app_rules_enabled)
        self._chk_app_rules.toggled.connect(self._set_app_rules_enabled)
        h_top.addWidget(self._chk_app_rules, stretch=1)
        sec.add_layout(h_top)

        # Active rule status indicator
        self._lbl_rule_status = QLabel(_("Aucune règle active"))
        self._lbl_rule_status.setStyleSheet("font-size:11px; color:#606060;")
        sec.add_widget(self._lbl_rule_status)

        # Real-time process display (visible when enabled)
        self._lbl_proc_detect = QLabel("")
        self._lbl_proc_detect.setStyleSheet("font-size:10px; color:#505050;")
        sec.add_widget(self._lbl_proc_detect)

        # Manage button
        btn_manage = QPushButton(_("Gérer les règles…"))
        btn_manage.setProperty("class", "pill-muted")
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.clicked.connect(self._open_app_rules_dialog)
        sec.add_widget(btn_manage)

        self.main_l.addWidget(sec)

    def _build_tools_section(self) -> None:
        self.main_l.addWidget(self._section_label(_("OUTILS")))
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

    def _build_settings_section(self) -> None:
        sec = _CollapsibleSection(_("PARAMÈTRES"), expanded=False)

        # F6 — Launch at Windows startup
        self._chk_startup = QCheckBox(_("Lancer au démarrage de Windows"))
        self._chk_startup.setChecked(_startup.is_enabled())
        self._chk_startup.toggled.connect(
            lambda v: _startup.set_enabled(v)
        )
        sec.add_widget(self._chk_startup)

        self.main_l.addWidget(sec)

    def _make_update_banner(self) -> QWidget:
        """Create the update-available banner (hidden by default)."""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        banner = QWidget()
        banner.setObjectName("UpdateBanner")
        banner.setStyleSheet(
            "QWidget#UpdateBanner{"
            f"background:rgba(96,205,255,0.10);"
            f"border:1px solid rgba(96,205,255,0.35);"
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

    # ── Helper widgets ────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        return lbl

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background:{BORDER_COLOR}; max-height:1px; border:none;")
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
        self._chk_app_rules.setChecked(self.app_rules_enabled)

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
            "app_rules_enabled":     self.app_rules_enabled,
        })
        self._rule_mgr.save(self._rules)
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

        # Apply saved per-monitor gamma values
        for c in self.cards:
            if c.device_name in self.gamma_values:
                c.set_gamma_value(float(self.gamma_values[c.device_name]))

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
        if self.app_rules_enabled and not self.focus_enabled:
            self._check_app_rules()

    # ─────────────────────────────────────────────────────────────────────────
    # App rules engine
    # ─────────────────────────────────────────────────────────────────────────

    def _check_app_rules(self) -> None:
        """Match the foreground process against rules and apply if changed."""
        proc = get_foreground_process()

        # Update the real-time process display
        if hasattr(self, "_lbl_proc_detect"):
            if proc:
                has_rule = any(r.enabled and r.process.lower() == proc for r in self._rules)
                color = ACCENT_COLOR if has_rule else "#505050"
                self._lbl_proc_detect.setText(_("Détecté : {}").format(proc))
                self._lbl_proc_detect.setStyleSheet(f"font-size:10px; color:{color};")
            else:
                self._lbl_proc_detect.setText("")

        # Find the first matching enabled rule
        matched: AppRule | None = None
        if proc:
            for rule in self._rules:
                if rule.enabled and rule.process.lower() == proc:
                    matched = rule
                    break

        # Stability guard: require 2 consecutive ticks before acting (avoids
        # flickering on fast alt-tab)
        if proc != self._rule_candidate:
            self._rule_candidate = proc
            self._rule_ticks = 0
            return
        self._rule_ticks += 1
        if self._rule_ticks < 2:
            return

        # Same rule already active → nothing to do
        prev = self._active_rule
        same = (matched is not None and prev is not None
                and matched.process == prev.process)
        if same:
            return

        if matched is None and prev is None:
            return

        # ── Leaving a rule (back to neutral) ─────────────────────────────
        if matched is None and prev is not None:
            self._restore_pre_rule()
            self._active_rule = None
            self._update_rule_status(None)
            return

        # ── Entering a rule (or switching between rules) ──────────────────
        device = get_foreground_window_monitor()

        # Save current state only when entering the first rule
        if not self._pre_rule_bri:
            target = [c for c in self.cards
                      if c.isEnabled() and (not device or c.device_name == device)]
            self._pre_rule_bri = {c.device_name: c.sl_bri.value() for c in target}
            self._pre_rule_con = {c.device_name: c.sl_con.value() for c in target}
            if matched.gamma is not None:
                self._pre_rule_gamma = {c.device_name: c.gamma_value for c in target}
            if matched.red is not None or matched.green is not None or matched.blue is not None:
                for c in target:
                    rgb = c.read_rgb()
                    if rgb is not None:
                        self._pre_rule_rgb[c.device_name] = rgb
            self._active_rule_device = device

        self._apply_app_rule(matched, device)
        self._active_rule = matched
        self._update_rule_status(matched)

    def _apply_app_rule(self, rule: AppRule, device: str | None) -> None:
        log.debug("Applying rule '%s' on %s: bri=%s con=%s gamma=%s rgb=(%s,%s,%s)",
                  rule.label, device or "all",
                  rule.brightness, rule.contrast, rule.gamma,
                  rule.red, rule.green, rule.blue)
        for c in self.cards:
            if not c.isEnabled():
                continue
            if device and c.device_name != device:
                continue
            c.apply_rule_values(rule.brightness, rule.contrast)
            c.apply_rule_rgb(rule.red, rule.green, rule.blue)
        if rule.gamma is not None:
            for c in self.cards:
                if c.isEnabled() and (not device or c.device_name == device):
                    c.set_gamma_value(rule.gamma)

    def _restore_pre_rule(self) -> None:
        if not self._pre_rule_bri:
            return
        for c in self.cards:
            if c.isEnabled():
                bri = self._pre_rule_bri.get(c.device_name)
                con = self._pre_rule_con.get(c.device_name)
                if bri is not None or con is not None:
                    c.apply_rule_values(bri, con)
        for device, gamma in self._pre_rule_gamma.items():
            for c in self.cards:
                if c.device_name == device and c.isEnabled():
                    c.set_gamma_value(gamma)
        for device, rgb in self._pre_rule_rgb.items():
            for c in self.cards:
                if c.device_name == device and c.isEnabled():
                    c.apply_rule_rgb(*rgb)
        self._pre_rule_bri.clear()
        self._pre_rule_con.clear()
        self._pre_rule_gamma.clear()
        self._pre_rule_rgb.clear()
        self._active_rule_device = None

    def _update_rule_status(self, rule: AppRule | None) -> None:
        """Update the status label in the app-rules section."""
        if not hasattr(self, "_lbl_rule_status"):
            return
        if rule:
            self._lbl_rule_status.setText(_("● {}").format(rule.label))
            self._lbl_rule_status.setStyleSheet(
                f"font-size:11px; color:{ACCENT_COLOR}; font-weight:600;"
            )
        else:
            self._lbl_rule_status.setText(_("Aucune règle active"))
            self._lbl_rule_status.setStyleSheet(
                "font-size:11px; color:#606060;"
            )

    def _set_app_rules_enabled(self, enabled: bool) -> None:
        self.app_rules_enabled = enabled
        if not enabled:
            self._restore_pre_rule()
            self._active_rule = None
            self._rule_candidate = None
            self._rule_ticks = 0
            self._update_rule_status(None)

    def _open_app_rules_dialog(self) -> None:
        from lumina_control.ui.app_rules_dialog import AppRulesDialog
        dlg = AppRulesDialog(
            rules=self._rules,
            detection_active=self.app_rules_enabled,
            parent=self,
        )
        dlg.rules_changed.connect(self._on_rules_changed)
        dlg.exec()

    def _on_rules_changed(self, rules: list) -> None:
        self._rules = rules
        self._rule_mgr.save(rules)
        # Reset active rule so it gets re-evaluated on next poll
        self._active_rule = None
        self._rule_candidate = None
        self._rule_ticks = 0

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
            if c.isEnabled():
                c.sl_bri.setValue(v)
        self._sync_guard = False

    def _set_glob(self, v: int) -> None:
        self.sl_glob.setValue(v)
        self._apply_glob()

    def _set_all_power(self, on: bool) -> None:
        for c in self.cards:
            if c.isEnabled():
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
            for c in self.cards if c.isEnabled()
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
            if card and card.isEnabled():
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
        master = next(
            (c for c in self.cards if c.device_name == self.sync_master_device),
            None,
        )
        if not master or not master.isEnabled():
            return
        bri = self._clamp(master.sl_bri.value() + self.sync_offset_bri
                          if self.sync_relative_enabled else master.sl_bri.value())
        con = self._clamp(master.sl_con.value() + self.sync_offset_con
                          if self.sync_relative_enabled else master.sl_con.value())
        self._sync_guard = True
        for c in self.cards:
            if c.device_name != master.device_name and c.isEnabled():
                c.sl_bri.setValue(bri)
                c.sl_con.setValue(con)
        self._sync_guard = False
        if self.sync_rgb_enabled:
            self._sync_rgb_from_master(master)

    def _on_monitor_changed(self, device_name: str, brightness, contrast) -> None:
        if self._sync_guard or not self.sync_enabled or self.focus_enabled:
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
            if c.device_name != device_name and c.isEnabled():
                c.sl_bri.setValue(bri)
                c.sl_con.setValue(con)
        self._sync_guard = False

    def _on_rgb_changed(self, device_name: str, rgb: dict) -> None:
        if not self.sync_enabled or not self.sync_rgb_enabled:
            return
        if device_name != self.sync_master_device:
            return
        for c in self.cards:
            if c.device_name != device_name and c.isEnabled():
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
            if c.device_name != master.device_name and c.isEnabled():
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
            self.pre_focus_values = {
                c.index: c.sl_bri.value() for c in self.cards if c.isEnabled()
            }
            self.last_active = None
            self._apply_focus(force=True)
        else:
            self._restore_pre_focus()

    def _restore_pre_focus(self) -> None:
        if not self.pre_focus_values:
            return
        self._sync_guard = True
        for c in self.cards:
            if c.index in self.pre_focus_values and c.isEnabled():
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
        if (not force and self.last_active == active_idx
                and self._last_focus_target == target
                and self._last_focus_dim == dim):
            return
        self.last_active = active_idx
        self._last_focus_target = target
        self._last_focus_dim = dim
        self._sync_guard = True
        for c in self.cards:
            if not c.isEnabled():
                continue
            desired = target if c.index == active_idx else bg
            if c.sl_bri.value() != desired:
                c.sl_bri.setValue(desired)
        self._sync_guard = False

    def _update_focus_dim_label(self, v: int) -> None:
        self.focus_dim = v
        self.lbl_focus_dim.setText(f"{v}%")

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
