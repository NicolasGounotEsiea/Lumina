"""Dialog for managing automatic app-based brightness/contrast/gamma profiles."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from lumina_control.app_rules import AppRule, DEFAULT_RULES
from lumina_control.config import ACCENT_COLOR, TEXT_MUTED
from lumina_control.i18n import _

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Rule row widget
# ─────────────────────────────────────────────────────────────────────────────

class _RuleRow(QFrame):
    """One row in the rules list."""

    edit_requested   = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, rule: AppRule, index: int, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self.setObjectName("RuleRow")
        self.setMinimumHeight(60)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 10, 10, 10)
        h.setSpacing(8)

        # ── Enable toggle ──────────────────────────────────────────────────
        self._chk = QCheckBox()
        self._chk.setChecked(rule.enabled)
        self._chk.setToolTip(_("Activer / désactiver"))
        h.addWidget(self._chk)

        # ── Info block ─────────────────────────────────────────────────────
        info = QVBoxLayout()
        info.setSpacing(2)

        self._lbl_name = QLabel(rule.label)
        self._lbl_name.setObjectName("RuleRowName")
        self._lbl_name.setProperty("rule-enabled", "true" if rule.enabled else "false")
        info.addWidget(self._lbl_name)

        parts = [f"<b>{rule.process}</b>"]
        if rule.window_title:
            parts.append(f"/{rule.window_title}/")
        if rule.brightness is not None:
            parts.append(_("Lum: {}%").format(rule.brightness))
        if rule.contrast is not None:
            parts.append(_("Con: {}%").format(rule.contrast))
        if rule.gamma is not None:
            parts.append(_("γ: {}").format(f"{rule.gamma:.2f}"))
        if any(v is not None for v in (rule.red, rule.green, rule.blue)):
            r = rule.red   if rule.red   is not None else "·"
            g = rule.green if rule.green is not None else "·"
            b = rule.blue  if rule.blue  is not None else "·"
            parts.append(_("RVB: {}/{}/{}").format(r, g, b))

        detail = QLabel("  ·  ".join(parts))
        detail.setObjectName("RuleRowDetail")
        detail.setTextFormat(Qt.RichText)
        info.addWidget(detail)

        h.addLayout(info, stretch=1)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_edit = QPushButton("✎")
        btn_edit.setProperty("class", "icon-btn")
        btn_edit.setFixedSize(28, 28)
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setToolTip(_("Modifier"))
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._index))
        h.addWidget(btn_edit)

        btn_del = QPushButton("✕")
        btn_del.setProperty("class", "icon-btn")
        btn_del.setProperty("danger", "true")
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setToolTip(_("Supprimer"))
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self._index))
        h.addWidget(btn_del)

    def set_enabled_visual(self, enabled: bool) -> None:
        self._lbl_name.setProperty("rule-enabled", "true" if enabled else "false")
        self._lbl_name.style().unpolish(self._lbl_name)
        self._lbl_name.style().polish(self._lbl_name)


# ─────────────────────────────────────────────────────────────────────────────
# Add / Edit form
# ─────────────────────────────────────────────────────────────────────────────

class _RuleFormDialog(QDialog):
    """Form for creating or editing a single AppRule."""

    def __init__(self, rule: AppRule | None = None, parent=None) -> None:
        super().__init__(parent)
        is_edit = rule is not None
        self.setWindowTitle(_("Modifier la règle") if is_edit else _("Nouvelle règle"))
        self.setMinimumWidth(460)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        # DO NOT set a stylesheet here — inherit from the app global stylesheet

        self._result: AppRule | None = None
        self._running_apps: list[tuple[str, str]] = []  # (exe, title)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── Current foreground process indicator ──────────────────────────
        from lumina_control.utils import get_foreground_process
        current_proc = get_foreground_process()
        if current_proc:
            row_cur = QHBoxLayout()
            row_cur.setSpacing(6)
            lbl_cur_prefix = QLabel(_("Actif maintenant :"))
            lbl_cur_prefix.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
            lbl_cur = QLabel(current_proc)
            lbl_cur.setStyleSheet(
                f"font-size:11px; color:{ACCENT_COLOR}; font-weight:600;"
                f" background:rgba(96,205,255,0.10); border-radius:4px; padding:2px 6px;"
            )
            btn_use = QPushButton(_("Utiliser"))
            btn_use.setProperty("class", "pill")
            btn_use.setFixedHeight(24)
            btn_use.setCursor(Qt.PointingHandCursor)
            btn_use.clicked.connect(lambda: (
                self._inp_proc.setText(current_proc),
                self._inp_label.setFocus(),
            ))
            row_cur.addWidget(lbl_cur_prefix)
            row_cur.addWidget(lbl_cur)
            row_cur.addStretch()
            row_cur.addWidget(btn_use)
            layout.addLayout(row_cur)

        # ── Application picker ─────────────────────────────────────────────
        layout.addWidget(self._muted_label(_("Applications en cours d'exécution")))

        row_pick = QHBoxLayout()
        row_pick.setSpacing(6)
        self._cmb_apps = QComboBox()
        self._cmb_apps.addItem(_("— choisir une app —"), None)
        self._cmb_apps.currentIndexChanged.connect(self._on_app_selected)
        row_pick.addWidget(self._cmb_apps, stretch=1)

        btn_refresh = QPushButton("↻")
        btn_refresh.setProperty("class", "icon-btn")
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.setToolTip(_("Actualiser la liste des applications"))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self._refresh_apps)
        row_pick.addWidget(btn_refresh)
        layout.addLayout(row_pick)

        # ── Manual exe entry ───────────────────────────────────────────────
        layout.addWidget(self._muted_label(_("Nom de l'exécutable (ex: vlc.exe)")))
        self._inp_proc = QLineEdit(rule.process if rule else "")
        self._inp_proc.setPlaceholderText(_("ex. vlc.exe"))
        layout.addWidget(self._inp_proc)

        # ── Display label ──────────────────────────────────────────────────
        layout.addWidget(self._muted_label(_("Nom affiché")))
        self._inp_label = QLineEdit(rule.label if rule else "")
        self._inp_label.setPlaceholderText(_("ex. VLC, Zoom, Photoshop…"))
        layout.addWidget(self._inp_label)

        # ── Window title filter (optional regex) ───────────────────────────
        layout.addWidget(self._muted_label(_("Filtre sur le titre de fenêtre (regex, optionnel)")))
        self._inp_title = QLineEdit(
            rule.window_title if (rule and rule.window_title) else ""
        )
        self._inp_title.setPlaceholderText(_("ex. Lecture en cours|Playing  — vide = toute fenêtre"))
        layout.addWidget(self._inp_title)

        sep = self._make_sep()
        layout.addWidget(sep)

        # ── Brightness ────────────────────────────────────────────────────
        bri_val = rule.brightness if (rule and rule.brightness is not None) else 50
        self._sl_bri, self._lbl_bri, self._chk_skip_bri = self._make_slider_row(
            layout, _("Luminosité"), bri_val, 0, 100, "%",
            skip=(rule.brightness is None if rule else False),
        )

        # ── Contrast ──────────────────────────────────────────────────────
        con_val = rule.contrast if (rule and rule.contrast is not None) else 50
        self._sl_con, self._lbl_con, self._chk_skip_con = self._make_slider_row(
            layout, _("Contraste"), con_val, 0, 100, "%",
            skip=(rule.contrast is None if rule else True),
        )

        # ── Gamma ─────────────────────────────────────────────────────────
        gam_val = int(round((rule.gamma if (rule and rule.gamma is not None) else 1.0) * 100))
        self._sl_gam, self._lbl_gam, self._chk_skip_gam = self._make_slider_row(
            layout, _("Gamma GPU"), gam_val, 50, 200, "",
            skip=(rule.gamma is None if rule else True),
            fmt_fn=lambda v: f"{v/100:.2f}",
        )

        layout.addWidget(self._make_sep())

        # ── RGB Gains (colorimetry) ────────────────────────────────────────
        lbl_rgb_hdr = QLabel(_("Colorimétrie  —  Gains RVB"))
        lbl_rgb_hdr.setStyleSheet("font-size:12px; font-weight:600;")
        layout.addWidget(lbl_rgb_hdr)

        lbl_rgb_info = QLabel(_(
            "Ajuste les canaux R/V/B indépendamment via DDC-CI  "
            "(nécessite le support Gains utilisateur sur le moniteur)."
        ))
        lbl_rgb_info.setWordWrap(True)
        lbl_rgb_info.setStyleSheet(f"font-size:10px; color:{TEXT_MUTED};")
        layout.addWidget(lbl_rgb_info)

        # Single "Ne pas modifier" toggle for the whole RGB section
        has_rgb = rule is not None and any(
            v is not None for v in (rule.red, rule.green, rule.blue)
        )
        self._chk_skip_rgb = QCheckBox(_("Ne pas modifier les gains RVB"))
        self._chk_skip_rgb.setChecked(not has_rgb)
        self._chk_skip_rgb.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        layout.addWidget(self._chk_skip_rgb)

        # RGB slider container (shown/hidden by checkbox)
        self._rgb_container = QWidget()
        rgb_l = QVBoxLayout(self._rgb_container)
        rgb_l.setContentsMargins(0, 0, 0, 0)
        rgb_l.setSpacing(4)

        r_val = rule.red   if (rule and rule.red   is not None) else 100
        g_val = rule.green if (rule and rule.green is not None) else 100
        b_val = rule.blue  if (rule and rule.blue  is not None) else 100

        self._sl_r, self._lbl_r = self._make_rgb_slider(rgb_l, _("Rouge"), r_val, "#FF6060")
        self._sl_g, self._lbl_g = self._make_rgb_slider(rgb_l, _("Vert"),  g_val, "#60D060")
        self._sl_b, self._lbl_b = self._make_rgb_slider(rgb_l, _("Bleu"),  b_val, "#60CDFF")

        # Live preview swatch
        preview_row = QHBoxLayout()
        preview_row.setSpacing(8)
        lbl_prev = QLabel(_("Aperçu :"))
        lbl_prev.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        self._swatch = QLabel()
        self._swatch.setFixedSize(48, 18)
        self._swatch.setStyleSheet("border-radius:4px;")
        preview_row.addWidget(lbl_prev)
        preview_row.addWidget(self._swatch)
        preview_row.addStretch()
        rgb_l.addLayout(preview_row)

        layout.addWidget(self._rgb_container)
        self._rgb_container.setVisible(has_rgb)

        def _on_rgb_toggle(skip: bool) -> None:
            self._rgb_container.setVisible(not skip)
            self.adjustSize()

        self._chk_skip_rgb.toggled.connect(_on_rgb_toggle)
        # Connect sliders to update swatch
        for sl in (self._sl_r, self._sl_g, self._sl_b):
            sl.valueChanged.connect(self._update_swatch)
        self._update_swatch()

        layout.addWidget(self._make_sep())

        # ── Save / Cancel ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton(_("Annuler"))
        btn_cancel.setProperty("class", "pill-muted")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton(_("Enregistrer"))
        btn_save.setProperty("class", "pill")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        # Populate running apps
        self._refresh_apps()

        # Pre-select existing process in combo if editing
        if rule:
            for i in range(self._cmb_apps.count()):
                if self._cmb_apps.itemData(i) == rule.process:
                    self._cmb_apps.blockSignals(True)
                    self._cmb_apps.setCurrentIndex(i)
                    self._cmb_apps.blockSignals(False)
                    break

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _muted_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        return lbl

    @staticmethod
    def _make_sep() -> QFrame:
        w = QFrame()
        w.setObjectName("Separator")
        w.setFrameShape(QFrame.HLine)
        return w

    def _make_slider_row(
        self, layout: QVBoxLayout, label: str,
        init: int, lo: int, hi: int, unit: str,
        skip: bool = False,
        fmt_fn=None,
    ) -> tuple[QSlider, QLabel, QCheckBox]:
        fmt = fmt_fn or (lambda v: f"{v}{unit}")

        row = QHBoxLayout()
        row.setSpacing(8)
        lbl_title = QLabel(label)
        lbl_title.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED};")
        lbl_title.setFixedWidth(90)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(init)
        sl.setEnabled(not skip)
        val_lbl = QLabel(fmt(init))
        val_lbl.setObjectName("ValueBadge")
        val_lbl.setFixedWidth(38)
        val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sl.valueChanged.connect(lambda v, lbl=val_lbl, f=fmt: lbl.setText(f(v)))
        row.addWidget(lbl_title)
        row.addWidget(sl)
        row.addWidget(val_lbl)
        layout.addLayout(row)

        chk = QCheckBox(_("Ne pas modifier"))
        chk.setChecked(skip)
        chk.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        chk.toggled.connect(lambda v, s=sl, lbl=val_lbl: (
            s.setEnabled(not v),
            lbl.setStyleSheet("" if not v else f"color:{TEXT_MUTED}; font-size:12px;")
        ))
        layout.addWidget(chk)
        return sl, val_lbl, chk

    def _make_rgb_slider(
        self, layout: QVBoxLayout, label: str, init: int, color: str
    ) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl_title = QLabel(label)
        lbl_title.setStyleSheet(
            f"font-size:12px; color:{color}; font-weight:600;"
        )
        lbl_title.setFixedWidth(50)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(0, 100)
        sl.setValue(init)
        sl.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;border-radius:2px;"
            f"background:{color}22;}}"
            f"QSlider::sub-page:horizontal{{background:{color};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-5px 0;"
            f"border-radius:7px;background:{color};}}"
        )
        val_lbl = QLabel(str(init))
        val_lbl.setStyleSheet(f"font-size:12px; color:{color}; font-weight:600;")
        val_lbl.setFixedWidth(30)
        val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sl.valueChanged.connect(lambda v, lbl=val_lbl: lbl.setText(str(v)))
        row.addWidget(lbl_title)
        row.addWidget(sl)
        row.addWidget(val_lbl)
        layout.addLayout(row)
        return sl, val_lbl

    def _update_swatch(self) -> None:
        if not hasattr(self, "_swatch"):
            return
        r = int(self._sl_r.value() * 2.55)
        g = int(self._sl_g.value() * 2.55)
        b = int(self._sl_b.value() * 2.55)
        self._swatch.setStyleSheet(
            f"background: rgb({r},{g},{b}); border-radius:4px;"
            f" border:1px solid #484848;"
        )

    # ── Running apps ──────────────────────────────────────────────────────────

    def _refresh_apps(self) -> None:
        from lumina_control.utils import get_user_processes
        self._running_apps = get_user_processes()
        proc_current = self._inp_proc.text().strip().lower()
        self._cmb_apps.blockSignals(True)
        self._cmb_apps.clear()
        self._cmb_apps.addItem(_("— choisir une app —"), None)
        selected_idx = 0
        for i, (exe, title) in enumerate(self._running_apps, start=1):
            self._cmb_apps.addItem(f"{title}  ({exe})", exe)
            if exe == proc_current:
                selected_idx = i
        self._cmb_apps.setCurrentIndex(selected_idx)
        self._cmb_apps.blockSignals(False)

    def _on_app_selected(self, combo_idx: int) -> None:
        exe = self._cmb_apps.itemData(combo_idx)
        if not exe:
            return
        self._inp_proc.setText(exe)
        if not self._inp_label.text():
            # Use window title as default label (strip long suffixes)
            for e, title in self._running_apps:
                if e == exe:
                    # Use first part of title (before " - ")
                    self._inp_label.setText(title.split(" - ")[0].strip()[:40])
                    break

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        proc  = self._inp_proc.text().strip().lower()
        label = self._inp_label.text().strip() or proc
        if not proc:
            self._inp_proc.setFocus()
            return
        bri = None if self._chk_skip_bri.isChecked() else self._sl_bri.value()
        con = None if self._chk_skip_con.isChecked() else self._sl_con.value()
        gam = None if self._chk_skip_gam.isChecked() else round(self._sl_gam.value() / 100, 2)
        skip_rgb = self._chk_skip_rgb.isChecked()
        red   = None if skip_rgb else self._sl_r.value()
        green = None if skip_rgb else self._sl_g.value()
        blue  = None if skip_rgb else self._sl_b.value()
        wt = self._inp_title.text().strip() or None
        self._result = AppRule(
            process=proc, label=label,
            brightness=bri, contrast=con, gamma=gam,
            red=red, green=green, blue=blue,
            enabled=True,
            window_title=wt,
        )
        self.accept()

    def result_rule(self) -> AppRule | None:
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# Main management dialog
# ─────────────────────────────────────────────────────────────────────────────

class AppRulesDialog(QDialog):
    """Full rule manager — shows list, allows add/edit/delete."""

    rules_changed = Signal(list)  # list[AppRule]

    def __init__(self, rules: list[AppRule], detection_active: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Profils par application"))
        self.setMinimumSize(520, 580)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        # DO NOT set inline stylesheet — inherit from global app stylesheet

        self._rules: list[AppRule] = list(rules)
        self._detection_active = detection_active

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr_l = QVBoxLayout(hdr)
        hdr_l.setContentsMargins(18, 16, 18, 10)
        hdr_l.setSpacing(3)

        t = QLabel(_("Profils automatiques par application"))
        t.setObjectName("AppTitle")
        sub = QLabel(
            _(
                "Détection automatique toutes les 500 ms · "
                "Les réglages sont restaurés dès que vous quittez l'application."
            )
        )
        sub.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        sub.setWordWrap(True)
        hdr_l.addWidget(t)
        hdr_l.addWidget(sub)

        # Detection status / warning banner
        if not detection_active:
            warn = QLabel("⚠  " + _("Détection inactive — activez les profils dans la fenêtre principale."))
            warn.setWordWrap(True)
            warn.setStyleSheet(
                "font-size:11px; color:#F0A000;"
                " background:rgba(240,160,0,0.12); border-radius:6px; padding:6px 8px;"
            )
            hdr_l.addWidget(warn)
        else:
            # Show currently detected foreground process
            from lumina_control.utils import get_foreground_process
            current_proc = get_foreground_process()
            proc_row = QHBoxLayout()
            proc_row.setSpacing(6)
            lbl_proc_prefix = QLabel(_("App en focus :"))
            lbl_proc_prefix.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
            lbl_proc_val = QLabel(current_proc or "—")
            lbl_proc_val.setStyleSheet(
                f"font-size:11px; color:{ACCENT_COLOR}; font-weight:600;"
            )
            proc_row.addWidget(lbl_proc_prefix)
            proc_row.addWidget(lbl_proc_val)
            proc_row.addStretch()
            hdr_l.addLayout(proc_row)

        layout.addWidget(hdr)

        layout.addWidget(self._sep())

        # ── Scrollable list ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._list_w = QWidget()
        self._list_l = QVBoxLayout(self._list_w)
        self._list_l.setContentsMargins(14, 12, 14, 12)
        self._list_l.setSpacing(6)
        self._list_l.addStretch()
        scroll.setWidget(self._list_w)
        layout.addWidget(scroll, stretch=1)

        layout.addWidget(self._sep())

        # ── Footer ────────────────────────────────────────────────────────
        foot = QWidget()
        foot_l = QHBoxLayout(foot)
        foot_l.setContentsMargins(14, 10, 14, 14)
        foot_l.setSpacing(8)

        btn_add = QPushButton("+ " + _("Ajouter une règle"))
        btn_add.setProperty("class", "pill")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._add_rule)

        btn_reset = QPushButton(_("Rétablir les défauts"))
        btn_reset.setProperty("class", "pill-muted")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_defaults)

        btn_close = QPushButton(_("Fermer"))
        btn_close.setProperty("class", "pill-muted")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)

        foot_l.addWidget(btn_add)
        foot_l.addWidget(btn_reset)
        foot_l.addStretch()
        foot_l.addWidget(btn_close)
        layout.addWidget(foot)

        self._rebuild_list()

    # ── List helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _sep() -> QFrame:
        w = QFrame()
        w.setObjectName("Separator")
        w.setFrameShape(QFrame.HLine)
        return w

    def _rebuild_list(self) -> None:
        while self._list_l.count() > 1:
            item = self._list_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._rules:
            empty = QLabel(_("Aucun profil configuré.\nCliquez sur  +  pour ajouter."))
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; padding:24px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_l.insertWidget(0, empty)
            return

        for i, rule in enumerate(self._rules):
            row = _RuleRow(rule, i)
            row._chk.toggled.connect(
                lambda checked, idx=i: self._toggle_enable(idx, checked)
            )
            row.edit_requested.connect(self._edit_rule)
            row.delete_requested.connect(self._delete_rule)
            self._list_l.insertWidget(self._list_l.count() - 1, row)

    def _toggle_enable(self, idx: int, enabled: bool) -> None:
        if 0 <= idx < len(self._rules):
            self._rules[idx].enabled = enabled
            self.rules_changed.emit(list(self._rules))

    def _add_rule(self) -> None:
        dlg = _RuleFormDialog(parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.result_rule():
            self._rules.append(dlg.result_rule())
            self._rebuild_list()
            self.rules_changed.emit(list(self._rules))

    def _edit_rule(self, idx: int) -> None:
        if not (0 <= idx < len(self._rules)):
            return
        dlg = _RuleFormDialog(rule=self._rules[idx], parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.result_rule():
            updated = dlg.result_rule()
            updated.enabled = self._rules[idx].enabled
            self._rules[idx] = updated
            self._rebuild_list()
            self.rules_changed.emit(list(self._rules))

    def _delete_rule(self, idx: int) -> None:
        if 0 <= idx < len(self._rules):
            self._rules.pop(idx)
            self._rebuild_list()
            self.rules_changed.emit(list(self._rules))

    def _reset_defaults(self) -> None:
        self._rules = list(DEFAULT_RULES)
        self._rebuild_list()
        self.rules_changed.emit(list(self._rules))
