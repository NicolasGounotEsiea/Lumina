"""Per-monitor control card widget."""
import logging

from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from lumina_control.i18n import _
from lumina_control.utils import set_device_gamma, wake_all_monitors
from lumina_control.monitor_enumerate import MonitorDescriptor
from lumina_control.ui.calibration import CalibrationDialog
from lumina_control.hdr import set_hdr, set_auto_hdr, set_sdr_white_level

log = logging.getLogger(__name__)


def _load_vcp_off_cache() -> dict:
    """Load the per-monitor VCP power-off value cache from AppData."""
    try:
        import json, os as _os
        from lumina_control.config import get_app_data_dir
        path = _os.path.join(get_app_data_dir(), "vcp_off_cache.json")
        if _os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


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
    read_done     = Signal(int, int)  # brightness, contrast
    read_failed   = Signal()
    rgb_read_done = Signal(object)    # tuple[int,int,int] | None
    write_failed  = Signal()          # emitted when a bri/con write is rejected by the monitor

    def __init__(self, monitor_handle, monitor_index: int,
                 device_name: str = "", vcp_off_value: int | None = None) -> None:
        super().__init__()
        self._monitor      = monitor_handle
        self._index        = monitor_index
        self._device_name  = device_name
        self._vcp_off_value: int | None = vcp_off_value  # pre-loaded or probed lazily

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
            self.write_failed.emit()

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

    @Slot(int)                     # state: 1=on, anything else=off
    def apply_power(self, state: int) -> None:
        import time as _time
        if state == 1:
            log.info("POWER mon=%d  ON  vcp_off_value=%s", self._index, self._vcp_off_value)
            # Unified wake: DPMS from this thread + 300 ms + VCP=1 retry.
            # The 300 ms delay is required — test confirmed DPMS+0ms+VCP=1 fails
            # while DPMS+300ms+VCP=1 succeeds on both monitor types.
            from lumina_control.utils import wake_all_monitors as _wake
            _wake()
            log.info("POWER mon=%d  DPMS sent, sleeping 300ms", self._index)
            _time.sleep(0.3)
            for attempt in range(6):
                try:
                    with self._monitor:
                        self._monitor.vcp.set_vcp_feature(VCP_POWER, 1)
                    log.info("POWER mon=%d  VCP=1 OK (attempt %d)", self._index, attempt)
                    return
                except Exception as e:
                    log.info("POWER mon=%d  VCP=1 attempt %d failed: %s",
                             self._index, attempt, e)
                    if attempt < 5:
                        _time.sleep(0.5)
            log.info("POWER mon=%d  all VCP=1 retries exhausted", self._index)
        else:
            log.info("POWER mon=%d  OFF  vcp_off_value=%s", self._index, self._vcp_off_value)
            if self._vcp_off_value is None:
                self._probe_vcp_off()
            else:
                self._send_power_off()

    def _send_power_off(self) -> None:
        import time as _time
        if self._vcp_off_value == 5:
            log.info("POWER mon=%d  OFF LG-type: VCP=4 → 600ms → GET → VCP=5", self._index)
            try:
                with self._monitor:
                    self._monitor.vcp.set_vcp_feature(VCP_POWER, 4)
                log.info("POWER mon=%d  VCP=4 sent", self._index)
            except Exception as e:
                log.info("POWER mon=%d  VCP=4 FAILED: %s", self._index, e)
            _time.sleep(0.6)
            try:
                with self._monitor:
                    val = self._monitor.vcp.get_vcp_feature(VCP_POWER)
                log.info("POWER mon=%d  DDC GET after VCP=4: %s (DDC alive)", self._index, val)
            except Exception as e:
                log.info("POWER mon=%d  DDC GET after VCP=4 FAILED (DDC dead?): %s", self._index, e)
        try:
            with self._monitor:
                self._monitor.vcp.set_vcp_feature(VCP_POWER, self._vcp_off_value)
            log.info("POWER mon=%d  VCP=%d sent OK", self._index, self._vcp_off_value)
        except Exception as e:
            log.info("POWER mon=%d  VCP=%d FAILED: %s", self._index, self._vcp_off_value, e)

    def _probe_vcp_off(self) -> None:
        """Discover the right VCP power-off value for this specific monitor.

        VCP=4 (standby): safe — DPMS can revive the DDC bus if it dies.
        VCP=5 (hard off): permanently kills DDC on some monitors (e.g. 27GL650F),
        but leaves DDC alive on others (e.g. LG UltraWide) while actually going dark.

        Strategy: send VCP=4, wait 600 ms, probe DDC liveness.
        - DDC dead  → 27GL-type: VCP=4 is correct, DPMS revives bus for wake.
        - DDC alive → LG-type: monitor did not go dark, must follow with VCP=5.
        """
        import time as _time
        try:
            with self._monitor:
                self._monitor.vcp.set_vcp_feature(VCP_POWER, 4)
        except Exception as e:
            log.debug("DDC power probe (VCP=4) failed on monitor %d: %s", self._index, e)
            self._vcp_off_value = 4
            return

        # Wait 1500 ms: LG UltraWide transiently kills its DDC bus for ~700 ms
        # after VCP=4 before reviving it.  600 ms was too short → LG was
        # misclassified as 27GL-type (DDC dead) and cached as vcp_off=4,
        # which causes a 10 s panel restart.  1500 ms reliably catches the revival.
        _time.sleep(1.5)

        ddc_alive = False
        try:
            with self._monitor:
                self._monitor.vcp.get_vcp_feature(VCP_POWER)
            ddc_alive = True
        except Exception:
            pass

        if ddc_alive:
            # LG-type: DDC survived VCP=4 → monitor may still be lit. Try VCP=5.
            # Safety check: verify DDC survives VCP=5 before committing to it.
            # Some monitors self-revive DDC after VCP=4 but die permanently on VCP=5.
            log.debug("Monitor %d: DDC alive after VCP=4, trying VCP=5", self._index)
            try:
                with self._monitor:
                    self._monitor.vcp.set_vcp_feature(VCP_POWER, 5)
            except Exception as e:
                log.debug("Monitor %d: VCP=5 send failed: %s → falling back to VCP=4", self._index, e)
                self._vcp_off_value = 4
                self._persist_vcp_off_value()
                return
            _time.sleep(0.3)
            ddc_after_5 = False
            try:
                with self._monitor:
                    self._monitor.vcp.get_vcp_feature(VCP_POWER)
                ddc_after_5 = True
            except Exception:
                pass
            if ddc_after_5:
                self._vcp_off_value = 5
                log.debug("Monitor %d: LG-type confirmed (DDC alive after VCP=5)", self._index)
            else:
                # VCP=5 killed DDC — this monitor is like 27GL with VCP=5.
                # Fall back to VCP=4 for future offs.  Current session: monitor is
                # off with dead DDC; DPMS will revive it on wake (same as 27GL+VCP=4).
                self._vcp_off_value = 4
                log.debug("Monitor %d: VCP=5 killed DDC → downgraded to VCP=4", self._index)
        else:
            # 27GL-type: DDC died from VCP=4 — DPMS will revive it on wake.
            self._vcp_off_value = 4
            log.debug("Monitor %d: 27GL-type (DDC-dead after VCP=4) → VCP=4 confirmed", self._index)

        self._persist_vcp_off_value()

    def _persist_vcp_off_value(self) -> None:
        if not self._device_name or self._vcp_off_value is None:
            return
        try:
            import json, os as _os
            # Use APPDATA env var — avoids Qt QStandardPaths (not safe on worker thread)
            appdata = _os.environ.get("APPDATA", "")
            if not appdata:
                return
            path = _os.path.join(appdata, "LuminaControl", "vcp_off_cache.json")
            cache: dict = {}
            if _os.path.exists(path):
                with open(path) as f:
                    cache = json.load(f)
            cache[self._device_name] = self._vcp_off_value
            with open(path, "w") as f:
                json.dump(cache, f)
        except Exception:
            pass

    @Slot()
    def read_rgb(self) -> None:
        """Read R/G/B gains and emit rgb_read_done (worker thread)."""
        try:
            with self._monitor:
                self._monitor.vcp.set_vcp_feature(VCP_COLOR_PRESET, 0x0B)
                r = self._monitor.vcp.get_vcp_feature(VCP_RED)[0]
                g = self._monitor.vcp.get_vcp_feature(VCP_GREEN)[0]
                b = self._monitor.vcp.get_vcp_feature(VCP_BLUE)[0]
            self.rgb_read_done.emit((r, g, b))
        except Exception as e:
            log.debug("Cannot read RGB for monitor %d: %s", self._index, e)
            self.rgb_read_done.emit(None)

    @Slot(object)                  # rgb: dict {vcp_code: value}
    def apply_rgb_dict(self, rgb: dict) -> None:
        try:
            with self._monitor:
                self._monitor.vcp.set_vcp_feature(VCP_COLOR_PRESET, 0x0B)
                for code, val in rgb.items():
                    if val is not None:
                        self._monitor.vcp.set_vcp_feature(code, int(val))
        except Exception as e:
            log.debug("DDC RGB-dict write failed on monitor %d: %s", self._index, e)


