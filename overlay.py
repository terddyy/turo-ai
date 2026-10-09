import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

BUBBLE_W = 440
BLUE = QColor("#3b82f6")
GREEN = QColor("#22c55e")
INK = QColor(15, 23, 42, 240)
FLIGHT_S = 0.75    # buddy flight time
SPOT_S = 0.35      # spotlight fade-in
TYPE_CPS = 70      # typewriter speed, characters per second
CONFETTI = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6"]


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
    """Full-screen click-through layer. Modes: idle, listening, thinking, message, pointing, done."""

    def __init__(self, level_fn=lambda: 0.0):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.level_fn = level_fn
        self.mode = "idle"
        self.mode_t = time.time()
        self.target = None      # QRectF in widget coords
        self.last_target = None
        self.text, self.text_t = "", 0.0
        self.step = 0
        self.buddy = QPointF(-100, -100)
        self.trail = []
        self.flight = None      # (start, control, end, t0)
        self.particles = []     # [x, y, vx, vy, color, size]
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
        if mode == "done":
            self._confetti()
        if mode in ("listening", "thinking"):
            self.target, self.flight = None, None
        self._set(mode)

    def clear(self):
        self.target, self.flight, self.text = None, None, ""
        self._set("idle")

    def _set(self, mode):
        if mode != self.mode:
            self.mode, self.mode_t = mode, time.time()

    def _confetti(self):
        c = (self.last_target or QRectF(self.buddy.x(), self.buddy.y(), 1, 1)).center()
        for _ in range(70):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(4, 13)
            self.particles.append([c.x(), c.y(), math.cos(a) * v, math.sin(a) * v - 6,
                                   QColor(random.choice(CONFETTI)), random.uniform(4, 8)])

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
        self.trail = (self.trail + [QPointF(self.buddy)])[-14:]
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.5     # gravity
            p[5] *= 0.97
        self.particles = [p for p in self.particles if p[1] < self.height() + 20 and p[5] > 1]
        lvl = min(self.level_fn() * 25, 1.0) if self.mode == "listening" else 0.0
        self.levels = self.levels[1:] + [lvl]
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now = time.time()
        landed = self.target is not None and (not self.flight or now - self.flight[3] >= FLIGHT_S)
        if self.mode == "pointing" and self.target is not None:
            self._draw_spotlight(p, now)
        if landed:
            self._draw_target(p, now)
        self._draw_trail(p)
        self._draw_buddy(p, now)
        if self.mode == "listening":
            self._draw_wave(p)
        elif self.mode == "thinking":
            self._draw_orbit(p, now)
        for x, y, _vx, _vy, color, size in self.particles:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRect(QRectF(x, y, size, size * 0.6))
        if self.text and (landed or self.target is None):
            self._draw_bubble(p, now, landed)

    def _draw_spotlight(self, p, now):
        fade = _ease(min((now - self.mode_t) / SPOT_S, 1.0))
        hole = QPainterPath()
        hole.addRoundedRect(self.target.adjusted(-14, -14, 14, 14), 12, 12)
        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(2, 6, 23, int(105 * fade)))
        p.drawPath(dim.subtracted(hole))

    def _draw_target(self, p, now):
        since = now - (self.flight[3] + FLIGHT_S if self.flight else self.mode_t)
        pulse = (math.sin(now * 5) + 1) / 2
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(GREEN, 4))
        p.drawRoundedRect(self.target.adjusted(-6, -6, 6, 6), 8, 8)
        ring = QColor(GREEN)
        ring.setAlpha(int(150 * (1 - pulse)))
        grow = 8 + 10 * pulse
        p.setPen(QPen(ring, 3))
        p.drawRoundedRect(self.target.adjusted(-grow, -grow, grow, grow), 12, 12)
        if since < 0.6:   # one-time landing ripple
            r = 10 + since * 160
            ripple = QColor(BLUE)
            ripple.setAlpha(int(200 * (1 - since / 0.6)))
            p.setPen(QPen(ripple, 3))
            p.drawEllipse(self.target.center(), r, r)

    def _draw_trail(self, p):
        if not self.flight or time.time() - self.flight[3] > FLIGHT_S + 0.3:
            return
        p.setPen(Qt.NoPen)
        for i, pt in enumerate(self.trail):
            c = QColor(BLUE)
            c.setAlpha(int(140 * i / len(self.trail)))
            p.setBrush(c)
            p.drawEllipse(pt + QPointF(6, 8), 2 + i * 0.35, 2 + i * 0.35)

    def _draw_buddy(self, p, now):
        bob = math.sin(now * 3) * 1.5 if not self.flight else 0
        b = self.buddy + QPointF(0, bob)
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

    def _draw_bubble(self, p, now, landed):
        shown = self.text[:int((now - self.text_t) * TYPE_CPS) + 1]
        p.setFont(QFont("Segoe UI", 11))
        flags = int(Qt.TextWordWrap)
        inner = BUBBLE_W - 36
        text_h = p.boundingRect(QRectF(0, 0, inner, 2000), flags, self.text).height()
        head = 26
        foot = 22 if self.mode == "pointing" else 0
        h = text_h + head + foot + 22
        anchor = self.target or QRectF(self.buddy.x(), self.buddy.y(), 24, 24)
        x = min(max(anchor.left(), 8), self.width() - BUBBLE_W - 8)
        y = anchor.bottom() + 18
        if y + h > self.height() - 8:
            y = max(anchor.top() - 18 - h, 8)
        appear = _ease(min((now - self.text_t) / 0.25, 1.0))   # slide up + fade in
        p.setOpacity(appear)
        bubble = QRectF(x, y + (1 - appear) * 12, BUBBLE_W, h)
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        p.drawRoundedRect(bubble, 14, 14)
        accent = GREEN if self.mode in ("pointing", "done") else BLUE
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(bubble.left(), bubble.top() + 12, 4, h - 24), 2, 2)
        # header: name + step chip
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.setPen(QColor("#93c5fd"))
        label = {"listening": "TURO · listening", "thinking": "TURO · thinking",
                 "done": "TURO · done"}.get(self.mode, "TURO")
        p.drawText(QRectF(bubble.left() + 18, bubble.top() + 10, 250, 18), int(Qt.AlignLeft), label)
        if self.step and self.mode in ("pointing", "done"):
            chip = QRectF(bubble.right() - 86, bubble.top() + 9, 72, 20)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(34, 197, 94, 60))
            p.drawRoundedRect(chip, 10, 10)
            p.setPen(QColor("#86efac"))
            p.drawText(chip, int(Qt.AlignCenter), f"Step {self.step}")
        # body: typewriter text
        p.setFont(QFont("Segoe UI", 11))
        p.setPen(QColor("white"))
        p.drawText(QRectF(bubble.left() + 18, bubble.top() + head + 8, inner, text_h + 4), flags, shown)
        if foot:
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(QColor("#94a3b8"))
            p.drawText(QRectF(bubble.left() + 18, bubble.bottom() - foot - 6, inner, foot), int(Qt.AlignLeft),
                       "Click the highlighted spot · say \"next\", \"do it\" or ask a follow-up · Esc to stop")
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
                                        "Click the View tab. Freeze Panes lives there.")),
        (8000, lambda: overlay.point_at((cx + 100, cy, cx + 220, cy + 70),
                                        "Now click Freeze Panes.")),
        (11500, lambda: (overlay.point_at(None, "All done! 🎉"), overlay.set_mode("done"))),
        (14500, app.quit),
    ]
    for ms, fn in script:
        QTimer.singleShot(ms, fn)
    sys.exit(app.exec())
