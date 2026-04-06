"""System tray icon and context menu."""
import logging

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from lumina_control.i18n import _
from lumina_control.ui.main_window import MainWindow

log = logging.getLogger(__name__)


class Tray:
    """Wraps QSystemTrayIcon and owns the MainWindow."""

    def __init__(self, app, icon_path: str) -> None:
        self.app = app
        self.window = MainWindow()

        self.tray = QSystemTrayIcon(QIcon(icon_path), app)
        menu = QMenu()

        menu.addAction(_("Afficher"), self.window.show_and_activate)
        menu.addAction(_("Patterns plein écran"), self.window.show_patterns)
        menu.addAction(_("Calibrage guidé"), self.window.show_calibration_wizard)
        menu.addSeparator()

        self.act_focus = QAction(_("Mode Focus"), menu)
        self.act_focus.setCheckable(True)
        self.act_focus.toggled.connect(
            lambda v: self.window.set_focus_enabled(v, source="menu")
        )
        menu.addAction(self.act_focus)

        menu.addAction(_("Sauver l'instantané"),    self.window.save_snapshot)
        menu.addAction(_("Restaurer l'instantané"), self.window.restore_snapshot)
        menu.addSeparator()
        menu.addAction(_("Quitter"), app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        self.window.register_focus_action(self.act_focus)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.window.toggle()
