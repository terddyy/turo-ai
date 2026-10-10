import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

PILL_MAX_W = 380   # message pills wrap past this width
BLUE = QColor("#3b82f6")
GREEN = QColor("#22c55e")
INK = QColor(15, 23, 42, 235)
FLIGHT_S = 0.6     # buddy flight time


def _screen_for(px, py):
    """The QScreen holding physical point (px, py), and its scale factor."""
    for s in QApplication.screens():
        g, d = s.geometry(), s.devicePixelRatio()
        if g.x() <= px < g.x() + g.width() * d and g.y() <= py < g.y() + g.height() * d:
            return s, d
    s = QApplication.primaryScreen()
    return s, s.devicePixelRatio()


def _ease(t):
    return t * t * (3 - 2 * t)


class Overlay(QWidget):
    """Full-screen click-through layer, kept minimal: a buddy pointer, a thin ring on the target and a
    one-line label. Full instructions live in the task card. Modes: idle, listening, thinking, message,
    pointing, done, capture (draw nothing while Turo screenshots the screen)."""

    def __init__(self, level_fn=lambda: 0.0, session_fn=lambda: False):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.level_fn = level_fn
        self.session_fn = session_fn   # True while Turo is in a conversation (no wake word needed)
        self.mode = "idle"
        self.mode_t = time.time()
        self.target = None      # QRectF in widget coords
        self.last_target = None
        self.text, self.text_t = "", 0.0
        self.step = 0
        self.buddy = QPointF(-100, -100)
        self.flight = None      # (start, control, end, t0)
        self.levels = [0.0] * 7
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.show()

    # --- called on the Qt thread via signals ---------------------------------------
    def point_at(self, rect, text):
        """rect: (left, top, right, bottom) in physical screen px, or None for a plain message."""
        now = time.time()
        if rect:
            screen, scale = _screen_for((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
            g = screen.geometry()
            if self.geometry() != g:
                self.setGeometry(g)
            left, top, right, bottom = ((v - o) / scale for v, o in
                                        zip(rect, (g.x(), g.y(), g.x(), g.y())))
            self.target = QRectF(left, top, right - left, bottom - top)
            self.last_target = self.target
            end = QPointF(self.target.left() - 4, self.target.center().y() + 6)
            start = self.buddy
            mid = (start + end) / 2
            control = QPointF(mid.x(), min(start.y(), end.y()) - 140)   # arc upward
            self.flight = (start, control, end, now)
            self.step += 1
            self._set("pointing")
        else:
            self.target, self.flight = None, None
            self._set("message")   # callers emit listening/thinking/done right after, if needed
        self.text, self.text_t = text, now
        self.show()

    def set_mode(self, mode):
        if mode == "reset":
            self.step = 0
            return
        if mode in ("listening", "thinking"):
            self.target, self.flight = None, None
        self._set(mode)

    def clear(self):
        self.target, self.flight, self.text = None, None, ""
        self._set("idle")

    def _set(self, mode):
        if mode != self.mode:
            self.mode, self.mode_t = mode, time.time()

    # --- animation ------------------------------------------------------------------
    def _tick(self):
        if self.flight:
            start, control, end, t0 = self.flight
            t = _ease(min((time.time() - t0) / FLIGHT_S, 1.0))
            self.buddy = start * (1 - t) ** 2 + control * 2 * (1 - t) * t + end * t * t
        elif not self.target:
            pos = self.mapFromGlobal(QCursor.pos())   # idle: ride next to the real cursor
            goal = QPointF(pos.x() + 22, pos.y() + 22)
            self.buddy = self.buddy + (goal - self.buddy) * 0.35
        lvl = min(self.level_fn() * 25, 1.0) if self.mode == "listening" else 0.0
        self.levels = self.levels[1:] + [lvl]
        self.update()

    def paintEvent(self, _event):
        if self.mode == "capture":   # Turo is taking a screenshot: stay out of it
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now = time.time()
        landed = self.target is not None and (not self.flight or now - self.flight[3] >= FLIGHT_S)
        if landed:
            self._draw_target(p, now)
        self._draw_buddy(p, now)
        if self.mode == "listening":
            self._draw_wave(p)
        elif self.mode == "thinking":
            self._draw_orbit(p, now)
        if self.text and (landed or self.target is None):
            self._draw_pill(p, now)

    def _draw_target(self, p, now):
        pulse = (math.sin(now * 3) + 1) / 2
        ring = QColor(GREEN)
        ring.setAlpha(int(170 + 85 * pulse))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(ring, 2.5))
        p.drawRoundedRect(self.target.adjusted(-5, -5, 5, 5), 7, 7)

    def _draw_buddy(self, p, now):
        bob = math.sin(now * 3) * 1.5 if not self.flight else 0
        b = self.buddy + QPointF(0, bob)
        if self.session_fn():   # "I'm with you": a soft breathing halo while the session is open
            breath = (math.sin(now * 2.5) + 1) / 2
            halo = QColor(BLUE)
            halo.setAlpha(int(40 + 50 * breath))
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(b + QPointF(9, 10), 20 + 5 * breath, 20 + 5 * breath)
        scale = 1.0 + (0.15 * (math.sin(now * 8) + 1) / 2 if self.mode == "listening" else 0)
        path = QPainterPath(QPointF(b.x(), b.y()))   # tip points up-left, like a cursor
        path.lineTo(b.x() + 7 * scale, b.y() + 22 * scale)
        path.lineTo(b.x() + 11 * scale, b.y() + 13 * scale)
        path.lineTo(b.x() + 22 * scale, b.y() + 9 * scale)
        path.closeSubpath()
        glow = QColor(BLUE)
        glow.setAlpha(60)
        p.setPen(QPen(glow, 8))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(QPen(QColor("white"), 2))
        p.setBrush(BLUE)
        p.drawPath(path)

    def _draw_wave(self, p):
        base = self.buddy + QPointF(30, 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BLUE))
        for i, lvl in enumerate(self.levels):
            h = 4 + lvl * 26
            p.drawRoundedRect(QRectF(base.x() + i * 6, base.y() + 14 - h / 2, 4, h), 2, 2)

    def _draw_orbit(self, p, now):
        c = self.buddy + QPointF(10, 10)
        p.setPen(Qt.NoPen)
        for i in range(3):
            a = now * 6 + i * 2 * math.pi / 3
            dot = QColor(BLUE)
            dot.setAlpha(255 - i * 60)
            p.setBrush(dot)
            p.drawEllipse(c + QPointF(math.cos(a) * 22, math.sin(a) * 22), 4, 4)

    def _draw_pill(self, p, now):
        """One short label: "2 · Click Freeze Panes" beside the target, or a small message by the buddy."""
        pointing = self.target is not None
        text = f"{self.step} · {self.text}" if pointing and self.step else self.text
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold if pointing else QFont.Normal))
        flags = int(Qt.TextWordWrap)
        box = p.boundingRect(QRectF(0, 0, PILL_MAX_W, 400), flags, text)
        w, h = box.width() + 30, box.height() + 14
        if pointing:   # right of the target, else below it, kept on screen
            t = self.target
            x, y = t.right() + 14, t.center().y() - h / 2
            if x + w > self.width() - 8:
                x, y = t.left(), t.bottom() + 12
        else:
            x, y = self.buddy.x() + 30, self.buddy.y() + 26
        x = min(max(x, 8), self.width() - w - 8)
        y = min(max(y, 8), self.height() - h - 8)
        p.setOpacity(_ease(min((now - self.text_t) / 0.2, 1.0)))   # quick fade-in
        pill = QRectF(x, y, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        p.drawRoundedRect(pill, h / 2 if h < 40 else 12, h / 2 if h < 40 else 12)
        p.setBrush(GREEN if self.mode in ("pointing", "done") else BLUE)
        p.drawEllipse(QPointF(pill.left() + 12, pill.top() + min(h / 2, 17)), 3.5, 3.5)
        p.setPen(QColor("white"))
        p.drawText(QRectF(pill.left() + 22, pill.top() + 7, box.width() + 4, box.height()), flags, text)
        p.setOpacity(1.0)


if __name__ == "__main__":
    # Demo of every animation on the primary screen; no app needed.
    import sys

    app = QApplication(sys.argv)
    overlay = Overlay(level_fn=lambda: abs(math.sin(time.time() * 3)) * 0.04)
    g = QApplication.primaryScreen().geometry()
    d = QApplication.primaryScreen().devicePixelRatio()
    cx, cy = g.x() + g.width() * d / 2, g.y() + g.height() * d / 2
    script = [
        (0, lambda: (overlay.point_at(None, "Yes? I'm listening…"), overlay.set_mode("listening"))),
        (2500, lambda: (overlay.point_at(None, '"How do I freeze the top row?"'), overlay.set_mode("thinking"))),
        (4500, lambda: overlay.point_at((cx - 300, cy - 200, cx - 240, cy - 170),
                                        "Click View")),
        (8000, lambda: overlay.point_at((cx + 100, cy, cx + 220, cy + 70),
                                        "Click Freeze Panes")),
        (11500, lambda: (overlay.point_at(None, "All done! 🎉"), overlay.set_mode("done"))),
        (14500, app.quit),
    ]
    for ms, fn in script:
        QTimer.singleShot(ms, fn)
    sys.exit(app.exec())
