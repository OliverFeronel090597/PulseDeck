from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QMessageBox
from PyQt6.QtCore import  QTimer, QEvent
from PyQt6.QtGui import QFont


class ArduinoCodeDialog(QDialog):
    def __init__(self, tx_keys, rx_keys, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Arduino Reference Code")
        self.resize(800, 700)
        # self.setStyleSheet(APP_QSS)
        layout = QVBoxLayout(self)
        info = QLabel("Copy this sketch to your Arduino.")
        info.setStyleSheet("color: #06d6a0; padding: 10px;")
        layout.addWidget(info)
        rx_decl = "\n".join([f'float val_{k.lower()} = 0.0;' for k in rx_keys]) or "// no values"
        read_blocks = ""
        for k in tx_keys:
            read_blocks += f'\n    if (key == "{k}") {{ val_{k.lower()} = val; }}'
        out_line = " ".join([f'"{k}:" + String(val_{k.lower()}) + ","' for k in rx_keys]) or '""'
        out_line = f"Serial.println(String({out_line[:-1] if out_line.endswith(',') else out_line}));"
        code = f'''// Auto-generated Sketch
String inputString = "";
bool stringComplete = false;
{rx_decl}

void setup() {{ Serial.begin(115200); inputString.reserve(200); }}
void loop() {{
  if (stringComplete) {{
    inputString.trim();
    int eq = inputString.indexOf('=');
    if (eq > 0) {{
      String key = inputString.substring(0, eq);
      key.toUpperCase();
      float val = inputString.substring(eq + 1).toFloat();
      {read_blocks if read_blocks else "// none"}
    }}
    inputString = "";
    stringComplete = false;
  }}
  static unsigned long lastSend = 0;
  if (millis() - lastSend > 100) {{ lastSend = millis(); {out_line} }}
}}
void serialEvent() {{
  while (Serial.available()) {{
    char inChar = (char)Serial.read();
    if (inChar == '\\n') stringComplete = true;
    else inputString += inChar;
  }}
}}'''
        self.code_edit = QPlainTextEdit()
        self.code_edit.setPlainText(code)
        self.code_edit.setFont(QFont("Consolas", 9))
        layout.addWidget(self.code_edit)
        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy")
        btn_copy.setObjectName("codeBtn")
        btn_copy.clicked.connect(self._copy)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_copy)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
    def _copy(self):
        QApplication.clipboard().setText(self.code_edit.toPlainText())
        QMessageBox.information(self, "Copied", "Copied.")