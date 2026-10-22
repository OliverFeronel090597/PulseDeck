from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QRectF, QSize


class Thermometer(QWidget):
    def __init__(self, data_key="", label="TEMP", unit="", width=150, height=250, **kwargs):
        super().__init__()
        self.data_key = data_key      # used by main.py to route incoming UART values
        self.label = label            # display name (Name field in the builder)
        self.unit = unit              # Unit field in the builder
        self._min = 0.0               # Min / Max fields in the builder
        self._max = 100.0
        self._value = 0.0

        # Colors: names listed in _serialize_current() are saved automatically
        self.label_color = QColor("#ffffff")
        self.unit_color = QColor("#00aaff")
        self.color = QColor("#e63946")       # mercury
        self.bg_color = QColor("#2b2b36")    # empty tube

        self.setMinimumSize(80, 120)

    # Required: called by main.py for every numeric UART update
    def setValue(self, v):
        self._value = max(self._min, min(float(v), self._max))
        self.update()

    def sizeHint(self):
        return QSize(150, 250)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Name at the top
        p.setPen(self.label_color)
        p.drawText(QRectF(0, 4, w, 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, str(self.label))

        # Geometry (everything is relative to the current size, so resizing just works)
        bulb_r = max(8.0, min(w, h) * 0.14)
        tube_w = bulb_r * 0.9
        cx = w / 2
        tube_top = 30.0
        bulb_cy = h - 30 - bulb_r
        tube_h = max(1.0, bulb_cy - tube_top)
        tube = QRectF(cx - tube_w / 2, tube_top, tube_w, tube_h)

        span = self._max - self._min
        ratio = 0.0 if span <= 0 else (self._value - self._min) / span
        fill_h = tube_h * ratio
        fill = QRectF(tube.left(), tube.bottom() - fill_h, tube_w, fill_h)

        # Empty tube + bulb
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.bg_color)
        p.drawRoundedRect(tube, tube_w / 2, tube_w / 2)
        p.drawEllipse(QRectF(cx - bulb_r, bulb_cy - bulb_r, bulb_r * 2, bulb_r * 2))

        # Mercury
        p.setBrush(self.color)
        p.drawRect(fill)
        p.drawEllipse(QRectF(cx - bulb_r * 0.8, bulb_cy - bulb_r * 0.8, bulb_r * 1.6, bulb_r * 1.6))

        # Value text at the bottom
        p.setPen(self.unit_color)
        p.drawText(QRectF(0, h - 26, w, 22), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._value:.1f} {self.unit}".strip())
