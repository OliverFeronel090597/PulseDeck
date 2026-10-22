import math
from collections import deque
from typing import Union, Tuple

from PyQt6.QtWidgets import QWidget, QSizePolicy, QSizeGrip
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, pyqtProperty, pyqtSignal, QPropertyAnimation, 
    QEasingCurve
)
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient, QConicalGradient,
    QPen, QBrush, QFont, QPolygonF, QLinearGradient, QPainterPath, 
)

ColorLike = Union[QColor, str, Tuple[int, int, int]]

def _c(value: ColorLike) -> QColor:
    if isinstance(value, QColor): return value
    if isinstance(value, tuple) and len(value) == 3: return QColor(*value)
    return QColor(value)

# ============================================================
#  Base Gauge
# ============================================================
class BaseGauge(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        
        w = kwargs.pop("width", 300)
        h = kwargs.pop("height", 300)

        self.animation_ms = 400
        self._value = 0.0
        self._min = 0.0
        self._max = 100.0
        self.data_key = kwargs.pop("data_key", "")
        
        self._is_locked = False
        self._resize_grip = None

        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

        # 80px minimum ensures text is not clipped in any sub-class
        self.setMinimumSize(100, 80) 
        self.resize(w, h)

        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def getValue(self): return self._value
    def setValue(self, v):
        v = max(self._min, min(float(v), self._max))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
            self.update()

    def getMin(self): return self._min
    def setMin(self, v):
        self._min = float(v)
        if self._value < self._min: self.setValue(self._min)
        self.update()

    def getMax(self): return self._max
    def setMax(self, v):
        self._max = float(v)
        if self._value > self._max: self.setValue(self._max)
        self.update()

    value = pyqtProperty(float, getValue, setValue)
    minimum = pyqtProperty(float, getMin, setMin)
    maximum = pyqtProperty(float, getMax, setMax)

    def animateTo(self, val, ms=None):
        self._anim.stop()
        self._anim.setDuration(ms if ms is not None else self.animation_ms)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(max(self._min, min(float(val), self._max)))
        self._anim.start()

    def set_locked(self, locked: bool):
        self._is_locked = locked
        if locked:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.setFixedSize(self.width(), self.height())
            if self._resize_grip: self._resize_grip.hide()
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMinimumSize(100, 80)
            self.setMaximumSize(16777215, 16777215)
            if not self._resize_grip:
                self._resize_grip = QSizeGrip(self)
            self._resize_grip.show()
            self._position_grip()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_grip()

    def _position_grip(self):
        if self._resize_grip:
            self._resize_grip.move(
                self.width() - self._resize_grip.width() - 2, 
                self.height() - self._resize_grip.height() - 2
            )

# ============================================================
#  Circular Dial
# ============================================================
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
        rect = QRectF((self.width() - side) / 2 + m, (self.height() - side) / 2 + m, side - 2 * m, side - 2 * m)
        center = rect.center()
        r = rect.width() / 2
        ratio = 0.0 if self._max <= self._min else max(0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))

        # Face
        grad = QRadialGradient(center, r)
        grad.setColorAt(0.0, _c(self.face_color))
        grad.setColorAt(1.0, _c(self.face_color_outer))
        p.setPen(QPen(_c(self.ring_color), self.ring_width))
        p.setBrush(QBrush(grad))
        p.drawEllipse(center, r, r)

        arc_r = r - self.outer_margin * 0.4 - self.value_arc_width / 2 - 4
        arc_rect = QRectF(center.x() - arc_r, center.y() - arc_r, arc_r * 2, arc_r * 2)

        # Background Arc
        pen = QPen(_c(self.background_arc_color), self.background_arc_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(arc_rect, int(self.start_angle * 16), int(-self.span_angle * 16))

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
                end_c = _c(self.value_arc_color_end) if self.value_arc_color_end else start_c.darker(120)
                cgrad = QConicalGradient(center, self.start_angle)
                cgrad.setColorAt(0.0, start_c)
                cgrad.setColorAt(max(0.001, self.span_angle / 360.0), end_c)
                cgrad.setColorAt(1.0, start_c)
                pen = QPen(QBrush(cgrad), self.value_arc_width)
            else:
                pen = QPen(start_c, self.value_arc_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(arc_rect, int(self.start_angle * 16), int(-ratio * self.span_angle * 16))

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
                p0 = QPointF(center.x() + r_out * math.cos(rad), center.y() - r_out * math.sin(rad))
                p1 = QPointF(center.x() + r_in * math.cos(rad), center.y() - r_in * math.sin(rad))
                p.setPen(QPen(_c(self.tick_color), width))
                p.drawLine(p0, p1)
                if major and self.show_tick_labels:
                    val = self._min + frac * (self._max - self._min)
                    lr = r * self.tick_label_radius_ratio
                    lx = center.x() + lr * math.cos(rad)
                    ly = center.y() - lr * math.sin(rad)
                    f = QFont(); f.setPointSize(self.tick_label_size)
                    p.setFont(f); p.setPen(_c(self.tick_label_color))
                    p.drawText(QRectF(lx - 24, ly - 8, 48, 16), Qt.AlignmentFlag.AlignCenter, self.tick_label_format.format(val))

        # Pointer
        angle = self.start_angle - ratio * self.span_angle
        rad = math.radians(angle)
        length = r * self.pointer_length_ratio
        tail = r * self.pointer_tail_ratio
        tip = QPointF(center.x() + length * math.cos(rad), center.y() - length * math.sin(rad))
        back = QPointF(center.x() - tail * math.cos(rad), center.y() + tail * math.sin(rad))
        perp = QPointF(-math.sin(rad), -math.cos(rad))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(_c(self.pointer_color))
        
        if self.pointer_style == "needle":
            pen = QPen(_c(self.pointer_color), self.pointer_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.drawLine(back, tip)
        elif self.pointer_style == "tapered":
            w = self.pointer_width * 2
            poly = QPolygonF([tip, QPointF(center.x() + perp.x() * w - tail * math.cos(rad), center.y() + perp.y() * w + tail * math.sin(rad)), QPointF(center.x() - perp.x() * w - tail * math.cos(rad), center.y() - perp.y() * w + tail * math.sin(rad))])
            p.drawPolygon(poly)
        else:
            w = self.pointer_width * 1.6
            base = QPointF(center.x() + (length * 0.15) * math.cos(rad), center.y() - (length * 0.15) * math.sin(rad))
            poly = QPolygonF([tip, QPointF(base.x() + perp.x() * w, base.y() + perp.y() * w), QPointF(base.x() - perp.x() * w, base.y() - perp.y() * w)])
            p.drawPolygon(poly)

        # Hub
        p.setBrush(_c(self.hub_color)); p.drawEllipse(center, self.hub_radius, self.hub_radius)
        p.setBrush(_c(self.hub_inner_color)); p.drawEllipse(center, self.hub_radius * 0.45, self.hub_radius * 0.45)

        # Center text
        if self.show_center_value:
            f = QFont(); f.setPointSize(self.center_value_size); f.setBold(True)
            p.setFont(f); p.setPen(_c(self.center_value_color))
            p.drawText(QRectF(center.x() - 70, center.y() + self.hub_radius + 6, 140, 30), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.center_value_format.format(self._value))

            if self.unit:
                p.setPen(_c(self.unit_color))
                f.setPointSize(self.unit_font_size); f.setBold(False)
                p.setFont(f)
                p.drawText(QRectF(center.x() - 70, center.y() + self.hub_radius + 32, 140, 16), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.unit)

        # Top Label
        if self.label:
            p.setPen(_c(self.label_color))
            f = QFont(); f.setPointSize(self.label_font_size); f.setBold(self.label_bold)
            p.setFont(f)
            p.drawText(QRectF(0, 6, self.width(), 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.label)

        p.end()


# ============================================================
#  Cylinder Gauge
# ============================================================
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
        body = QRectF(side, self.margin_top, w - side * 2, h - self.margin_top - self.margin_bottom)
        eh = body.width() * self.ellipse_ratio
        cx = body.center().x()
        
        top_rect = QRectF(body.left(), body.top() - eh / 2, body.width(), eh)
        bottom_rect = QRectF(body.left(), body.bottom() - eh / 2, body.width(), eh)
        ratio = 0.0 if self._max <= self._min else max(0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))
        surface_y = body.bottom() - body.height() * ratio

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        bg = QLinearGradient(body.left(), 0, body.right(), 0)
        bg.setColorAt(0.0, _c(self.body_color_bottom))
        bg.setColorAt(0.5, _c(self.body_color))
        bg.setColorAt(1.0, _c(self.body_color_bottom))
        p.setBrush(QBrush(bg))
        if self.corner_radius > 0: p.drawRoundedRect(body, self.corner_radius, self.corner_radius)
        else: p.drawRect(body)
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
                p.setBrush(c); p.drawRect(QRectF(body.left(), y0, body.width(), y1 - y0))
            p.restore()

        # Liquid
        if ratio > 0.001:
            liquid = QPainterPath()
            liquid.moveTo(body.left(), surface_y)
            liquid.lineTo(body.left(), body.bottom())
            liquid.arcTo(bottom_rect, 180, 180)
            liquid.lineTo(body.right(), surface_y)
            surf_rect = QRectF(body.left(), surface_y - eh / 2, body.width(), eh)
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
            g.setColorAt(0.0, QColor(0, 0, 0, self.glass_shadow_alpha))
            g.setColorAt(0.15, QColor(0, 0, 0, self.glass_shadow_alpha // 6))
            g.setColorAt(0.35, QColor(255, 255, 255, self.glass_highlight_alpha))
            g.setColorAt(0.55, QColor(255, 255, 255, self.glass_highlight_alpha // 3))
            g.setColorAt(0.85, QColor(0, 0, 0, self.glass_shadow_alpha // 5))
            g.setColorAt(1.0, QColor(0, 0, 0, self.glass_shadow_alpha))
            p.save()
            clip = QPainterPath(); clip.addRect(body); p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawRect(body)
            p.restore()

        # Outline
        p.setPen(QPen(_c(self.outline_color), self.outline_width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(body.left(), body.top()), QPointF(body.left(), body.bottom()))
        p.drawLine(QPointF(body.right(), body.top()), QPointF(body.right(), body.bottom()))
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
                p.drawLine(QPointF(body.right() + 4, y), QPointF(body.right() + 4 + length, y))
                if major:
                    val = self._min + frac * span
                    p.drawText(QRectF(body.right() + 16, y - 8, 60, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.scale_format.format(val))

        # Text
        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size); f.setBold(self.label_bold)
        p.setFont(f)
        p.drawText(QRectF(0, 6, self.width(), 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.label)

        if self.show_value:
            p.setPen(_c(self.value_color))
            f.setPointSize(self.value_font_size); f.setBold(self.value_bold)
            p.setFont(f)
            txt = self.value_format.format(self._value) + self.unit_separator + self.unit
            p.drawText(QRectF(body.left(), body.center().y() - 15, body.width(), 30), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, txt)
        
        p.end()


# ============================================================
#  Bar Gauge (Horizontal) — Square corners + 10px side padding
# ============================================================
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

        kwargs.setdefault("width", 350)
        kwargs.setdefault("height", 85)
        super().__init__(parent, **kwargs)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        ratio = 0.0 if self._max <= self._min else max(0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))

        # 1. Top Labels (10px margin left/right)
        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(10, 0, w - 20, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)

        val_txt = f"{self.value_format.format(self._value)} {self.unit}"
        p.drawText(QRectF(10, 0, w - 20, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val_txt)

        # 2. Strict Bar Area (10px left/right padding)
        pad_x = 10
        bar_w = w - pad_x * 2
        bar_y = 22
        bar_h = max(10, h - bar_y - 22 - 2)
        
        bar_rect = QRectF(pad_x, bar_y, bar_w, bar_h)
        
        # Background bar (Square corners, NO roundedRect)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(self.bg_color))
        p.drawRect(bar_rect)

        if ratio > 0:
            fill_rect = QRectF(pad_x, bar_y, bar_w * ratio, bar_h)
            grad = QLinearGradient(fill_rect.left(), 0, fill_rect.right(), 0)
            c = _c(self.color)
            grad.setColorAt(0.0, c.darker(110))
            grad.setColorAt(1.0, c)
            p.setBrush(QBrush(grad))
            p.drawRect(fill_rect)

        # 3. Ticks (Strictly below the bar)
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
                    p.drawText(QRectF(x - 25, tick_y + 3, 50, 16), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.tick_label_format.format(val))
                    p.setPen(QPen(_c(self.tick_color), 1))
                    
        p.end()


# ============================================================
#  Progress Bar (Loading)
# ============================================================
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
        ratio = 0.0 if self._max <= self._min else max(0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))

        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(10, 0, w - 20, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)

        if self.show_value:
            val_txt = self.value_format.format(self._value) + self.unit
            p.drawText(QRectF(10, 0, w - 20, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val_txt)

        pad_x = 10
        bar_y = 24
        bar_w = w - pad_x * 2
        bar_h = h - bar_y
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c(self.bg_color))
        p.drawRoundedRect(QRectF(pad_x, bar_y, bar_w, bar_h), bar_h/2, bar_h/2)

        if ratio > 0:
            fill_rect = QRectF(pad_x, bar_y, max(bar_h, bar_w * ratio), bar_h)
            grad = QLinearGradient(fill_rect.left(), 0, fill_rect.right(), 0)
            c = _c(self.color)
            grad.setColorAt(0.0, c.darker(110))
            grad.setColorAt(1.0, c)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill_rect, bar_h/2, bar_h/2)
            
        p.end()


# ============================================================
#  Line Graph (Real-time Chart)
# ============================================================
class LineGraph(BaseGauge):
    def __init__(self, parent=None, **kwargs):
        self.label = "SIGNAL"
        self.label_color = QColor(255, 255, 255)
        self.label_font_size = 9
        self.bg_color = QColor(21, 21, 26)
        self.border_color = QColor(63, 63, 78)
        self.show_shadow = False
        self.unit = ""
        self.value_format = "{:.1f}"
        self.auto_range = True
        
        _initial_series = kwargs.pop("series", None) or [{"name": "Series 1", "color": "#ef476f"}]
        self._series_keys = [s["name"] for s in _initial_series]
        self.series = list(_initial_series)

        self.max_points = kwargs.pop("max_points", 50)
        self._history = []
        
        kwargs.setdefault("width", 350)
        kwargs.setdefault("height", 200)
        super().__init__(parent, **kwargs)

        self._rebuild_history()
        self.valueChanged.connect(self._record_value)

    def _rebuild_history(self):
        self._history = []
        for _ in self.series:
            d = deque(maxlen=self.max_points)
            for _ in range(self.max_points):
                d.append(0.0)
            self._history.append(d)

    def set_series_keys(self, keys, colors: list = None):
        if isinstance(keys, str):
            keys = [k.strip().upper() for k in keys.split(",") if k.strip()]
        elif not keys:
            keys = ["Series 1"]

        default_colors = ["#ef476f", "#06d6a0", "#118ab2", "#ffd166", "#f4a261", "#8338ec"]
        self._series_keys = list(keys)
        self.series = []
        for i, k in enumerate(keys):
            color = (colors[i] if colors and i < len(colors) else default_colors[i % len(default_colors)])
            self.series.append({"name": k, "color": color})
            
        self._rebuild_history()
        self.update()

    def _record_value(self, v):
        if self._history:
            self._history[0].append(v)
            self.update()

    def set_series_value(self, index: int, value: float):
        if 0 <= index < len(self._history):
            self._history[index].append(value)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        margin = 10
        plot_rect = QRectF(margin + 30, margin + 20, w - margin * 2 - 30, h - margin * 2 - 20)

        p.setPen(QPen(_c(self.border_color), 1))
        p.setBrush(_c(self.bg_color))
        p.drawRoundedRect(plot_rect, 4, 4)

        p.setPen(_c(self.label_color))
        f = QFont(); f.setPointSize(self.label_font_size); f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, w, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)
        p.drawText(QRectF(0, 0, w, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self.value_format.format(self._value)} {self.unit}")

        all_vals = []
        for hist in self._history:
            all_vals.extend(hist)
        if all_vals and self.auto_range:
            lo = min(all_vals); hi = max(all_vals)
            if hi == lo: hi += 1.0
            span = hi - lo
            pad = span * 0.1
            lo -= pad; hi += pad; span = hi - lo
        else:
            lo = self._min; hi = self._max; span = hi - lo

        f.setPointSize(8); p.setFont(f); p.setPen(QColor(120, 120, 130))
        p.drawText(QRectF(0, plot_rect.top() - 8, 28, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{hi:.1f}")
        p.drawText(QRectF(0, plot_rect.bottom() - 8, 28, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{lo:.1f}")

        for i, series_cfg in enumerate(self.series):
            if i >= len(self._history): break
            hist = self._history[i]
            if len(hist) < 2: continue
            
            path = QPainterPath()
            for j, val in enumerate(hist):
                x = plot_rect.left() + (j / (self.max_points - 1)) * plot_rect.width()
                ratio = 0.0 if span <= 0 else max(0.0, min(1.0, (val - lo) / span))
                y = plot_rect.bottom() - ratio * plot_rect.height()
                if j == 0: path.moveTo(x, y)
                else: path.lineTo(x, y)
                
            color = _c(series_cfg.get("color", "#ffffff"))
            p.setPen(QPen(color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        if len(self.series) > 1:
            f.setPointSize(8); p.setFont(f)
            x_offset = plot_rect.left() + 5
            y_offset = plot_rect.bottom() - 15
            for i, series_cfg in enumerate(self.series):
                color = _c(series_cfg.get("color", "#ffffff"))
                name = series_cfg.get("name", f"S{i+1}")
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(color)
                p.drawRect(QRectF(x_offset, y_offset, 10, 10))
                p.setPen(QColor(200, 200, 200))
                p.drawText(QRectF(x_offset + 15, y_offset - 3, 60, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
                x_offset += 70
        p.end()
        
# ============================================================
#  Plain Label (Text Only)
# ============================================================
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