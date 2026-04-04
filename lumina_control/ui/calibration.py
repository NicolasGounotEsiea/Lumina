"""Calibration dialogs: per-monitor RGB gain and guided calibration wizard."""
import logging
from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QApplication,
)

from lumina_control.ui.patterns import PatternWindow

log = logging.getLogger(__name__)


class CalibrationDialog(QDialog):
    """Fine-tune per-monitor RGB gains via DDC-CI VCP codes."""

    # VCP codes for R/G/B gains
    _CHANNELS = [
        ("R", 0x16, "SliderR"),
        ("G", 0x18, "SliderG"),
        ("B", 0x1A, "SliderB"),
    ]

    def __init__(self, monitor_handle, monitor_name: str, device_name: str,
                 sync_rgb_callback=None, parent=None) -> None:
        super().__init__(parent)
        self.monitor = monitor_handle
        self.device_name = device_name
        self.sync_rgb_callback = sync_rgb_callback
        self.sync_rgb = True
        self._syncing = False
        self._sliders: dict[int, QSlider] = {}
        self._labels: dict[int, QLabel] = {}
        self._loaded: dict[int, int] = {}

        self.setWindowTitle("Calibrage RGB")
        self.setFixedSize(360, 360)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel(f"Calibrage : {monitor_name}")
        title.setObjectName("Title")
        layout.addWidget(title)

        info = QLabel("Ajustement fin des gains RGB (si supporté par l'écran).")
        info.setWordWrap(True)
        info.setStyleSheet("color: #4e5d78; font-size: 11px; font-style: italic;")
        layout.addWidget(info)

        # Unlock "User Color" mode before adjusting
        QTimer.singleShot(100, self._unlock_user_mode)

        # Link / reload toolbar
        tools = QHBoxLayout()
        self.chk_link = QCheckBox("Lier R/G/B")
        self.chk_link.setChecked(True)
        self.chk_link.toggled.connect(lambda v: setattr(self, "sync_rgb", v))
        btn_reload = QPushButton("Recharger")
        btn_reload.setProperty("class", "pill-muted")
        btn_reload.clicked.connect(self._reload_all)
        tools.addWidget(self.chk_link)
        tools.addStretch()
        tools.addWidget(btn_reload)
        layout.addLayout(tools)

        # RGB sliders
        for label, code, obj_name in self._CHANNELS:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(16)
            lbl.setStyleSheet("font-weight:bold;")
            sl = QSlider(Qt.Horizontal)
            sl.setObjectName(obj_name)
            sl.setRange(0, 100)
            val_lbl = QLabel("--")
            val_lbl.setObjectName("ValueBadge")
            val_lbl.setFixedWidth(30)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sl.valueChanged.connect(partial(self._on_channel_change, code))
            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(val_lbl)
            layout.addLayout(row)
            self._sliders[code] = sl
            self._labels[code] = val_lbl
            QTimer.singleShot(200, partial(self._load_channel, code))

        # Global gain slider
        gain_row = QHBoxLayout()
        lbl_gain = QLabel("Gain global")
        lbl_gain.setObjectName("Subtle")
        self.sl_gain = QSlider(Qt.Horizontal)
        self.sl_gain.setRange(0, 100)
        self.lbl_gain = QLabel("--")
        self.lbl_gain.setObjectName("ValueBadge")
        self.lbl_gain.setFixedWidth(30)
        self.lbl_gain.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sl_gain.valueChanged.connect(lambda v: self.lbl_gain.setText(str(v)))
        self.sl_gain.sliderReleased.connect(self._apply_gain)
        gain_row.addWidget(lbl_gain)
        gain_row.addWidget(self.sl_gain)
        gain_row.addWidget(self.lbl_gain)
        layout.addLayout(gain_row)

        layout.addStretch()
        btn_ok = QPushButton("Fermer")
        btn_ok.setProperty("class", "pill")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    # ── DDC-CI helpers ────────────────────────────────────────────────────────

    def _unlock_user_mode(self) -> None:
        try:
            with self.monitor:
                self.monitor.vcp.set_vcp_feature(0x14, 0x0B)
        except Exception as e:
            log.debug("Could not unlock user colour mode: %s", e)

    def _load_channel(self, code: int) -> None:
        sl = self._sliders[code]
        lbl = self._labels[code]
        try:
            with self.monitor:
                val = self.monitor.vcp.get_vcp_feature(code)[0]
            sl.blockSignals(True)
            sl.setValue(val)
            sl.blockSignals(False)
            lbl.setText(str(val))
            self._loaded[code] = val
            if len(self._loaded) == 3:
                avg = int(round(sum(self._loaded.values()) / 3))
                self.sl_gain.blockSignals(True)
                self.sl_gain.setValue(avg)
                self.sl_gain.blockSignals(False)
                self.lbl_gain.setText(str(avg))
        except Exception as e:
            log.debug("Cannot read VCP 0x%02X: %s", code, e)
            lbl.setText("N/A")
            sl.setEnabled(False)

    def _reload_all(self) -> None:
        self._loaded.clear()
        for code in self._sliders:
            self._load_channel(code)

    def _apply_gain(self) -> None:
        val = self.sl_gain.value()
        self._syncing = True
        for sl in self._sliders.values():
            sl.setValue(val)
        self._syncing = False

    def _on_channel_change(self, code: int, value: int) -> None:
        self._labels[code].setText(str(value))
        try:
            with self.monitor:
                self.monitor.vcp.set_vcp_feature(code, value)
        except Exception as e:
            log.debug("Cannot set VCP 0x%02X: %s", code, e)
        self._emit_rgb_sync()
        if self.sync_rgb and not self._syncing:
            self._syncing = True
            for c, sl in self._sliders.items():
                if c != code:
                    sl.setValue(value)
            self._syncing = False

    def _emit_rgb_sync(self) -> None:
        if not self.sync_rgb_callback:
            return
        rgb = {code: sl.value() for code, sl in self._sliders.items()}
        self.sync_rgb_callback(self.device_name, rgb)


