from PyQt6.QtWidgets import  QWidget, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor


class DashboardCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.guides = [] 
        self.setStyleSheet("background-color: #15151a;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(800, 600)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        
        painter.setPen(QPen(QColor("#7272c2"), 1, Qt.PenStyle.DotLine))
        for x in range(0, self.width(), 20):
            painter.drawLine(int(x), 0, int(x), int(self.height()))
        for y in range(0, self.height(), 20):
            painter.drawLine(0, int(y), int(self.width()), int(y))

        if self.guides:
            painter.setPen(QPen(QColor("#00ffff"), 1, Qt.PenStyle.DashLine))
            for (x1, y1, x2, y2) in self.guides:
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))