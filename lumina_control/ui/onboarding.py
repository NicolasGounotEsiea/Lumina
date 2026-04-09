"""First-run onboarding wizard."""
import logging

from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from lumina_control.i18n import _

log = logging.getLogger(__name__)

_STEP_COUNT = 4


class _ScanWorker(QObject):
    """Runs enumerate_monitors() on a background thread."""
    done   = Signal(list)   # list[MonitorDescriptor]
    failed = Signal(str)

    def run(self) -> None:
        try:
            from lumina_control.monitor_enumerate import enumerate_monitors
            self.done.emit(enumerate_monitors())
        except Exception as e:
            log.debug("DDC scan failed: %s", e)
            self.failed.emit(str(e))


class OnboardingDialog(QDialog):
    """Multi-step first-run wizard."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Bienvenue dans Lumina Control"))
        self.setFixedWidth(500)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_ddc())
        self._stack.addWidget(self._page_features())
        self._stack.addWidget(self._page_done())
        layout.addWidget(self._stack)

        # ── Navigation bar ────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        nav = QWidget()
        nav_l = QHBoxLayout(nav)
        nav_l.setContentsMargins(20, 12, 20, 14)
        nav_l.setSpacing(8)

        self._lbl_step = QLabel()
        self._lbl_step.setObjectName("Subtle")
        nav_l.addWidget(self._lbl_step)
        nav_l.addStretch()

        self._btn_back = QPushButton(_("Précédent"))
        self._btn_back.setProperty("class", "pill-muted")
        self._btn_back.setCursor(Qt.PointingHandCursor)
        self._btn_back.clicked.connect(self._go_back)

        self._btn_next = QPushButton(_("Suivant"))
        self._btn_next.setProperty("class", "pill")
        self._btn_next.setCursor(Qt.PointingHandCursor)
        self._btn_next.clicked.connect(self._go_next)

        nav_l.addWidget(self._btn_back)
        nav_l.addWidget(self._btn_next)
        layout.addWidget(nav)

        self._update_nav()

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _page_welcome(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 24)
        l.setSpacing(16)

        icon = QLabel("◈")
        icon.setObjectName("AccentIcon")
        icon.setStyleSheet("font-size: 52px;")
        icon.setAlignment(Qt.AlignCenter)
        l.addWidget(icon)

        title = QLabel(_("Bienvenue dans Lumina Control"))
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        l.addWidget(title)

        desc = QLabel(_(
            "Contrôlez la luminosité, le contraste et la colorimétrie "
            "de vos écrans directement depuis la barre des tâches — "
            "sans driver tiers, via le protocole DDC-CI.\n\n"
            "Cet assistant va vérifier la compatibilité de vos écrans "
            "et vous présenter les fonctionnalités clés."
        ))
        desc.setObjectName("Subtle")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        l.addWidget(desc)

        l.addStretch()
        return w

    def _page_ddc(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 28, 32, 16)
        l.setSpacing(12)

        title = QLabel(_("Détection DDC-CI"))
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        l.addWidget(title)

        intro = QLabel(_(
            "DDC-CI est le protocole qui permet de contrôler vos écrans. "
            "Il doit être activé dans le menu OSD (boutons physiques) de chaque moniteur."
        ))
        intro.setObjectName("Subtle")
        intro.setWordWrap(True)
        l.addWidget(intro)

        self._ddc_results = QLabel(_("Scan en cours…"))
        self._ddc_results.setObjectName("Subtle")
        self._ddc_results.setWordWrap(True)
        l.addWidget(self._ddc_results)

        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        l.addWidget(sep)

        self._ddc_warn = QLabel(_(
            "Si un écran est marqué indisponible :\n"
            "  1. Appuyez sur le bouton physique de votre moniteur\n"
            "  2. Cherchez « DDC/CI » dans le menu et activez-le\n"
            "  3. Rafraîchissez les écrans depuis le panneau principal"
        ))
        self._ddc_warn.setObjectName("Subtle")
        self._ddc_warn.setWordWrap(True)
        l.addWidget(self._ddc_warn)

        l.addStretch()
        return w

    def _page_features(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 28, 32, 16)
        l.setSpacing(12)

        title = QLabel(_("Fonctionnalités clés"))
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        l.addWidget(title)

        features = [
            ("☀", _("Luminosité & contraste"),
             _("Contrôlez chaque écran individuellement ou synchronisez-les en maître/esclave avec décalages relatifs.")),
            ("⚙", _("Profils par application"),
             _("Préréglage automatique dès qu'une application spécifique est au premier plan — luminosité, contraste, gamma, gains RGB.")),
            ("🎮", _("Mode Jeu"),
             _("Détection automatique du plein écran : préréglage appliqué et écritures DDC-CI suspendues pour ne pas interrompre le jeu.")),
        ]

        for icon_txt, feat_title, feat_desc in features:
            card = QFrame()
            card.setObjectName("Card")
            card_l = QHBoxLayout(card)
            card_l.setContentsMargins(14, 10, 14, 10)
            card_l.setSpacing(12)

            ic = QLabel(icon_txt)
            ic.setFixedWidth(28)
            ic.setStyleSheet("font-size: 22px;")
            ic.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

            text_l = QVBoxLayout()
            text_l.setSpacing(3)
            lbl_t = QLabel(feat_title)
            lbl_t.setObjectName("Title")
            lbl_d = QLabel(feat_desc)
            lbl_d.setObjectName("Subtle")
            lbl_d.setWordWrap(True)
            text_l.addWidget(lbl_t)
            text_l.addWidget(lbl_d)

            card_l.addWidget(ic, 0, Qt.AlignTop)
            card_l.addLayout(text_l)
            l.addWidget(card)

        l.addStretch()
        return w

    def _page_done(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 24)
        l.setSpacing(16)
        l.setAlignment(Qt.AlignCenter)

        icon = QLabel("✓")
        icon.setStyleSheet("font-size: 52px; color: #6CCB5F;")
        icon.setAlignment(Qt.AlignCenter)
        l.addWidget(icon)

        title = QLabel(_("Tout est prêt !"))
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        l.addWidget(title)

        desc = QLabel(_(
            "Lumina Control est actif dans la barre des tâches.\n"
            "Cliquez sur l'icône pour ouvrir le panneau de contrôle.\n\n"
            "Vous pouvez relancer cet assistant à tout moment depuis\n"
            "la section Paramètres du panneau."
        ))
        desc.setObjectName("Subtle")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        l.addWidget(desc)

        l.addStretch()
        return w

    # ── DDC scan (background thread) ──────────────────────────────────────────

    def _run_ddc_scan(self) -> None:
        self._ddc_results.setText(_("Scan en cours…"))
        self._ddc_warn.setVisible(False)

        self._scan_thread = QThread()
        self._scan_worker = _ScanWorker()
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.done.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.start()

    def _on_scan_done(self, descs: list) -> None:
        ddc_ok = [d for d in descs if d.ddc_handle is not None]
        ddc_no = [d for d in descs if d.ddc_handle is None]

        lines = []
        for d in ddc_ok:
            lines.append(f"  ✓  {d.label}")
        for d in ddc_no:
            lines.append(f"  ✗  {d.label}  ({_('DDC-CI indisponible')})")

        if not descs:
            self._ddc_results.setText(_("Aucun écran détecté."))
            self._ddc_warn.setVisible(True)
        else:
            header = _("{} écran(s) détecté(s) :").format(len(descs))
            self._ddc_results.setText(header + "\n" + "\n".join(lines))
            self._ddc_warn.setVisible(len(ddc_no) > 0)

    def _on_scan_failed(self, error: str) -> None:
        self._ddc_results.setText(_("Scan impossible : {}").format(error))
        self._ddc_warn.setVisible(True)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _update_nav(self) -> None:
        idx = self._stack.currentIndex()
        self._lbl_step.setText(_("Étape {} / {}").format(idx + 1, _STEP_COUNT))
        self._btn_back.setVisible(idx > 0)
        self._btn_next.setText(_("Terminer") if idx == _STEP_COUNT - 1 else _("Suivant"))

    def _go_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx < _STEP_COUNT - 1:
            self._stack.setCurrentIndex(idx + 1)
            self._update_nav()
            if idx + 1 == 1:
                QTimer.singleShot(150, self._run_ddc_scan)
        else:
            self.accept()