# ── WMI helpers (wmi package preferred, win32com.client fallback) ─────────────

def _wmi_connect():
    """Return (conn, via_com: bool).  Tries ``wmi`` package first, then win32com.

    When via_com is True the connection is an SWbemServices object obtained via
    SWbemLocator.  Method calls must go through ExecMethod_ (direct dispatch
    fails to coerce Python ints to the correct COM VARIANT types for WMI).
    """
    try:
        import wmi as _wmi
        return _wmi.WMI(namespace="wmi"), False
    except ImportError:
        pass
    import pythoncom
    pythoncom.CoInitialize()
    import win32com.client
    loc = win32com.client.Dispatch("WbemScripting.SWbemLocator")
    svc = loc.ConnectServer(".", "root/wmi")
    return svc, True


def _wmi_brightness_instances(conn, via_com: bool) -> list:
    if via_com:
        return list(conn.InstancesOf("WmiMonitorBrightness"))
    return conn.WmiMonitorBrightness()


def _wmi_set_brightness(conn, via_com: bool, index: int, brightness: int) -> None:
    """Write brightness via the appropriate WMI method invocation path."""
    if via_com:
        items = list(conn.ExecQuery("SELECT * FROM WmiMonitorBrightnessMethods"))
        if index >= len(items):
            return
        in_p = items[index].Methods_("WmiSetBrightness").InParameters.SpawnInstance_()
        in_p.Brightness = brightness
        in_p.Timeout    = 0
        items[index].ExecMethod_("WmiSetBrightness", in_p)
    else:
        methods = conn.WmiMonitorBrightnessMethods()
        if index >= len(methods):
            return
        methods[index].WmiSetBrightness(Brightness=brightness, Timeout=0)


