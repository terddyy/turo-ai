import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

BUBBLE_W = 420
BLUE = QColor("#3b82f6")
GREEN = QColor("#22c55e")
FLIGHT_S = 0.7   # seconds for the buddy to fly to a target


def _screen_for(px, py):
    """The QScreen holding physical point (px, py), and its scale factor."""
    for s in QApplication.screens():
        g, d = s.geometry(), s.devicePixelRatio()
        if g.x() <= px < g.x() + g.width() * d and g.y() <= py < g.y() + g.height() * d:
            return s, d
    s = QApplication.primaryScreen()
    return s, s.devicePixelRatio()


class Overlay(QWidget):
    """Full-screen click-through layer: a buddy pointer that follows the mouse,
    flies to the target, rings it, and shows a speech bubble."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.target = None    # QRectF in widget coords
        self.text = ""
        self.buddy = QPointF(-100, -100)
        self.flight = None    # (start, control, end, t0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.show()

    # --- called from the Qt thread via signals -------------------------------
    def point_at(self, rect, text):
        """rect: (left, top, right, bottom) in physical screen px from UIA/screenshot, or None."""
        if rect:
            screen, scale = _screen_for((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
            g = screen.geometry()
            if self.geometry() != g:
                self.setGeometry(g)
            left, top, right, bottom = ((v - o) / scale for v, o in
                                        zip(rect, (g.x(), g.y(), g.x(), g.y())))
            self.target = QRectF(left, top, right - left, bottom - top)
            end = QPointF(self.target.left() - 4, self.target.center().y() + 4)
            start = self.buddy
            mid = (start + end) / 2
            control = QPointF(mid.x(), min(start.y(), end.y()) - 120)   # arc upward
            self.flight = (start, control, end, time.time())
        else:
            self.target = None
            self.flight = None
        self.text = text
        self.show()
        self.update()

    def clear(self):
        self.target, self.text, self.flight = None, "", None
        self.update()

    # --- animation -------------------------------------------------------------
    def _tick(self):
        if self.flight:
            start, control, end, t0 = self.flight
            t = min((time.time() - t0) / FLIGHT_S, 1.0)
            t = t * t * (3 - 2 * t)   # ease in-out
            a = start * (1 - t) ** 2 + control * 2 * (1 - t) * t + end * t * t
            self.buddy = a
        elif not self.target:
            # Idle: ride next to the real cursor.
            pos = self.mapFromGlobal(QCursor.pos())
            self.buddy = QPointF(pos.x() + 22, pos.y() + 22)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now = time.time()
        landed = self.target and (not self.flight or now - self.flight[3] >= FLIGHT_S)
        if landed:
            pulse = (math.sin(now * 5) + 1) / 2
            p.setPen(QPen(GREEN, 4))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(self.target.adjusted(-6, -6, 6, 6), 8, 8)
            grow = 8 + 10 * pulse
            ring = QColor(GREEN)
            ring.setAlpha(int(160 * (1 - pulse)))
            p.setPen(QPen(ring, 3))
            p.drawRoundedRect(self.target.adjusted(-grow, -grow, grow, grow), 12, 12)
        self._draw_buddy(p)
        if self.text and (landed or not self.target):
            self._draw_bubble(p)

    def _draw_buddy(self, p):
        b = self.buddy
        path = QPainterPath(QPointF(b.x(), b.y()))   # tip points up-left, like a cursor
        path.lineTo(b.x() + 6, b.y() + 20)
        path.lineTo(b.x() + 10, b.y() + 12)
        path.lineTo(b.x() + 20, b.y() + 8)
        path.closeSubpath()
        p.setPen(QPen(QColor("white"), 2))
        p.setBrush(BLUE)
        p.drawPath(path)

    def _draw_bubble(self, p):
        p.setFont(QFont("Segoe UI", 11))
        inner = BUBBLE_W - 24
        flags = int(Qt.TextWordWrap)
        h = p.boundingRect(QRectF(0, 0, inner, 1000), flags, self.text).height() + 20
        anchor = self.target or QRectF(self.buddy.x(), self.buddy.y(), 20, 20)
        x = min(max(anchor.left(), 8), self.width() - BUBBLE_W - 8)
        y = anchor.bottom() + 14
        if y + h > self.height() - 8:
            y = max(anchor.top() - 14 - h, 8)
        bubble = QRectF(x, y, BUBBLE_W, h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 24, 39, 235))
        p.drawRoundedRect(bubble, 12, 12)
        p.setPen(QColor("white"))
        p.drawText(bubble.adjusted(12, 10, -12, -10), flags, self.text)


if __name__ == "__main__":
    import sys

    import screen

    app = QApplication(sys.argv)
    overlay = Overlay()
    time.sleep(3)   # switch to Excel now
    title, items = screen.list_controls()
    hit = next((i for i in items if i["name"] == "View"), items[0] if items else None)
    print(title, hit)
    QTimer.singleShot(500, lambda: overlay.point_at(hit["rect"] if hit else None,
                                                    "Test: the box should sit on this control."))
    sys.exit(app.exec())
