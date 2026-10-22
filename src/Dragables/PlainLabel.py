"""PlainLabel — text-only widget, formatted like `[NAME: value]`."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont

from src.Dragables.BaseGauge import BaseGauge, _c


class PlainLabel(BaseGauge):
    def __init__(self, parent=None, **kwargs):
        self.text = "Label"
        self.label_text_name = kwargs.get("label_text_name", self.text)
        self.color = QColor(255, 255, 255)
        self.font_size = 14
        self.bold = False
        self.align = Qt.AlignmentFlag.AlignCenter
        self.background_color = QColor(0, 0, 0, 0)

        kwargs.setdefault("width", 200)
        kwargs.setdefault("height", 40)
        super().__init__(parent, **kwargs)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        if self.background_color.alpha() > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_c(self.background_color))
            p.drawRoundedRect(QRectF(0, 0, w, h), 4, 4)

        p.setPen(_c(self.color))
        f = QFont(); f.setPointSize(self.font_size); f.setBold(self.bold)
        p.setFont(f)
        p.drawText(QRectF(0, 0, w, h), self.align, self.text)
        p.end()