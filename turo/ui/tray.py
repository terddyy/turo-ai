"""Turo's system tray icon and menu."""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from turo.ui.style import make_icon


class Tray(QSystemTrayIcon):
    def __init__(self, home, on_ask, on_toggle_listen, on_quit):
        super().__init__(make_icon(), home)
        self.setToolTip("Turo: say “Hey Turo”")
        menu = QMenu()
        for text, fn in [("Open Turo", home.show_front), ("Ask (type)…", on_ask),
                         ("Pause / resume listening", on_toggle_listen), ("Tour", home.show_tour)]:
            act = QAction(text, menu)
            act.triggered.connect(fn)
            menu.addAction(act)
        menu.addSeparator()
        quit_act = QAction("Quit Turo", menu)
        quit_act.triggered.connect(on_quit)
        menu.addAction(quit_act)
        self._menu = menu
        self.setContextMenu(menu)
        self.activated.connect(lambda reason: home.show_front()
                               if reason == QSystemTrayIcon.Trigger else None)
        self.show()
