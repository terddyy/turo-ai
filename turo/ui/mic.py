"""Floating mic button in the bottom-right corner: click and talk (Turo stops listening when you stop), or hold it
like push-to-talk. It never takes focus, so the app you're asking about stays in front."""
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from turo.ui.style import glyph_pixmap

SIZE = 52


class MicButton(QWidget):
    pressed = Signal()
    released = Signal()

    def __init__(self, level_fn=lambda: 0.0):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowDoesNotAcceptFocus)   # WS_EX_NOACTIVATE: clicking keeps the app in front
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(SIZE, SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Talk to Turo: click and speak, or hold while you talk. Win+Alt works the same way.")
        self.level_fn, self.on = level_fn, False
        self.icon = glyph_pixmap("mic", "#ffffff", 20)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        g = QApplication.primaryScreen().availableGeometry()
        self.move(g.right() - SIZE - 16, g.bottom() - SIZE - 16)
        self.show()

    def set_on(self, on):
        self.on = on
        if on:
            self.timer.start(50)   # live loudness ring
        else:
            self.timer.stop()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed.emit()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.released.emit()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        center = QPointF(SIZE / 2, SIZE / 2)
        if self.on:
            ring = 20 + min(self.level_fn() * 40, 1.0) * 6
            p.setBrush(QColor(239, 68, 68, 90))
            p.drawEllipse(center, ring, ring)
        p.setBrush(QColor("#ef4444" if self.on else "#3b82f6"))
        p.drawEllipse(center, 20, 20)
        p.drawPixmap(int(SIZE / 2 - 10), int(SIZE / 2 - 10), self.icon)


if __name__ == "__main__":
    app = QApplication([])
    mic = MicButton()
    mic.pressed.connect(lambda: (print("pressed"), mic.set_on(not mic.on)))
    mic.released.connect(lambda: print("released"))
    app.exec()
