"""
BaseGauge — shared base class for every gauge widget.

Provides:
    - value / minimum / maximum as Qt properties (animatable)
    - data_key, unit, label attributes used by PulseDeck
    - animation helper (animateTo)
    - optional lock + size grip behaviour
    - _min / _max shims for backwards compatibility with MainWindow
"""

import math
from typing import Union, Tuple

from PyQt6.QtWidgets import QWidget, QSizePolicy, QSizeGrip
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, pyqtProperty, pyqtSignal,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import QColor

ColorLike = Union[QColor, str, Tuple[int, int, int]]


def _c(value: ColorLike) -> QColor:
    """Coerce a colour-like value (QColor / str / (r,g,b)) to QColor."""
    if isinstance(value, QColor):
        return value
    if isinstance(value, tuple) and len(value) == 3:
        return QColor(*value)
    return QColor(value)


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
        self.unit = kwargs.pop("unit", "")
        self.label = kwargs.pop("label", "")

        self._is_locked = False
        self._resize_grip = None

        # Apply any remaining attributes that exist on this instance
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

        self.setMinimumSize(100, 80)
        self.resize(w, h)

        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # --- Value / range -------------------------------------------------
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
        if self._value < self._min:
            self.setValue(self._min)
        self.update()

    def getMax(self): return self._max

    def setMax(self, v):
        self._max = float(v)
        if self._value > self._max:
            self.setValue(self._max)
        self.update()

    value   = pyqtProperty(float, getValue, setValue)
    minimum = pyqtProperty(float, getMin,   setMin)
    maximum = pyqtProperty(float, getMax,   setMax)

    # --- Animation -----------------------------------------------------
    def animateTo(self, val, ms=None):
        self._anim.stop()
        self._anim.setDuration(ms if ms is not None else self.animation_ms)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(max(self._min, min(float(val), self._max)))
        self._anim.start()

    # --- Lock / resize grip -------------------------------------------
    def set_locked(self, locked: bool):
        self._is_locked = locked
        if locked:
            self.setSizePolicy(QSizePolicy.Policy.Fixed,
                               QSizePolicy.Policy.Fixed)
            self.setFixedSize(self.width(), self.height())
            if self._resize_grip:
                self._resize_grip.hide()
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Expanding)
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
                self.height() - self._resize_grip.height() - 2,
            )