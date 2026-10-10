"""Apps page: the skills Turo has (skills/*.md) and a button to open that folder."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from turo.config import ROOT
from turo.ui.pages import page_layout
from turo.ui.style import glyph_icon, make_card, make_chip, make_label


class AppsPage(QWidget):
    def __init__(self, skill_list):
        super().__init__()
        lay = page_layout(self, "Skills", "Apps Turo knows well",
                          "Turo works in any app by reading your screen. For these it also has a skill: "
                          "built-in know-how about where things are.")
        grid = QGridLayout()
        grid.setSpacing(12)
        for n, (title, words) in enumerate(skill_list):
            card = make_card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(18, 14, 18, 16)
            cl.setSpacing(10)
            cl.addWidget(make_label(title, "h2"))
            chips = QHBoxLayout()
            chips.setSpacing(6)
            for w in words[:3]:
                chips.addWidget(make_chip(w.strip("=- ")))
            chips.addStretch()
            cl.addLayout(chips)
            grid.addWidget(card, n // 2, n % 2)
        lay.addLayout(grid)
        lay.addSpacing(10)
        more = QPushButton("  Add or edit skills")
        more.setIcon(glyph_icon("folder", "#c3cbd9"))
        more.clicked.connect(lambda: os.startfile(ROOT / "skills"))
        lay.addWidget(more, 0, Qt.AlignLeft)
        lay.addStretch()
