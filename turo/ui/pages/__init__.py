"""One module per Home page. Each page is a QWidget that talks to the window only through its own signals."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from turo.ui.style import make_label


def page_layout(page: QWidget, eyebrow: str, title: str, subtitle: str = "") -> QVBoxLayout:
    """Common page frame: glow background, small caps eyebrow, big title, optional muted subtitle."""
    page.setObjectName("page")
    page.setAttribute(Qt.WA_StyledBackground, True)
    lay = QVBoxLayout(page)
    lay.setContentsMargins(36, 30, 36, 28)
    lay.setSpacing(6)
    lay.addWidget(make_label(eyebrow.upper(), "eyebrow", wrap=False))
    lay.addWidget(make_label(title, "title"))
    if subtitle:
        lay.addWidget(make_label(subtitle, "muted"))
    lay.addSpacing(14)
    return lay


def repolish(widget: QFrame, name: str) -> None:
    """Swap a widget's style role (objectName) at runtime and redraw it."""
    widget.setObjectName(name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
