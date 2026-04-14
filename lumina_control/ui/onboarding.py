"""First-run onboarding wizard."""
import logging
from typing import Callable

from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from lumina_control.config import ACCENT_COLOR, TEXT_MUTED
from lumina_control.i18n import _

log = logging.getLogger(__name__)

_STEP_COUNT = 5


class _ScanWorker(QObject):
    """Runs enumerate_monitors() on a background thread."""
    done   = Signal(list)   # list[MonitorDescriptor]
    failed = Signal(str)

    def run(self) -> None:
        try:
            from lumina_control.monitor_enumerate import enumerate_monitors
            self.done.emit(enumerate_monitors())
        except Exception as exc:
            log.debug("DDC scan failed: %s", exc)
            self.failed.emit(str(exc))


class OnboardingDialog(QDialog):
    """Multi-step first-run wizard.

    Parameters
    ----------
    apply_demo:
        Optional callback — called when the user clicks "Appliquer le profil Soirée".
        Should apply 45 % brightness + warm tint on the real monitors.
    restore_demo:
        Optional callback — called when the user clicks "Restaurer" or closes the dialog
        while the demo is active.
    """

    def __init__(
        self,
        parent=None,
        apply_demo: Callable | None = None,
        restore_demo: Callable | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Bienvenue dans Lumina Control"))
        self.setFixedWidth(520)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._apply_demo   = apply_demo
        self._restore_demo = restore_demo
        self._demo_active  = False
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_ddc())
        self._stack.addWidget(self._page_screen_control())
        self._stack.addWidget(self._page_advanced())
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

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _feature_card(self, icon: str, title: str, desc: str) -> QFrame:
        """Return a styled card widget for a feature entry."""
        card = QFrame()
        card.setObjectName("Card")
        card_l = QHBoxLayout(card)
        card_l.setContentsMargins(14, 10, 14, 10)
        card_l.setSpacing(12)

        ic = QLabel(icon)
        ic.setFixedWidth(28)
        ic.setStyleSheet("font-size: 20px;")
        ic.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        text_l = QVBoxLayout()
        text_l.setSpacing(3)
        lbl_t = QLabel(title)
        lbl_t.setObjectName("Title")
        lbl_d = QLabel(desc)
        lbl_d.setObjectName("Subtle")
        lbl_d.setWordWrap(True)
        text_l.addWidget(lbl_t)
        text_l.addWidget(lbl_d)

        card_l.addWidget(ic, 0, Qt.AlignTop)
        card_l.addLayout(text_l)
        return card

    def _scrollable_page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        """Return (page_widget, inner_layout) with a scroll area pre-configured."""
        page = QWidget()
        page_l = QVBoxLayout(page)
        page_l.setContentsMargins(0, 0, 0, 0)
        page_l.setSpacing(0)

        # Fixed header (no scroll)
        hdr = QWidget()
        hdr_l = QVBoxLayout(hdr)
        hdr_l.setContentsMargins(32, 24, 32, 12)
        hdr_l.setSpacing(6)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 16px; font-weight: 700;")
        hdr_l.addWidget(lbl_t)
        lbl_s = QLabel(subtitle)
        lbl_s.setObjectName("Subtle")
        lbl_s.setWordWrap(True)
        hdr_l.addWidget(lbl_s)
        page_l.addWidget(hdr)

        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        page_l.addWidget(sep)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setContentsMargins(32, 16, 32, 20)
        inner_l.setSpacing(10)
        scroll.setWidget(inner)
        page_l.addWidget(scroll)

        return page, inner_l

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _page_welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 40, 40, 24)
        lay.setSpacing(16)

        icon = QLabel("◈")
        icon.setObjectName("AccentIcon")
        icon.setStyleSheet("font-size: 52px;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        title = QLabel(_("Bienvenue dans Lumina Control"))
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

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
        lay.addWidget(desc)

        # Quick summary pills
        pills_w = QWidget()
        pills_l = QHBoxLayout(pills_w)
        pills_l.setContentsMargins(0, 8, 0, 0)
        pills_l.setSpacing(8)
        pills_l.setAlignment(Qt.AlignCenter)
        for txt in [_("🖥  Multi-écrans"), _("🎮  Mode Jeu"), _("🌙  Mode Nuit")]:
            p = QLabel(txt)
            p.setObjectName("ValueBadge")
            p.setAlignment(Qt.AlignCenter)
            p.setStyleSheet(
                "padding: 4px 12px; border-radius: 12px;"
                "font-size: 12px; font-weight: 600;"
            )
            pills_l.addWidget(p)
        lay.addWidget(pills_w)

        lay.addStretch()
        return w

    def _page_ddc(self) -> QWidget:
        """Page 2 — DDC scan + monitor list + interactive 'Soirée' demo."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 28, 32, 16)
        lay.setSpacing(12)

        title = QLabel(_("Vos écrans, en un coup d'œil"))
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay.addWidget(title)

        intro = QLabel(_(
            "Lumina Control détecte vos moniteurs et leur position. "
            "DDC-CI doit être activé dans le menu OSD (boutons physiques) de chaque écran."
        ))
        intro.setObjectName("Subtle")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        # Scan results area
        self._ddc_results = QLabel(_("Scan en cours…"))
        self._ddc_results.setObjectName("Subtle")
        self._ddc_results.setWordWrap(True)
        lay.addWidget(self._ddc_results)

        sep = QFrame()
        sep.setObjectName("Separator")
        sep.setFrameShape(QFrame.HLine)
        lay.addWidget(sep)

        # ── Interactive demo card ─────────────────────────────────────────────
        if self._apply_demo:
            demo = QFrame()
            demo.setObjectName("Card")
            demo_l = QHBoxLayout(demo)
            demo_l.setContentsMargins(14, 12, 14, 12)
            demo_l.setSpacing(12)

            icon_lbl = QLabel("🌆")
            icon_lbl.setFixedWidth(32)
            icon_lbl.setStyleSheet("font-size: 22px;")
            icon_lbl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

            text_v = QVBoxLayout()
            text_v.setSpacing(3)
            demo_title = QLabel(_("Voyez la différence en direct"))
            demo_title.setObjectName("Title")
            demo_desc = QLabel(_(
                "45 % de luminosité + teinte chaude — "
                "Lumina Control agit sur vos écrans en 2 secondes."
            ))
            demo_desc.setObjectName("Subtle")
            demo_desc.setWordWrap(True)
            text_v.addWidget(demo_title)
            text_v.addWidget(demo_desc)

            self._btn_demo = QPushButton(_("Appliquer"))
            self._btn_demo.setProperty("class", "pill")
            self._btn_demo.setFixedWidth(100)
            self._btn_demo.setCursor(Qt.PointingHandCursor)
            self._btn_demo.clicked.connect(self._toggle_demo)

            demo_l.addWidget(icon_lbl, 0, Qt.AlignTop)
            demo_l.addLayout(text_v, stretch=1)
            demo_l.addWidget(self._btn_demo, 0, Qt.AlignVCenter)
            lay.addWidget(demo)

        sep2 = QFrame()
        sep2.setObjectName("Separator")
        sep2.setFrameShape(QFrame.HLine)
        lay.addWidget(sep2)

        self._ddc_warn = QLabel(_(
            "Si un écran est marqué indisponible :\n"
            "  1. Appuyez sur le bouton physique de votre moniteur\n"
            "  2. Cherchez « DDC/CI » dans le menu et activez-le\n"
            "  3. Rafraîchissez les écrans depuis le panneau principal"
        ))
        self._ddc_warn.setObjectName("Subtle")
        self._ddc_warn.setWordWrap(True)
        lay.addWidget(self._ddc_warn)

        tip = QLabel(_(
            "💡  Vous pouvez relancer ce scan à tout moment via le bouton ↻ "
            "en haut du panneau principal."
        ))
        tip.setObjectName("Subtle")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        lay.addStretch()
        return w

    def _page_screen_control(self) -> QWidget:
        page, inner = self._scrollable_page(
            _("Contrôle des écrans"),
            _("Les réglages s'appliquent en temps réel via DDC-CI — sans logiciel de pilote tiers."),
        )
        features = [
            ("☀", _("Luminosité & contraste globaux"),
             _("Un slider unique ajuste tous vos écrans en même temps. "
               "Les préréglages Jour (80 %) et Nuit (25 %) sont accessibles en un clic.")),
            ("🔗", _("Synchronisation maître / esclave"),
             _("Liez vos écrans : le maître pilote les autres en absolu ou avec un décalage fixe "
               "(ex. écran secondaire toujours 10 % moins lumineux).")),
            ("🎯", _("Mode Focus"),
             _("L'écran actif reste à pleine luminosité ; les autres sont atténués du niveau "
               "que vous choisissez. Utile pour se concentrer sur une seule fenêtre.")),
            ("🌙", _("Mode Nuit"),
             _("Applique une teinte chaude (GPU) sur tous vos écrans pour réduire la lumière bleue "
               "en soirée. Intensité réglable de 0 à 100 %.")),
        ]
        for icon, feat_title, feat_desc in features:
            inner.addWidget(self._feature_card(icon, feat_title, feat_desc))
        inner.addStretch()
        return page

    def _page_advanced(self) -> QWidget:
        page, inner = self._scrollable_page(
            _("Fonctions avancées"),
            _("Des outils pour les utilisateurs exigeants et les configurations multi-écrans complexes."),
        )
        features = [
            ("🎮", _("Mode Jeu"),
             _("Détection automatique du plein écran : un préréglage de luminosité/contraste "
               "est appliqué à l'entrée, et les écritures DDC-CI sont suspendues pour ne pas "
               "interrompre le jeu. Tout est restauré à la sortie.")),
            ("⚙", _("Profils par application"),
             _("Associez un préréglage (luminosité, contraste, gamma, gains RGB) à un exécutable. "
               "Lumina Control détecte automatiquement l'application au premier plan et "
               "applique les réglages — puis les restaure dès que vous changez d'application.")),
            ("🕑", _("Planification horaire"),
             _("Appliquez automatiquement un profil nommé pendant une plage horaire : "
               "\"la nuit de 22h à 7h, passer en mode Cinéma\". "
               "Aucun concurrent direct ne le fait aussi simplement sur Windows.")),
            ("⌨", _("Raccourcis globaux"),
             _("Ctrl+Alt+↑/↓ pour régler la luminosité, Ctrl+Alt+F Focus, "
               "Ctrl+Alt+G Gaming, Ctrl+Alt+N Nuit — sans alt-tabber pendant un jeu ou un stream.")),
            ("📁", _("Profils nommés"),
             _("Sauvegardez l'état complet de tous vos écrans (luminosité, contraste, gamma) "
               "sous un nom personnalisé, et rechargez-le en un clic. "
               "Idéal pour alterner entre une configuration \"Travail\" et \"Cinéma\".")),
            ("🎨", _("Calibrage RGB & Gamma GPU"),
             _("Ajustez finement les gains Rouge / Vert / Bleu via DDC-CI pour corriger les "
               "dominantes de couleur. Le gamma GPU (GDI32) agit indépendamment du DDC-CI "
               "et s'applique même si votre moniteur ne supporte pas DDC.")),
        ]
        for icon, feat_title, feat_desc in features:
            inner.addWidget(self._feature_card(icon, feat_title, feat_desc))
        inner.addStretch()
        return page

    def _page_done(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 40, 40, 24)
        lay.setSpacing(16)
        lay.setAlignment(Qt.AlignCenter)

        icon = QLabel("✓")
        icon.setStyleSheet("font-size: 52px; color: #6CCB5F;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        title = QLabel(_("Tout est prêt !"))
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        desc = QLabel(_(
            "Lumina Control est actif dans la barre des tâches.\n"
            "Cliquez sur l'icône pour ouvrir le panneau de contrôle.\n\n"
            "Vous pouvez relancer cet assistant à tout moment depuis\n"
            "la section Paramètres du panneau."
        ))
        desc.setObjectName("Subtle")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        lay.addWidget(desc)

        # Quick reminder of key sections
        reminder = QFrame()
        reminder.setObjectName("Card")
        rem_l = QVBoxLayout(reminder)
        rem_l.setContentsMargins(16, 12, 16, 12)
        rem_l.setSpacing(6)
        rem_title = QLabel(_("Rappel — où trouver chaque fonction"))
        rem_title.setObjectName("Title")
        rem_l.addWidget(rem_title)
        tips = [
            _("☀  Luminosité globale    → barre en haut du panneau"),
            _("🔗  Synchronisation       → section SYNCHRONISATION"),
            _("🎯  Mode Focus            → section MODE FOCUS"),
            _("🌙  Mode Nuit             → section PARAMÈTRES"),
            _("🎮  Mode Jeu              → section MODE JEU"),
            _("⚙  Profils par app       → section PROFILS AUTOMATIQUES"),
            _("🕑  Planification         → section PLANIFICATION"),
            _("📁  Profils nommés        → section PROFILS NOMMÉS"),
            _("🎨  Calibrage             → bouton ⚙ sur chaque écran"),
        ]
        for tip in tips:
            lbl = QLabel(tip)
            lbl.setObjectName("Subtle")
            lbl.setStyleSheet("font-size: 12px;")
            rem_l.addWidget(lbl)
        lay.addWidget(reminder)

        lay.addStretch()
        return w

    # ── Demo (interactive brightness preview) ─────────────────────────────────

    def _toggle_demo(self) -> None:
        if not self._demo_active:
            if self._apply_demo:
                self._apply_demo()
            self._demo_active = True
            if hasattr(self, "_btn_demo"):
                self._btn_demo.setText(_("Restaurer"))
                self._btn_demo.setProperty("class", "pill-muted")
                self._btn_demo.style().unpolish(self._btn_demo)
                self._btn_demo.style().polish(self._btn_demo)
        else:
            if self._restore_demo:
                self._restore_demo()
            self._demo_active = False
            if hasattr(self, "_btn_demo"):
                self._btn_demo.setText(_("Appliquer"))
                self._btn_demo.setProperty("class", "pill")
                self._btn_demo.style().unpolish(self._btn_demo)
                self._btn_demo.style().polish(self._btn_demo)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Restore demo state if the user closes the dialog while it's active."""
        if self._demo_active and self._restore_demo:
            self._restore_demo()
        super().closeEvent(event)

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
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
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
