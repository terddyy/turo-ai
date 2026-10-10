"""Shared look for Turo's windows: colours, stylesheet, the Turo icon and small widget helpers."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel

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
