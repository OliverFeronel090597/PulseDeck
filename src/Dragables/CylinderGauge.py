"""CylinderGauge — a vertical tank / liquid level gauge."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient,
    QPen, QBrush, QFont, QLinearGradient, QPainterPath,
)

from src.Dragables.BaseGauge import BaseGauge, _c


class CylinderGauge(BaseGauge):
    def __init__(self, parent=None, **kwargs):
        self.margin_top = 60
        self.margin_bottom = 50
        self.margin_side = 70
        self.ellipse_ratio = 0.28
        self.corner_radius = 0.0
        self.body_color = QColor(240, 244, 248)
        self.body_color_bottom = QColor(225, 232, 240)
        self.rim_color = QColor(248, 250, 252)
        self.outline_color = QColor(90, 100, 115)
        self.outline_width = 2.0
        self.liquid_color = QColor(0, 170, 230)
        self.liquid_gradient = True
        self.liquid_opacity = 1.0
        self.surface_highlight = True
        self.surface_color = None
        self.glass_shading = True
        self.glass_highlight_alpha = 70
        self.glass_shadow_alpha = 90
        self.show_scale = True
        self.scale_ticks = 10
        self.scale_major_every = 2
        self.scale_color = QColor(90, 100, 115)
        self.scale_font_size = 8
        self.scale_tick_minor = 4
        self.scale_tick_major = 8
        self.scale_format = "{:.0f}"
        self.zones = []
        self.zone_opacity = 90
        self.label = "LEVEL"
        self.label_color = QColor(60, 70, 85)
        self.label_font_size = 9
        self.label_bold = True
        self.value_color = QColor(30, 40, 55)
        self.value_font_size = 18
        self.value_bold = False
        self.value_format = "{:.1f}"
        self.unit = "%"
        self.unit_separator = " "
        self.show_value = True

        kwargs.setdefault("width", 280)
        kwargs.setdefault("height", 350)
        super().__init__(parent, **kwargs)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        side = self.margin_side if self.show_scale else self.margin_side * 0.5
        body = QRectF(side, self.margin_top,
                      w - side * 2, h - self.margin_top - self.margin_bottom)
        eh = body.width() * self.ellipse_ratio
        cx = body.center().x()

        top_rect = QRectF(body.left(), body.top() - eh / 2,
                          body.width(), eh)
        bottom_rect = QRectF(body.left(), body.bottom() - eh / 2,
                             body.width(), eh)
        ratio = 0.0 if self._max <= self._min else max(
            0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))
        surface_y = body.bottom() - body.height() * ratio

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        bg = QLinearGradient(body.left(), 0, body.right(), 0)
        bg.setColorAt(0.0, _c(self.body_color_bottom))
        bg.setColorAt(0.5, _c(self.body_color))
        bg.setColorAt(1.0, _c(self.body_color_bottom))
        p.setBrush(QBrush(bg))
        if self.corner_radius > 0:
            p.drawRoundedRect(body, self.corner_radius, self.corner_radius)
        else:
            p.drawRect(body)
        p.setBrush(_c(self.body_color_bottom)); p.drawEllipse(bottom_rect)
        p.setBrush(_c(self.rim_color)); p.drawEllipse(top_rect)

        # Zones
        if self.zones:
            p.save()
            clip = QPainterPath(); clip.addRect(body); p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            for z in self.zones:
                s, e, col = z
                y0 = body.bottom() - body.height() * e
                y1 = body.bottom() - body.height() * s
                c = _c(col); c.setAlpha(self.zone_opacity)
                p.setBrush(c)
                p.drawRect(QRectF(body.left(), y0, body.width(), y1 - y0))
            p.restore()

        # Liquid
        if ratio > 0.001:
            liquid = QPainterPath()
            liquid.moveTo(body.left(), surface_y)
            liquid.lineTo(body.left(), body.bottom())
            liquid.arcTo(bottom_rect, 180, 180)
            liquid.lineTo(body.right(), surface_y)
            surf_rect = QRectF(body.left(), surface_y - eh / 2,
                               body.width(), eh)
            liquid.arcTo(surf_rect, 0, 180)
            liquid.closeSubpath()

            c = _c(self.liquid_color)
            if self.liquid_gradient:
                grad = QLinearGradient(body.left(), 0, body.right(), 0)
                grad.setColorAt(0.0, c.darker(140))
                grad.setColorAt(0.35, c.lighter(115))
                grad.setColorAt(0.55, c.lighter(140))
                grad.setColorAt(0.75, c)
                grad.setColorAt(1.0, c.darker(150))
                brush = QBrush(grad)
            else:
                brush = QBrush(c)

            p.save()
            p.setOpacity(self.liquid_opacity)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(brush)
            p.drawPath(liquid)
            if self.surface_highlight:
                sc = _c(self.surface_color) if self.surface_color else c.lighter(160)
                sg = QRadialGradient(cx, surface_y, body.width() / 2)
                sg.setColorAt(0.0, sc); sg.setColorAt(1.0, c.lighter(110))
                p.setBrush(QBrush(sg)); p.drawEllipse(surf_rect)
            p.restore()

        # Glass
        if self.glass_shading:
            g = QLinearGradient(body.left(), 0, body.right(), 0)
            g.setColorAt(0.0,  QColor(0, 0, 0, self.glass_shadow_alpha))
            g.setColorAt(0.15, QColor(0, 0, 0, self.glass_shadow_alpha // 6))
            g.setColorAt(0.35, QColor(255, 255, 255,
                                       self.glass_highlight_alpha))
            g.setColorAt(0.55, QColor(255, 255, 255,
                                       self.glass_highlight_alpha // 3))
            g.setColorAt(0.85, QColor(0, 0, 0,
                                      self.glass_shadow_alpha // 5))
            g.setColorAt(1.0,  QColor(0, 0, 0, self.glass_shadow_alpha))
            p.save()
            clip = QPainterPath(); clip.addRect(body); p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
            p.drawRect(body)
            p.restore()

        # Outline
        p.setPen(QPen(_c(self.outline_color), self.outline_width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(body.left(), body.top()),
                   QPointF(body.left(), body.bottom()))
        p.drawLine(QPointF(body.right(), body.top()),
                   QPointF(body.right(), body.bottom()))
        p.drawArc(bottom_rect, 180 * 16, 180 * 16)
        p.drawArc(top_rect, 0, 180 * 16)
        inner = top_rect.adjusted(4, 2, -4, -2)
        p.setPen(QPen(_c(self.rim_color).lighter(105), 1))
        p.drawEllipse(inner)

        # Scale
        if self.show_scale:
            p.setPen(QPen(_c(self.scale_color), 1))
            f = QFont(); f.setPointSize(self.scale_font_size); p.setFont(f)
            span = self._max - self._min
            for i in range(self.scale_ticks + 1):
                frac = i / self.scale_ticks
                y = body.bottom() - body.height() * frac
                major = (i % self.scale_major_every == 0)
                length = self.scale_tick_major if major else self.scale_tick_minor
                p.drawLine(QPointF(body.right() + 4, y),
                           QPointF(body.right() + 4 + length, y))
                if major:
                    val = self._min + frac * span
                    p.drawText(QRectF(body.right() + 16, y - 8, 60, 16),
                               Qt.AlignmentFlag.AlignLeft |
                               Qt.AlignmentFlag.AlignVCenter,
                               self.scale_format.format(val))

        # Text
        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size)
        f.setBold(self.label_bold)
        p.setFont(f)
        p.drawText(QRectF(0, 6, self.width(), 20),
                   Qt.AlignmentFlag.AlignHCenter |
                   Qt.AlignmentFlag.AlignVCenter, self.label)

        if self.show_value:
            p.setPen(_c(self.value_color))
            f.setPointSize(self.value_font_size); f.setBold(self.value_bold)
            p.setFont(f)
            txt = self.value_format.format(self._value) + \
                  self.unit_separator + self.unit
            p.drawText(QRectF(body.left(),
                              body.center().y() - 15, body.width(), 30),
                       Qt.AlignmentFlag.AlignHCenter |
                       Qt.AlignmentFlag.AlignVCenter, txt)

        p.end()