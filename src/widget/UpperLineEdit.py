from PyQt6.QtWidgets import QLineEdit

class UpperLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.textChanged.connect(self._force_upper)
    def _force_upper(self, text):
        upper = text.upper()
        if text != upper:
            self.blockSignals(True)
            self.setText(upper)
            self.blockSignals(False)