# ── WMI brightness worker ────────────────────────────────────────────────────

class _WMIWorker(QObject):
    """Brightness control for built-in laptop screens via Windows WMI.

    Same signal/slot interface as _DDCWorker so MonitorCard can use either
    transparently.  Only brightness is supported — contrast is not exposed
    by WMI and is ignored silently.

    Tries the ``wmi`` Python package first; falls back to ``win32com.client``
    (ships with pywin32) so the feature works without the optional wmi package.
    The connection is cached per worker thread; reset on any error.
    """

    read_done     = Signal(int, int)   # brightness, contrast (contrast always 50)
    read_failed   = Signal()
    rgb_read_done = Signal(object)     # unused — kept for interface parity
    write_failed  = Signal()           # unused — WMI writes do not fail silently

    def __init__(self, wmi_index: int, monitor_index: int) -> None:
        super().__init__()
        self._wmi_index  = wmi_index
        self._index      = monitor_index
        self._wmi_conn   = None
        self._wmi_via_com: bool = False

    def _get_wmi(self):
        if self._wmi_conn is None:
            self._wmi_conn, self._wmi_via_com = _wmi_connect()
        return self._wmi_conn

    def _reset_wmi(self) -> None:
        self._wmi_conn    = None
        self._wmi_via_com = False

    @Slot()
    def read_initial(self) -> None:
        try:
            c         = self._get_wmi()
            instances = _wmi_brightness_instances(c, self._wmi_via_com)
            if self._wmi_index < len(instances):
                b = int(instances[self._wmi_index].CurrentBrightness)
                self.read_done.emit(b, 50)
                return
        except Exception as e:
            log.debug("WMI read failed on monitor %d: %s", self._index, e)
            self._reset_wmi()
        self.read_failed.emit()

    @Slot(object, object)
    def apply_bri_con(self, bri, con) -> None:
        if bri is None:
            return
        try:
            c = self._get_wmi()
            _wmi_set_brightness(c, self._wmi_via_com, self._wmi_index, int(bri))
        except Exception as e:
            log.debug("WMI brightness write failed on monitor %d: %s", self._index, e)
            self._reset_wmi()

    # Stubs — WMI does not support these operations
    @Slot(object, object, object)
    def apply_rgb(self, r, g, b) -> None:
        pass

    @Slot(int)
    def apply_power(self, state: int) -> None:
        pass

    @Slot(object)
    def apply_rgb_dict(self, rgb: dict) -> None:
        pass

    @Slot()
    def read_rgb(self) -> None:
        self.rgb_read_done.emit(None)


# ── MonitorCard ───────────────────────────────────────────────────────────────

