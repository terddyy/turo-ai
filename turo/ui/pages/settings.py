"""Settings page: listening, spoken replies, the cursor buddy, and the voice."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from turo.ui.pages import page_layout
from turo.ui.style import glyph_icon, make_card, make_label

TOGGLES = [("wake", "Listen for “Hey Turo”", "Audio is processed on this laptop and never saved."),
           ("speak", "Read each step out loud", "Turo speaks every instruction as it shows it."),
           ("buddy", "Show the cursor buddy when idle", "The little blue pointer that follows your mouse.")]


class SettingsPage(QWidget):
    changed = Signal(str, object)
    tour_requested = Signal()

    def __init__(self, settings, voices):
        super().__init__()
        lay = page_layout(self, "Preferences", "Settings")
        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 8, 20, 8)
        cl.setSpacing(0)
        for n, (key, title, about) in enumerate(TOGGLES):
            box = QCheckBox()
            box.setChecked(bool(settings.get(key)))
            box.toggled.connect(lambda on, key=key: self.changed.emit(key, on))
            cl.addLayout(self._row(title, about, box))
            cl.addWidget(self._divider())
        combo = QComboBox()
        for vid, label in voices.items():
            combo.addItem(label, vid)
        combo.setCurrentIndex(max(combo.findData(settings.get("voice")), 0))
        combo.currentIndexChanged.connect(lambda _: self.changed.emit("voice", combo.currentData()))
        cl.addLayout(self._row("Voice", "Offline Kokoro voices. Turo says hi in the new one.", combo))
        lay.addWidget(card)
        lay.addSpacing(10)
        tour = QPushButton("  Show the tour again")
        tour.setIcon(glyph_icon("play", "#c3cbd9", size=12))
        tour.clicked.connect(self.tour_requested.emit)
        lay.addWidget(tour, 0, Qt.AlignLeft)
        lay.addStretch()

    @staticmethod
    def _row(title, about, control):
        row = QHBoxLayout()
        row.setContentsMargins(0, 14, 0, 14)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(make_label(title, wrap=False))
        text.addWidget(make_label(about, "faint"))
        row.addLayout(text, 1)
        row.addWidget(control, 0, Qt.AlignVCenter)
        return row

    @staticmethod
    def _divider():
        line = QFrame()
        line.setFixedHeight(1)
        line.setObjectName("dot_off")
        return line
