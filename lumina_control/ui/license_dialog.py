"""Dialog d'activation de licence."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout,
)

from lumina_control.i18n import _
from lumina_control.license import LicenseResult, get_machine_id, store_key, verify

log = logging.getLogger(__name__)


class LicenseDialog(QDialog):
    """Affiché au démarrage si aucune licence valide n'est trouvée."""

    def __init__(self, parent=None, *, purchase_url: str = "") -> None:
        super().__init__(parent)
        self._purchase_url = purchase_url
        self._result: LicenseResult | None = None
        self._build_ui()
        self.setWindowTitle(_("Activer Lumina Control"))
        self.setFixedWidth(500)
        self.setModal(True)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )

    @property
    def license_result(self) -> LicenseResult | None:
        return self._result

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(28, 28, 28, 24)

        # En-tête
        title = QLabel(_("Lumina Control — Activation"))
        f = QFont("Segoe UI")
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        sub = QLabel(_("Entrez votre clé de licence pour activer le logiciel."))
        sub.setWordWrap(True)
        sub.setObjectName("Subtle")
        root.addWidget(sub)

        # Séparateur
        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # Champ clé de licence
        lbl_key = QLabel(_("Clé de licence"))
        lbl_key.setObjectName("Subtle")
        root.addWidget(lbl_key)

        self._txt_key = QTextEdit()
        self._txt_key.setPlaceholderText(
            _("Collez votre clé ici…\n(format : xxxxxx.yyyyyy)")
        )
        self._txt_key.setFixedHeight(76)
        self._txt_key.setAcceptRichText(False)
        self._txt_key.setLineWrapMode(QTextEdit.WidgetWidth)
        root.addWidget(self._txt_key)

        # Label d'erreur (caché par défaut)
        self._lbl_error = QLabel("")
        self._lbl_error.setStyleSheet("color: #FF6B6B; font-size: 11px;")
        self._lbl_error.setWordWrap(True)
        self._lbl_error.setVisible(False)
        root.addWidget(self._lbl_error)

        # Identifiant machine
        mid_row = QHBoxLayout()
        mid_row.setSpacing(6)
        lbl_mid = QLabel(_("Identifiant machine :"))
        lbl_mid.setObjectName("Subtle")
        lbl_mid.setStyleSheet("font-size: 10px;")
        mid_val = QLabel(get_machine_id())
        mid_val.setStyleSheet(
            "font-family: 'Cascadia Code', 'Consolas', monospace;"
            "font-size: 10px;"
            "background: rgba(255,255,255,0.06);"
            "border: 1px solid rgba(255,255,255,0.10);"
            "border-radius: 3px; padding: 2px 8px;"
        )
        mid_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        mid_val.setCursor(Qt.IBeamCursor)
        mid_row.addWidget(lbl_mid)
        mid_row.addWidget(mid_val)
        mid_row.addStretch()
        root.addLayout(mid_row)

        root.addSpacing(4)

        # Boutons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        if self._purchase_url:
            btn_buy = QPushButton(_("Acheter une licence"))
            btn_buy.setObjectName("Subtle")
            btn_buy.setCursor(Qt.PointingHandCursor)
            btn_buy.clicked.connect(self._open_purchase)
            btn_row.addWidget(btn_buy)

        btn_row.addStretch()

        self._btn_activate = QPushButton(_("Activer"))
        self._btn_activate.setObjectName("FocusToggle")
        self._btn_activate.setFixedWidth(120)
        self._btn_activate.setCursor(Qt.PointingHandCursor)
        self._btn_activate.setDefault(True)
        self._btn_activate.clicked.connect(self._on_activate)
        btn_row.addWidget(self._btn_activate)

        root.addLayout(btn_row)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_activate(self) -> None:
        key = self._txt_key.toPlainText().strip()
        if not key:
            self._show_error(_("Veuillez entrer une clé de licence."))
            return

        self._btn_activate.setText(_("Vérification…"))
        self._btn_activate.setEnabled(False)
        self._lbl_error.setVisible(False)
        self.repaint()

        result = verify(key)

        if result.valid:
            store_key(key)
            self._result = result
            log.info("Licence activée — %s (%s)", result.email, result.plan)
            self.accept()
        else:
            self._show_error(result.error or _("Clé invalide."))
            self._btn_activate.setText(_("Activer"))
            self._btn_activate.setEnabled(True)

    def _show_error(self, msg: str) -> None:
        self._lbl_error.setText(msg)
        self._lbl_error.setVisible(True)

    def _open_purchase(self) -> None:
        if self._purchase_url:
            QDesktopServices.openUrl(QUrl(self._purchase_url))
