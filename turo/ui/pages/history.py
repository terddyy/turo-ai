"""History page: past questions; double-click one to ask it again."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from turo.ui.pages import page_layout
from turo.ui.store import load_history


class HistoryPage(QWidget):
    ask = Signal(str)

    def __init__(self):
        super().__init__()
        lay = page_layout(self, "History", "Your questions",
                          "Double-click one to ask it again (switch to that app first).")
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._ask_again)
        lay.addWidget(self.list, 1)

    def refresh(self) -> None:
        self.list.clear()
        items = load_history()
        if not items:
            empty = QListWidgetItem("Nothing yet. Ask Turo something!")
            empty.setFlags(Qt.NoItemFlags)
            self.list.addItem(empty)
        for h in items:
            item = QListWidgetItem(f"{h['q']}\n{h.get('app') or 'an app'}  ·  {h.get('t', '')}")
            item.setData(Qt.UserRole, h["q"])
            self.list.addItem(item)

    def _ask_again(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.UserRole)
        if text:
            self.ask.emit(text)
