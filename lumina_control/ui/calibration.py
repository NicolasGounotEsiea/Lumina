"""Calibration dialogs: per-monitor RGB gains, tone curves and guided wizard."""
import logging
import os
from functools import partial

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QFileDialog, QSlider, QTabWidget,
    QVBoxLayout, QWidget,
)

from lumina_control.i18n import _
from lumina_control.ui.patterns import PatternWindow

log = logging.getLogger(__name__)


# ── Interactive tone curve widget ─────────────────────────────────────────────

class _CurveWidget(QWidget):
    """Interactive per-channel (R/G/B) tone curve editor.

    Control points in [0, 1]² space are interpolated via monotone cubic
    spline (Fritsch-Carlson) to a 256-entry LUT used with SetDeviceGammaRamp.

    - Left-click empty area  → add a control point
    - Left-drag existing pt  → move it
    - Right-click (non-endpoint) → delete point
    """

    curve_changed = Signal()

    _PAD_L = 26    # left margin (room for Y tick labels)
    _PAD_R = 14
    _PAD_T = 14
    _PAD_B = 24    # bottom margin (room for X tick labels)
    _HIT   = 11    # px hit-test radius for control points
    _DRAW  = 6     # px drawn radius for control points

    _CH_COL: dict[str, tuple[int, int, int]] = {
        "R": (230, 90,  95),
        "G": (95,  200, 110),
        "B": (95,  140, 240),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(334, 220)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        self._curves: dict[str, list[tuple[float, float]]] = {
            ch: [(0.0, 0.0), (1.0, 1.0)] for ch in ("R", "G", "B")
        }
        self._active: str = "R"
        self._drag_idx: int | None = None
        self._hover_idx: int | None = None
        # Normalised (x, y) of cursor during drag — shown as live coord readout.
        self._drag_norm: tuple[float, float] | None = None

    # ── Public helpers ────────────────────────────────────────────────────────

    def set_channel(self, ch: str) -> None:
        self._active = ch
        self._drag_idx = None
        self.update()

    def reset_channel(self, ch: str | None = None) -> None:
        target = ch or self._active
        self._curves[target] = [(0.0, 0.0), (1.0, 1.0)]
        self._drag_idx = None
        self.update()
        self.curve_changed.emit()

    def get_lut(self, ch: str) -> list[int]:
        """Return a 256-entry GDI32 LUT (0-65535) for channel *ch*."""
        from lumina_control.curve_editor import monotone_lut
        return monotone_lut(self._curves[ch])

    # ── Coordinate helpers ────────────────────────────────────────────────────

    def _plot_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) of the inner plot area."""
        x = self._PAD_L
        y = self._PAD_T
        w = self.width()  - self._PAD_L - self._PAD_R
        h = self.height() - self._PAD_T - self._PAD_B
        return x, y, w, h

    def _to_px(self, x: float, y: float) -> tuple[int, int]:
        px_x, px_y, w, h = self._plot_rect()
        return (int(round(px_x + x * w)),
                int(round(px_y + (1.0 - y) * h)))

    def _to_norm(self, px: int, py: int) -> tuple[float, float]:
        px_x, px_y, w, h = self._plot_rect()
        x = max(0.0, min(1.0, (px - px_x) / w)) if w > 0 else 0.0
        y = max(0.0, min(1.0, 1.0 - (py - px_y) / h)) if h > 0 else 0.0
        return x, y

    def _hit_test(self, px: int, py: int,
                  pts: list[tuple[float, float]]) -> int | None:
        for i, (x, y) in enumerate(pts):
            cx, cy = self._to_px(x, y)
            if abs(px - cx) <= self._HIT and abs(py - cy) <= self._HIT:
                return i
        return None

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        r_full = self.rect().adjusted(0, 0, -1, -1)

        # ── Outer rounded panel (fill + 1 px border) ──────────────────────────
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(16, 17, 20))
        p.drawRoundedRect(r_full, 10, 10)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawRoundedRect(
            float(r_full.x()) + 0.5, float(r_full.y()) + 0.5,
            float(r_full.width()), float(r_full.height()),
            10, 10,
        )

        px_x, px_y, w, h = self._plot_rect()

        # ── Plot area background (slightly darker inset card) ─────────────────
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(10, 11, 13))
        p.drawRoundedRect(px_x - 4, px_y - 4, w + 8, h + 8, 6, 6)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawRoundedRect(
            float(px_x) - 3.5, float(px_y) - 3.5, float(w + 7), float(h + 7),
            6, 6,
        )

        # ── Grid (quarter lines) — pixel-snapped for crispness ────────────────
        grid = QPen(QColor(255, 255, 255, 16), 1)
        grid.setCosmetic(True)
        p.setPen(grid)
        for i in (1, 2, 3):
            gx = px_x + round(i * w / 4) + 0.5
            gy = px_y + round(i * h / 4) + 0.5
            p.drawLine(int(gx), px_y, int(gx), px_y + h)
            p.drawLine(px_x, int(gy), px_x + w, int(gy))

        # ── Diagonal reference (identity) ─────────────────────────────────────
        pen_diag = QPen(QColor(255, 255, 255, 28), 1, Qt.DashLine)
        pen_diag.setDashPattern([3, 3])
        p.setPen(pen_diag)
        p.drawLine(px_x, px_y + h, px_x + w, px_y)

        # ── Axis tick labels (0 / 50 / 100) ───────────────────────────────────
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor(255, 255, 255, 70))
        fm_tick = p.fontMetrics()
        # X axis: 0, 50, 100 underneath
        for frac, lbl_txt in ((0.0, "0"), (0.5, "50"), (1.0, "100")):
            tx = px_x + int(frac * w)
            tw = fm_tick.horizontalAdvance(lbl_txt)
            p.drawText(tx - tw // 2, px_y + h + fm_tick.ascent() + 4, lbl_txt)
        # Y axis: 0, 50, 100 to the left
        for frac, lbl_txt in ((0.0, "0"), (0.5, "50"), (1.0, "100")):
            ty = px_y + int((1.0 - frac) * h)
            tw = fm_tick.horizontalAdvance(lbl_txt)
            p.drawText(px_x - tw - 6, ty + fm_tick.ascent() // 2 - 1, lbl_txt)

        # ── Inactive channels (ghosted but readable as reference) ─────────────
        for ch in ("R", "G", "B"):
            if ch == self._active:
                continue
            rc, gc, bc = self._CH_COL[ch]
            pen_inactive = QPen(QColor(rc, gc, bc, 72))
            pen_inactive.setWidthF(1.4)
            pen_inactive.setCapStyle(Qt.RoundCap)
            pen_inactive.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen_inactive)
            self._draw_curve_path(p, ch, px_x, px_y, w, h)

        # ── Area fill under active curve (subtle gradient) ────────────────────
        rc, gc, bc = self._CH_COL[self._active]
        area_path = self._build_curve_path(
            self._active, px_x, px_y, w, h, closed_baseline=True)
        grad = QLinearGradient(0, px_y, 0, px_y + h)
        grad.setColorAt(0.0, QColor(rc, gc, bc, 72))
        grad.setColorAt(1.0, QColor(rc, gc, bc, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(area_path)

        # ── Active channel curve ──────────────────────────────────────────────
        pen_active = QPen(QColor(rc, gc, bc, 255))
        pen_active.setWidthF(2.4)
        pen_active.setCapStyle(Qt.RoundCap)
        pen_active.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen_active)
        p.setBrush(Qt.NoBrush)
        self._draw_curve_path(p, self._active, px_x, px_y, w, h)

        # ── Control points (active channel) ───────────────────────────────────
        pts = self._curves[self._active]
        for i, (x, y) in enumerate(pts):
            cx, cy = self._to_px(x, y)
            is_end  = (i == 0 or i == len(pts) - 1)
            is_drag = (i == self._drag_idx)
            is_hov  = (i == self._hover_idx and not is_drag)
            d = self._DRAW + (1 if is_drag else 0)
            # halo on drag/hover
            if is_drag or is_hov:
                halo_alpha = 70 if is_drag else 42
                p.setBrush(QColor(rc, gc, bc, halo_alpha))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - d - 4, cy - d - 4,
                              2 * (d + 4), 2 * (d + 4))
            # ring: dark outline then coloured fill
            p.setPen(QPen(QColor(8, 9, 11, 230), 2.0))
            fill_alpha = 230 if is_end else 255
            p.setBrush(QColor(rc, gc, bc, fill_alpha))
            p.drawEllipse(cx - d, cy - d, 2 * d, 2 * d)
            # inner highlight dot
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 120))
            p.drawEllipse(cx - 1, cy - 2, 2, 2)

        # ── Channel pill label (top-left of plot) ─────────────────────────────
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        fm_lbl = p.fontMetrics()
        lbl_text = self._active
        tw = fm_lbl.horizontalAdvance(lbl_text)
        pill_w = tw + 14
        pill_h = fm_lbl.height() + 2
        pill_x = px_x
        pill_y = px_y + 4
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(rc, gc, bc, 50))
        p.drawRoundedRect(pill_x, pill_y, pill_w, pill_h,
                          pill_h / 2, pill_h / 2)
        p.setPen(QColor(rc, gc, bc, 235))
        p.drawText(pill_x + 7, pill_y + fm_lbl.ascent(), lbl_text)

        # ── Live coordinate readout (top-right while dragging) ────────────────
        if self._drag_norm is not None:
            cx_v, cy_v = self._drag_norm
            txt = f"{int(round(cx_v*100))},{int(round(cy_v*100))}"
            p.setFont(QFont("Segoe UI", 8))
            fm_co = p.fontMetrics()
            tw2 = fm_co.horizontalAdvance(txt)
            box_w = tw2 + 12
            box_h = fm_co.height() + 2
            box_x = px_x + w - box_w
            box_y = px_y + 4
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 140))
            p.drawRoundedRect(box_x, box_y, box_w, box_h,
                              box_h / 2, box_h / 2)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(box_x + 6, box_y + fm_co.ascent(), txt)

        # ── Hint text (shown only on default identity curve) ──────────────────
        elif len(self._curves[self._active]) == 2:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor(255, 255, 255, 56))
            hint = _("Clic : ajouter un point  ·  clic droit : supprimer")
            fm_h = p.fontMetrics()
            hx = px_x + (w - fm_h.horizontalAdvance(hint)) // 2
            hy = px_y + h // 2 + fm_h.ascent() // 2 + 8
            p.drawText(hx, hy, hint)

        p.end()

    def _build_curve_path(self, ch: str,
                          px_x: int, px_y: int, w: int, h: int,
                          closed_baseline: bool = False) -> QPainterPath:
        from lumina_control.curve_editor import monotone_lut
        lut = monotone_lut(self._curves[ch])
        path = QPainterPath()
        for i, val in enumerate(lut):
            fx = px_x + i * w / 255.0
            fy = px_y + h - val / 65535.0 * h
            if i == 0:
                path.moveTo(fx, fy)
            else:
                path.lineTo(fx, fy)
        if closed_baseline:
            path.lineTo(px_x + w, px_y + h)
            path.lineTo(px_x, px_y + h)
            path.closeSubpath()
        return path

    def _draw_curve_path(self, painter: QPainter, ch: str,
                         px_x: int, px_y: int, w: int, h: int) -> None:
        painter.drawPath(self._build_curve_path(ch, px_x, px_y, w, h))

    # ── Mouse interaction ─────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        pts = self._curves[self._active]
        hit = self._hit_test(event.x(), event.y(), pts)

        if event.button() == Qt.RightButton:
            # Remove non-endpoint points on right-click
            if hit is not None and 0 < hit < len(pts) - 1:
                pts.pop(hit)
                self._drag_idx = None
                self.update()
                self.curve_changed.emit()
            return

        if event.button() == Qt.LeftButton:
            if hit is not None:
                self._drag_idx = hit
            else:
                # Insert a new point at the clicked position
                x, y = self._to_norm(event.x(), event.y())
                insert_at = len(pts)
                for j, (px, _py) in enumerate(pts):
                    if px > x:
                        insert_at = j
                        break
                pts.insert(insert_at, (x, y))
                self._drag_idx = insert_at
                self.update()
                self.curve_changed.emit()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_idx is None:
            return
        pts  = self._curves[self._active]
        x, y = self._to_norm(event.x(), event.y())
        idx  = self._drag_idx

        # Endpoints: x locked to 0/1, y locked to 0/1 (required for valid GPU ramp)
        if idx == 0:
            x = 0.0
            y = 0.0
        elif idx == len(pts) - 1:
            x = 1.0
            y = 1.0
        else:
            # Middle points: x keeps ordering, y is free — non-monotone
            # LUTs are clamped to monotone in set_device_gamma_ramp.
            x = max(pts[idx - 1][0] + 0.01, min(pts[idx + 1][0] - 0.01, x))

        pts[idx] = (x, y)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_idx is not None:
            self._drag_idx = None
            self.curve_changed.emit()


# ── Calibration dialog (tabbed: Gains RGB + Courbes) ─────────────────────────

class CalibrationDialog(QDialog):
    """Fine-tune per-monitor RGB gains (DDC-CI) and/or custom tone curves (GDI32)."""

    _CHANNELS = [
        ("R", 0x16, "SliderR"),
        ("G", 0x18, "SliderG"),
        ("B", 0x1A, "SliderB"),
    ]

    def __init__(self, monitor_handle, monitor_name: str, device_name: str,
                 sync_rgb_callback=None, curves_applied_callback=None,
                 initial_curves=None, parent=None) -> None:
        super().__init__(parent)
        self.monitor                  = monitor_handle
        self.device_name              = device_name
        self.sync_rgb_callback        = sync_rgb_callback
        self._curves_applied_callback = curves_applied_callback
        self._initial_curves          = initial_curves
        self.sync_rgb          = True
        self._syncing          = False
        self._sliders:  dict[int, QSlider] = {}
        self._labels:   dict[int, QLabel]  = {}
        self._loaded:   dict[int, int]     = {}
        self._ch_btns:  dict[str, QPushButton] = {}

        self.setWindowTitle(_("Calibrage : {}").format(monitor_name))
        self.setFixedSize(374, 510)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_rgb_tab(),    _("Gains RGB"))
        self._tabs.addTab(self._build_curves_tab(), _("Courbes"))

        # If no DDC-CI handle, curves-only mode
        if self.monitor is None:
            self._tabs.setTabEnabled(0, False)
            self._tabs.setCurrentIndex(1)

        root.addWidget(self._tabs)

        btn_ok = QPushButton(_("Fermer"))
        btn_ok.setProperty("class", "pill")
        btn_ok.clicked.connect(self.accept)
        root.addWidget(btn_ok)

        # Trigger DDC-CI unlock only when DDC is available
        if self.monitor is not None:
            QTimer.singleShot(100, self._unlock_user_mode)

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _build_rgb_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 10, 8, 8)

        info = QLabel(_("Ajustement fin des gains RGB (si supporté par l'écran)."))
        info.setWordWrap(True)
        info.setObjectName("Subtle")
        layout.addWidget(info)

        # Link / reload toolbar
        tools = QHBoxLayout()
        self.chk_link = QCheckBox(_("Lier R/G/B"))
        self.chk_link.setChecked(True)
        self.chk_link.toggled.connect(lambda v: setattr(self, "sync_rgb", v))
        btn_reload = QPushButton(_("Recharger"))
        btn_reload.setProperty("class", "pill-muted")
        btn_reload.clicked.connect(self._reload_all)
        tools.addWidget(self.chk_link)
        tools.addStretch()
        tools.addWidget(btn_reload)
        layout.addLayout(tools)

        # R / G / B sliders
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
            self._labels[code]  = val_lbl
            QTimer.singleShot(200, partial(self._load_channel, code))

        # Global gain slider
        gain_row = QHBoxLayout()
        lbl_gain = QLabel(_("Gain global"))
        lbl_gain.setObjectName("Subtle")
        self.sl_gain  = QSlider(Qt.Horizontal)
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
        return tab

    def _build_curves_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 10, 8, 8)

        # Channel selector
        ch_row = QHBoxLayout()
        lbl_ch = QLabel(_("Canal :"))
        lbl_ch.setObjectName("Subtle")
        ch_row.addWidget(lbl_ch)
        for ch in ("R", "G", "B"):
            btn = QPushButton(ch)
            btn.setCheckable(True)
            btn.setFixedSize(40, 28)
            btn.clicked.connect(partial(self._set_curve_channel, ch))
            ch_row.addWidget(btn)
            self._ch_btns[ch] = btn
        ch_row.addStretch()
        layout.addLayout(ch_row)
        self._ch_btns["R"].setChecked(True)
        self._update_ch_btn_styles("R")

        # Preset buttons
        preset_row = QHBoxLayout()
        lbl_pre = QLabel(_("Présets :"))
        lbl_pre.setObjectName("Subtle")
        preset_row.addWidget(lbl_pre)
        _PRESETS = {
            "S-Curve": [(0.0, 0.0), (0.25, 0.18), (0.75, 0.82), (1.0, 1.0)],
            "Film":    [(0.0, 0.0), (0.1, 0.12), (0.5, 0.52), (0.9, 0.88), (1.0, 1.0)],
            "γ 2.2":   [(0.0, 0.0), (0.25, 0.53), (0.5, 0.73), (0.75, 0.88), (1.0, 1.0)],
        }
        for name, pts in _PRESETS.items():
            btn_pre = QPushButton(name)
            btn_pre.setProperty("class", "pill-muted")
            btn_pre.setFixedHeight(24)
            btn_pre.clicked.connect(partial(self._apply_preset, pts))
            preset_row.addWidget(btn_pre)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # Curve editor widget
        self._curve_widget = _CurveWidget()
        # Restore saved control points if provided
        if self._initial_curves:
            for ch, saved_pts in self._initial_curves.items():
                if ch in ("R", "G", "B"):
                    self._curve_widget._curves[ch] = [tuple(p) for p in saved_pts]
            self._curve_widget.update()
        layout.addWidget(self._curve_widget, alignment=Qt.AlignCenter)

        # Reset / Apply row
        ctrl_row = QHBoxLayout()
        btn_reset = QPushButton(_("Réinitialiser"))
        btn_reset.setProperty("class", "pill-muted")
        btn_reset.clicked.connect(self._reset_curve)
        btn_apply = QPushButton(_("Appliquer la courbe"))
        btn_apply.setProperty("class", "pill")
        btn_apply.setToolTip(_(
            "Applique les courbes via GDI32 (GPU).\n"
            "Le slider Gamma et le Mode Nuit les remplaceront si vous les ajustez."
        ))
        btn_apply.clicked.connect(self._apply_curves)
        ctrl_row.addWidget(btn_reset)
        ctrl_row.addStretch()
        ctrl_row.addWidget(btn_apply)
        layout.addLayout(ctrl_row)

        # ICC export
        btn_icc = QPushButton(_("Exporter profil ICC…"))
        btn_icc.setProperty("class", "pill-muted")
        btn_icc.setToolTip(_(
            "Génère un profil ICC v2 avec ces courbes tonales.\n"
            "Reconnu par Photoshop, Lightroom, DaVinci Resolve…"
        ))
        btn_icc.clicked.connect(self._export_icc)
        layout.addWidget(btn_icc)

        layout.addStretch()
        return tab

    # ── Channel buttons ───────────────────────────────────────────────────────

    def _update_ch_btn_styles(self, active: str) -> None:
        # (r, g, b) matching _CurveWidget._CH_COL
        rgb = {"R": (210, 65, 65), "G": (65, 185, 65), "B": (65, 110, 220)}
        for ch, btn in self._ch_btns.items():
            r, g, b = rgb[ch]
            if ch == active:
                btn.setStyleSheet(
                    f"QPushButton{{"
                    f"background:rgba({r},{g},{b},52);"
                    f"border:1px solid rgba({r},{g},{b},200);"
                    f"color:rgb({r},{g},{b});"
                    f"border-radius:6px;font-weight:bold;font-size:12px;}}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton{{"
                    f"background:rgba(255,255,255,8);"
                    f"border:1px solid rgba(255,255,255,28);"
                    f"color:rgba({r},{g},{b},140);"
                    f"border-radius:6px;font-weight:bold;font-size:12px;}}"
                    f"QPushButton:hover{{"
                    f"background:rgba({r},{g},{b},18);"
                    f"border:1px solid rgba({r},{g},{b},100);"
                    f"color:rgba({r},{g},{b},200);}}"
                )

    def _set_curve_channel(self, ch: str) -> None:
        for c, btn in self._ch_btns.items():
            btn.setChecked(c == ch)
        self._update_ch_btn_styles(ch)
        self._curve_widget.set_channel(ch)

    # ── Curves actions ────────────────────────────────────────────────────────

    def _apply_preset(self, pts: list) -> None:
        """Apply a preset to all three channels and immediately apply to the GPU."""
        for ch in ("R", "G", "B"):
            self._curve_widget._curves[ch] = list(pts)
        self._curve_widget.update()
        self._curve_widget.curve_changed.emit()
        self._apply_curves()

    def _reset_curve(self) -> None:
        """Reset all channels to identity and clear the applied curves."""
        for ch in ("R", "G", "B"):
            self._curve_widget.reset_channel(ch)
        self._apply_curves()

    def _apply_curves(self) -> None:
        r   = self._curve_widget.get_lut("R")
        g   = self._curve_widget.get_lut("G")
        b   = self._curve_widget.get_lut("B")
        pts = {ch: [list(p) for p in self._curve_widget._curves[ch]]
               for ch in ("R", "G", "B")}
        if self._curves_applied_callback is not None:
            # Let MonitorCard compose curves with current gamma + warmth
            self._curves_applied_callback(r, g, b, pts)
        else:
            # Fallback: apply directly (no gamma/warmth composition)
            from lumina_control.curve_editor import set_device_gamma_ramp
            ok = set_device_gamma_ramp(self.device_name, r, g, b)
            if not ok:
                log.warning("set_device_gamma_ramp returned False for %s",
                            self.device_name)

    def _export_icc(self) -> None:
        from lumina_control.curve_editor import write_icc_profile
        default_name = "LuminaControl_profile.icc"
        title = _("Exporter profil ICC")
        path, _filt = QFileDialog.getSaveFileName(
            self,
            title,
            os.path.join(os.path.expanduser("~"), default_name),
            "ICC Profile (*.icc *.icm)",
        )
        if not path:
            return

        r = self._curve_widget.get_lut("R")
        g = self._curve_widget.get_lut("G")
        b = self._curve_widget.get_lut("B")

        if write_icc_profile(r, g, b, path):
            msg = QMessageBox(self)
            msg.setWindowTitle(_("Profil ICC exporté"))
            msg.setText(_("Profil ICC exporté :") + "\n" + path)
            msg.addButton(QMessageBox.Ok)
            btn_open = msg.addButton(_("Ouvrir"), QMessageBox.ActionRole)
            msg.exec()
            if msg.clickedButton() is btn_open:
                try:
                    os.startfile(path)
                except Exception as e:
                    log.debug("os.startfile failed: %s", e)
        else:
            QMessageBox.warning(
                self,
                _("Erreur export ICC"),
                _("L'export du profil ICC a échoué."),
            )

    # ── DDC-CI helpers ────────────────────────────────────────────────────────

    def _unlock_user_mode(self) -> None:
        try:
            with self.monitor:
                self.monitor.vcp.set_vcp_feature(0x14, 0x0B)
        except Exception as e:
            log.debug("Could not unlock user colour mode: %s", e)

    def _load_channel(self, code: int) -> None:
        sl  = self._sliders[code]
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
        self.setWindowTitle(_("Calibrage guidé"))
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

        title = QLabel(_("Calibrage guidé"))
        title.setObjectName("Title")
        layout.addWidget(title)

        self.lbl_step = QLabel()
        self.lbl_step.setObjectName("Subtle")
        layout.addWidget(self.lbl_step)

        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("Title")
        layout.addWidget(self.lbl_title)

        self.lbl_help = QLabel()
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setObjectName("Subtle")
        layout.addWidget(self.lbl_help)

        row_screen = QHBoxLayout()
        lbl_screen = QLabel(_("Écran cible"))
        lbl_screen.setObjectName("Subtle")
        self.cmb_screen = QComboBox()
        self.cmb_screen.setFixedWidth(160)
        row_screen.addWidget(lbl_screen)
        row_screen.addWidget(self.cmb_screen)
        row_screen.addStretch()
        layout.addLayout(row_screen)

        btn_show = QPushButton(_("Afficher le pattern"))
        btn_show.setProperty("class", "pill")
        btn_show.clicked.connect(self._show_pattern)
        layout.addWidget(btn_show)
        self.btn_show = btn_show

        row_nav = QHBoxLayout()
        self.btn_prev = QPushButton(_("Précédent"))
        self.btn_prev.setProperty("class", "pill-muted")
        self.btn_prev.clicked.connect(self._prev_step)
        self.btn_next = QPushButton(_("Suivant"))
        self.btn_next.setProperty("class", "pill")
        self.btn_next.clicked.connect(self._next_step)
        row_nav.addWidget(self.btn_prev)
        row_nav.addWidget(self.btn_next)
        layout.addLayout(row_nav)

        layout.addStretch()
        btn_close = QPushButton(_("Fermer"))
        btn_close.setProperty("class", "pill-muted")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _refresh_screens(self) -> None:
        self.cmb_screen.blockSignals(True)
        self.cmb_screen.clear()
        for i, _s in enumerate(QApplication.screens()):
            self.cmb_screen.addItem(_("Écran {}").format(i + 1), i)
        self.cmb_screen.blockSignals(False)
        self.btn_show.setEnabled(bool(QApplication.screens()))

    def _update_ui(self) -> None:
        step = self.STEPS[self.step_index]
        self.lbl_step.setText(_("Étape {} / {}").format(
            self.step_index + 1, len(self.STEPS)))
        self.lbl_title.setText(_(step["title"]))
        self.lbl_help.setText(_(step["help"]))
        self.btn_prev.setEnabled(self.step_index > 0)
        self.btn_next.setEnabled(self.step_index < len(self.STEPS) - 1)

    def _show_pattern(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        idx        = self.cmb_screen.currentData() or 0
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
