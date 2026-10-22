from PyQt6.QtCore import QFile, QTextStream
from PyQt6.QtWidgets import QWidget


def apply_stylesheet(widget: QWidget, path: str):
    qss_file = QFile(path)
    if qss_file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
        widget.setStyleSheet(QTextStream(qss_file).readAll())
