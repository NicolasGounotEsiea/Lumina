"""Dialog for managing time-based schedule automation."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from lumina_control.config import TEXT_MUTED
from lumina_control.i18n import _
from lumina_control.schedules import Schedule

log = logging.getLogger(__name__)

_DAY_KEYS = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]


# ─────────────────────────────────────────────────────────────────────────────
# Add / Edit form
# ─────────────────────────────────────────────────────────────────────────────

class _ScheduleFormDialog(QDialog):
    """Form for creating or editing a single Schedule."""

    def __init__(
        self,
        named_profiles: list[str],
        schedule: Schedule | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        is_edit = schedule is not None
        self.setWindowTitle(_("Modifier la plage") if is_edit else _("Nouvelle plage horaire"))
        self.setMinimumWidth(420)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._result: Schedule | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── Name ──────────────────────────────────────────────────────────────
        layout.addWidget(self._muted(_("Nom de la plage")))
        self._inp_name = QLineEdit(schedule.name if schedule else "")
        self._inp_name.setPlaceholderText(_("ex. Soirée cinéma, Travail, Nuit…"))
        layout.addWidget(self._inp_name)

        # ── Profile picker ────────────────────────────────────────────────────
        layout.addWidget(self._muted(_("Profil à appliquer")))
        self._cmb_profile = QComboBox()
        if not named_profiles:
            self._cmb_profile.addItem(_("— aucun profil nommé —"), None)
        else:
            for p in named_profiles:
                self._cmb_profile.addItem(p, p)
        if schedule and schedule.profile:
            for i in range(self._cmb_profile.count()):
                if self._cmb_profile.itemData(i) == schedule.profile:
                    self._cmb_profile.setCurrentIndex(i)
                    break
        layout.addWidget(self._cmb_profile)

        # ── Time range ────────────────────────────────────────────────────────
        layout.addWidget(self._muted(_("Plage horaire  (ex. 22h → 7h passe minuit)")))
        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        lbl_from = QLabel(_("De"))
        lbl_from.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED};")
        self._spin_start = QSpinBox()
        self._spin_start.setRange(0, 23)
        self._spin_start.setSuffix("h")
        self._spin_start.setValue(schedule.start_hour if schedule else 22)
        lbl_to = QLabel(_("à"))
        lbl_to.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED};")
        self._spin_end = QSpinBox()
        self._spin_end.setRange(0, 23)
        self._spin_end.setSuffix("h")
        self._spin_end.setValue(schedule.end_hour if schedule else 7)
        time_row.addWidget(lbl_from)
        time_row.addWidget(self._spin_start)
        time_row.addWidget(lbl_to)
        time_row.addWidget(self._spin_end)
        time_row.addStretch()
        layout.addLayout(time_row)

        # ── Days of week ──────────────────────────────────────────────────────
        layout.addWidget(self._muted(_("Jours actifs")))
        days_row = QHBoxLayout()
        days_row.setSpacing(4)
        active_days = set(schedule.days if schedule else range(7))
        self._day_checks: list[QCheckBox] = []
        for i, key in enumerate(_DAY_KEYS):
            chk = QCheckBox(_(key))
            chk.setChecked(i in active_days)
            days_row.addWidget(chk)
            self._day_checks.append(chk)
        layout.addLayout(days_row)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # ── Buttons ───────────────────────────────────────────────────────────
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

    @staticmethod
    def _muted(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        return lbl

    def _save(self) -> None:
        name = self._inp_name.text().strip()
        if not name:
            self._inp_name.setFocus()
            return
        profile = self._cmb_profile.currentData()
        if not profile:
            return
        days = [i for i, chk in enumerate(self._day_checks) if chk.isChecked()]
        if not days:
            days = list(range(7))
        self._result = Schedule(
            name=name,
            profile=profile,
            start_hour=self._spin_start.value(),
            end_hour=self._spin_end.value(),
            days=days,
            enabled=True,
        )
        self.accept()

    def result_schedule(self) -> Schedule | None:
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# Main management dialog
# ─────────────────────────────────────────────────────────────────────────────

class SchedulesDialog(QDialog):
    """CRUD manager for time-based schedules."""

    schedules_changed = Signal(list)  # list[Schedule]

    def __init__(
        self,
        schedules: list[Schedule],
        named_profiles: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Planification horaire"))
        self.setMinimumSize(500, 460)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        self._schedules: list[Schedule] = list(schedules)
        self._named_profiles = named_profiles

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr_l = QVBoxLayout(hdr)
        hdr_l.setContentsMargins(18, 16, 18, 10)
        hdr_l.setSpacing(4)
        t = QLabel(_("Planification horaire"))
        t.setObjectName("AppTitle")
        sub = QLabel(_(
            "Applique automatiquement un profil nommé pendant une plage horaire. "
            "Si plusieurs plages sont actives en même temps, "
            "la première de la liste s'applique."
        ))
        sub.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        sub.setWordWrap(True)
        hdr_l.addWidget(t)
        hdr_l.addWidget(sub)
        layout.addWidget(hdr)

        layout.addWidget(self._sep())

        # ── Scrollable list ───────────────────────────────────────────────────
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

        # ── Footer ────────────────────────────────────────────────────────────
        foot = QWidget()
        foot_l = QHBoxLayout(foot)
        foot_l.setContentsMargins(14, 10, 14, 14)
        foot_l.setSpacing(8)
        btn_add = QPushButton("+ " + _("Ajouter une plage"))
        btn_add.setProperty("class", "pill")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._add_schedule)
        btn_close = QPushButton(_("Fermer"))
        btn_close.setProperty("class", "pill-muted")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        foot_l.addWidget(btn_add)
        foot_l.addStretch()
        foot_l.addWidget(btn_close)
        layout.addWidget(foot)

        self._rebuild_list()

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

        if not self._schedules:
            empty = QLabel(_("Aucune plage configurée.\nCliquez sur  +  pour ajouter."))
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; padding:24px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_l.insertWidget(0, empty)
            return

        for i, sched in enumerate(self._schedules):
            row = self._make_row(sched, i)
            self._list_l.insertWidget(self._list_l.count() - 1, row)

    def _make_row(self, sched: Schedule, idx: int) -> QFrame:
        row = QFrame()
        row.setObjectName("RuleRow")
        row.setMinimumHeight(56)
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(8)

        chk = QCheckBox()
        chk.setChecked(sched.enabled)
        chk.toggled.connect(lambda v, i=idx: self._toggle_enable(i, v))
        h.addWidget(chk)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(sched.name)
        name_lbl.setObjectName("RuleRowName")

        day_abbr = [_d for _d in (_("Lu"), _("Ma"), _("Me"), _("Je"),
                                   _("Ve"), _("Sa"), _("Di"))]
        if len(sched.days) == 7:
            days_str = _("tous les jours")
        else:
            days_str = "".join(day_abbr[_d] for _d in sorted(sched.days))

        detail_lbl = QLabel(
            f"{sched.start_hour:02d}h → {sched.end_hour:02d}h"
            f"  ·  {sched.profile}  ·  {days_str}"
        )
        detail_lbl.setObjectName("RuleRowDetail")
        info.addWidget(name_lbl)
        info.addWidget(detail_lbl)
        h.addLayout(info, stretch=1)

        btn_edit = QPushButton("✎")
        btn_edit.setProperty("class", "icon-btn")
        btn_edit.setFixedSize(28, 28)
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(lambda _c, i=idx: self._edit_schedule(i))
        h.addWidget(btn_edit)

        btn_del = QPushButton("✕")
        btn_del.setProperty("class", "icon-btn")
        btn_del.setProperty("danger", "true")
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(lambda _c, i=idx: self._delete_schedule(i))
        h.addWidget(btn_del)
        return row

    def _toggle_enable(self, idx: int, enabled: bool) -> None:
        if 0 <= idx < len(self._schedules):
            self._schedules[idx].enabled = enabled
            self.schedules_changed.emit(list(self._schedules))

    def _add_schedule(self) -> None:
        dlg = _ScheduleFormDialog(self._named_profiles, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.result_schedule():
            self._schedules.append(dlg.result_schedule())
            self._rebuild_list()
            self.schedules_changed.emit(list(self._schedules))

    def _edit_schedule(self, idx: int) -> None:
        if not (0 <= idx < len(self._schedules)):
            return
        dlg = _ScheduleFormDialog(
            self._named_profiles, schedule=self._schedules[idx], parent=self
        )
        if dlg.exec() == QDialog.Accepted and dlg.result_schedule():
            updated = dlg.result_schedule()
            updated.enabled = self._schedules[idx].enabled
            self._schedules[idx] = updated
            self._rebuild_list()
            self.schedules_changed.emit(list(self._schedules))

    def _delete_schedule(self, idx: int) -> None:
        if 0 <= idx < len(self._schedules):
            self._schedules.pop(idx)
            self._rebuild_list()
            self.schedules_changed.emit(list(self._schedules))
