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
    get_profile_path, get_settings_path,
)
from lumina_control.profiles import ProfileManager
from lumina_control.utils import (
    get_active_screen_index, set_gamma_all, wake_all_monitors,
)
from lumina_control.monitor_enumerate import enumerate_monitors
from lumina_control.ui.monitor_card import MonitorCard
from lumina_control.ui.patterns import PatternWindow
from lumina_control.ui.calibration import CalibrationWizard

log = logging.getLogger(__name__)


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
        self.focus_enabled         = s["focus_enabled"]
        self.focus_dim             = s["focus_dim"]

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
        eff.setBlurRadius(32)
        eff.setColor(QColor(0, 0, 0, 180))
        eff.setOffset(0, 6)
        self.container.setGraphicsEffect(eff)
        outer_l.addWidget(self.container)

        container_l = QVBoxLayout(self.container)
        container_l.setSpacing(0)
        container_l.setContentsMargins(0, 0, 0, 0)

        # ── Fixed header ─────────────────────────────
        header = QWidget()
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(16, 12, 12, 12)
        header_l.setSpacing(10)

        icon_lbl = QLabel("◈")
        icon_lbl.setStyleSheet(f"color: {ACCENT_COLOR}; font-size: 20px; padding: 0;")

        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)
        title_lbl = QLabel(APP_NAME)
        title_lbl.setObjectName("AppTitle")
        subtitle_lbl = QLabel("Multi-écrans · contrôle rapide")
        subtitle_lbl.setObjectName("AppSubtitle")
        title_stack.addWidget(title_lbl)
        title_stack.addWidget(subtitle_lbl)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseWinBtn")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("Masquer la fenêtre")
        btn_close.clicked.connect(self.hide)

        header_l.addWidget(icon_lbl)
        header_l.addLayout(title_stack)
        header_l.addStretch()
        header_l.addWidget(btn_close)
        container_l.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; max-height: 1px; border: none;")
        container_l.addWidget(sep)

        # ── Scrollable content ────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(570)

        content_w = QWidget()
        self.main_l = QVBoxLayout(content_w)
        self.main_l.setSpacing(12)
        self.main_l.setContentsMargins(15, 14, 15, 14)
        scroll.setWidget(content_w)
        container_l.addWidget(scroll)

        self._build_quick_section()
        self.main_l.addWidget(self._sep())
        self._build_sync_section()
        self.main_l.addWidget(self._sep())
        self._build_gamma_section()
        self.main_l.addWidget(self._sep())
        self._build_tools_section()
        self.main_l.addWidget(self._sep())
        self._build_snapshot_section()
        self.main_l.addWidget(self._sep())
        self._build_focus_section()
        self.main_l.addWidget(self._sep())

        # Monitor cards zone
        self.main_l.addWidget(self._section_label("ÉCRANS"))
        self.mon_l = QVBoxLayout()
        self.mon_l.setSpacing(10)
        self.main_l.addLayout(self.mon_l)
        self.main_l.addStretch()

        # Footer
        btn_quit = QPushButton("Quitter l'application")
        btn_quit.setObjectName("QuitBtn")
        btn_quit.setCursor(Qt.PointingHandCursor)
        btn_quit.clicked.connect(QApplication.quit)
        self.main_l.addWidget(btn_quit, alignment=Qt.AlignCenter)

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_quick_section(self) -> None:
        hdr = QHBoxLayout()
        hdr.addWidget(self._section_label("RÉGLAGES RAPIDES"))
        hdr.addStretch()
        btn_ref = QPushButton("↻ Rafraîchir")
        btn_ref.setProperty("class", "pill-muted")
        btn_ref.setProperty("quick", "true")
        btn_ref.setToolTip("Rafraîchir la liste des écrans")
        btn_ref.clicked.connect(self.refresh)
        hdr.addWidget(btn_ref)
        self.main_l.addLayout(hdr)

        row_glob = QHBoxLayout()
        lbl = QLabel("Luminosité globale")
        lbl.setObjectName("Subtle")
        self.sl_glob = QSlider(Qt.Horizontal)
        self.sl_glob.setRange(0, 100)
        self.sl_glob.setValue(50)
        self.sl_glob.sliderReleased.connect(self._apply_glob)
        self.sl_glob.valueChanged.connect(lambda v: self.lbl_glob_val.setText(f"{v}%"))
        self.lbl_glob_val = QLabel("50%")
        self.lbl_glob_val.setObjectName("ValueBadge")
        self.lbl_glob_val.setFixedWidth(40)
        self.lbl_glob_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_glob.addWidget(lbl)
        row_glob.addWidget(self.sl_glob)
        row_glob.addWidget(self.lbl_glob_val)
        self.main_l.addLayout(row_glob)

        h_pre = QHBoxLayout()
        btn_day = QPushButton("☀  Jour  80%")
        btn_day.setProperty("class", "pill")
        btn_day.setProperty("quick", "true")
        btn_day.setStyleSheet(
            f"color:{WARM_COLOR}; border-color:rgba(251,191,36,0.3);"
            f" background:rgba(251,191,36,0.08);"
        )
        btn_day.clicked.connect(partial(self._set_glob, 80))
        btn_night = QPushButton("☾  Nuit  25%")
        btn_night.setProperty("class", "pill")
        btn_night.setProperty("quick", "true")
        btn_night.clicked.connect(partial(self._set_glob, 25))
        h_pre.addWidget(btn_day)
        h_pre.addWidget(btn_night)
        self.main_l.addLayout(h_pre)

        h_actions = QHBoxLayout()
        for label, slot, cls in [
            ("⏻  Allumer tout",  partial(self._set_all_power, True),  "pill"),
            ("⭘  Éteindre tout", partial(self._set_all_power, False), "pill-muted"),
            ("⏵  Réveiller",     wake_all_monitors,                   "pill-muted"),
        ]:
            btn = QPushButton(label)
            btn.setProperty("class", cls)
            btn.setProperty("quick", "true")
            btn.setProperty("quickRole", "action")
            btn.clicked.connect(slot)
            h_actions.addWidget(btn)
        self.main_l.addLayout(h_actions)

    def _build_sync_section(self) -> None:
        self.main_l.addWidget(self._section_label("SYNCHRONISATION"))

        h_sync = QHBoxLayout()
        self.chk_sync = QCheckBox("Synchroniser les écrans")
        self.chk_sync.toggled.connect(self._set_sync_enabled)
        lbl_master = QLabel("Maître")
        lbl_master.setObjectName("Subtle")
        self.cmb_master = QComboBox()
        self.cmb_master.setFixedWidth(130)
        self.cmb_master.currentIndexChanged.connect(self._set_sync_master)
        h_sync.addWidget(self.chk_sync)
        h_sync.addStretch()
        h_sync.addWidget(lbl_master)
        h_sync.addWidget(self.cmb_master)
        self.main_l.addLayout(h_sync)

        h2 = QHBoxLayout()
        self.chk_sync_rgb = QCheckBox("Gains RGB")
        self.chk_sync_rgb.toggled.connect(self._set_sync_rgb_enabled)
        self.btn_sync_now = QPushButton("Sync maintenant")
        self.btn_sync_now.setProperty("class", "pill-muted")
        self.btn_sync_now.clicked.connect(self.sync_now)
        h2.addWidget(self.chk_sync_rgb)
        h2.addStretch()
        h2.addWidget(self.btn_sync_now)
        self.main_l.addLayout(h2)

        h3 = QHBoxLayout()
        self.chk_sync_relative = QCheckBox("Décalages relatifs")
        self.chk_sync_relative.toggled.connect(self._set_sync_relative_enabled)
        h3.addWidget(self.chk_sync_relative)
        h3.addStretch()
        self.main_l.addLayout(h3)

        for attr, label, lo, hi, slot_lbl, slot_rel in [
            ("sl_sync_bri", "Offset lum.", -40, 40,
             "lbl_sync_bri_val", self._update_sync_bri_label),
            ("sl_sync_con", "Offset cont.", -40, 40,
             "lbl_sync_con_val", self._update_sync_con_label),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("Subtle")
            sl = QSlider(Qt.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(0)
            sl.valueChanged.connect(slot_rel)
            sl.sliderReleased.connect(self._apply_sync_offsets)
            val_lbl = QLabel("0%")
            val_lbl.setObjectName("ValueBadge")
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(val_lbl)
            self.main_l.addLayout(row)
            setattr(self, attr, sl)
            setattr(self, slot_lbl, val_lbl)

    def _build_gamma_section(self) -> None:
        self.main_l.addWidget(self._section_label("CORRECTION GAMMA GPU"))

        row = QHBoxLayout()
        lbl = QLabel("Gamma")
        lbl.setObjectName("Subtle")
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
        self.main_l.addLayout(row)

        h_btn = QHBoxLayout()
        self.btn_gamma_import = QPushButton("Importer")
        self.btn_gamma_import.setProperty("class", "pill-muted")
        self.btn_gamma_import.clicked.connect(self._import_gamma)
        self.btn_gamma_export = QPushButton("Exporter")
        self.btn_gamma_export.setProperty("class", "pill-muted")
        self.btn_gamma_export.clicked.connect(self._export_gamma)
        btn_reset = QPushButton("Reset gamma")
        btn_reset.setProperty("class", "pill-muted")
        btn_reset.clicked.connect(self.reset_gamma)
        h_btn.addWidget(self.btn_gamma_import)
        h_btn.addWidget(self.btn_gamma_export)
        h_btn.addStretch()
        h_btn.addWidget(btn_reset)
        self.main_l.addLayout(h_btn)

    def _build_tools_section(self) -> None:
        self.main_l.addWidget(self._section_label("OUTILS"))
        h = QHBoxLayout()
        btn_patterns = QPushButton("Patterns plein écran")
        btn_patterns.setProperty("class", "pill")
        btn_patterns.setProperty("quick", "true")
        btn_patterns.clicked.connect(self.show_patterns)
        btn_wizard = QPushButton("Calibrage guidé")
        btn_wizard.setProperty("class", "pill-muted")
        btn_wizard.clicked.connect(self.show_calibration_wizard)
        h.addWidget(btn_patterns)
        h.addWidget(btn_wizard)
        self.main_l.addLayout(h)

    def _build_snapshot_section(self) -> None:
        self.main_l.addWidget(self._section_label("INSTANTANÉ"))
        h = QHBoxLayout()
        btn_save = QPushButton("Sauver")
        btn_save.setProperty("class", "pill")
        btn_save.clicked.connect(self.save_snapshot)
        btn_restore = QPushButton("Restaurer")
        btn_restore.setProperty("class", "pill-muted")
        btn_restore.clicked.connect(self.restore_snapshot)
        self.lbl_snapshot = QLabel("Aucun instantané")
        self.lbl_snapshot.setObjectName("Subtle")
        h.addWidget(btn_save)
        h.addWidget(btn_restore)
        h.addStretch()
        h.addWidget(self.lbl_snapshot)
        self.main_l.addLayout(h)

    def _build_focus_section(self) -> None:
        h = QHBoxLayout()
        h.addWidget(self._section_label("MODE FOCUS"))
        h.addStretch()
        self.btn_focus = QPushButton("Désactivé")
        self.btn_focus.setObjectName("FocusToggle")
        self.btn_focus.setCheckable(True)
        self.btn_focus.toggled.connect(lambda v: self.set_focus_enabled(v, source="ui"))
        h.addWidget(self.btn_focus)
        self.main_l.addLayout(h)

        lbl_help = QLabel("Garde l'écran actif lumineux, assombrit les autres.")
        lbl_help.setObjectName("Subtle")
        self.main_l.addWidget(lbl_help)

        row = QHBoxLayout()
        lbl_dim = QLabel("Atténuation")
        lbl_dim.setObjectName("Subtle")
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
        self.main_l.addLayout(row)

    # ── Helper widgets ────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        lbl.setStyleSheet(
            f"color:#4e5d78; font-size:10px; font-weight:700;"
            f" padding-left:8px; border-left:2px solid {ACCENT_COLOR};"
        )
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
        ]
        for w in widgets:
            w.blockSignals(True)

        self.chk_sync.setChecked(self.sync_enabled)
        self.chk_sync_rgb.setChecked(self.sync_rgb_enabled)
        self.chk_sync_relative.setChecked(self.sync_relative_enabled)
        self.sl_sync_bri.setValue(self.sync_offset_bri)
        self.sl_sync_con.setValue(self.sync_offset_con)
        self.sl_gamma.setValue(int(round(self.gamma_value * 100)))

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
            self.btn_focus.setText("Activé")
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
            "focus_enabled":         self.focus_enabled,
            "focus_dim":             self.focus_dim,
        })
        log.debug("Settings saved.")

    # ─────────────────────────────────────────────────────────────────────────
    # Monitor management
    # ─────────────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        while self.mon_l.count():
            w = self.mon_l.takeAt(0).widget()
            if w:
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
            self.mon_l.addWidget(QLabel("Erreur lors du scan des écrans"))

        self.adjustSize()
        self._refresh_sync_combo()
        self._update_sync_ui()
        if self.sync_enabled:
            self.sync_now()
        if self.focus_enabled:
            self._apply_focus(force=True)

    def _poll(self) -> None:
        idx = get_active_screen_index()
        if self.isVisible():
            for c in self.cards:
                c.set_active(c.index == idx)
        self._apply_focus()

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
            self.lbl_snapshot.setText(f"Dernier : {snap['saved_at']}")
        else:
            self.lbl_snapshot.setText("Aucun instantané")

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
        self.lbl_snapshot.setText(f"Dernier : {saved_at}")

    def restore_snapshot(self) -> None:
        snap = self._profile.load_snapshot()
        if not snap or not snap.get("monitors"):
            self.lbl_snapshot.setText("Instantané introuvable")
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
            self.lbl_snapshot.setText(f"Dernier : {snap['saved_at']}")

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
        set_gamma_all(self.gamma_value)

    def reset_gamma(self) -> None:
        self.sl_gamma.setValue(100)
        self.gamma_value = 1.0
        set_gamma_all(1.0)

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
        set_gamma_all(gamma)

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
        self.btn_focus.setText("Activé" if enabled else "Désactivé")
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

    def _apply_focus(self, force: bool = False) -> None:
        if not self.focus_enabled or not self.cards:
            return
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
