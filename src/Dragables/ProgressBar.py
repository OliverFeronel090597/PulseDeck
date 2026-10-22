"""ProgressBar — rounded loading-style bar."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush, QLinearGradient

from src.Dragables.BaseGauge import BaseGauge, _c


class ProgressBar(BaseGauge):
    def __init__(self, parent=None, **kwargs):
        self.label = ""
        self.label_color = QColor(200, 200, 200)
        self.label_font_size = 9
        self.color = QColor(17, 138, 178)
        self.bg_color = QColor(30, 30, 36)
        self.text_color = QColor(255, 255, 255)
        self.font_size = 12
        self.unit = "%"
        self.value_format = "{:.0f}"
        self.show_value = True

        kwargs.setdefault("width", 300)
        kwargs.setdefault("height", 60)
        super().__init__(parent, **kwargs)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        ratio = 0.0 if self._max <= self._min else max(
            0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))

        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(10, 0, w - 20, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.label)

        if self.show_value:
            val_txt = self.value_format.format(self._value) + self.unit
            p.drawText(QRectF(10, 0, w - 20, 20),
                       Qt.AlignmentFlag.AlignRight |
                       Qt.AlignmentFlag.AlignVCenter, val_txt)

        pad_x = 10
        bar_y = 24
        bar_w = w - pad_x * 2
        bar_h = h - bar_y
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(self.bg_color))
        p.drawRoundedRect(QRectF(pad_x, bar_y, bar_w, bar_h),
                          bar_h / 2, bar_h / 2)

        if ratio > 0:
            fill_rect = QRectF(pad_x, bar_y,
                               max(bar_h, bar_w * ratio), bar_h)
            grad = QLinearGradient(fill_rect.left(), 0,
                                   fill_rect.right(), 0)
            c = _c(self.color)
            grad.setColorAt(0.0, c.darker(110))
            grad.setColorAt(1.0, c)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, bar_h / 2, bar_h / 2)

        p.end()