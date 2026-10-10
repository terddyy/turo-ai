"""Turo's Home window: a sidebar and a stack of pages (turo/ui/pages). The window only routes between
pages and forwards their signals; each page owns its own widgets."""
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from turo.ui.pages.apps import AppsPage
from turo.ui.pages.ask import AskPage
from turo.ui.pages.history import HistoryPage
from turo.ui.pages.settings import SettingsPage
from turo.ui.pages.tour import TourPage
from turo.ui.store import load_settings
from turo.ui.style import QSS, glyph_icon, glyph_pixmap, make_icon, make_label

HOME, TOUR, APPS, HISTORY, SETTINGS = range(5)
NAV = [("home", "Home"), ("tour", "Tour"), ("apps", "Apps"), ("history", "History"), ("settings", "Settings")]


class Home(QWidget):
    ask = Signal(str)                 # the user typed a question
    setting_changed = Signal(str, object)
    hidden_to_tray = Signal()          # the user closed the window; Turo keeps running

    def __init__(self, settings, skill_list, status_fn, voices):
        super().__init__()
        self.settings, self.status_fn = settings, status_fn
        self.setWindowTitle("Turo")
        self.setWindowIcon(make_icon())
        self.setObjectName("window")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(QSS)
        self.resize(900, 640)

        self.ask_page, self.tour_page = AskPage(), TourPage()
        self.history_page = HistoryPage()
        settings_page = SettingsPage(settings, voices)
        self.ask_page.ask.connect(self._ask_text)
        self.history_page.ask.connect(self._ask_text)
        self.tour_page.finished.connect(self._tour_done)
        settings_page.changed.connect(self._set)
        settings_page.tour_requested.connect(self.show_tour)

        self.pages = QStackedWidget()
        for page in (self.ask_page, self.tour_page, AppsPage(skill_list), self.history_page, settings_page):
            self.pages.addWidget(page)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        root.addWidget(self.pages, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(1500)
        self.go(HOME)

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("side")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(208)
        nav = QVBoxLayout(side)
        nav.setContentsMargins(14, 22, 14, 18)
        nav.setSpacing(4)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(make_icon().pixmap(36, 36))
        brand.addWidget(logo)
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(make_label("Turo", "brand", wrap=False))
        words.addWidget(make_label("to point · to teach", "faint", wrap=False))
        brand.addLayout(words)
        brand.addStretch()
        nav.addLayout(brand)
        nav.addSpacing(22)
        self.nav_group = QButtonGroup(self)
        for i, (glyph, name) in enumerate(NAV):
            b = QPushButton(f"  {name}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIcon(glyph_icon(glyph))
            b.setIconSize(QSize(16, 16))
            b.clicked.connect(lambda _=False, i=i: self.go(i))
            self.nav_group.addButton(b, i)
            nav.addWidget(b)
        nav.addStretch()
        foot = QHBoxLayout()
        foot.setSpacing(8)
        lock = QLabel()
        lock.setPixmap(glyph_pixmap("lock", "#34d399", 14))
        foot.addWidget(lock, 0, Qt.AlignTop)
        foot.addWidget(make_label("Runs on this laptop.\nNothing leaves it.", "faint"), 1)
        nav.addLayout(foot)
        return side

    # --- navigation ------------------------------------------------------------
    def go(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)
        if index == HISTORY:
            self.history_page.refresh()
        elif index == TOUR:
            self.tour_page.show_card()
        elif index == HOME:
            self._refresh_status()

    def open_ask(self) -> None:
        self.go(HOME)
        self.show_front()
        self.ask_page.focus_ask()

    def show_tour(self) -> None:
        self.tour_page.index = 0
        self.go(TOUR)
        self.show_front()

    def show_front(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):   # closing hides to the tray; Quit is in the tray menu
        event.ignore()
        self.hide()
        self.hidden_to_tray.emit()

    # --- actions -----------------------------------------------------------------
    def _set(self, key, value) -> None:
        self.settings[key] = value
        self.setting_changed.emit(key, value)

    def _tour_done(self) -> None:
        self._set("onboarded", True)
        self.go(HOME)
        self.ask_page.focus_ask()

    def _ask_text(self, text: str) -> None:
        if text:
            self.hide()   # get out of the way so Turo sees the app, not this window
            self.ask.emit(text)

    def _refresh_status(self) -> None:
        if self.isVisible() and self.pages.currentIndex() == HOME:
            self.ask_page.show_status(self.status_fn())


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    h = Home(load_settings(), [("Microsoft Excel", ["excel"]), ("Claude", ["claude"])],
             lambda: {"Local AI": (True, "qwen3-vl:4b-instruct ready"), "Microphone": (True, "on"),
                      "Voice": (True, "Kokoro"), "Listening": (False, "paused")},
             {"af_heart": "Heart (warm, US)"})
    h.ask.connect(lambda t: print("ask:", t))
    h.show_tour()
    sys.exit(app.exec())
