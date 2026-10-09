from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

BUBBLE_W, BUBBLE_H = 420, 72


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.target = None
        self.text = ""

    def point_at(self, rect, text):
        # UI Automation gives physical pixels; Qt draws in scaled pixels.
        scale = self.devicePixelRatioF()
        if rect:
            left, top, right, bottom = (v / scale for v in rect)
            self.target = QRectF(left, top, right - left, bottom - top)
        else:
            self.target = None
        self.text = text
        self.show()
        self.update()

    def clear(self):
        self.target, self.text = None, ""
        self.hide()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        anchor = self.target or QRectF(40, 40, 0, 0)
        if self.target:
            p.setPen(QPen(QColor("#22c55e"), 4))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(self.target.adjusted(-6, -6, 6, 6), 8, 8)
        if not self.text:
            return
        # Below the target, flipped above it near the bottom edge, kept inside the screen.
        x = min(max(anchor.left(), 8), self.width() - BUBBLE_W - 8)
        y = anchor.bottom() + 14
        if y + BUBBLE_H > self.height() - 8:
            y = max(anchor.top() - 14 - BUBBLE_H, 8)
        bubble = QRectF(x, y, BUBBLE_W, BUBBLE_H)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 24, 39, 235))
        p.drawRoundedRect(bubble, 10, 10)
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(bubble.adjusted(12, 8, -12, -8), Qt.TextWordWrap, self.text)


if __name__ == "__main__":
    import sys
    import time

    import screen

    app = QApplication(sys.argv)
    overlay = Overlay()
    time.sleep(3)   # switch to Excel now
    title, items = screen.list_controls()
    hit = next((i for i in items if i["name"] == "View"), items[0] if items else None)
    print(title, hit)
    overlay.point_at(hit["rect"] if hit else None, "Test: the box should sit on this control. Clicks pass through.")
    sys.exit(app.exec())
