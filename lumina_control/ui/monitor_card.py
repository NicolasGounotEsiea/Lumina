"""Per-monitor control card widget."""
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
)

from lumina_control.config import ACCENT_COLOR, CARD_HOVER
from lumina_control.utils import wake_all_monitors
from lumina_control.monitor_enumerate import MonitorDescriptor
from lumina_control.ui.calibration import CalibrationDialog

log = logging.getLogger(__name__)

# DDC-CI VCP codes
VCP_BRIGHTNESS = 0x10
VCP_CONTRAST   = 0x12
VCP_POWER      = 0xD6


class MonitorCard(QFrame):
    """Card widget exposing brightness, contrast and power controls for one monitor."""

    def __init__(self, descriptor: MonitorDescriptor,
                 sync_hook=None, sync_rgb_hook=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.descriptor  = descriptor
        self.monitor     = descriptor.ddc_handle
        self.index       = descriptor.index
        self.device_name = descriptor.device_name
        self.sync_hook     = sync_hook
        self.sync_rgb_hook = sync_rgb_hook
        self.power_on = True

        # Debounce timer so we don't flood DDC-CI on every slider tick
        self._timer = QTimer(singleShot=True, interval=150)
        self._timer.timeout.connect(self._apply_changes)
        self._pending_bri: int | None = None
        self._pending_con: int | None = None

        self._build_ui()
        if self.monitor is not None:
            QTimer.singleShot(100, self._read_initial)
        else:
            self.lbl_name.setText(f"Écran {self.index + 1}  (N/A)")
            self.setEnabled(False)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 12)

        # Header row
        h = QHBoxLayout()
        h.setSpacing(4)
        self.lbl_name = QLabel(self.descriptor.label)
        self.lbl_name.setObjectName("Title")

        btn_set = QPushButton("⚙")
        btn_set.setProperty("class", "icon-btn")
        btn_set.setFixedSize(30, 30)
        btn_set.setCursor(Qt.PointingHandCursor)
        btn_set.clicked.connect(self._open_calibration)

        self.btn_pow = QPushButton("⏻")
        self.btn_pow.setObjectName("PowerBtn")
        self.btn_pow.setProperty("class", "icon-btn")
        self.btn_pow.setFixedSize(30, 30)
        self.btn_pow.setCursor(Qt.PointingHandCursor)
        self.btn_pow.clicked.connect(self.toggle_power)
        self.btn_pow.setProperty("active", "true")

        h.addWidget(self.lbl_name)
        h.addStretch()
        h.addWidget(btn_set)
        h.addWidget(self.btn_pow)
        layout.addLayout(h)

        # Resolution / refresh info
        self.lbl_details = QLabel(self.descriptor.details)
        self.lbl_details.setObjectName("MonitorDetails")
        layout.addWidget(self.lbl_details)

        # Brightness / contrast sliders
        self._add_slider_row(layout, "Luminosité", self._on_brightness_change, "bri")
        self._add_slider_row(layout, "Contraste",  self._on_contrast_change,   "con")

    def _screen_details(self) -> str:  # kept for compat, prefer descriptor.details
        return self.descriptor.details

    def _add_slider_row(self, layout, label: str, slot, name: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setObjectName("Subtle")
        lbl.setFixedWidth(62)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(0, 100)
        sl.valueChanged.connect(slot)
        val = QLabel("--")
        val.setObjectName("ValueBadge")
        val.setFixedWidth(34)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)
        row.addWidget(sl)
        row.addWidget(val)
        layout.addLayout(row)
        setattr(self, f"sl_{name}", sl)
        setattr(self, f"lbl_{name}", val)

    # ── DDC-CI read / write ───────────────────────────────────────────────────

    def _read_initial(self) -> None:
        try:
            with self.monitor:
                b = self.monitor.get_luminance()
                c = self.monitor.get_contrast()
            for sl, val, v in [(self.sl_bri, self.lbl_bri, b),
                               (self.sl_con, self.lbl_con, c)]:
                sl.blockSignals(True)
                sl.setValue(v)
                sl.blockSignals(False)
                val.setText(str(v))
        except Exception as e:
            log.debug("Cannot read monitor %d: %s", self.index, e)
            self.lbl_name.setText(f"Écran {self.index + 1}  (N/A)")
            self.setEnabled(False)

    def _on_brightness_change(self, v: int) -> None:
        self.lbl_bri.setText(str(v))
        self._pending_bri = v
        self._timer.start()

    def _on_contrast_change(self, v: int) -> None:
        self.lbl_con.setText(str(v))
        self._pending_con = v
        self._timer.start()

    def _apply_changes(self) -> None:
        applied_bri = self._pending_bri
        applied_con = self._pending_con
        try:
            with self.monitor:
                if self._pending_bri is not None:
                    self.monitor.set_luminance(self._pending_bri)
                    self._pending_bri = None
                if self._pending_con is not None:
                    self.monitor.set_contrast(self._pending_con)
                    self._pending_con = None
        except Exception as e:
            log.debug("DDC-CI write failed on monitor %d: %s", self.index, e)
        if self.sync_hook and (applied_bri is not None or applied_con is not None):
            self.sync_hook(self.device_name, applied_bri, applied_con)

    # ── Power ─────────────────────────────────────────────────────────────────

    def set_power(self, on: bool) -> None:
        if self.power_on == on:
            return
        self.power_on = on
        self.btn_pow.setProperty("active", "true" if on else "false")
        self.style().unpolish(self.btn_pow)
        self.style().polish(self.btn_pow)
        try:
            if not on:
                with self.monitor:
                    self.monitor.vcp.set_vcp_feature(VCP_POWER, 5)
            else:
                wake_all_monitors()
                QTimer.singleShot(200, self._force_on)
        except Exception as e:
            log.debug("Power toggle failed on monitor %d: %s", self.index, e)

    def toggle_power(self) -> None:
        self.set_power(not self.power_on)

    def _force_on(self) -> None:
        try:
            with self.monitor:
                self.monitor.vcp.set_vcp_feature(VCP_POWER, 1)
        except Exception as e:
            log.debug("Force-on failed on monitor %d: %s", self.index, e)

    # ── RGB sync (from CalibrationDialog callback) ────────────────────────────

    def set_rgb_values(self, rgb: dict) -> None:
        try:
            with self.monitor:
                for code, val in rgb.items():
                    if val is not None:
                        self.monitor.vcp.set_vcp_feature(code, int(val))
        except Exception as e:
            log.debug("RGB sync failed on monitor %d: %s", self.index, e)

    # ── Calibration dialog ────────────────────────────────────────────────────

    def _open_calibration(self) -> None:
        dlg = CalibrationDialog(
            self.monitor,
            self.descriptor.label,
            self.device_name,
            sync_rgb_callback=self.sync_rgb_hook,
            parent=self.window(),
        )
        dlg.exec()

    # ── Active highlight ──────────────────────────────────────────────────────

    def set_active(self, is_active: bool) -> None:
        if is_active:
            self.setStyleSheet(
                f"QFrame#Card {{ border: 1px solid {ACCENT_COLOR};"
                f" background-color: {CARD_HOVER}; }}"
            )
        else:
            self.setStyleSheet("")
