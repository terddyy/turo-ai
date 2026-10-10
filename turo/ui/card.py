"""The task card: a small always-on-top card in the corner with the task, a checklist of steps, and
Next / Do it / Stop. The screen itself only gets the buddy cursor and a short label."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from turo.ui.style import QSS, make_icon, make_label


class GuideCard(QWidget):
    """Small always-on-top card in the corner: the task, a checklist of steps, and Next / Do it / Stop.
    The screen itself only gets a thin ring and a short label; the full instruction lives here."""
    next_clicked = Signal()
    do_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(QSS + "QWidget#guide { background:#0d1526; border:1px solid #2a3c60; border-top:2px solid #4f8ff8; border-radius:14px; }"
                           "QPushButton { padding:6px 12px; }")
        self.setFixedWidth(340)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("guide")
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_icon(20).pixmap(20, 20))
        head.addWidget(logo)
        self.status = make_label("Turo", wrap=False)
        self.status.setStyleSheet("color:#93c5fd; font-weight:600;")
        head.addWidget(self.status, 1)
        close = QPushButton("×")
        close.setFixedWidth(30)
        close.clicked.connect(self.hide)
        head.addWidget(close)
        lay.addLayout(head)
        self.title = make_label("")
        self.title.setStyleSheet("font-size:15px; font-weight:700;")
        lay.addWidget(self.title)
        self.steps_box = QVBoxLayout()
        self.steps_box.setSpacing(6)
        lay.addLayout(self.steps_box)
        row = QHBoxLayout()
        for text, sig, primary in [("Next", self.next_clicked, True), ("Do it", self.do_clicked, False),
                                   ("Stop", self.stop_clicked, False)]:
            b = QPushButton(text)
            if primary:
                b.setObjectName("primary")
            b.clicked.connect(sig.emit)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.steps = []   # (text, done)

    def start(self, question):
        self.title.setText(question)
        self.steps = []
        self._render("Looking at your screen…")
        self._place()
        self.show()

    def thinking(self):
        self._render("Looking at your screen…")

    def add_step(self, text):
        self.steps = [(t, True) for t, _ in self.steps] + [(text, False)]
        self._render(f"Step {len(self.steps)}")
        self.show()

    def finish(self):
        self.steps = [(t, True) for t, _ in self.steps]
        self._render("All done 🎉")

    def _render(self, status):
        self.status.setText(f"Turo · {status}")
        while self.steps_box.count():
            item = self.steps_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, (text, done) in enumerate(self.steps[-5:], start=max(1, len(self.steps) - 4)):
            lab = make_label(f"{'✓' if done else '●'}  {i}. {text}")
            lab.setStyleSheet("color:#64748b;" if done else "color:#e5e7eb; font-size:14px;")
            self.steps_box.addWidget(lab)
        self._place()

    def _place(self):
        # Size from the wrapped text's real height (adjustSize() guessed too small and Qt logged a warning
        # on every step), then sit in the bottom-right corner above the taskbar.
        h = self.layout().totalHeightForWidth(self.width())
        g = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(g.right() - self.width() - 16, g.bottom() - h - 16, self.width(), h)
