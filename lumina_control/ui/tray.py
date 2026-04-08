"""System tray icon and context menu."""
import logging

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from lumina_control.i18n import _
from lumina_control.ui.main_window import MainWindow

log = logging.getLogger(__name__)

_ICON_SIZE = 64


def _make_brightness_icon(base_icon_path: str, brightness: int) -> QIcon:
    """Overlay a small brightness badge on the original app icon."""
    result = QPixmap(_ICON_SIZE, _ICON_SIZE)
    result.fill(Qt.transparent)
    p = QPainter(result)
    p.setRenderHint(QPainter.Antialiasing)

    # Draw original icon as base
    base = QPixmap(base_icon_path)
    if not base.isNull():
        base = base.scaled(_ICON_SIZE, _ICON_SIZE, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
        p.drawPixmap(0, 0, base)

    # Small pill badge at bottom-center
    text = f"{brightness}%"
    pill_w, pill_h = 34, 16
    pill_x = (_ICON_SIZE - pill_w) // 2
    pill_y = _ICON_SIZE - pill_h - 1

    p.setBrush(QColor(0, 0, 0, 195))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, 8, 8)

    p.setPen(QColor("white"))
    font = QFont("Segoe UI")
    font.setPixelSize(11)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRect(pill_x, pill_y, pill_w, pill_h), Qt.AlignCenter, text)
    p.end()
    return QIcon(result)


class Tray:
    """Wraps QSystemTrayIcon and owns the MainWindow."""

    def __init__(self, app, icon_path: str) -> None:
        self.app = app
        self.window = MainWindow()

        self._icon_path = icon_path
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
        self.window.brightness_changed.connect(self._update_icon)
        self._update_icon(self.window.sl_glob.value())

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.window.toggle()

    def _update_icon(self, brightness: int) -> None:
        icon = _make_brightness_icon(self._icon_path, brightness)
        self.tray.setIcon(icon)
        self.tray.setToolTip(f"Lumina Control  —  {brightness}%")
        self.window.setWindowIcon(icon)
