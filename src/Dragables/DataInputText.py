from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QPushButton, QWidget

# This only imports for type-hinting, it prevents circular import crashes
if TYPE_CHECKING:
    from main import MainWindow

class DataInputText(QWidget):
    # Now 'main_window' has full autocomplete and type checking!
    def __init__(self, main_window: "MainWindow", data_key: str, label_text: str):
        super().__init__()
        self.main: "MainWindow" = main_window
        self.data_key = data_key
        self.label_text = label_text
        
        self.setFixedSize(250, 75)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        self.lbl = QLabel(f"[{label_text}]")
        self.lbl.setStyleSheet("color: #06d6a0; font-weight: bold; font-size: 11pt; border: 1px solid #06d6a0; background-color: #15151a; border-radius: 4px; padding: 2px 4px;")
        
        input_layout = QHBoxLayout()
        self.line = QLineEdit()
        self.line.setPlaceholderText("TX data...")
        self.line.textChanged.connect(self._check_text)
        
        self.btn = QPushButton("Send")
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self._send)
        
        input_layout.addWidget(self.line)
        input_layout.addWidget(self.btn)
        
        layout.addWidget(self.lbl)
        layout.addLayout(input_layout)

    def _check_text(self):
        self.btn.setEnabled(len(self.line.text().strip()) > 0)

    def _send(self):
        text = self.line.text().strip()
        if text:
            # This will now work perfectly because self.main is typed as MainWindow
            self.main.send_uart_command(f"{self.data_key}={text}")

    def update_rx(self, val_str):
        if not self.line.hasFocus():
            self.line.blockSignals(True)
            self.line.setText(val_str)
            self.line.blockSignals(False)
            self._check_text()