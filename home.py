"""Turo's Home window and tray icon: onboarding tour, status, ask box, app skills, history, settings."""
import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget)

DATA = Path(os.environ.get("APPDATA", ".")) / "Turo"
SETTINGS_FILE = DATA / "settings.json"
HISTORY_FILE = DATA / "history.json"
DEFAULTS = {"onboarded": False, "wake": True, "speak": True, "voice": "af_heart"}

QSS = """
QWidget { background: #0b1220; color: #e5e7eb; font-family: 'Segoe UI'; font-size: 13px; }
QLabel, QCheckBox { background: transparent; }
QLabel#title { font-size: 26px; font-weight: 700; }
QLabel#h2 { font-size: 18px; font-weight: 700; }
QLabel#muted, QLabel.muted { color: #94a3b8; }
QLabel#emoji { font-size: 48px; }
QFrame#card { background: #111a2e; border: 1px solid #1e293b; border-radius: 14px; }
QPushButton { background: #1e293b; border: none; border-radius: 10px; padding: 9px 16px; }
QPushButton:hover { background: #273449; }
QPushButton#primary { background: #3b82f6; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #2563eb; }
QPushButton#nav { background: transparent; text-align: left; padding: 10px 14px; color: #94a3b8; }
QPushButton#nav:hover { background: #111a2e; color: #e5e7eb; }
QPushButton#nav[active="true"] { background: #172554; color: white; font-weight: 600; }
QLineEdit { background: #0b1220; border: 1px solid #334155; border-radius: 10px; padding: 10px 12px;
            font-size: 14px; }
QLineEdit:focus { border-color: #3b82f6; }
QListWidget { background: transparent; border: none; }
QListWidget::item { padding: 10px; border-radius: 8px; }
QListWidget::item:hover { background: #111a2e; }
QComboBox { background: #1e293b; border: none; border-radius: 8px; padding: 6px 10px; }
QCheckBox { spacing: 10px; }
"""

TOUR = [
    ("👋", "Meet Turo",
     "Your friendly on-screen tutor. Ask how to do something in any app, and Turo points at the exact spot "
     "and walks you through it, step by step. Everything runs on this laptop, even with Wi-Fi off.",
     []),
    ("🗣️", "Just say “Hey Turo”",
     "Then ask the way you'd ask a friend: “Hey Turo, how do I freeze the top row?”. "
     "Prefer the keyboard? Press F9 and type, or hold Win + Alt and talk.",
     ["Hey Turo", "F9 type", "Win + Alt talk"]),
    ("🟩", "Follow the green box",
     "Turo flies to the right button and lights it up. Click it, and Turo moves on to the next step by itself. "
     "When a step needs typing, Turo copies an example for you: just press Ctrl+V.",
     ["Click the box", "Ctrl+V"]),
    ("💬", "Keep talking",
     "Once you've said “Hey Turo”, it stays with you for the whole task. Say “next”, “repeat”, "
     "ask a follow-up, or say “do it” and Turo clicks for you. It never presses Send or Delete for you.",
     ["next", "repeat", "do it", "stop / Esc"]),
    ("🧩", "Works in any app",
     "Turo reads your screen, so it works everywhere. It has extra know-how (skills) for Excel, Word, "
     "PowerPoint, File Explorer, your browser, Settings and AI apps like ChatGPT and Claude.",
     []),
]


