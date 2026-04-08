"""System tray icon and context menu."""
import ctypes
import ctypes.wintypes as _W
import logging

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from lumina_control.i18n import _
from lumina_control.ui.main_window import MainWindow

log = logging.getLogger(__name__)

_ICON_SIZE = 64
_WM_SETICON  = 0x0080
_ICON_SMALL  = 0
_ICON_BIG    = 1
_prev_hicon: int = 0


def _qicon_to_hicon(icon: QIcon, size: int = 32) -> int:
    """Convert a QIcon to a Windows HICON via GDI CreateDIBSection.

    Required because QWidget.setWindowIcon() on a frameless window does not
    call SendMessage(WM_SETICON), so the taskbar button keeps the stale icon.
    """
    from PySide6.QtGui import QImage

    px = icon.pixmap(size, size)
    if px.isNull():
        return 0
    img = px.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    if not w or not h:
        return 0

    bits = img.bits()
    bits.setsize(img.sizeInBytes())
    data = bytes(bits)

    # --- 32-bit top-down DIB ------------------------------------------------
    class _BIH(ctypes.Structure):
        _fields_ = [
            ('biSize',          _W.DWORD), ('biWidth',        _W.LONG),
            ('biHeight',        _W.LONG),  ('biPlanes',       _W.WORD),
            ('biBitCount',      _W.WORD),  ('biCompression',  _W.DWORD),
            ('biSizeImage',     _W.DWORD), ('biXPelsPerMeter',_W.LONG),
            ('biYPelsPerMeter', _W.LONG),  ('biClrUsed',      _W.DWORD),
            ('biClrImportant',  _W.DWORD),
        ]

    bmi = _BIH(biSize=ctypes.sizeof(_BIH), biWidth=w, biHeight=-h,
               biPlanes=1, biBitCount=32, biCompression=0, biSizeImage=w * h * 4)

    hdc    = ctypes.windll.gdi32.CreateCompatibleDC(0)
    pvBits = ctypes.c_void_p()
    hbm    = ctypes.windll.gdi32.CreateDIBSection(
        hdc, ctypes.byref(bmi), 0, ctypes.byref(pvBits), None, 0)
    ctypes.windll.gdi32.DeleteDC(hdc)
    if not hbm or not pvBits.value:
        return 0

    ctypes.memmove(pvBits.value, data, len(data))

    # 1-bit mask (all-zero → use color bitmap's alpha channel for transparency)
    hbm_mask = ctypes.windll.gdi32.CreateBitmap(w, h, 1, 1, None)

    class _II(ctypes.Structure):
        _fields_ = [
            ('fIcon', _W.BOOL), ('xHotspot', _W.DWORD), ('yHotspot', _W.DWORD),
            ('hbmMask', _W.HANDLE), ('hbmColor', _W.HANDLE),
        ]

    hicon = ctypes.windll.user32.CreateIconIndirect(
        ctypes.byref(_II(fIcon=True, hbmMask=hbm_mask, hbmColor=hbm)))

    ctypes.windll.gdi32.DeleteObject(hbm)
    ctypes.windll.gdi32.DeleteObject(hbm_mask)
    return int(hicon) if hicon else 0


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

        self.act_gaming = QAction(_("Mode Jeu"), menu)
        self.act_gaming.setCheckable(True)
        self.act_gaming.toggled.connect(
            lambda v: self.window.set_gaming_mode_enabled(v, source="menu")
        )
        menu.addAction(self.act_gaming)

        menu.addAction(_("Sauver l'instantané"),    self.window.save_snapshot)
        menu.addAction(_("Restaurer l'instantané"), self.window.restore_snapshot)
        menu.addSeparator()
        menu.addAction(_("Quitter"), app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        self.window.register_focus_action(self.act_focus)
        self.window.register_gaming_action(self.act_gaming)
        self.window.brightness_changed.connect(self._update_icon)
        self._update_icon(self.window.sl_glob.value())

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.window.toggle()

    def _update_icon(self, brightness: int) -> None:
        global _prev_hicon
        icon = _make_brightness_icon(self._icon_path, brightness)
        self.tray.setIcon(icon)
        self.tray.setToolTip(f"Lumina Control  —  {brightness}%")
        self.window.setWindowIcon(icon)
        # Frameless widgets don't receive WM_SETICON from setWindowIcon —
        # send it directly so the taskbar button picks up the badge.
        try:
            hwnd = int(self.window.winId())
            if hwnd:
                hicon = _qicon_to_hicon(icon, 32)
                if hicon:
                    ctypes.windll.user32.SendMessageW(hwnd, _WM_SETICON, _ICON_SMALL, hicon)
                    ctypes.windll.user32.SendMessageW(hwnd, _WM_SETICON, _ICON_BIG,   hicon)
                    if _prev_hicon:
                        ctypes.windll.user32.DestroyIcon(_prev_hicon)
                    _prev_hicon = hicon
        except Exception as e:
            log.debug("WM_SETICON failed: %s", e)