# ─────────────────────────────────────────────────────────────────────────────

class CalibrationWizard(QDialog):
    """Step-by-step guided calibration using full-screen test patterns."""

    STEPS = [
        {"title": "Uniformité Blanc",    "pattern": "uniform_white",
         "help": "Vérifier les zones plus sombres ou jaunâtres sur fond blanc."},
        {"title": "Uniformité Gris 50%", "pattern": "uniform_gray",
         "help": "Détecter les dominantes de couleur sur gris neutre."},
        {"title": "Uniformité Noir",     "pattern": "uniform_black",
         "help": "Observer les fuites de lumière (backlight bleeding)."},
        {"title": "Gradient Horizontal", "pattern": "grad_h",
         "help": "Vérifier les bandes et la linéarité de la gradation."},
        {"title": "Gamma Steps",         "pattern": "gamma_steps",
         "help": "Vérifier la progressivité des niveaux de gris."},
        {"title": "Sharpness",           "pattern": "sharpness",
         "help": "Vérifier la netteté et la sur-accentuation."},
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibrage guidé")
        self.setFixedSize(420, 340)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.step_index = 0
        self.pattern_window: PatternWindow | None = None
        self._build_ui()
        self._refresh_screens()
        self._update_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Calibrage guidé")
        title.setObjectName("Title")
        layout.addWidget(title)

        self.lbl_step = QLabel()
        self.lbl_step.setObjectName("Subtle")
        layout.addWidget(self.lbl_step)

        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("SectionTitle")
        self.lbl_title.setStyleSheet(
            "font-size:13px; font-weight:600; color:#e2e8f0;"
        )
        layout.addWidget(self.lbl_title)

        self.lbl_help = QLabel()
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setObjectName("Subtle")
        layout.addWidget(self.lbl_help)

        row_screen = QHBoxLayout()
        lbl_screen = QLabel("Écran cible")
        lbl_screen.setObjectName("Subtle")
        self.cmb_screen = QComboBox()
        self.cmb_screen.setFixedWidth(160)
        row_screen.addWidget(lbl_screen)
        row_screen.addWidget(self.cmb_screen)
        row_screen.addStretch()
        layout.addLayout(row_screen)

        btn_show = QPushButton("Afficher le pattern")
        btn_show.setProperty("class", "pill")
        btn_show.clicked.connect(self._show_pattern)
        layout.addWidget(btn_show)
        self.btn_show = btn_show

        row_nav = QHBoxLayout()
        self.btn_prev = QPushButton("Précédent")
        self.btn_prev.setProperty("class", "pill-muted")
        self.btn_prev.clicked.connect(self._prev_step)
        self.btn_next = QPushButton("Suivant")
        self.btn_next.setProperty("class", "pill")
        self.btn_next.clicked.connect(self._next_step)
        row_nav.addWidget(self.btn_prev)
        row_nav.addWidget(self.btn_next)
        layout.addLayout(row_nav)

        layout.addStretch()
        btn_close = QPushButton("Fermer")
        btn_close.setProperty("class", "pill-muted")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _refresh_screens(self) -> None:
        self.cmb_screen.blockSignals(True)
        self.cmb_screen.clear()
        for i, s in enumerate(QApplication.screens()):
            self.cmb_screen.addItem(f"Écran {i + 1}", i)
        self.cmb_screen.blockSignals(False)
        self.btn_show.setEnabled(bool(QApplication.screens()))

    def _update_ui(self) -> None:
        step = self.STEPS[self.step_index]
        self.lbl_step.setText(f"Étape {self.step_index + 1} / {len(self.STEPS)}")
        self.lbl_title.setText(step["title"])
        self.lbl_help.setText(step["help"])
        self.btn_prev.setEnabled(self.step_index > 0)
        self.btn_next.setEnabled(self.step_index < len(self.STEPS) - 1)

    def _show_pattern(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        idx = self.cmb_screen.currentData() or 0
        pattern_id = self.STEPS[self.step_index]["pattern"]
        if self.pattern_window and self.pattern_window.isVisible():
            self.pattern_window.screen_index = idx
            self.pattern_window._apply_screen()
            self.pattern_window.set_pattern_by_id(pattern_id)
            self.pattern_window.activateWindow()
            return
        self.pattern_window = PatternWindow(start_screen_idx=idx)
        self.pattern_window.set_pattern_by_id(pattern_id)
        self.pattern_window.destroyed.connect(
            lambda: setattr(self, "pattern_window", None)
        )
        self.pattern_window.showFullScreen()

    def _next_step(self) -> None:
        if self.step_index < len(self.STEPS) - 1:
            self.step_index += 1
            self._update_ui()
            if self.pattern_window and self.pattern_window.isVisible():
                self._show_pattern()

    def _prev_step(self) -> None:
        if self.step_index > 0:
            self.step_index -= 1
            self._update_ui()
            if self.pattern_window and self.pattern_window.isVisible():
                self._show_pattern()