class MonitorCard(QFrame):
    """Card widget exposing brightness, contrast and power controls for one monitor."""

    # ── Signals dispatched to _DDCWorker (cross-thread) ──────────────────────
    _sig_read     = Signal()
    _sig_bri_con  = Signal(object, object)
    _sig_rgb      = Signal(object, object, object)
    _sig_power    = Signal(int)
    _sig_rgb_dict = Signal(object)
    _sig_read_rgb = Signal()           # request an async RGB read

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
        self._last_ddc_rgb: dict | None = None  # cache for named-profile save

        # Debounce timer — fires after 150 ms of slider inactivity
        self._timer = QTimer(singleShot=True, interval=150)
        self._timer.timeout.connect(self._apply_changes)
        self._pending_bri: int | None = None
        self._pending_con: int | None = None
        self._ddc_suspended: bool = False

        self._thread: QThread | None = None
        self._worker: _DDCWorker | None = None
        self.available: bool = True   # False when DDC-CI handle is absent or read fails
        self._rgb_reading: bool = False  # re-entrance guard for read_rgb()

        # Custom per-channel LUTs (256 × 0-65535) set from the Curves tab.
        # None = no custom curves; gamma + warmth use the simple power-law ramp.
        # When set, gamma and warmth are composed ON TOP of these LUTs.
        self._custom_luts: tuple[list[int], list[int], list[int]] | None = None
        # Control points that produced _custom_luts — persisted to settings.json.
        self._custom_curve_points: dict | None = None
        # Called (no args) after curves change so MainWindow can save settings.
        self._save_hook = None
        self._ramp_fail_count: int = 0
        self._ramp_unsupported: bool = False

        # Software contrast + RGB gains (GDI32) for non-DDC monitors.
        # sw_contrast: 0.5 = identity, 0.0 = flat grey, 1.0 = max contrast.
        # sw_*_gain:   1.0 = identity, 0.0 = black.
        self.sw_contrast: float = 0.5
        self.sw_r_gain: float = 1.0
        self.sw_g_gain: float = 1.0
        self.sw_b_gain: float = 1.0

        self._build_ui()

        backend = descriptor.brightness_backend
        if backend == "ddc":
            self._start_worker()
        elif backend == "wmi":
            self._start_wmi_worker(descriptor.wmi_index or 0)
        else:
            self._mark_sw_only()

    @property
    def _use_sw_controls(self) -> bool:
        """True when brightness backend is not DDC-CI (WMI or none)."""
        return self.descriptor.brightness_backend != "ddc"

    # ── Worker thread lifecycle ───────────────────────────────────────────────

    def _start_worker(self) -> None:
        self._thread = QThread()          # no parent — managed manually
        self._worker = _DDCWorker(self.monitor, self.index,
                                  device_name=self.device_name,
                                  vcp_off_value=_load_vcp_off_cache().get(self.device_name))
        self._worker.moveToThread(self._thread)

        # Dispatch signals → worker slots (queued, run on worker thread)
        self._sig_read.connect(self._worker.read_initial)
        self._sig_bri_con.connect(self._worker.apply_bri_con)
        self._sig_rgb.connect(self._worker.apply_rgb)
        self._sig_power.connect(self._worker.apply_power)
        self._sig_rgb_dict.connect(self._worker.apply_rgb_dict)
        self._sig_read_rgb.connect(self._worker.read_rgb)

        # Worker results → UI slots (queued back to main thread)
        self._worker.read_done.connect(self._on_initial_values)
        self._worker.read_failed.connect(self._mark_unavailable)
        self._worker.write_failed.connect(self._on_write_failed)

        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

        # Trigger the initial brightness/contrast read
        QTimer.singleShot(100, self._sig_read.emit)

    def _start_wmi_worker(self, wmi_index: int) -> None:
        self._thread = QThread()
        self._worker = _WMIWorker(wmi_index, self.index)
        self._worker.moveToThread(self._thread)

        self._sig_read.connect(self._worker.read_initial)
        self._sig_bri_con.connect(self._worker.apply_bri_con)
        self._sig_rgb.connect(self._worker.apply_rgb)
        self._sig_power.connect(self._worker.apply_power)
        self._sig_rgb_dict.connect(self._worker.apply_rgb_dict)
        self._sig_read_rgb.connect(self._worker.read_rgb)

        self._worker.read_done.connect(self._on_initial_values)
        # WMI failure → sw-only (gamma + sw contrast still work via GDI32)
        self._worker.read_failed.connect(self._mark_sw_only)
        self._worker.write_failed.connect(self._on_write_failed)

        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

        # Contrast routed through GDI32 software simulation for WMI monitors
        self.sl_con.setToolTip(_("Contraste simulé via GPU (GDI32) — indépendant du DDC-CI. 50 = neutre."))
        # _btn_set remains enabled: the Courbes tab works on all monitors via GDI32
        self.btn_pow.setEnabled(False)    # no DDC power command

        QTimer.singleShot(100, self._sig_read.emit)

    def cleanup(self) -> None:
        """Stop the worker thread gracefully (call before deleteLater)."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(600)   # up to 600 ms for any in-flight op

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 12)

        # ── Header row (always visible) ───────────────────────────────────────
        h = QHBoxLayout()
        h.setSpacing(4)
        self.lbl_name = QLabel(self.descriptor.label)
        self.lbl_name.setObjectName("Title")

        self._btn_set = QPushButton("⚙")
        self._btn_set.setProperty("class", "icon-btn")
        self._btn_set.setFixedSize(30, 30)
        self._btn_set.setCursor(Qt.PointingHandCursor)
        self._btn_set.clicked.connect(self._open_calibration)

        self.btn_pow = QPushButton("⏻")
        self.btn_pow.setObjectName("PowerBtn")
        self.btn_pow.setProperty("class", "icon-btn")
        self.btn_pow.setFixedSize(30, 30)
        self.btn_pow.setCursor(Qt.PointingHandCursor)
        self.btn_pow.clicked.connect(self.toggle_power)
        self.btn_pow.setProperty("active", "true")

        self._lbl_hdr_badge = QLabel("HDR")
        self._lbl_hdr_badge.setObjectName("HDRBadge")
        self._lbl_hdr_badge.setVisible(False)

        h.addWidget(self.lbl_name)
        h.addStretch()
        h.addWidget(self._lbl_hdr_badge)
        h.addWidget(self._btn_set)
        h.addWidget(self.btn_pow)
        layout.addLayout(h)

        # ── Controls body (hidden when DDC-CI unavailable) ────────────────────
        self._body = QWidget()
        body_l = QVBoxLayout(self._body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(8)

        self.lbl_details = QLabel(self.descriptor.details)
        self.lbl_details.setObjectName("MonitorDetails")
        body_l.addWidget(self.lbl_details)

        self._bri_row_w = self._add_slider_row(body_l, _("☀  Lum."), self._on_brightness_change, "bri")
        self._con_row_w = self._add_slider_row(body_l, _("◑  Con."), self._on_contrast_change,   "con")

        # Write-blocked warning — shown when the monitor rejects DDC-CI writes
        self._lbl_write_warn = QLabel(_(
            "⚠  Réglages sans effet — le moniteur refuse les commandes DDC-CI.\n"
            "Cause probable : un preset image (Game / FPS / Cinema) est actif dans l'OSD.\n"
            "Appuyez sur le bouton physique du moniteur → Menu Image → choisissez le mode Utilisateur ou Standard."
        ))
        self._lbl_write_warn.setObjectName("WriteWarnLabel")
        self._lbl_write_warn.setWordWrap(True)
        self._lbl_write_warn.setVisible(False)
        body_l.addWidget(self._lbl_write_warn)

        # Gamma slider (GPU-based, independent of DDC-CI)
        self._gamma_row_w = QWidget()
        row_g = QHBoxLayout(self._gamma_row_w)
        row_g.setContentsMargins(0, 0, 0, 0)
        row_g.setSpacing(8)
        lbl_g = QLabel(_("γ  Gamma"))
        lbl_g.setObjectName("Subtle")
        lbl_g.setFixedWidth(56)
        _gamma_tip = _(
            "Ajuste la luminosité perçue des tons intermédiaires via la carte graphique.\n"
            "Fonctionne même si le DDC-CI est indisponible.\n"
            "1.00 = neutre  ·  < 1.00 = plus sombre  ·  > 1.00 = plus clair\n"
            "Pour un réglage global (tous les écrans), voir la section « GAMMA GPU »."
        )
        lbl_g.setToolTip(_gamma_tip)
        self.sl_gamma = QSlider(Qt.Horizontal)
        self.sl_gamma.setRange(60, 240)
        self.sl_gamma.setValue(100)
        self.sl_gamma.setToolTip(_gamma_tip)
        self.sl_gamma.valueChanged.connect(self._on_gamma_label)
        self.sl_gamma.sliderReleased.connect(self._apply_gamma)
        self.lbl_gamma = QLabel("1.00")
        self.lbl_gamma.setObjectName("ValueBadge")
        self.lbl_gamma.setFixedWidth(34)
        self.lbl_gamma.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_g.addWidget(lbl_g)
        row_g.addWidget(self.sl_gamma)
        row_g.addWidget(self.lbl_gamma)
        body_l.addWidget(self._gamma_row_w)

        # HDR active notice — shown instead of DDC/gamma controls when HDR is on
        self._hdr_notice = QLabel(_(
            "⚠  HDR actif — DDC-CI indisponible.\n"
            "Réglez la luminosité du contenu SDR via le slider ci-dessous."
        ))
        self._hdr_notice.setObjectName("WriteWarnLabel")
        self._hdr_notice.setWordWrap(True)
        self._hdr_notice.setVisible(False)
        body_l.addWidget(self._hdr_notice)

        layout.addWidget(self._body)

        # ── HDR controls (shown only when monitor supports HDR) ───────────────
        self._hdr_frame = self._build_hdr_frame()
        self._hdr_frame.setVisible(False)
        layout.addWidget(self._hdr_frame)

        # ── N/A help block (shown when DDC-CI unavailable) ────────────────────
        self._na_frame = self._build_na_frame()
        self._na_frame.setVisible(False)
        layout.addWidget(self._na_frame)

    def _build_hdr_frame(self) -> QFrame:
        """Control block for HDR-capable monitors (toggle + SDR white level + Auto HDR)."""
        frame = QFrame()
        frame.setObjectName("HDRFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 4, 0, 0)
        fl.setSpacing(6)

        # ── HDR on/off toggle row ─────────────────────────────────────────────
        row_hdr = QHBoxLayout()
        row_hdr.setSpacing(8)
        lbl_hdr = QLabel("HDR")
        lbl_hdr.setObjectName("Subtle")
        lbl_hdr.setFixedWidth(56)
        self._btn_hdr = QPushButton(_("Désactivé"))
        self._btn_hdr.setObjectName("FocusToggle")
        self._btn_hdr.setCheckable(True)
        self._btn_hdr.setFixedWidth(90)
        self._btn_hdr.toggled.connect(self._on_hdr_toggled)
        row_hdr.addWidget(lbl_hdr)
        row_hdr.addWidget(self._btn_hdr)
        row_hdr.addStretch()
        fl.addLayout(row_hdr)

        # ── SDR white level slider (visible when HDR active) ──────────────────
        self._sdr_row = QWidget()
        sdr_l = QHBoxLayout(self._sdr_row)
        sdr_l.setContentsMargins(0, 0, 0, 0)
        sdr_l.setSpacing(8)
        lbl_sdr = QLabel(_("☀  SDR"))
        lbl_sdr.setObjectName("Subtle")
        lbl_sdr.setFixedWidth(56)
        lbl_sdr.setToolTip(_("Luminosité du contenu SDR en mode HDR (80–500 nits)."))
        self.sl_sdr = QSlider(Qt.Horizontal)
        self.sl_sdr.setRange(0, 100)
        self.sl_sdr.setValue(50)
        self.sl_sdr.valueChanged.connect(self._on_sdr_label)
        self.sl_sdr.sliderReleased.connect(self._apply_sdr_white_level)
        self.lbl_sdr = QLabel("50%")
        self.lbl_sdr.setObjectName("ValueBadge")
        self.lbl_sdr.setFixedWidth(34)
        self.lbl_sdr.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sdr_l.addWidget(lbl_sdr)
        sdr_l.addWidget(self.sl_sdr)
        sdr_l.addWidget(self.lbl_sdr)
        self._sdr_row.setVisible(False)
        fl.addWidget(self._sdr_row)

        # ── Auto HDR toggle (Windows 11 22H2+, hidden if unsupported) ─────────
        self._auto_hdr_row = QWidget()
        auto_l = QHBoxLayout(self._auto_hdr_row)
        auto_l.setContentsMargins(0, 0, 0, 0)
        auto_l.setSpacing(8)
        lbl_auto = QLabel(_("Auto HDR"))
        lbl_auto.setObjectName("Subtle")
        lbl_auto.setFixedWidth(56)
        self._btn_auto_hdr = QPushButton(_("Désactivé"))
        self._btn_auto_hdr.setObjectName("FocusToggle")
        self._btn_auto_hdr.setCheckable(True)
        self._btn_auto_hdr.setFixedWidth(90)
        self._btn_auto_hdr.toggled.connect(self._on_auto_hdr_toggled)
        auto_l.addWidget(lbl_auto)
        auto_l.addWidget(self._btn_auto_hdr)
        auto_l.addStretch()
        self._auto_hdr_row.setVisible(False)
        fl.addWidget(self._auto_hdr_row)

        return frame

    def refresh_hdr(self) -> None:
        """Refresh HDR state from the OS and update controls. Call from poll timer."""
        from lumina_control.hdr import get_hdr_info
        info = get_hdr_info(self.device_name)
        if info is None or not info.hdr_supported:
            self._hdr_frame.setVisible(False)
            self._lbl_hdr_badge.setVisible(False)
            return

        self._hdr_frame.setVisible(True)
        self._lbl_hdr_badge.setVisible(True)
        if info.hdr_enabled:
            self._lbl_hdr_badge.setStyleSheet(
                "color:#ffaa00;font-weight:bold;font-size:10px;"
                "background:rgba(255,170,0,18);border:1px solid rgba(255,170,0,80);"
                "border-radius:3px;padding:1px 4px;"
            )
        else:
            self._lbl_hdr_badge.setStyleSheet(
                "color:#888;font-weight:bold;font-size:10px;"
                "background:rgba(128,128,128,12);border:1px solid rgba(128,128,128,40);"
                "border-radius:3px;padding:1px 4px;"
            )

        # HDR toggle — block signals to avoid feedback loop
        self._btn_hdr.blockSignals(True)
        self._btn_hdr.setChecked(info.hdr_enabled)
        self._btn_hdr.setText(_("Activé") if info.hdr_enabled else _("Désactivé"))
        self._btn_hdr.blockSignals(False)

        # Hide DDC/gamma controls when HDR is active — they have no effect
        self._bri_row_w.setVisible(not info.hdr_enabled)
        self._con_row_w.setVisible(not info.hdr_enabled)
        self._gamma_row_w.setVisible(not info.hdr_enabled)
        self._lbl_write_warn.setVisible(self._lbl_write_warn.isVisible() and not info.hdr_enabled)
        self._hdr_notice.setVisible(info.hdr_enabled)

        # SDR white level slider
        self._sdr_row.setVisible(info.hdr_enabled)
        if info.hdr_enabled:
            self.sl_sdr.blockSignals(True)
            self.sl_sdr.setValue(info.sdr_white_level_pct)
            self.sl_sdr.blockSignals(False)
            self.lbl_sdr.setText(f"{info.sdr_white_level_pct}%")

        # Auto HDR (only show if supported)
        self._auto_hdr_row.setVisible(info.auto_hdr_supported)
        if info.auto_hdr_supported:
            self._btn_auto_hdr.blockSignals(True)
            self._btn_auto_hdr.setChecked(info.auto_hdr_enabled)
            self._btn_auto_hdr.setText(
                _("Activé") if info.auto_hdr_enabled else _("Désactivé"))
            self._btn_auto_hdr.blockSignals(False)

    def _on_hdr_toggled(self, checked: bool) -> None:
        self._btn_hdr.setText(_("Activé") if checked else _("Désactivé"))
        self._sdr_row.setVisible(checked)
        set_hdr(self.device_name, checked)

    def _on_sdr_label(self, v: int) -> None:
        self.lbl_sdr.setText(f"{v}%")

    def _apply_sdr_white_level(self) -> None:
        set_sdr_white_level(self.device_name, self.sl_sdr.value())

    def _on_auto_hdr_toggled(self, checked: bool) -> None:
        self._btn_auto_hdr.setText(_("Activé") if checked else _("Désactivé"))
        set_auto_hdr(self.device_name, checked)

    def _build_na_frame(self) -> QFrame:
        """Help block shown when DDC-CI is unavailable for this monitor."""
        frame = QFrame()
        frame.setObjectName("NAHelpFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(4)

        title = QLabel("⚠  " + _("DDC-CI indisponible"))
        title.setObjectName("NATitle")
        fl.addWidget(title)

        hint = QLabel(_(
            "DDC-CI inaccessible — activez « DDC/CI » dans le menu OSD du moniteur (boutons physiques) "
            "puis relancez l'application.\n"
            "Le slider γ Gamma et le contraste GPU restent disponibles ci-dessus."
        ))
        hint.setObjectName("NAHint")
        hint.setWordWrap(True)
        fl.addWidget(hint)

        return frame

    def _add_slider_row(self, layout, label: str, slot, name: str) -> QWidget:
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
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
        layout.addWidget(wrapper)
        setattr(self, f"sl_{name}", sl)
        setattr(self, f"lbl_{name}", val)
        return wrapper

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
    def _on_write_failed(self) -> None:
        """Show the write-blocked warning when the monitor rejects a DDC-CI write."""
        self._lbl_write_warn.setVisible(True)

    @Slot()
    def _mark_unavailable(self) -> None:
        """DDC-CI connection failed. Disable DDC controls; gamma (GDI32) still works."""
        self.available = False
        self.lbl_name.setText(_("Écran {}  (N/A)").format(self.index + 1))
        self.btn_pow.setEnabled(False)
        self.sl_bri.setEnabled(False)
        self.sl_con.setEnabled(False)
        # Body stays visible — gamma slider (GDI32) remains functional
        self._na_frame.setVisible(True)

    @Slot()
    def _mark_sw_only(self) -> None:
        """No DDC-CI or WMI brightness. Gamma + sw contrast (GDI32) still work."""
        self.btn_pow.setEnabled(False)
        self.sl_bri.setEnabled(False)
        self.lbl_bri.setText("N/A")
        self.sl_bri.setToolTip(_("Luminosité non disponible (aucun backend DDC-CI ou WMI)."))
        # Contrast starts at neutral (50) so sw_contrast is identity by default
        self.sl_con.blockSignals(True)
        self.sl_con.setValue(50)
        self.sl_con.blockSignals(False)
        self.lbl_con.setText("50")
        self.sw_contrast = 0.5

    # ── DDC-CI write (dispatched to worker thread) ────────────────────────────

    def _on_brightness_change(self, v: int) -> None:
        self.lbl_bri.setText(str(v))
        self._pending_bri = v
        self._timer.start()

    def _on_contrast_change(self, v: int) -> None:
        self.lbl_con.setText(str(v))
        if self._use_sw_controls:
            self.sw_contrast = v / 100.0
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
        if not self.power_on:
            return  # Monitor is off — don't send DDC writes that would wake it
        if self._ddc_suspended:
            return  # Keep pending values; will flush on resume
        bri = self._pending_bri
        con = self._pending_con
        self._pending_bri = None
        self._pending_con = None
        # Dispatch to worker thread — returns immediately, UI stays responsive
        self._sig_bri_con.emit(bri, con)
        # For non-DDC monitors contrast is simulated via GDI32
        if self._use_sw_controls and con is not None:
            self._apply_ramp()
        if self.sync_hook and (bri is not None or con is not None):
            self.sync_hook(self.device_name, bri, con)

    def set_ddc_suspended(self, suspended: bool) -> None:
        """Suspend or resume DDC-CI writes. On resume, flush any pending values."""
        self._ddc_suspended = suspended
        if not suspended:
            self._apply_changes()

    # ── Gamma + warmth (GPU / GDI32 — runs on main thread, fast) ────────────

    def _on_gamma_label(self, v: int) -> None:
        self.gamma_value = v / 100.0
        self.lbl_gamma.setText(f"{self.gamma_value:.2f}")

    def _apply_gamma(self) -> None:
        self._apply_ramp()

    def _apply_ramp(self, user_triggered: bool = False) -> None:
        """Apply GDI32 ramp: custom curves + gamma + warmth + sw contrast/gains.

        Falls back to plain gamma when no custom effects are active, or when the
        driver doesn't support arbitrary ramps.  *user_triggered*=True means the
        user just clicked Apply — on failure we fall through immediately so the
        user gets visible feedback.  Background calls tolerate 2 transient
        failures before falling back, to avoid flicker on brief driver hiccups.
        """
        if not self.power_on:
            return  # Monitor is off — skip GPU ramp to avoid waking it
        has_sw_effect = (
            self._use_sw_controls and (
                self.sw_contrast != 0.5
                or self.sw_r_gain != 1.0
                or self.sw_g_gain != 1.0
                or self.sw_b_gain != 1.0
            )
        )
        use_compose = (self._custom_luts is not None or has_sw_effect) and not self._ramp_unsupported
        if use_compose:
            from lumina_control.curve_editor import compose_ramp, set_device_gamma_ramp
            if self._custom_luts is not None:
                r_lut, g_lut, b_lut = self._custom_luts
            else:
                identity = [int(round(i / 255 * 65535)) for i in range(256)]
                r_lut = g_lut = b_lut = identity
            r, g, b = compose_ramp(
                r_lut, g_lut, b_lut,
                self.gamma_value, self.current_warmth,
                self.sw_contrast, self.sw_r_gain, self.sw_g_gain, self.sw_b_gain,
            )
            if set_device_gamma_ramp(self.device_name, r, g, b):
                self._ramp_fail_count = 0
                return
            if user_triggered:
                log.warning(
                    "SetDeviceGammaRamp a échoué sur %s — repli sur gamma simple "
                    "(driver/moniteur ne supporte pas les rampes personnalisées).",
                    self.device_name,
                )
                self._ramp_unsupported = True
                self._ramp_fail_count = 0
                # fall through to set_device_gamma for immediate feedback
            else:
                self._ramp_fail_count += 1
                if self._ramp_fail_count >= 3:
                    log.warning(
                        "SetDeviceGammaRamp non supporté sur %s — courbes "
                        "sauvegardées mais non appliquées à l'affichage.",
                        self.device_name,
                    )
                    self._ramp_unsupported = True
                    self._ramp_fail_count = 0
                else:
                    return  # Échec transitoire — préserver le ramp existant.
        set_device_gamma(self.device_name, self.gamma_value, self.current_warmth)

    def set_gamma_value(self, gamma: float) -> None:
        """Set gamma on this monitor: update slider, label and apply via GDI32."""
        self.gamma_value = max(0.6, min(2.4, float(gamma)))
        self.sl_gamma.blockSignals(True)
        self.sl_gamma.setValue(int(round(self.gamma_value * 100)))
        self.sl_gamma.blockSignals(False)
        self.lbl_gamma.setText(f"{self.gamma_value:.2f}")
        self._apply_ramp()

    def set_warmth(self, warmth: float) -> None:
        """Apply warm tint to this monitor (0.0 = neutral, 1.0 = max warm)."""
        self.current_warmth = warmth
        self._apply_ramp()

    # ── RGB gains (dispatched to worker thread) ───────────────────────────────

    def read_rgb(self) -> tuple[int, int, int] | None:
        """Read current R/G/B gains via the worker thread.

        Dispatches the DDC read to the worker and waits for the result using
        a local QEventLoop so the main thread remains responsive (processes
        events) while the DDC operation is in progress.
        """
        if not self.monitor or self._worker is None or self._rgb_reading:
            return None
        from PySide6.QtCore import QEventLoop, QTimer as _QT
        self._rgb_reading = True
        loop = QEventLoop()
        result: list = [None]

        def _on_done(val):
            result[0] = val
            loop.quit()

        # SingleShotConnection: auto-disconnects after one delivery
        self._worker.rgb_read_done.connect(_on_done, Qt.SingleShotConnection)
        self._sig_read_rgb.emit()
        # Safety timeout: bail out after 500 ms to avoid deadlock
        _QT.singleShot(500, loop.quit)
        loop.exec()

        self._rgb_reading = False
        return result[0]

    def apply_rule_rgb(self, red: int | None, green: int | None, blue: int | None) -> None:
        """Apply R/G/B gain values via DDC-CI (async) or SW gains for non-DDC monitors."""
        if red is None and green is None and blue is None:
            return
        if self._use_sw_controls:
            # Convert 0-100 DDC scale to 0.0-1.0 SW gain; None keeps current gain
            self._on_sw_rgb_applied(
                (red  / 100.0) if red  is not None else self.sw_r_gain,
                (green / 100.0) if green is not None else self.sw_g_gain,
                (blue / 100.0) if blue is not None else self.sw_b_gain,
            )
        elif self.monitor:
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
            self._sig_power.emit(0)
        else:
            wake_all_monitors()
            self._sig_power.emit(1)
            # Panel takes several seconds to physically light up after VCP=1.
            # Block the button so the user doesn't click again thinking it failed.
            self.btn_pow.setEnabled(False)
            QTimer.singleShot(7000, lambda: self.btn_pow.setEnabled(True))

    def toggle_power(self) -> None:
        self.set_power(not self.power_on)

    # ── RGB sync (from CalibrationDialog callback, async) ────────────────────

    def set_rgb_values(self, rgb: dict) -> None:
        self._last_ddc_rgb = rgb
        self._sig_rgb_dict.emit(rgb)

    # ── Calibration dialog ────────────────────────────────────────────────────

    @staticmethod
    def _is_identity_curves(curve_points: dict) -> bool:
        """Return True if all channels are the default two-point identity curve."""
        for pts in curve_points.values():
            if len(pts) != 2:
                return False
            x0, y0 = pts[0][0], pts[0][1]
            x1, y1 = pts[1][0], pts[1][1]
            if not (abs(x0) < 1e-9 and abs(y0) < 1e-9
                    and abs(x1 - 1.0) < 1e-9 and abs(y1 - 1.0) < 1e-9):
                return False
        return True

    def _on_curves_applied(self, r_lut: list[int], g_lut: list[int],
                           b_lut: list[int], curve_points: dict | None = None) -> None:
        """Receive LUTs from CalibrationDialog and compose with gamma + warmth."""
        # Each explicit user apply resets failure state so the driver gets fresh tries.
        self._ramp_fail_count = 0
        self._ramp_unsupported = False
        # If every channel is identity, treat as "no custom curves" so that the
        # normal gamma path stays active (avoids set_device_gamma_ramp failing
        # silently on drivers/monitors that reject arbitrary ramps).
        if curve_points is not None and self._is_identity_curves(curve_points):
            self._custom_luts = None
            self._custom_curve_points = None
        else:
            self._custom_luts = (r_lut, g_lut, b_lut)
            if curve_points is not None:
                self._custom_curve_points = curve_points
        self._apply_ramp(user_triggered=True)
        # Persist immediately so a crash doesn't lose the user's work.
        if self._save_hook is not None:
            QTimer.singleShot(300, self._save_hook)

    def _on_sw_rgb_applied(self, r_gain: float, g_gain: float, b_gain: float) -> None:
        """Receive software RGB gains from CalibrationDialog (non-DDC monitors)."""
        self.sw_r_gain = r_gain
        self.sw_g_gain = g_gain
        self.sw_b_gain = b_gain
        self._apply_ramp()

    def _open_calibration(self) -> None:
        sw_rgb_cb = self._on_sw_rgb_applied if self._use_sw_controls else None
        initial_sw = (
            {0x16: int(round(self.sw_r_gain * 100)),
             0x18: int(round(self.sw_g_gain * 100)),
             0x1A: int(round(self.sw_b_gain * 100))}
            if self._use_sw_controls else None
        )
        dlg = CalibrationDialog(
            self.monitor,
            self.descriptor.label,
            self.device_name,
            sync_rgb_callback=self.sync_rgb_hook,
            curves_applied_callback=self._on_curves_applied,
            initial_curves=self._custom_curve_points,
            sw_rgb_callback=sw_rgb_cb,
            initial_sw_rgb=initial_sw,
            parent=self.window(),
        )
        # Suspend the DDC worker while CalibrationDialog has direct I2C access
        # to avoid concurrent use of the same DDC handle from two threads.
        was_suspended = self._ddc_suspended
        if not self._use_sw_controls:
            self.set_ddc_suspended(True)
        dlg.exec()
        if not self._use_sw_controls:
            self.set_ddc_suspended(was_suspended)
        # Cache DDC RGB gains so named profiles can save them
        if not self._use_sw_controls and dlg._sliders:
            self._last_ddc_rgb = {code: sl.value() for code, sl in dlg._sliders.items()}

    # ── Active highlight ──────────────────────────────────────────────────────

    def set_active(self, is_active: bool) -> None:
        self.setProperty("active", "true" if is_active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
