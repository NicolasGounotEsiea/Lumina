"""Full-screen test pattern window for visual calibration."""
import logging

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication, QWidget

log = logging.getLogger(__name__)

PATTERNS = [
    ("Uniformité Blanc",   "uniform_white"),
    ("Uniformité Gris 50%","uniform_gray"),
    ("Uniformité Noir",    "uniform_black"),
    ("Rouge",              "solid_red"),
    ("Vert",               "solid_green"),
    ("Bleu",               "solid_blue"),
    ("Gradient Horizontal","grad_h"),
    ("Gradient Vertical",  "grad_v"),
    ("Gamma Steps",        "gamma_steps"),
    ("Sharpness",          "sharpness"),
]


class PatternWindow(QWidget):
    """Frameless, full-screen window that renders calibration test patterns."""

    def __init__(self, start_screen_idx: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.screen_index = start_screen_idx
        self.pattern_index = 0
        self.show_overlay = True
        self._checker_cache: QImage | None = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.BlankCursor)
        self._apply_screen()

    # ── Screen / pattern navigation ───────────────────────────────────────────

    def _apply_screen(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        self.screen_index = max(0, min(self.screen_index, len(screens) - 1))
        screen = screens[self.screen_index]
        handle = self.windowHandle()
        if handle:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())

    def set_pattern_by_id(self, pattern_id: str) -> bool:
        for i, (_, pid) in enumerate(PATTERNS):
            if pid == pattern_id:
                self.pattern_index = i
                self.update()
                return True
        return False

    def _next_pattern(self) -> None:
        self.pattern_index = (self.pattern_index + 1) % len(PATTERNS)
        self.update()

    def _prev_pattern(self) -> None:
        self.pattern_index = (self.pattern_index - 1) % len(PATTERNS)
        self.update()

    def _next_screen(self) -> None:
        screens = QApplication.screens()
        if screens:
            self.screen_index = (self.screen_index + 1) % len(screens)
            self._apply_screen()
            self.update()

    def _prev_screen(self) -> None:
        screens = QApplication.screens()
        if screens:
            self.screen_index = (self.screen_index - 1) % len(screens)
            self._apply_screen()
            self.update()

    # ── Qt events ────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_screen()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._next_pattern()
        elif event.button() == Qt.RightButton:
            self._prev_pattern()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key_Escape, Qt.Key_Q):
            self.close()
        elif key in (Qt.Key_Right, Qt.Key_Space):
            self._next_pattern()
        elif key == Qt.Key_Left:
            self._prev_pattern()
        elif key == Qt.Key_Up:
            self._next_screen()
        elif key == Qt.Key_Down:
            self._prev_screen()
        elif key == Qt.Key_H:
            self.show_overlay = not self.show_overlay
            self.update()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _checker_image(self) -> QImage:
        if self._checker_cache is not None:
            return self._checker_cache
        size = 256
        img = QImage(size, size, QImage.Format_RGB32)
        for y in range(size):
            for x in range(size):
                v = 255 if (x + y) % 2 == 0 else 0
                img.setPixel(x, y, QColor(v, v, v).rgb())
        self._checker_cache = img
        return img

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        rect = self.rect()
        name, pid = PATTERNS[self.pattern_index]

        if pid == "uniform_white":
            p.fillRect(rect, QColor(255, 255, 255))
        elif pid == "uniform_gray":
            p.fillRect(rect, QColor(128, 128, 128))
        elif pid == "uniform_black":
            p.fillRect(rect, QColor(0, 0, 0))
        elif pid == "solid_red":
            p.fillRect(rect, QColor(255, 0, 0))
        elif pid == "solid_green":
            p.fillRect(rect, QColor(0, 255, 0))
        elif pid == "solid_blue":
            p.fillRect(rect, QColor(0, 0, 255))
        elif pid == "grad_h":
            g = QLinearGradient(rect.left(), 0, rect.right(), 0)
            g.setColorAt(0.0, QColor(0, 0, 0))
            g.setColorAt(1.0, QColor(255, 255, 255))
            p.fillRect(rect, g)
        elif pid == "grad_v":
            g = QLinearGradient(0, rect.top(), 0, rect.bottom())
            g.setColorAt(0.0, QColor(0, 0, 0))
            g.setColorAt(1.0, QColor(255, 255, 255))
            p.fillRect(rect, g)
        elif pid == "gamma_steps":
            steps = 16
            sw = max(1, rect.width() // steps)
            for i in range(steps):
                val = int(i / (steps - 1) * 255)
                p.fillRect(QRect(rect.left() + i * sw, rect.top(), sw + 1, rect.height()),
                           QColor(val, val, val))
        elif pid == "sharpness":
            img = self._checker_image()
            scaled = img.scaled(rect.width(), rect.height(),
                                Qt.IgnoreAspectRatio, Qt.FastTransformation)
            p.drawImage(rect, scaled)

        if self.show_overlay:
            ow, oh = 440, 90
            p.fillRect(QRect(20, 20, ow, oh), QColor(0, 0, 0, 160))
            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(QRect(30, 25, ow - 20, 24), Qt.AlignLeft | Qt.AlignVCenter,
                       f"Pattern : {name}   Écran : {self.screen_index + 1}/{len(QApplication.screens())}")
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRect(30, 48, ow - 20, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       "←/→ : pattern   ↑/↓ : écran   H : overlay")
            p.drawText(QRect(30, 66, ow - 20, 18), Qt.AlignLeft | Qt.AlignVCenter,
                       "Échap / Q : fermer   Clic gauche/droit : pattern suivant/précédent")
