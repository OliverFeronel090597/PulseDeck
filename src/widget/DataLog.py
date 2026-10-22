from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import  QTimer, QEvent

class DataLog(QDialog):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.setInterval(5000)
        self._fade_timer.timeout.connect(self._apply_fade)
        
    def _apply_fade(self):
        if not self.isActiveWindow() and self.isVisible():
            self.setWindowOpacity(0.5)
            
    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._fade_timer.stop()
                self.setWindowOpacity(1.0)
            else:
                self._fade_timer.start()
        super().changeEvent(event)

