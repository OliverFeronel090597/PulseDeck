"""BarGauge — horizontal bar with ticks underneath."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient

from src.Dragables.BaseGauge import BaseGauge, _c


class BarGauge(BaseGauge):
    def __init__(self, parent=None, **kwargs):
        self.label = "FLOW"
        self.label_color = QColor(255, 255, 255)
        self.label_font_size = 9
        self.color = QColor(6, 214, 160)
        self.bg_color = QColor(30, 30, 36)
        self.tick_color = QColor(85, 85, 102)
        self.tick_label_color = QColor(170, 170, 170)
        self.tick_label_size = 8
        self.tick_label_format = "{:.0f}"
        self.major_ticks = 5
        self.show_ticks = True
        self.show_tick_labels = True
        self.unit = ""
        self.value_format = "{:.1f}"

        kwargs.setdefault("width", 100)
        kwargs.setdefault("height", 100)
        super().__init__(parent, **kwargs)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        ratio = 0.0 if self._max <= self._min else max(
            0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))

        # Top labels
        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(10, 0, w - 20, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.label)

        val_txt = f"{self.value_format.format(self._value)} {self.unit}"
        p.drawText(QRectF(10, 0, w - 20, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   val_txt)

        # Bar area
        pad_x = 10
        bar_w = w - pad_x * 2
        bar_y = 22
        bar_h = max(10, h - bar_y - 22 - 2)
        bar_rect = QRectF(pad_x, bar_y, bar_w, bar_h)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(self.bg_color))
        p.drawRect(bar_rect)

        if ratio > 0:
            fill_rect = QRectF(pad_x, bar_y, bar_w * ratio, bar_h)
            grad = QLinearGradient(fill_rect.left(), 0,
                                   fill_rect.right(), 0)
            c = _c(self.color)
            grad.setColorAt(0.0, c.darker(110))
            grad.setColorAt(1.0, c)
            p.setBrush(QBrush(grad))
            p.drawRect(fill_rect)

        # Ticks
        if self.show_ticks:
            p.setPen(QPen(_c(self.tick_color), 1))
            f.setPointSize(self.tick_label_size)
            p.setFont(f)
            tick_y = bar_y + bar_h + 2
            for i in range(self.major_ticks + 1):
                frac = i / self.major_ticks
                x = pad_x + frac * bar_w
                p.drawLine(QPointF(x, tick_y), QPointF(x, tick_y + 3))
                if self.show_tick_labels:
                    val = self._min + frac * (self._max - self._min)
                    p.setPen(_c(self.tick_label_color))
                    p.drawText(QRectF(x - 25, tick_y + 3, 50, 16),
                               Qt.AlignmentFlag.AlignHCenter |
                               Qt.AlignmentFlag.AlignTop,
                               self.tick_label_format.format(val))
                    p.setPen(QPen(_c(self.tick_color), 1))

        p.end()