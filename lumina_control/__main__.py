"""Entry point for ``python -m lumina_control``."""
import logging
import os
import sys

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _setup_file_logging() -> None:
    """Add a rotating file handler to the root logger.

    Written to %APPDATA%\\LuminaControl\\logs\\lumina.log (500 KB × 3 backups).
    The console handler keeps WARNING level; the file handler captures INFO+.
    """
    from logging.handlers import RotatingFileHandler
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(appdata, "LuminaControl", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "lumina.log")

    fh = RotatingFileHandler(
        log_path, maxBytes=500_000, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    # Lower root so INFO can reach the file handler
    root.setLevel(logging.INFO)
    # Lock the existing console handler at WARNING so the terminal stays clean
    for h in root.handlers:
        if h is not fh and not h.level:
            h.setLevel(logging.WARNING)
    root.addHandler(fh)
    log.info("Lumina Control — log file ready at %s", log_path)


def _resolve_icon() -> str:
    """Return a valid path to the app icon, creating a fallback if necessary."""
    from lumina_control.config import ICON_PATH, get_app_data_dir
    if os.path.exists(ICON_PATH):
        return ICON_PATH
    # Create a simple coloured circle as fallback
    from PySide6.QtGui import QColor, QPainter, QPixmap
    from PySide6.QtCore import Qt
    from lumina_control.config import ACCENT_COLOR
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setBrush(QColor(ACCENT_COLOR))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.end()
    target = os.path.join(get_app_data_dir(), "icon.png")
    pix.save(target)
    return target


def main() -> None:
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from lumina_control.config import APP_NAME, SINGLE_INSTANCE_SERVER
    from lumina_control.style import get_stylesheet
    from lumina_control.utils import is_windows_dark_mode

    # ── Single-instance guard ─────────────────────────────────────────────────
    probe = QLocalSocket()
    probe.connectToServer(SINGLE_INSTANCE_SERVER)
    if probe.waitForConnected(150):
        probe.write(b"activate")
        probe.flush()
        probe.waitForBytesWritten(150)
        probe.disconnectFromServer()
        sys.exit(0)

    # ── File logging (before any component starts) ────────────────────────────
    _setup_file_logging()
    from lumina_control.config import APP_VERSION
    log.info("Lumina Control %s — startup", APP_VERSION)

    # ── Application setup ─────────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_NAME)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    # Apply stylesheet matching the current Windows theme
    _dark = [is_windows_dark_mode()]
    _tray_ref: list = [None]   # filled after Tray is created
    app.setStyleSheet(get_stylesheet(_dark[0]))

    from PySide6.QtCore import QTimer as _QTimer
    def _check_theme() -> None:
        d = is_windows_dark_mode()
        if d != _dark[0]:
            _dark[0] = d
            gaming = _tray_ref[0].window.gaming_enabled if _tray_ref[0] else False
            app.setStyleSheet(get_stylesheet(d, gaming=gaming))
    _theme_timer = _QTimer(app)   # parent = app keeps it alive
    _theme_timer.timeout.connect(_check_theme)
    _theme_timer.start(5000)  # check every 5 s

    icon_path = _resolve_icon()

    # Detect first run before creating the tray (which writes settings)
    from lumina_control.config import get_settings_path
    _first_run = not os.path.exists(get_settings_path())

    from lumina_control.ui.tray import Tray
    tray = Tray(app, icon_path)
    _tray_ref[0] = tray   # now the theme checker knows gaming state

    if _first_run:
        from lumina_control.ui.onboarding import OnboardingDialog
        from PySide6.QtCore import QTimer as _OTimer

        def _open_onboarding() -> None:
            dlg = OnboardingDialog(
                tray.window,
                apply_demo=tray.window._onboarding_apply_evening,
                restore_demo=tray.window._onboarding_restore,
            )
            dlg.exec()

        _OTimer.singleShot(600, _open_onboarding)

    # Save settings, reset gamma and unregister hotkeys on clean exit
    app.aboutToQuit.connect(tray.window.save_settings)
    app.aboutToQuit.connect(tray.window.reset_gamma)
    app.aboutToQuit.connect(tray.window._hotkey_mgr.unregister_all)

    # ── Single-instance server (accept activation from new instances) ─────────
    QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE_SERVER)

    def _on_new_connection() -> None:
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            if client:
                client.readAll()
                client.disconnectFromServer()
        tray.window.show_and_activate()

    server.newConnection.connect(_on_new_connection)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
