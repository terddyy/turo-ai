"""The first-run tour: five cards with a fade between them."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from turo.ui.pages import page_layout, repolish
from turo.ui.style import glyph_icon, make_card, make_chip, make_label

TOUR = [
    ("👋", "Meet Turo",
     "Your friendly on-screen tutor. Ask how to do something in any app, and Turo points at the exact spot "
     "and walks you through it, step by step. Everything runs on this laptop, even with Wi-Fi off.",
     []),
    ("🗣️", "Just say “Hey Turo”",
     "Then ask the way you'd ask a friend: “Hey Turo, how do I freeze the top row?”. "
     "Prefer the keyboard? Press F9 and type, or hold Win + Alt and talk.",
     ["Hey Turo", "F9 type", "Win + Alt talk"]),
    ("🟩", "Follow the buddy",
     "Turo flies to the right button and lights it up. Click it, and Turo moves on to the next step by itself. "
     "When a step needs typing, Turo copies an example for you: just press Ctrl+V.",
     ["Click where it points", "Ctrl+V"]),
    ("💬", "Keep talking",
     "Once you've said “Hey Turo”, it stays with you for the whole task. Say “next”, “repeat”, "
     "ask a follow-up, or say “do it” and Turo clicks for you. It never presses Send or Delete for you.",
     ["next", "repeat", "do it", "stop / Esc"]),
    ("🧩", "Works in any app",
     "Turo reads your screen, so it works everywhere. It has extra know-how (skills) for Excel, Word, "
     "PowerPoint, File Explorer, your browser, Settings and AI apps like ChatGPT and Claude.",
     []),
]


class TourPage(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__()
        lay = page_layout(self, "Welcome", "A quick tour")
        self.card = make_card()
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(36, 32, 36, 32)
        cl.setSpacing(14)
        self.badge = make_label("", "badge", wrap=False)
        self.badge.setFixedSize(76, 76)
        self.badge.setAlignment(Qt.AlignCenter)
        self.step_label = make_label("", "eyebrow", wrap=False)
        self.heading = make_label("", "title")
        self.body = make_label("", "body")
        self.chips = QHBoxLayout()
        self.chips.setSpacing(8)
        cl.addWidget(self.badge)
        cl.addSpacing(6)
        cl.addWidget(self.step_label)
        cl.addWidget(self.heading)
        cl.addWidget(self.body)
        cl.addLayout(self.chips)
        cl.addStretch()
        lay.addWidget(self.card, 1)
        lay.addSpacing(14)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.dots = []
        for _ in TOUR:
            dot = QFrame()
            dot.setFixedHeight(6)
            self.dots.append(dot)
            bar.addWidget(dot)
        bar.addStretch()
        self.back = QPushButton(" Back")
        self.back.setIcon(glyph_icon("back", "#c3cbd9", size=12))
        self.next = QPushButton("Next")
        self.next.setObjectName("primary")
        self.back.clicked.connect(lambda: self.step(-1))
        self.next.clicked.connect(lambda: self.step(1))
        bar.addWidget(self.back)
        bar.addWidget(self.next)
        lay.addLayout(bar)
        self.index = 0

    def restart(self) -> None:
        self.index = 0
        self.show_card()

    def step(self, delta: int) -> None:
        if delta > 0 and self.index == len(TOUR) - 1:
            self.finished.emit()
            return
        self.index = max(0, min(len(TOUR) - 1, self.index + delta))
        self.show_card()

    def show_card(self) -> None:
        emoji, title, body, chips = TOUR[self.index]
        self.badge.setText(emoji)
        self.step_label.setText(f"STEP {self.index + 1} OF {len(TOUR)}")
        self.heading.setText(title)
        self.body.setText(body)
        while self.chips.count():
            item = self.chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for c in chips:
            self.chips.addWidget(make_chip(c))
        self.chips.addStretch()
        for i, dot in enumerate(self.dots):
            dot.setFixedWidth(28 if i == self.index else 10)
            repolish(dot, "dot_on" if i <= self.index else "dot_off")
        self.back.setEnabled(self.index > 0)
        self.next.setText("Start using Turo" if self.index == len(TOUR) - 1 else "Next")
        self._fade_in()

    def _fade_in(self) -> None:
        # One effect at a time: Qt can't nest opacity effects, so it's removed when the fade ends.
        effect = QGraphicsOpacityEffect(self.card)
        self.card.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(300)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(lambda: self.card.setGraphicsEffect(None))
        self._fade.start()
