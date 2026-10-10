"""Home page: the ask box, the ready check and the quick keys."""
import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from turo.ui.pages import page_layout, repolish
from turo.ui.style import make_card, make_chip, make_keys, make_label

STATUS_KEYS = ("Local AI", "Microphone", "Voice", "Listening", "Memory")
QUICK_KEYS = [(("F9",), "Type a question"), (("Win", "Alt"), "Hold to talk"),
              (("F10",), "Next step"), (("F7",), "Do it for me"),
              (("Esc",), "Stop"), (None, "Ask out loud")]


def greeting() -> str:
    hour = time.localtime().tm_hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"


class AskPage(QWidget):
    ask = Signal(str)

    def __init__(self):
        super().__init__()
        lay = page_layout(self, greeting(), "What do you want to learn?",
                          "Switch to the app you need help with, then ask. Turo looks at the app you were "
                          "just using and points at the right spot.")
        lay.addWidget(self._ask_card())
        lay.addSpacing(12)
        lay.addWidget(self._status_card())
        lay.addSpacing(12)
        lay.addWidget(self._keys_card())
        lay.addStretch()

    # --- building --------------------------------------------------------------------
    def _ask_card(self) -> QFrame:
        card = make_card()
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 16, 16, 14)
        col.setSpacing(10)
        row = QHBoxLayout()
        self.ask_box = QLineEdit()
        self.ask_box.setPlaceholderText("How do I freeze the top row?")
        self.ask_box.returnPressed.connect(self._submit)
        go = QPushButton("Ask Turo")
        go.setObjectName("primary")
        go.clicked.connect(self._submit)
        row.addWidget(self.ask_box, 1)
        row.addWidget(go)
        col.addLayout(row)
        hint = QHBoxLayout()
        hint.setSpacing(8)
        hint.addWidget(make_label("Or say", "faint", wrap=False))
        hint.addWidget(make_chip("“Hey Turo”"))
        hint.addWidget(make_label("from any app, or press", "faint", wrap=False))
        hint.addLayout(make_keys("F9"))
        hint.addStretch()
        col.addLayout(hint)
        return card

    def _status_card(self) -> QFrame:
        card = make_card()
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 16, 20, 18)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        head = QHBoxLayout()
        head.addWidget(make_label("Ready check", "h2", wrap=False))
        head.addStretch()
        self.summary = make_label("Checking…", "pill_warn", wrap=False)
        head.addWidget(self.summary)
        grid.addLayout(head, 0, 0, 1, 3)
        self.rows = {}
        for r, key in enumerate(STATUS_KEYS, start=1):
            led = QFrame()
            led.setObjectName("led_warn")
            led.setFixedSize(8, 8)
            detail = make_label("checking…", "muted")
            grid.addWidget(led, r, 0)
            grid.addWidget(make_label(key, wrap=False), r, 1)
            grid.addWidget(detail, r, 2)
            self.rows[key] = (led, detail)
        grid.setColumnMinimumWidth(1, 90)
        grid.setColumnStretch(2, 1)
        return card

    def _keys_card(self) -> QFrame:
        card = make_card()
        col = QVBoxLayout(card)
        col.setContentsMargins(20, 16, 20, 18)
        col.setSpacing(12)
        col.addWidget(make_label("Quick keys", "h2", wrap=False))
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        for n, (keys, what) in enumerate(QUICK_KEYS):
            cell = QHBoxLayout()
            cell.setSpacing(10)
            if keys:
                cell.addLayout(make_keys(*keys))
            else:
                cell.addWidget(make_chip("“Hey Turo”"))
            cell.addWidget(make_label(what, "muted", wrap=False))
            cell.addStretch()
            grid.addLayout(cell, n // 2, n % 2)
        col.addLayout(grid)
        return card

    # --- behaviour -------------------------------------------------------------------
    def focus_ask(self) -> None:
        self.ask_box.setFocus()
        self.ask_box.selectAll()

    def show_status(self, status: dict) -> None:
        problems = 0
        for key, (ok, detail) in status.items():
            if key in self.rows:
                led, lab = self.rows[key]
                repolish(led, "led_ok" if ok else "led_warn")
                lab.setText(detail)
                problems += not ok
        self.summary.setText("All set" if not problems else f"{problems} need{'s' if problems == 1 else ''} attention")
        repolish(self.summary, "pill_ok" if not problems else "pill_warn")

    def _submit(self) -> None:
        text = self.ask_box.text().strip()
        self.ask_box.clear()
        if text:
            self.ask.emit(text)
