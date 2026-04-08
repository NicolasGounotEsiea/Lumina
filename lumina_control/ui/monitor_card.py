"""Per-monitor control card widget."""
import logging

from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
)

from lumina_control.i18n import _
from lumina_control.utils import set_device_gamma, wake_all_monitors
from lumina_control.monitor_enumerate import MonitorDescriptor
from lumina_control.ui.calibration import CalibrationDialog

log = logging.getLogger(__name__)

# DDC-CI VCP codes
VCP_BRIGHTNESS   = 0x10
VCP_CONTRAST     = 0x12
VCP_COLOR_PRESET = 0x14
VCP_RED          = 0x16
VCP_GREEN        = 0x18
VCP_BLUE         = 0x1A
VCP_POWER        = 0xD6


# ── DDC-CI background worker ──────────────────────────────────────────────────

class _DDCWorker(QObject):
    """Serialises all DDC-CI operations for one monitor on a QThread.

    All public slots are called via queued cross-thread signals from the
    MonitorCard (main thread), so they execute on the worker thread without
    blocking the UI.
    """

    # Emitted on the worker thread → received on the main thread (queued)
    read_done   = Signal(int, int)  # brightness, contrast
    read_failed = Signal()

    def __init__(self, monitor_handle, monitor_index: int) -> None:
        super().__init__()
        self._monitor = monitor_handle
        self._index   = monitor_index

    @Slot()
    def read_initial(self) -> None:
        try:
            with self._monitor:
                b = self._monitor.get_luminance()
                c = self._monitor.get_contrast()
            self.read_done.emit(b, c)
        except Exception as e:
            log.debug("Cannot read monitor %d: %s", self._index, e)
            self.read_failed.emit()

    @Slot(object, object)          # bri: int|None, con: int|None
    def apply_bri_con(self, bri, con) -> None:
        try:
            with self._monitor:
                if bri is not None:
                    self._monitor.set_luminance(bri)
                if con is not None:
                    self._monitor.set_contrast(con)
        except Exception as e:
            log.debug("DDC bri/con write failed on monitor %d: %s", self._index, e)

    @Slot(object, object, object)  # r, g, b: int|None
    def apply_rgb(self, r, g, b) -> None:
        if r is None and g is None and b is None:
            return
        try:
            with self._monitor:
                self._monitor.vcp.set_vcp_feature(VCP_COLOR_PRESET, 0x0B)
                if r is not None:
                    self._monitor.vcp.set_vcp_feature(VCP_RED,   r)
                if g is not None:
                    self._monitor.vcp.set_vcp_feature(VCP_GREEN, g)
                if b is not None:
                    self._monitor.vcp.set_vcp_feature(VCP_BLUE,  b)
        except Exception as e:
            log.debug("DDC RGB write failed on monitor %d: %s", self._index, e)

    @Slot(int)                     # VCP_POWER value (1=on, 5=standby)
    def apply_power(self, state: int) -> None:
        try:
            with self._monitor:
                self._monitor.vcp.set_vcp_feature(VCP_POWER, state)
        except Exception as e:
            log.debug("DDC power write failed on monitor %d: %s", self._index, e)

    @Slot(object)                  # rgb: dict {vcp_code: value}
    def apply_rgb_dict(self, rgb: dict) -> None:
        try:
            with self._monitor:
                for code, val in rgb.items():
                    if val is not None:
                        self._monitor.vcp.set_vcp_feature(code, int(val))
        except Exception as e:
            log.debug("DDC RGB-dict write failed on monitor %d: %s", self._index, e)


# ── MonitorCard ───────────────────────────────────────────────────────────────

