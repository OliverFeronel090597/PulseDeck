"""CircularDial — a classic needle / tapered / triangle dial gauge."""

import math

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient, QConicalGradient,
    QPen, QBrush, QFont, QPolygonF,
)

from src.Dragables.BaseGauge import BaseGauge, _c


class CircularDial(BaseGauge):
    def __init__(self, parent=None, **kwargs):
        self.start_angle = 225.0
        self.span_angle = 270.0
        self.outer_margin = 20
        self.face_color = QColor(245, 248, 252)
        self.face_color_outer = QColor(220, 226, 235)
        self.ring_color = QColor(90, 100, 115)
        self.ring_width = 4.0
        self.background_arc_width = 10.0
        self.background_arc_color = QColor(210, 216, 225)
        self.show_value_arc = True
        self.value_arc_width = 10.0
        self.value_arc_color = QColor(0, 170, 230)
        self.value_arc_gradient = True
        self.value_arc_color_end = None
        self.show_ticks = True
        self.major_ticks = 9
        self.minor_per_major = 4
        self.tick_color = QColor(90, 100, 115)
        self.major_tick_len = 12.0
        self.minor_tick_len = 6.0
        self.major_tick_width = 2.0
        self.minor_tick_width = 1.0
        self.show_tick_labels = True
        self.tick_label_size = 9
        self.tick_label_color = QColor(60, 70, 85)
        self.tick_label_format = "{:.0f}"
        self.tick_label_radius_ratio = 0.72
        self.pointer_style = "needle"
        self.pointer_color = QColor(220, 60, 60)
        self.pointer_width = 4.0
        self.pointer_length_ratio = 0.82
        self.pointer_tail_ratio = 0.18
        self.hub_radius = 12.0
        self.hub_color = QColor(60, 70, 85)
        self.hub_inner_color = QColor(200, 210, 220)
        self.zones = []
        self.show_zone_arcs = True
        self.zone_arc_width = 6.0
        self.zone_arc_opacity = 220
        self.show_center_value = True
        self.center_value_size = 20
        self.center_value_color = QColor(30, 40, 55)
        self.center_value_format = "{:.1f}"
        self.label = "VALUE"
        self.label_color = QColor(60, 70, 85)
        self.label_font_size = 9
        self.label_bold = True
        self.unit = ""
        self.unit_color = QColor(120, 130, 145)
        self.unit_font_size = 9

        kwargs.setdefault("width", 300)
        kwargs.setdefault("height", 300)
        super().__init__(parent, **kwargs)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        side = min(self.width(), self.height())
        m = self.outer_margin
        rect = QRectF((self.width() - side) / 2 + m,
                      (self.height() - side) / 2 + m,
                      side - 2 * m, side - 2 * m)
        center = rect.center()
        r = rect.width() / 2
        ratio = 0.0 if self._max <= self._min else max(
            0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))

        # Face
        grad = QRadialGradient(center, r)
        grad.setColorAt(0.0, _c(self.face_color))
        grad.setColorAt(1.0, _c(self.face_color_outer))
        p.setPen(QPen(_c(self.ring_color), self.ring_width))
        p.setBrush(QBrush(grad))
        p.drawEllipse(center, r, r)

        arc_r = r - self.outer_margin * 0.4 - self.value_arc_width / 2 - 4
        arc_rect = QRectF(center.x() - arc_r, center.y() - arc_r,
                          arc_r * 2, arc_r * 2)

        # Background Arc
        pen = QPen(_c(self.background_arc_color), self.background_arc_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(arc_rect, int(self.start_angle * 16),
                  int(-self.span_angle * 16))

        # Zones
        if self.show_zone_arcs and self.zones:
            for z in self.zones:
                s, e, col = z
                c = _c(col); c.setAlpha(self.zone_arc_opacity)
                pen = QPen(c, self.zone_arc_width)
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                p.setPen(pen)
                a0 = self.start_angle - s * self.span_angle
                a1 = self.start_angle - e * self.span_angle
                p.drawArc(arc_rect, int(a0 * 16), int((a1 - a0) * 16))

        # Value Arc
        if self.show_value_arc and ratio > 0.001:
            start_c = _c(self.value_arc_color)
            if self.value_arc_gradient:
                end_c = _c(self.value_arc_color_end) if self.value_arc_color_end \
                        else start_c.darker(120)
                cgrad = QConicalGradient(center, self.start_angle)
                cgrad.setColorAt(0.0, start_c)
                cgrad.setColorAt(max(0.001, self.span_angle / 360.0), end_c)
                cgrad.setColorAt(1.0, start_c)
                pen = QPen(QBrush(cgrad), self.value_arc_width)
            else:
                pen = QPen(start_c, self.value_arc_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(arc_rect, int(self.start_angle * 16),
                      int(-ratio * self.span_angle * 16))

        # Ticks
        if self.show_ticks:
            total = self.major_ticks * self.minor_per_major
            r_out = r - self.outer_margin * 0.4 - self.background_arc_width - 6
            for i in range(total + 1):
                frac = i / total
                major = (i % self.minor_per_major == 0)
                angle = self.start_angle - frac * self.span_angle
                rad = math.radians(angle)
                length = self.major_tick_len if major else self.minor_tick_len
                width = self.major_tick_width if major else self.minor_tick_width
                r_in = r_out - length
                p0 = QPointF(center.x() + r_out * math.cos(rad),
                             center.y() - r_out * math.sin(rad))
                p1 = QPointF(center.x() + r_in * math.cos(rad),
                             center.y() - r_in * math.sin(rad))
                p.setPen(QPen(_c(self.tick_color), width))
                p.drawLine(p0, p1)
                if major and self.show_tick_labels:
                    val = self._min + frac * (self._max - self._min)
                    lr = r * self.tick_label_radius_ratio
                    lx = center.x() + lr * math.cos(rad)
                    ly = center.y() - lr * math.sin(rad)
                    f = QFont(); f.setPointSize(self.tick_label_size)
                    p.setFont(f); p.setPen(_c(self.tick_label_color))
                    p.drawText(QRectF(lx - 24, ly - 8, 48, 16),
                               Qt.AlignmentFlag.AlignCenter,
                               self.tick_label_format.format(val))

        # Pointer
        angle = self.start_angle - ratio * self.span_angle
        rad = math.radians(angle)
        length = r * self.pointer_length_ratio
        tail = r * self.pointer_tail_ratio
        tip = QPointF(center.x() + length * math.cos(rad),
                      center.y() - length * math.sin(rad))
        back = QPointF(center.x() - tail * math.cos(rad),
                       center.y() + tail * math.sin(rad))
        perp = QPointF(-math.sin(rad), -math.cos(rad))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(self.pointer_color))

        if self.pointer_style == "needle":
            pen = QPen(_c(self.pointer_color), self.pointer_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.drawLine(back, tip)
        elif self.pointer_style == "tapered":
            w = self.pointer_width * 2
            poly = QPolygonF([
                tip,
                QPointF(center.x() + perp.x() * w - tail * math.cos(rad),
                        center.y() + perp.y() * w + tail * math.sin(rad)),
                QPointF(center.x() - perp.x() * w - tail * math.cos(rad),
                        center.y() - perp.y() * w + tail * math.sin(rad)),
            ])
            p.drawPolygon(poly)
        else:
            w = self.pointer_width * 1.6
            base = QPointF(
                center.x() + (length * 0.15) * math.cos(rad),
                center.y() - (length * 0.15) * math.sin(rad))
            poly = QPolygonF([
                tip,
                QPointF(base.x() + perp.x() * w, base.y() + perp.y() * w),
                QPointF(base.x() - perp.x() * w, base.y() - perp.y() * w),
            ])
            p.drawPolygon(poly)

        # Hub
        p.setBrush(_c(self.hub_color))
        p.drawEllipse(center, self.hub_radius, self.hub_radius)
        p.setBrush(_c(self.hub_inner_color))
        p.drawEllipse(center, self.hub_radius * 0.45, self.hub_radius * 0.45)

        # Center text
        if self.show_center_value:
            f = QFont(); f.setPointSize(self.center_value_size); f.setBold(True)
            p.setFont(f); p.setPen(_c(self.center_value_color))
            p.drawText(QRectF(center.x() - 70,
                              center.y() + self.hub_radius + 6, 140, 30),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       self.center_value_format.format(self._value))

            if self.unit:
                p.setPen(_c(self.unit_color))
                f.setPointSize(self.unit_font_size); f.setBold(False)
                p.setFont(f)
                p.drawText(QRectF(center.x() - 70,
                                  center.y() + self.hub_radius + 32, 140, 16),
                           Qt.AlignmentFlag.AlignHCenter |
                           Qt.AlignmentFlag.AlignVCenter, self.unit)

        # Top label
        if self.label:
            p.setPen(_c(self.label_color))
            f = QFont(); f.setPointSize(self.label_font_size)
            f.setBold(self.label_bold)
            p.setFont(f)
            p.drawText(QRectF(0, 6, self.width(), 20),
                       Qt.AlignmentFlag.AlignHCenter |
                       Qt.AlignmentFlag.AlignVCenter, self.label)

        p.end()