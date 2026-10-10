"""Turo's look in one place: colour tokens, the stylesheet built from them, icons and small widget builders.
Every window uses these, so a colour change here changes the whole app."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from turo.config import ROOT

# --- tokens ----------------------------------------------------------------------------
C = {
    "bg": "#0a101d", "side": "#070c17", "surface": "#111a2e", "surface_hi": "#16223b",
    "line": "#1d2a42", "line_hi": "#2a3c60", "text": "#e6eaf2", "soft": "#c3cbd9", "muted": "#8b97ad",
    "faint": "#5d6a82", "accent": "#4f8ff8", "accent_deep": "#2f6fe8", "accent_ink": "#bcd4ff",
    "accent_soft": "#13213d", "ok": "#34d399", "warn": "#fbbf24",
}
TEXT_FONT = "'Segoe UI Variable Text', 'Segoe UI'"
DISPLAY_FONT = "'Segoe UI Variable Display', 'Segoe UI'"
CHECK_SVG = (ROOT / "assets" / "check.svg").as_posix()

# Icon glyphs (Segoe Fluent Icons on Windows 11, Segoe MDL2 Assets on Windows 10: same code points).
GLYPH = {"home": 0xE80F, "tour": 0xEA80, "apps": 0xE71D, "history": 0xE81C, "settings": 0xE713,
         "folder": 0xE838, "play": 0xE768, "back": 0xE72B, "next": 0xE72A, "lock": 0xE72E, "mic": 0xE720}

QSS = """
QWidget {{ color: {text}; font-family: {tf}; font-size: 13px; }}
QWidget#window, QWidget#page {{ background: qradialgradient(cx:0.9, cy:0, radius:1.1, fx:0.9, fy:0,
    stop:0 #142650, stop:0.45 {bg}, stop:1 {bg}); }}
QWidget#side {{ background: {side}; border-right: 1px solid {line}; }}
QLabel, QCheckBox {{ background: transparent; }}

QLabel#eyebrow {{ color: {accent}; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; }}
QLabel#title {{ font-family: {df}; font-size: 30px; font-weight: 700; }}
QLabel#h2 {{ font-family: {df}; font-size: 16px; font-weight: 700; }}
QLabel#brand {{ font-family: {df}; font-size: 20px; font-weight: 800; }}
QLabel#body {{ color: {soft}; font-size: 15px; }}
QLabel#muted {{ color: {muted}; }}
QLabel#faint {{ color: {faint}; font-size: 12px; }}
QLabel#badge {{ background: {accent_soft}; border: 1px solid {line_hi}; border-radius: 18px; font-size: 34px; }}
QLabel#chip {{ background: {accent_soft}; color: {accent_ink}; border: 1px solid #24406e; border-radius: 11px;
               padding: 4px 11px; font-weight: 600; }}
QLabel#key {{ background: {surface_hi}; color: {text}; border: 1px solid {line_hi}; border-bottom: 3px solid #0b1324;
              border-radius: 7px; padding: 3px 9px; font-family: 'Cascadia Mono', Consolas; font-size: 12px;
              font-weight: 600; }}
QLabel#pill_ok {{ background: #0f2a24; color: {ok}; border: 1px solid #1d4d40; border-radius: 11px;
                  padding: 3px 10px; font-weight: 600; }}
QLabel#pill_warn {{ background: #2e2610; color: {warn}; border: 1px solid #574617; border-radius: 11px;
                    padding: 3px 10px; font-weight: 600; }}

QFrame#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121c31, stop:1 #0f182a);
               border: 1px solid {line}; border-top-color: #273a5c; border-radius: 16px; }}
QFrame#dot_on {{ background: {accent}; border-radius: 3px; }}
QFrame#dot_off {{ background: {line_hi}; border-radius: 3px; }}
QFrame#led_ok {{ background: {ok}; border-radius: 4px; }}
QFrame#led_warn {{ background: {warn}; border-radius: 4px; }}

QPushButton {{ background: {surface_hi}; border: 1px solid #22314f; border-radius: 10px; padding: 9px 16px; }}
QPushButton:hover {{ background: #20304d; border-color: #2f4670; }}
QPushButton:pressed {{ background: #15203a; }}
QPushButton:disabled {{ color: {faint}; background: transparent; border-color: {line}; }}
QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5b97fa, stop:1 {accent_deep});
                       border: 1px solid #6aa4ff; color: white; font-weight: 600; padding: 10px 20px; }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6ea6ff, stop:1 #3b7cf0); }}
QPushButton#primary:pressed {{ background: #2a63d4; }}
QPushButton#nav {{ background: transparent; border: none; border-radius: 9px; text-align: left;
                   padding: 10px 12px; color: {muted}; font-size: 13px; }}
QPushButton#nav:hover {{ background: {surface}; color: {text}; }}
QPushButton#nav:checked {{ background: {accent_soft}; color: white; font-weight: 600; }}

QLineEdit {{ background: #080d18; border: 1px solid #263552; border-radius: 12px; padding: 12px 14px;
             font-size: 15px; selection-background-color: {accent_deep}; }}
QLineEdit:hover {{ border-color: #33476d; }}
QLineEdit:focus {{ border-color: {accent}; background: #0a1122; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ background: {surface}; border: 1px solid {line}; border-radius: 12px; padding: 12px 14px;
                     margin-bottom: 8px; }}
QListWidget::item:hover {{ background: {surface_hi}; border-color: {line_hi}; }}
QListWidget::item:selected {{ background: {accent_soft}; border-color: {accent}; color: white; }}

QComboBox {{ background: {surface_hi}; border: 1px solid #22314f; border-radius: 9px; padding: 7px 12px;
             min-width: 180px; }}
QComboBox:hover {{ border-color: #2f4670; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {surface}; border: 1px solid {line_hi}; selection-background-color:
                               {accent_soft}; outline: none; padding: 4px; }}

QCheckBox {{ spacing: 12px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px; border: 1px solid {line_hi};
                        background: #080d18; }}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; image: url({check}); }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: #263552; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
""".format(tf=TEXT_FONT, df=DISPLAY_FONT, check=CHECK_SVG, **C)


# --- icons ---------------------------------------------------------------------------
def make_icon(size=64):
    """Generated Turo mark shared by windows, branding and the tray."""
    return QIcon(str(ROOT / "assets" / "turo-logo.ico"))


def _icon_font():
    families = QFontDatabase.families()
    return "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"


def glyph_pixmap(name, color, size=16):
    """A Windows system icon glyph drawn crisp at 2x."""
    pix = QPixmap(size * 2, size * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.TextAntialiasing)
    font = QFont(_icon_font())
    font.setPixelSize(size)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, chr(GLYPH[name]))
    p.end()
    return pix


def glyph_icon(name, color=C["muted"], on_color="#ffffff", size=16):
    """Icon that turns white when its (checkable) button is on."""
    icon = QIcon()
    icon.addPixmap(glyph_pixmap(name, color, size), QIcon.Normal, QIcon.Off)
    icon.addPixmap(glyph_pixmap(name, on_color, size), QIcon.Normal, QIcon.On)
    return icon


# --- widget builders -----------------------------------------------------------------
def make_card():
    f = QFrame()
    f.setObjectName("card")
    return f


def make_label(text, name=None, wrap=True):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def make_chip(text):
    return make_label(text, "chip", wrap=False)


def make_keys(*keys):
    """Keyboard keys drawn as keycaps, e.g. make_keys("Win", "Alt")."""
    row = QHBoxLayout()
    row.setSpacing(4)
    for k in keys:
        row.addWidget(make_label(k, "key", wrap=False))
    return row
