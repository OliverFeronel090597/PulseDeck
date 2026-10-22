"""LineGraph — real-time multi-series rolling chart."""

from collections import deque

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath

from src.Dragables.BaseGauge import BaseGauge, _c


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