class MonitorCard(QFrame):
    """Card widget exposing brightness, contrast and power controls for one monitor."""

    # ── Signals dispatched to _DDCWorker (cross-thread) ──────────────────────
    _sig_read     = Signal()
    _sig_bri_con  = Signal(object, object)
    _sig_rgb      = Signal(object, object, object)
    _sig_power    = Signal(int)
    _sig_rgb_dict = Signal(object)

    def __init__(self, descriptor: MonitorDescriptor,
                 sync_hook=None, sync_rgb_hook=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.descriptor    = descriptor
        self.monitor       = descriptor.ddc_handle
        self.index         = descriptor.index
        self.device_name   = descriptor.device_name
        self.sync_hook     = sync_hook
        self.sync_rgb_hook = sync_rgb_hook
        self.power_on      = True
        self.gamma_value   = 1.0
        self.current_warmth: float = 0.0

        # Debounce timer — fires after 150 ms of slider inactivity
        self._timer = QTimer(singleShot=True, interval=150)
        self._timer.timeout.connect(self._apply_changes)
        self._pending_bri: int | None = None
        self._pending_con: int | None = None
        self._ddc_suspended: bool = False

        self._thread: QThread | None = None
        self._worker: _DDCWorker | None = None

        self._build_ui()

        if self.monitor is not None:
            self._start_worker()
        else:
            self.lbl_name.setText(_("Écran {}  (N/A)").format(self.index + 1))
            self.setEnabled(False)

    # ── Worker thread lifecycle ───────────────────────────────────────────────

    def _start_worker(self) -> None:
        self._thread = QThread()          # no parent — managed manually
        self._worker = _DDCWorker(self.monitor, self.index)
        self._worker.moveToThread(self._thread)

        # Dispatch signals → worker slots (queued, run on worker thread)
        self._sig_read.connect(self._worker.read_initial)
        self._sig_bri_con.connect(self._worker.apply_bri_con)
        self._sig_rgb.connect(self._worker.apply_rgb)
        self._sig_power.connect(self._worker.apply_power)
        self._sig_rgb_dict.connect(self._worker.apply_rgb_dict)

        # Worker results → UI slots (queued back to main thread)
        self._worker.read_done.connect(self._on_initial_values)
        self._worker.read_failed.connect(self._mark_unavailable)

        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

        # Trigger the initial brightness/contrast read
        QTimer.singleShot(100, self._sig_read.emit)

    def cleanup(self) -> None:
        """Stop the DDC worker thread gracefully (call before deleteLater)."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(600)   # up to 600 ms for any in-flight DDC op

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
        self._add_slider_row(layout, _("☀  Lum."), self._on_brightness_change, "bri")
        self._add_slider_row(layout, _("◑  Con."), self._on_contrast_change,   "con")

        # Gamma slider (GPU-based, independent of DDC-CI)
        row_g = QHBoxLayout()
        row_g.setSpacing(8)
        lbl_g = QLabel(_("γ  Gamma"))
        lbl_g.setObjectName("Subtle")
        lbl_g.setFixedWidth(56)
        self.sl_gamma = QSlider(Qt.Horizontal)
        self.sl_gamma.setRange(60, 240)
        self.sl_gamma.setValue(100)
        self.sl_gamma.valueChanged.connect(self._on_gamma_label)
        self.sl_gamma.sliderReleased.connect(self._apply_gamma)
        self.lbl_gamma = QLabel("1.00")
        self.lbl_gamma.setObjectName("ValueBadge")
        self.lbl_gamma.setFixedWidth(34)
        self.lbl_gamma.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_g.addWidget(lbl_g)
        row_g.addWidget(self.sl_gamma)
        row_g.addWidget(self.lbl_gamma)
        layout.addLayout(row_g)

    def _add_slider_row(self, layout, label: str, slot, name: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setObjectName("Subtle")
        lbl.setFixedWidth(56)
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

    # ── DDC-CI read (result lands back on main thread via signal) ─────────────

    @Slot(int, int)
    def _on_initial_values(self, b: int, c: int) -> None:
        for sl, val, v in [(self.sl_bri, self.lbl_bri, b),
                           (self.sl_con, self.lbl_con, c)]:
            sl.blockSignals(True)
            sl.setValue(v)
            sl.blockSignals(False)
            val.setText(str(v))

    @Slot()
    def _mark_unavailable(self) -> None:
        self.lbl_name.setText(_("Écran {}  (N/A)").format(self.index + 1))
        self.setEnabled(False)

    # ── DDC-CI write (dispatched to worker thread) ────────────────────────────

    def _on_brightness_change(self, v: int) -> None:
        self.lbl_bri.setText(str(v))
        self._pending_bri = v
        self._timer.start()

    def _on_contrast_change(self, v: int) -> None:
        self.lbl_con.setText(str(v))
        self._pending_con = v
        self._timer.start()

    def apply_rule_values(self, brightness: int | None, contrast: int | None) -> None:
        """Force-apply brightness/contrast from an app rule."""
        if brightness is not None:
            self.lbl_bri.setText(str(brightness))
            self._pending_bri = brightness
            self.sl_bri.blockSignals(True)
            self.sl_bri.setValue(brightness)
            self.sl_bri.blockSignals(False)
        if contrast is not None:
            self.lbl_con.setText(str(contrast))
            self._pending_con = contrast
            self.sl_con.blockSignals(True)
            self.sl_con.setValue(contrast)
            self.sl_con.blockSignals(False)
        if brightness is not None or contrast is not None:
            self._timer.start()

    def _apply_changes(self) -> None:
        if self._ddc_suspended:
            return  # Keep pending values; will flush on resume
        bri = self._pending_bri
        con = self._pending_con
        self._pending_bri = None
        self._pending_con = None
        # Dispatch to worker thread — returns immediately, UI stays responsive
        self._sig_bri_con.emit(bri, con)
        if self.sync_hook and (bri is not None or con is not None):
            self.sync_hook(self.device_name, bri, con)

    def set_ddc_suspended(self, suspended: bool) -> None:
        """Suspend or resume DDC-CI writes. On resume, flush any pending values."""
        self._ddc_suspended = suspended
        if not suspended:
            self._apply_changes()

    # ── Gamma (GPU / GDI32 — runs on main thread, fast) ──────────────────────

    def _on_gamma_label(self, v: int) -> None:
        self.gamma_value = v / 100.0
        self.lbl_gamma.setText(f"{self.gamma_value:.2f}")

    def _apply_gamma(self) -> None:
        set_device_gamma(self.device_name, self.gamma_value, self.current_warmth)

    def set_gamma_value(self, gamma: float) -> None:
        """Set gamma on this monitor: update slider, label and apply via GDI32."""
        self.gamma_value = max(0.6, min(2.4, float(gamma)))
        self.sl_gamma.blockSignals(True)
        self.sl_gamma.setValue(int(round(self.gamma_value * 100)))
        self.sl_gamma.blockSignals(False)
        self.lbl_gamma.setText(f"{self.gamma_value:.2f}")
        set_device_gamma(self.device_name, self.gamma_value, self.current_warmth)

    def set_warmth(self, warmth: float) -> None:
        """Apply warm tint to this monitor (0.0 = neutral, 1.0 = max warm)."""
        self.current_warmth = warmth
        set_device_gamma(self.device_name, self.gamma_value, warmth)

    # ── RGB gains (dispatched to worker thread) ───────────────────────────────

    def read_rgb(self) -> tuple[int, int, int] | None:
        """Read current R/G/B gains synchronously (called infrequently from main thread)."""
        if not self.monitor:
            return None
        try:
            with self.monitor:
                self.monitor.vcp.set_vcp_feature(VCP_COLOR_PRESET, 0x0B)
                r = self.monitor.vcp.get_vcp_feature(VCP_RED)[0]
                g = self.monitor.vcp.get_vcp_feature(VCP_GREEN)[0]
                b = self.monitor.vcp.get_vcp_feature(VCP_BLUE)[0]
            return (r, g, b)
        except Exception as e:
            log.debug("Cannot read RGB for monitor %d: %s", self.index, e)
            return None

    def apply_rule_rgb(self, red: int | None, green: int | None, blue: int | None) -> None:
        """Apply R/G/B gain values via DDC-CI (async)."""
        if not self.monitor or (red is None and green is None and blue is None):
            return
        self._sig_rgb.emit(red, green, blue)

    # ── Power (dispatched to worker thread) ───────────────────────────────────

    def set_power(self, on: bool) -> None:
        if self.power_on == on:
            return
        self.power_on = on
        self.btn_pow.setProperty("active", "true" if on else "false")
        self.style().unpolish(self.btn_pow)
        self.style().polish(self.btn_pow)
        if not on:
            self._sig_power.emit(5)
        else:
            wake_all_monitors()
            QTimer.singleShot(200, lambda: self._sig_power.emit(1))

    def toggle_power(self) -> None:
        self.set_power(not self.power_on)

    # ── RGB sync (from CalibrationDialog callback, async) ────────────────────

    def set_rgb_values(self, rgb: dict) -> None:
        self._sig_rgb_dict.emit(rgb)

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
        self.setProperty("active", "true" if is_active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