# --- persistence -------------------------------------------------------------------
def load_settings():
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_settings(settings):
    DATA.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def add_history(question, app):
    items = [h for h in load_history() if h.get("q") != question][:49]
    items.insert(0, {"q": question, "app": app, "t": time.strftime("%b %d, %I:%M %p")})
    DATA.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def make_icon(size=64):
    """Turo's mark: the blue buddy pointer on a dark circle."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#0b1220"))
    p.setPen(QPen(QColor("#3b82f6"), size * 0.06))
    p.drawEllipse(QPointF(size / 2, size / 2), size * 0.45, size * 0.45)
    s, ox, oy = size / 64, size * 0.30, size * 0.24
    path = QPainterPath(QPointF(ox, oy))
    for x, y in ((14, 40), (22, 26), (36, 20)):
        path.lineTo(ox + x * s, oy + y * s * 0.9)
    path.closeSubpath()
    p.setPen(QPen(QColor("white"), size * 0.04))
    p.setBrush(QColor("#3b82f6"))
    p.drawPath(path)
    p.end()
    return QIcon(pix)


def _card():
    f = QFrame()
    f.setObjectName("card")
    return f


def _label(text, name=None, wrap=True):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _chip(text):
    lab = QLabel(text)
    lab.setStyleSheet("background:#172554; color:#bfdbfe; border-radius:10px; padding:4px 10px; font-weight:600;")
    return lab


class Home(QWidget):
    ask = Signal(str)                 # the user typed a question
    setting_changed = Signal(str, object)

    def __init__(self, settings, skill_list, status_fn, voices):
        super().__init__()
        self.settings, self.status_fn = settings, status_fn
        self.setWindowTitle("Turo")
        self.setWindowIcon(make_icon())
        self.setStyleSheet(QSS)
        self.resize(860, 600)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QVBoxLayout()
        nav.setContentsMargins(14, 18, 14, 18)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(make_icon(36).pixmap(36, 36))
        brand.addWidget(logo)
        brand.addWidget(_label("Turo", "h2"))
        brand.addStretch()
        nav.addLayout(brand)
        nav.addSpacing(16)
        self.pages = QStackedWidget()
        self.nav_buttons = []
        for i, (name, page) in enumerate([("🏠  Home", self._home_page()), ("✨  Tour", self._tour_page()),
                                          ("🧩  Apps", self._apps_page(skill_list)),
                                          ("🕘  History", self._history_page()),
                                          ("⚙️  Settings", self._settings_page(voices))]):
            self.pages.addWidget(page)
            b = QPushButton(name)
            b.setObjectName("nav")
            b.clicked.connect(lambda _=False, i=i: self.go(i))
            nav.addWidget(b)
            self.nav_buttons.append(b)
        nav.addStretch()
        nav.addWidget(_label("Runs on this laptop.\nNothing leaves it.", "muted"))
        side = QWidget()
        side.setLayout(nav)
        side.setFixedWidth(190)
        side.setStyleSheet("background:#070d18;")
        root.addWidget(side)
        root.addWidget(self.pages, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(1500)
        self.go(0)

    # --- navigation ------------------------------------------------------------
    def go(self, index):
        self.pages.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setProperty("active", i == index)
            b.style().unpolish(b)
            b.style().polish(b)
        if index == 3:
            self._fill_history()
        if index == 1:
            self._show_tour_card()   # the tour card fades in (one effect only: Qt can't nest them)

    def open_ask(self):
        self.go(0)
        self.show_front()
        self.ask_box.setFocus()
        self.ask_box.selectAll()

    def show_tour(self):
        self.tour_index = 0
        self.go(1)
        self.show_front()

    def show_front(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):   # closing hides to the tray; Quit is in the tray menu
        event.ignore()
        self.hide()

    # --- pages -------------------------------------------------------------------
    def _page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 26, 28, 26)
        lay.setSpacing(16)
        return w, lay

    def _home_page(self):
        w, lay = self._page()
        lay.addWidget(_label("Hi! What do you want to do?", "title"))
        lay.addWidget(_label("Switch to the app you need help with and say “Hey Turo”, or type here. "
                             "Turo will look at the app you were just using.", "muted"))
        ask = _card()
        row = QHBoxLayout(ask)
        row.setContentsMargins(14, 14, 14, 14)
        self.ask_box = QLineEdit()
        self.ask_box.setPlaceholderText("e.g. How do I freeze the top row?   ·   How do I upload a PDF to ChatGPT?")
        self.ask_box.returnPressed.connect(self._submit)
        go = QPushButton("Ask Turo")
        go.setObjectName("primary")
        go.clicked.connect(self._submit)
        row.addWidget(self.ask_box, 1)
        row.addWidget(go)
        lay.addWidget(ask)

        status = _card()
        grid = QGridLayout(status)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setVerticalSpacing(10)
        grid.addWidget(_label("Ready check", "h2"), 0, 0, 1, 3)
        self.status_rows = {}
        for r, key in enumerate(["Local AI", "Microphone", "Voice", "Listening"], start=1):
            dot = QLabel("●")
            name = _label(key, wrap=False)
            detail = _label("checking…", "muted")
            grid.addWidget(dot, r, 0)
            grid.addWidget(name, r, 1)
            grid.addWidget(detail, r, 2)
            self.status_rows[key] = (dot, detail)
        grid.setColumnStretch(2, 1)
        lay.addWidget(status)

        tips = _card()
        tl = QVBoxLayout(tips)
        tl.setContentsMargins(18, 16, 18, 16)
        tl.addWidget(_label("Quick keys", "h2"))
        chips = QHBoxLayout()
        for c in ["“Hey Turo”", "F9 type", "Win+Alt talk", "“next”", "“do it” / F7", "Esc stop"]:
            chips.addWidget(_chip(c))
        chips.addStretch()
        tl.addLayout(chips)
        lay.addWidget(tips)
        lay.addStretch()
        return w

    def _tour_page(self):
        w, lay = self._page()
        self.tour_card = _card()
        cl = QVBoxLayout(self.tour_card)
        cl.setContentsMargins(36, 32, 36, 32)
        cl.setSpacing(14)
        self.tour_emoji = _label("", "emoji")
        self.tour_title = _label("", "title")
        self.tour_body = _label("")
        self.tour_body.setStyleSheet("font-size:15px; line-height:150%; color:#cbd5e1;")
        self.tour_chips = QHBoxLayout()
        cl.addWidget(self.tour_emoji)
        cl.addWidget(self.tour_title)
        cl.addWidget(self.tour_body)
        cl.addLayout(self.tour_chips)
        cl.addStretch()
        lay.addWidget(self.tour_card, 1)
        bar = QHBoxLayout()
        self.tour_dots = _label("", "muted", wrap=False)
        self.tour_back = QPushButton("Back")
        self.tour_next = QPushButton("Next")
        self.tour_next.setObjectName("primary")
        self.tour_back.clicked.connect(lambda: self._tour_step(-1))
        self.tour_next.clicked.connect(lambda: self._tour_step(1))
        bar.addWidget(self.tour_dots)
        bar.addStretch()
        bar.addWidget(self.tour_back)
        bar.addWidget(self.tour_next)
        lay.addLayout(bar)
        self.tour_index = 0
        return w

    def _tour_step(self, delta):
        if delta > 0 and self.tour_index == len(TOUR) - 1:
            self.settings["onboarded"] = True
            self.setting_changed.emit("onboarded", True)
            self.go(0)
            self.ask_box.setFocus()
            return
        self.tour_index = max(0, min(len(TOUR) - 1, self.tour_index + delta))
        self._show_tour_card()

    def _show_tour_card(self):
        emoji, title, body, chips = TOUR[self.tour_index]
        self.tour_emoji.setText(emoji)
        self.tour_title.setText(title)
        self.tour_body.setText(body)
        while self.tour_chips.count():
            item = self.tour_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for c in chips:
            self.tour_chips.addWidget(_chip(c))
        self.tour_chips.addStretch()
        self.tour_dots.setText("  ".join("●" if i == self.tour_index else "○" for i in range(len(TOUR))))
        self.tour_back.setEnabled(self.tour_index > 0)
        last = self.tour_index == len(TOUR) - 1
        self.tour_next.setText("Start using Turo" if last else "Next")
        effect = QGraphicsOpacityEffect(self.tour_card)
        self.tour_card.setGraphicsEffect(effect)
        self._card_fade = QPropertyAnimation(effect, b"opacity", self)
        self._card_fade.setDuration(300)
        self._card_fade.setStartValue(0.0)
        self._card_fade.setEndValue(1.0)
        self._card_fade.setEasingCurve(QEasingCurve.OutCubic)
        self._card_fade.finished.connect(lambda: self.tour_card.setGraphicsEffect(None))
        self._card_fade.start()

    def _apps_page(self, skill_list):
        w, lay = self._page()
        lay.addWidget(_label("Apps Turo knows well", "title"))
        lay.addWidget(_label("Turo works in any app by reading your screen. For these it also has a skill: "
                             "built-in know-how about where things are.", "muted"))
        grid = QGridLayout()
        grid.setSpacing(12)
        for n, (title, words) in enumerate(skill_list):
            card = _card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.addWidget(_label(title, "h2"))
            cl.addWidget(_label("Opens for: " + ", ".join(w.strip("=- ") for w in words[:4]), "muted"))
            grid.addWidget(card, n // 2, n % 2)
        lay.addLayout(grid)
        more = QPushButton("Add or edit skills…")
        more.clicked.connect(lambda: os.startfile(Path(__file__).parent / "skills"))
        lay.addWidget(more, 0, Qt.AlignLeft)
        lay.addStretch()
        return w

    def _history_page(self):
        w, lay = self._page()
        lay.addWidget(_label("Your questions", "title"))
        lay.addWidget(_label("Double-click one to ask it again (switch to that app first).", "muted"))
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(lambda item: self._ask_text(item.data(Qt.UserRole)))
        lay.addWidget(self.history_list, 1)
        return w

    def _fill_history(self):
        self.history_list.clear()
        items = load_history()
        if not items:
            self.history_list.addItem("Nothing yet. Ask Turo something!")
        for h in items:
            item = QListWidgetItem(f"{h['q']}\n{h.get('app') or 'an app'}  ·  {h.get('t', '')}")
            item.setData(Qt.UserRole, h["q"])
            self.history_list.addItem(item)

    def _settings_page(self, voices):
        w, lay = self._page()
        lay.addWidget(_label("Settings", "title"))
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(14)
        for key, text in [("wake", "Listen for “Hey Turo” (audio stays on this laptop)"),
                          ("speak", "Read each step out loud")]:
            box = QCheckBox(text)
            box.setChecked(bool(self.settings.get(key)))
            box.toggled.connect(lambda on, key=key: self._set(key, on))
            cl.addWidget(box)
        row = QHBoxLayout()
        row.addWidget(_label("Voice", wrap=False))
        combo = QComboBox()
        for vid, label in voices.items():
            combo.addItem(label, vid)
        idx = combo.findData(self.settings.get("voice"))
        combo.setCurrentIndex(max(idx, 0))
        combo.currentIndexChanged.connect(lambda _: self._set("voice", combo.currentData()))
        row.addWidget(combo)
        row.addStretch()
        cl.addLayout(row)
        lay.addWidget(card)
        tour = QPushButton("Show the tour again")
        tour.clicked.connect(self.show_tour)
        lay.addWidget(tour, 0, Qt.AlignLeft)
        lay.addStretch()
        return w

    # --- actions -----------------------------------------------------------------
    def _set(self, key, value):
        self.settings[key] = value
        self.setting_changed.emit(key, value)

    def _submit(self):
        self._ask_text(self.ask_box.text().strip())
        self.ask_box.clear()

    def _ask_text(self, text):
        if text:
            self.hide()   # get out of the way so Turo sees the app, not this window
            self.ask.emit(text)

    def _refresh_status(self):
        if not self.isVisible() or self.pages.currentIndex() != 0:
            return
        for key, (ok, detail) in self.status_fn().items():
            if key in self.status_rows:
                dot, lab = self.status_rows[key]
                dot.setStyleSheet(f"color: {'#22c55e' if ok else '#f59e0b'}; font-size: 16px;")
                lab.setText(detail)


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
        self.setStyleSheet(QSS + "QWidget#guide { background:#0b1220; border:1px solid #1e293b; border-radius:14px; }"
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
        self.status = _label("Turo", wrap=False)
        self.status.setStyleSheet("color:#93c5fd; font-weight:600;")
        head.addWidget(self.status, 1)
        close = QPushButton("×")
        close.setFixedWidth(30)
        close.clicked.connect(self.hide)
        head.addWidget(close)
        lay.addLayout(head)
        self.title = _label("")
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
            lab = _label(f"{'✓' if done else '●'}  {i}. {text}")
            lab.setStyleSheet("color:#64748b;" if done else "color:#e5e7eb; font-size:14px;")
            self.steps_box.addWidget(lab)
        self._place()

    def _place(self):
        # Size from the wrapped text's real height (adjustSize() guessed too small and Qt logged a warning
        # on every step), then sit in the bottom-right corner above the taskbar.
        h = self.layout().totalHeightForWidth(self.width())
        g = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(g.right() - self.width() - 16, g.bottom() - h - 16, self.width(), h)


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
