import os
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QFont, QFontDatabase, QColor
from PyQt6.QtCore import Qt, QSize

class SevenSegmentDisplay(QWidget):
    def __init__(self, data_key, label, unit="", width=250, height=120, **kwargs):
        super().__init__()
        self.data_key = data_key
        self.label = label
        self.unit = unit
        
        # Values
        self._val = 0.0
        self._max = kwargs.get("maximum", 100.0)
        self._min = kwargs.get("minimum", 0.0)
        
        # Colors (matching the color picker expectations)
        self.label_color = QColor("#c8c8c8")
        self.segment_color = QColor("#00ff00")  # Bright Green
        self.bg_color = QColor("#15151a")
        self.unit_color = QColor("#06d6a0")

        # Set a base minimum size for the DraggableWrapper
        self.setMinimumSize(150, 80) 
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)
        
        # Widget Label (e.g., "SPEED")
        self.lbl_name = QLabel(f"{self.label}")
        self.lbl_name.setStyleSheet(f"color: {self.label_color.name()}; background: transparent; font-family: Consolas; font-size: 10pt; font-weight: bold; border: none;")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # 7-Segment Value Display
        self.lbl_value = QLabel("0.0")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # CRITICAL: 'border: none' prevents the QSS from adding padding that breaks the font
        self.lbl_value.setStyleSheet(f"color: {self.segment_color.name()}; background: transparent; border: none;")
        
        # Load the custom font
        self.font_family = self._load_font()
        self._update_value_font()

        self.layout.addWidget(self.lbl_name)
        self.layout.addWidget(self.lbl_value, 1)

    def _load_font(self):
        """Loads the 7-Segment font from the src/fonts folder."""
        # Build the absolute path to the font file
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Note: Ensure this path matches exactly where you saved the file
        font_path = os.path.join(base_dir, "src", "fonts", "seven-segment", "7 Segment.ttf")
        font_path = os.path.normpath(font_path)
        
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
                
        print(f"[WARNING] 7-Segment font not found at {font_path}. Using fallback.")
        return "Consolas"

    def _update_value_font(self):
        """Updates the font size dynamically based on the widget's height."""
        # Prevent tiny fonts by enforcing a minimum calculation size
        h = max(self.height(), 80)
        
        # The 7-seg font looks best when the size is proportional to the height
        # We use 0.6 to make it large enough to fill the box
        size = int(h * 0.55)
        
        # We must use setStyleSheet here to override the global QSS
        self.lbl_value.setStyleSheet(
            f"color: {self.segment_color.name()}; "
            f"background: transparent; "
            f"font-family: '{self.font_family}'; "
            f"font-size: {size}px; "
            f"border: none;"
        )

    def sizeHint(self):
        """Tells the layout the default preferred size"""
        return QSize(250, 120)

    def minimumSizeHint(self):
        """Tells the DraggableWrapper the absolute minimum size it can shrink to"""
        return QSize(120, 80)

    def setValue(self, val):
        self._val = float(val)
        # Format the string (keeps 1 decimal place)
        self.lbl_value.setText(f"{self._val:.1f}")

    def resizeEvent(self, event):
        """Recalculate font size when widget resizes"""
        super().resizeEvent(event)
        self._update_value_font()

    def update_rx(self, val_str):
        try:
            self.setValue(float(val_str))
        except ValueError:
            pass