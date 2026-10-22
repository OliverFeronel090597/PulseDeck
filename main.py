"""
PulseDeck - UART Dashboard & Simulator
======================================
Developer: Oliver Feronel
Run from `src/`:
    python main.py
"""

import sys
import os
import math
import random
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QGroupBox,
    QDoubleSpinBox, QSpinBox, QFrame, QListWidget, QListWidgetItem, QMessageBox, QDialog,
    QFormLayout, QColorDialog, QTabWidget, QInputDialog, QFileDialog, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QIODevice, QRect, QSettings, QSize
from PyQt6.QtGui import QFont, QColor, QAction, QIcon
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo

# Gauges and widgets (Separated imports)
from src.Dragables.MultiTypeGauge   import CircularDial
from src.Dragables.MultiTypeGauge   import CylinderGauge
from src.Dragables.MultiTypeGauge   import BarGauge
from src.Dragables.MultiTypeGauge   import ProgressBar
from src.Dragables.MultiTypeGauge   import LineGraph
from src.Dragables.MultiTypeGauge   import PlainLabel
from src.Dragables.DataInputText       import DataInputText
from src.Dragables.SevenSegmentDisplay import SevenSegmentDisplay
from src.Dragables.Thermometer         import Thermometer

# Widgets and utilities
from src.widget.UpperLineEdit       import UpperLineEdit
from src.widget.DashboardCanvas     import DashboardCanvas
from src.widget.ArduinoCodeDialog   import ArduinoCodeDialog
from src.widget.DataLog             import DataLog
from src.widget.DraggableWrapper    import DraggableWrapper

from src.style.StyleUtils           import apply_stylesheet

DATA_FILE = "dashboard.json"


class MainWindow(QMainWindow):
    """Main application window: toolbar, dashboard canvas, floating tools/log panels,
    project storage, UART connection and the data simulator."""

    def __init__(self):
        """Create the window, set up serial port and simulator timer, build the UI,
        restore saved layout, and load the last used project."""
        super().__init__()
        self.setWindowTitle("PulseDeck")
        self.setWindowIcon(QIcon("src/PulseDeck.png"))
        self.resize(1400, 850)
        apply_stylesheet(self, "src/style/styles.qss")
        
        self.gauge_map = {}
        self.is_layout_locked = False
        self.selected_wrapper = None
        self.current_project = None
        self.is_rx_paused = False
        self.settings = QSettings("UARTDashboard", "MainWindow")
        
        # State flags for deferred loading
        self._pending_project = None
        self._is_loading = False
        
        if not os.path.exists(DATA_FILE):
            self._write_data({
                "last_project": None,
                "projects": {}
            })
        
        self.serial = QSerialPort(self)
        self.serial.readyRead.connect(self._read_serial)
        self.sim_timer = QTimer(self)
        self.sim_timer.setInterval(50)
        self.sim_timer.timeout.connect(self._simulate_data)
        self.sim_time = 0.0
        self.is_connected = False

        self._build_ui()
        self._create_menus()
        self._restore_layout_state()
        
        self._refresh_ports()
        self._refresh_project_list()
        
        data = self._read_data()
        last = data.get("last_project")
        names = list(data.get("projects", {}).keys())
        
        if last in names:
            self.current_project = last
            self.project_combo.blockSignals(True)
            self.project_combo.setCurrentText(last)
            self.project_combo.blockSignals(False)
            self._pending_project = last
            self._update_project_state()
        else:
            self.current_project = None
            self._update_project_state()

    def showEvent(self, event):
        """Defer initial project loading until the window is shown so the canvas
        has its correct final size and widgets don't get clamped to (0,0)."""
        super().showEvent(event)
        if getattr(self, "_pending_project", None):
            proj = self._pending_project
            self._pending_project = None
            self._load_project(proj)

    def _get_widget_name(self, w):
        """Return the display name of a widget, reading the attribute that its type uses."""
        if isinstance(w, PlainLabel): return getattr(w, "label_text_name", "")
        if isinstance(w, DataInputText): return getattr(w, "label_text", "")
        if isinstance(w, SevenSegmentDisplay): return getattr(w, "label", "")
        return getattr(w, "label", "")

    def _set_widget_name(self, w, name):
        """Set the display name of a widget and refresh whichever label shows it."""
        if isinstance(w, PlainLabel):
            w.label_text_name = name
            w.text = f"[{name}: 0]"
        elif isinstance(w, DataInputText):
            w.label_text = name
            if hasattr(w, "lbl"): w.lbl.setText(f"[{name}]")
        elif isinstance(w, SevenSegmentDisplay):
            if hasattr(w, "lbl_name"): w.lbl_name.setText(name)
            w.label = name
        elif hasattr(w, "label"):
            w.label = name

    def _read_data(self) -> dict:
        """Load dashboard.json and return it as a dict, with defaults if the file is
        missing, corrupt or the wrong shape."""
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data.setdefault("last_project", None)
            data.setdefault("projects", {})
            return data
        except Exception:
            return {"last_project": None, "projects": {}}

    def _write_data(self, data):
        """Write the data dict to dashboard.json, keeping a .bak copy of the previous file."""
        try:
            import shutil
            if os.path.exists(DATA_FILE):
                shutil.copy(DATA_FILE, DATA_FILE + ".bak")
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self._log("Data saved to " + DATA_FILE)
        except Exception as e:
            self._log(f"Save error: {e}")

    def _build_ui(self):
        """Build the control toolbar, dashboard canvas, floating Tools window (builder and
        color tabs) and floating Raw UART Log window, and assemble the central layout."""
        top_box = QGroupBox("Control")
        top_layout = QHBoxLayout(top_box)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(8)
        
        top_layout.addWidget(QLabel("Project:"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(150)
        self.project_combo.currentTextChanged.connect(self._on_project_changed)
        top_layout.addWidget(self.project_combo)
        
        self.btn_new_proj = QPushButton("New"); self.btn_new_proj.setObjectName("projBtn")
        self.btn_new_proj.clicked.connect(self._new_project); top_layout.addWidget(self.btn_new_proj)
        self.btn_del_proj = QPushButton("Del"); self.btn_del_proj.setObjectName("delBtn")
        self.btn_del_proj.clicked.connect(self._delete_project); top_layout.addWidget(self.btn_del_proj)
        self.btn_import = QPushButton("Import"); self.btn_import.clicked.connect(self._import_json)
        top_layout.addWidget(self.btn_import)
        self.btn_export = QPushButton("Export"); self.btn_export.clicked.connect(self._export_current)
        top_layout.addWidget(self.btn_export)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.Shape.VLine); sep1.setFrameShadow(QFrame.Shadow.Sunken)
        top_layout.addWidget(sep1)

        top_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox(); self.port_combo.setMinimumWidth(100)
        top_layout.addWidget(self.port_combo)
        
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("115200"); self.baud_combo.setFixedWidth(90)
        top_layout.addWidget(self.baud_combo)
        
        self.btn_refresh = QPushButton("⟳"); self.btn_refresh.setFixedWidth(30)
        self.btn_refresh.clicked.connect(self._refresh_ports); top_layout.addWidget(self.btn_refresh)
        
        self.btn_connect = QPushButton("Connect"); self.btn_connect.setCheckable(True)
        self.btn_connect.toggled.connect(self._toggle_connection)
        top_layout.addWidget(self.btn_connect)

        self.btn_pause_rx = QPushButton("Pause RX"); self.btn_pause_rx.setObjectName("pauseBtn")
        self.btn_pause_rx.setCheckable(True)
        self.btn_pause_rx.toggled.connect(self._toggle_pause_rx)
        top_layout.addWidget(self.btn_pause_rx)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine); sep2.setFrameShadow(QFrame.Shadow.Sunken)
        top_layout.addWidget(sep2)

        self.btn_lock = QPushButton("Lock Layout"); self.btn_lock.setCheckable(True)
        self.btn_lock.setObjectName("lockBtn"); self.btn_lock.toggled.connect(self._toggle_global_lock)
        top_layout.addWidget(self.btn_lock)
        
        self.btn_send_all = QPushButton("Send All TX"); self.btn_send_all.setObjectName("sendAllBtn")
        self.btn_send_all.clicked.connect(self._send_all_tx); top_layout.addWidget(self.btn_send_all)

        self.btn_gen_code = QPushButton("Arduino Code"); self.btn_gen_code.setObjectName("codeBtn")
        self.btn_gen_code.clicked.connect(self._gen_arduino_code); top_layout.addWidget(self.btn_gen_code)

        self.btn_show_tools = QPushButton("🛠 Tools")
        self.btn_show_tools.clicked.connect(self._toggle_tools_window)
        top_layout.addWidget(self.btn_show_tools)

        self.btn_show_log = QPushButton("📜 Log")
        self.btn_show_log.clicked.connect(self._toggle_log_window)
        top_layout.addWidget(self.btn_show_log)

        top_layout.addStretch(1)
        self.btn_simulate = QPushButton("Start Receive (Sim)"); self.btn_simulate.setCheckable(True)
        self.btn_simulate.toggled.connect(self._toggle_simulation); top_layout.addWidget(self.btn_simulate)

        self.canvas = DashboardCanvas()
        
        self.tools_window = DataLog(self, "Tools")
        self.tools_window.resize(320, 650)
        
        self.dock_tabs = QTabWidget()

        # Build the Builder tab; it adds itself directly to dock_tabs.
        self._build_builder_panel()

        self.tab_colors = QWidget()
        self.color_layout = QVBoxLayout(self.tab_colors)
        self.color_layout.setContentsMargins(10, 10, 10, 10)
        self.color_buttons = {}
        self.color_layout.addWidget(QLabel("Select a widget on the canvas to edit colors."))
        self.color_layout.addStretch()
        
        self.dock_tabs.addTab(self.tab_colors, "Colors")
        
        tools_layout = QVBoxLayout(self.tools_window)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.addWidget(self.dock_tabs)

        self.log_window = DataLog(self, "Raw UART Log")
        self.log_window.resize(600, 300)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self.log_text.clear)
        
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(5, 5, 5, 5)
        log_layout.addWidget(self.log_text)
        log_layout.addWidget(btn_clear_log, 0, Qt.AlignmentFlag.AlignRight)
        
        self.log_window.setLayout(QVBoxLayout())
        self.log_window.layout().setContentsMargins(0,0,0,0)
        self.log_window.layout().addWidget(log_widget)

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(top_box)
        main_layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

    def resizeEvent(self, event):
        """Keep every dashboard widget inside the canvas when the window is resized."""
        super().resizeEvent(event)
        
        # Do not clamp widgets while a project is actively being loaded
        if getattr(self, "_is_loading", False):
            return
            
        for wrap in self.gauge_map.values():
            nx = min(wrap.x(), self.canvas.width() - wrap.width())
            ny = min(wrap.y(), self.canvas.height() - wrap.height())
            if nx != wrap.x() or ny != wrap.y():
                wrap.move(max(0, nx), max(0, ny))

    def _create_menus(self):
        """Create the File, View and Help menus and connect their actions."""
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False) 
        
        file_menu = menubar.addMenu("&File")
        action_new = QAction("New Project", self)
        action_new.triggered.connect(self._new_project)
        file_menu.addAction(action_new)
        
        action_del = QAction("Delete Project", self)
        action_del.triggered.connect(self._delete_project)
        file_menu.addAction(action_del)
        
        file_menu.addSeparator()
        
        action_import = QAction("Import Project", self)
        action_import.triggered.connect(self._import_json)
        file_menu.addAction(action_import)
        
        action_export = QAction("Export Project", self)
        action_export.triggered.connect(self._export_current)
        file_menu.addAction(action_export)
        
        file_menu.addSeparator()
        
        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        view_menu = menubar.addMenu("&View")
        
        self.action_tools = QAction("Tools Panel", self)
        self.action_tools.setCheckable(True)
        self.action_tools.setChecked(True)
        self.action_tools.triggered.connect(self._toggle_tools_window)
        view_menu.addAction(self.action_tools)
        
        self.action_log = QAction("Raw UART Log", self)
        self.action_log.setCheckable(True)
        self.action_log.setChecked(True)
        self.action_log.triggered.connect(self._toggle_log_window)
        view_menu.addAction(self.action_log)

        help_menu = menubar.addMenu("&Help")
        action_about = QAction("About", self)
        action_about.triggered.connect(self._show_about)
        help_menu.addAction(action_about)

    def _show_about(self):
        """Show the About dialog with the app description, features and developer credit."""
        QMessageBox.about(self, "About PulseDeck", 
                          "<h3>PulseDeck v1.0</h3>"
                          "<p>A powerful, highly customizable UART Dashboard & Simulator.</p>"
                          "<p><b>Features:</b></p>"
                          "<ul>"
                          "<li>Multi-project support</li>"
                          "<li>Live UART data parsing & simulation</li>"
                          "<li>Dynamic MS Word-style alignment guides</li>"
                          "<li>Floating tool & log panels with smart opacity</li>"
                          "<li>Auto-generated Arduino reference code</li>"
                          "</ul>"
                          "<p><b>Developer:</b> Oliver Feronel</p>"
                          "<p>Built with PyQt6.</p>")

    def _toggle_tools_window(self):
        """Show or hide the floating Tools window and sync the View menu check mark."""
        if self.tools_window.isVisible():
            self.tools_window.hide()
            self.action_tools.setChecked(False)
        else:
            self.tools_window.show()
            self.tools_window.raise_()
            self.tools_window.activateWindow()
            self.action_tools.setChecked(True)

    def _toggle_log_window(self):
        """Show or hide the floating Raw UART Log window and sync the View menu check mark."""
        if self.log_window.isVisible():
            self.log_window.hide()
            self.action_log.setChecked(False)
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()
            self.action_log.setChecked(True)

    def _restore_layout_state(self):
        """Restore saved window geometry and the visibility of the Tools and Log windows
        from QSettings."""
        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        if self.settings.contains("tools_geom"):
            self.tools_window.restoreGeometry(self.settings.value("tools_geom"))
        if self.settings.contains("log_geom"):
            self.log_window.restoreGeometry(self.settings.value("log_geom"))
        
        if self.settings.contains("tools_visible"):
            if self.settings.value("tools_visible", type=bool):
                self.tools_window.show()
                self.action_tools.setChecked(True)
            else:
                self.tools_window.hide()
                self.action_tools.setChecked(False)
        else:
            self.tools_window.show()
            
        if self.settings.contains("log_visible"):
            if self.settings.value("log_visible", type=bool):
                self.log_window.show()
                self.action_log.setChecked(True)
            else:
                self.log_window.hide()
                self.action_log.setChecked(False)

    def _build_builder_panel(self):
        """Build the Builder tab (add/edit widget form and signal registry list) and add
        it directly to the Tools tab widget."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.edit_box = QGroupBox("Add New Widget")
        edit_layout = QFormLayout(self.edit_box)
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "CircularDial", "CylinderGauge", "BarGauge", "ProgressBar", 
            "PlainLabel", "DataInputText", "LineGraph", 
            "SevenSegmentDisplay", "Thermometer"
        ])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.name_input = UpperLineEdit(); self.name_input.setPlaceholderText("Display Name")
        self.name_input.textChanged.connect(self._on_name_changed)
        self.key_input = UpperLineEdit(); self.key_input.setPlaceholderText("Data Key")
        self.unit_input = UpperLineEdit(); self.unit_input.setPlaceholderText("e.g. km/h")
        self.min_input = QDoubleSpinBox(); self.min_input.setRange(-99999, 99999)
        self.max_input = QDoubleSpinBox(); self.max_input.setRange(-99999, 99999); self.max_input.setValue(100)
        self.signals_input = UpperLineEdit(); self.signals_input.setPlaceholderText("Signal1, Signal2...")
        
        self.width_input = QSpinBox(); self.width_input.setRange(100, 2000); self.width_input.setValue(250)
        self.height_input = QSpinBox(); self.height_input.setRange(60, 2000); self.height_input.setValue(250)
        
        edit_layout.addRow("Widget Type:", self.type_combo)
        edit_layout.addRow("Display Name:", self.name_input)
        edit_layout.addRow("Data Key:", self.key_input)
        edit_layout.addRow("Unit:", self.unit_input)
        edit_layout.addRow("Min Value:", self.min_input)
        edit_layout.addRow("Max Value:", self.max_input)
        edit_layout.addRow("Graph Signals:", self.signals_input)
        edit_layout.addRow("Width:", self.width_input)
        edit_layout.addRow("Height:", self.height_input)
        
        self.extra_fields = [self.unit_input, self.min_input, self.max_input, self.signals_input]
        for f in self.extra_fields: self._hide_row(f)
        
        self.btn_action = QPushButton("Add Widget")
        self.btn_action.clicked.connect(self._action_clicked)
        self.btn_cancel = QPushButton("Cancel Edit")
        self.btn_cancel.clicked.connect(self._clear_selection)
        self.btn_cancel.hide()
        
        edit_layout.addRow(self.btn_action)
        edit_layout.addRow(self.btn_cancel)
        layout.addWidget(self.edit_box)

        list_box = QGroupBox("Signal Registry")
        list_layout = QVBoxLayout(list_box)
        self.signal_list = QListWidget()
        self.signal_list.itemClicked.connect(self._list_item_clicked)
        list_layout.addWidget(self.signal_list)
        layout.addWidget(list_box)

        # Add the built panel straight to the Tools tab widget.
        self.dock_tabs.addTab(panel, "Builder")

        # Initialize the form for the default widget type so the correct optional
        # rows (unit / min / max, etc.) are visible immediately on startup.
        self._on_type_changed(self.type_combo.currentText())

    def _on_type_changed(self, text):
        """Update the key placeholder and the visible form fields when the widget type changes."""
        self.key_input.setPlaceholderText("Keys (TEMP,PRES)" if text == "LineGraph" else "Key")
        self._show_hide_fields(text)

    def _show_hide_fields(self, g_type):
        """Show only the optional form rows (unit, min, max, signals) that the given widget
        type uses."""
        for f in self.extra_fields: self._hide_row(f)
        
        if g_type in ["CircularDial", "CylinderGauge", "BarGauge", "ProgressBar", "SevenSegmentDisplay", "Thermometer"]:
            self._show_row(self.unit_input)
            self._show_row(self.min_input)
            self._show_row(self.max_input)
        elif g_type == "LineGraph":
            self._show_row(self.signals_input)
            self._show_row(self.min_input)
            self._show_row(self.max_input)
        elif g_type == "PlainLabel":
            self._show_row(self.unit_input)

    def _update_project_state(self):
        """Enable or disable the builder and project buttons depending on whether a
        project is currently selected."""
        valid = bool(self.current_project)
        self.dock_tabs.setEnabled(valid)
        if not valid:
            self._log("No project selected. Create or select one to begin.")
            self.btn_action.setEnabled(False)
            self.btn_del_proj.setEnabled(False)
            self.btn_import.setEnabled(False)
            self.btn_export.setEnabled(False)
        else:
            self.btn_action.setEnabled(True)
            self.btn_del_proj.setEnabled(True)
            self.btn_import.setEnabled(True)
            self.btn_export.setEnabled(True)

    def _refresh_project_list(self):
        """Reload the project dropdown from disk, with a '-- None --' entry first, and
        reselect the current project."""
        data = self._read_data()
        names = sorted(data.get("projects", {}).keys())
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItems(["-- None --"] + names)
        if self.current_project in names:
            self.project_combo.setCurrentText(self.current_project)
        else:
            self.project_combo.setCurrentText("-- None --")
        self.project_combo.blockSignals(False)

    def _on_project_changed(self, name):
        """Save the old project and load the one picked in the dropdown (or clear the
        canvas for '-- None --')."""
        if name == "-- None --":
            if self.current_project:
                self._save_project(self.current_project)
            self.current_project = None
            self._clear_canvas()
            self._update_project_state()
            return
            
        if not name or name == self.current_project:
            return
        if self.current_project:
            self._save_project(self.current_project)
        self.current_project = name
        self._load_project(name)
        self._update_project_state()

    def _new_project(self):
        """Ask for a project name in a dialog, create an empty project with it (rejecting
        duplicates) and switch to it."""
        dlg = QDialog(self)
        dlg.setWindowTitle("New Project")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Project name (CAPS):"))
        line = UpperLineEdit()
        line.setPlaceholderText("PROJECT NAME")
        layout.addWidget(line)
        
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)
        
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
            
        name = line.text().strip().upper()
        if not name: return
        data = self._read_data()
        if name in data["projects"]:
            QMessageBox.warning(self, "Exists", f"'{name}' already exists.")
            return
        
        data["projects"][name] = {"name": name, "widgets": []}
        data["last_project"] = name
        self._write_data(data)
        self.current_project = name
        self._refresh_project_list()
        self._clear_canvas()
        self._update_project_state()
        self._log(f"Created '{name}'.")

    def _delete_project(self):
        """Delete the current project after confirmation, then load another one or clear the
        canvas. 'DEFAULT' and the last remaining project cannot be deleted."""
        name = self.current_project
        if not name: return
        if name == "DEFAULT":
            QMessageBox.warning(self, "Cannot Delete", "'DEFAULT' cannot be deleted.")
            return
        data = self._read_data()
        if len(data["projects"]) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Only project left.")
            return
        reply = QMessageBox.question(self, "Delete", f"Delete '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        del data["projects"][name]
        remaining = sorted(data["projects"].keys())
        data["last_project"] = remaining[0] if remaining else None
        self._write_data(data)
        self.current_project = data["last_project"]
        self._refresh_project_list()
        if self.current_project:
            self._load_project(self.current_project)
        else:
            self._clear_canvas()
        self._update_project_state()
        self._log(f"Deleted '{name}'.")

    def _load_project(self, name):
        """Clear the canvas and rebuild every widget saved in the named project, restoring
        position, size, name, unit, range, colors and graph series."""
        self._is_loading = True
        try:
            self._clear_canvas()
            data = self._read_data()
            proj = data.get("projects", {}).get(name)
            if not proj:
                return
            for item in proj.get("widgets", []):
                keys = item["key"].split(",")
                w_size = item.get("w", 250)
                h_size = item.get("h", 250)
                
                wrap = self.create_widget(item["type"], keys, item.get("name", keys[0]),
                                   item["x"], item["y"], w_size, h_size)
                self._apply_serialized_data(wrap, item)
            self._log(f"Loaded '{name}'.")
            self._update_signal_list()
        finally:
            self._is_loading = False

    def _save_project(self, name):
        """Serialize the widgets on the canvas and store them under the given project name
        as the last used project."""
        if not name: return
        data = self._read_data()
        data["projects"][name] = {"name": name, "widgets": self._serialize_current()}
        data["last_project"] = name
        self._write_data(data)
        self._log(f"Project '{name}' saved.")

    def _serialize_widget(self, wrap):
        """Convert a single widget wrapper to a JSON-ready dict."""
        colors = {}
        w = wrap.widget
        for attr in ["label_color", "unit_color", "color", "bg_color", "pointer_color",
                     "face_color", "face_color_outer", "ring_color", "value_arc_color",
                     "tick_color", "tick_label_color", "center_value_color",
                     "body_color", "body_color_bottom", "rim_color", "outline_color",
                     "liquid_color", "scale_color", "border_color", "segment_color"]:
            if hasattr(w, attr):
                v = getattr(w, attr)
                colors[attr] = v.name() if isinstance(v, QColor) else v
        
        item = {
            "type": wrap.gauge_type, "key": wrap.data_key,
            "name": self._get_widget_name(w),
            "x": wrap.x(), "y": wrap.y(), "w": wrap.width(), "h": wrap.height(),
            "unit": getattr(w, "unit", ""),
            "min": getattr(w, "_min", 0.0), "max": getattr(w, "_max", 100.0),
            "colors": colors
        }
        if isinstance(w, LineGraph):
            item["series"] = w.series
        return item

    def _apply_serialized_data(self, wrap, item):
        """Apply previously serialized data to a newly created widget wrapper."""
        if not wrap: return
        w_size = item.get("w", 250)
        h_size = item.get("h", 250)
        wrap._original_size = QSize(w_size, h_size)
        
        w = wrap.widget
        self._set_widget_name(w, item.get("name", ""))
        if hasattr(w, "unit"): w.unit = item.get("unit", "")
        if hasattr(w, "_min"): w._min = item.get("min", 0.0)
        if hasattr(w, "_max"): w._max = item.get("max", 100.0)
        for attr, color_name in item.get("colors", {}).items():
            if hasattr(w, attr):
                setattr(w, attr, QColor(color_name))
        
        if isinstance(w, LineGraph):
            keys = item["key"].split(",")
            w.set_series_keys(keys)
            series_data = item.get("series", [])
            for i, s in enumerate(series_data):
                if i < len(w.series):
                    w.series[i]["color"] = s.get("color", w.series[i]["color"])
                    w.series[i]["name"] = s.get("name", w.series[i]["name"])
        w.update()

    def _serialize_current(self) -> list:
        """Convert every widget on the canvas into a JSON-ready dict."""
        return [self._serialize_widget(wrap) for wrap in self.gauge_map.values()]

    def _export_current(self):
        """Save the current project to a user-chosen .json file."""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Project", f"{self.current_project}.json", "JSON Files (*.json)")
        if not path: return
        payload = {"name": self.current_project, "widgets": self._serialize_current()}
        try:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
            self._log(f"Exported '{self.current_project}'.")
        except Exception as e:
            self._log(f"Export error: {e}")

    def _import_json(self):
        """Import a project from a .json file (a project dict or a bare widget list),
        renaming it with a _N suffix if the name is taken, and add it to dashboard.json."""
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON Files (*.json)")
        if not path: return
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"Import error: {e}")
            return
        bundle = self._read_data()
        if isinstance(data, dict) and "widgets" in data:
            name = data.get("name", "IMPORTED").upper()
            if name in bundle["projects"]:
                base, i = name, 1
                while f"{base}_{i}" in bundle["projects"]: i += 1
                name = f"{base}_{i}"
            bundle["projects"][name] = {"name": name, "widgets": data["widgets"]}
        elif isinstance(data, list):
            name, ok = QInputDialog.getText(self, "Import", "Save as (CAPS):")
            if not ok or not name.strip(): return
            name = name.strip().upper()
            if name in bundle["projects"]:
                base, i = name, 1
                while f"{base}_{i}" in bundle["projects"]: i += 1
                name = f"{base}_{i}"
            bundle["projects"][name] = {"name": name, "widgets": data}
        else:
            self._log("Unknown format."); return
        self._write_data(bundle)
        self._refresh_project_list()
        self._log(f"Imported.")

    def _gen_arduino_code(self):
        """Collect the RX and TX data keys used by the widgets and open the Arduino
        reference code dialog for them."""
        rx, tx = set(), set()
        for wrap in self.gauge_map.values():
            if isinstance(wrap.widget, LineGraph):
                for k in getattr(wrap.widget, "_series_keys", []): rx.add(k)
            elif isinstance(wrap.widget, DataInputText):
                tx.add(wrap.data_key); rx.add(wrap.data_key)
            elif hasattr(wrap.widget, "data_key") and wrap.widget.data_key:
                rx.add(wrap.widget.data_key)
        if not rx and not tx:
            QMessageBox.warning(self, "No Keys", "Add a widget first."); return
        ArduinoCodeDialog(list(tx), list(rx), self).exec()

    def _on_name_changed(self, text):
        """While adding a new widget, auto-fill the data key from the display name using
        only letters, digits and underscores."""
        if not self.selected_wrapper:
            self.key_input.setText("".join(c for c in text if c.isalnum() or c == "_"))

    def _hide_row(self, w):
        """Hide a form row (its label and field) in the builder form, given the field widget."""
        for i in range(self.edit_box.layout().rowCount()):
            it = self.edit_box.layout().itemAt(i, QFormLayout.ItemRole.FieldRole)
            if it and it.widget() == w:
                self.edit_box.layout().itemAt(i, QFormLayout.ItemRole.LabelRole).widget().hide()
                w.hide(); break

    def _show_row(self, w):
        """Show a form row (its label and field) in the builder form, given the field widget."""
        for i in range(self.edit_box.layout().rowCount()):
            it = self.edit_box.layout().itemAt(i, QFormLayout.ItemRole.FieldRole)
            if it and it.widget() == w:
                self.edit_box.layout().itemAt(i, QFormLayout.ItemRole.LabelRole).widget().show()
                w.show(); break

    def _toggle_global_lock(self, checked):
        """Lock or unlock the dashboard layout; locking also hides the Tools window and
        clears the selection."""
        self.is_layout_locked = checked
        if checked:
            self.btn_lock.setText("Unlock Layout")
            self.btn_lock.setStyleSheet("background-color: #06d6a0; color: #1e1e24;")
            self.tools_window.hide()
            self.action_tools.setChecked(False)
            self._clear_selection()
        else:
            self.btn_lock.setText("Lock Layout")
            self.btn_lock.setStyleSheet("")
            self.tools_window.show()
            self.action_tools.setChecked(True)

    def _select_wrapper(self, wrapper):
        """Select a widget on the canvas and switch the builder form into edit mode,
        filled with that widget's current settings."""
        if wrapper.is_locked: return
        
        self.selected_wrapper = wrapper
        self.edit_box.setTitle("Edit Widget")
        self.btn_action.setText("Save Changes")
        self.btn_cancel.show()
        self.type_combo.setEnabled(False); self.key_input.setEnabled(True)
        
        self.type_combo.setCurrentText(wrapper.gauge_type)
        self._show_hide_fields(wrapper.gauge_type)
        
        w = wrapper.widget
        self.name_input.setText(self._get_widget_name(w))
        self.key_input.setText(wrapper.data_key)
        self.unit_input.setText(getattr(w, "unit", ""))
        if hasattr(w, "_min"): self.min_input.setValue(w._min)
        if hasattr(w, "_max"): self.max_input.setValue(w._max)
        if wrapper.gauge_type == "LineGraph":
            self.signals_input.setText(", ".join(w._series_keys))
            
        self.width_input.setValue(wrapper.width())
        self.height_input.setValue(wrapper.height())
        self._populate_color_tab(wrapper)

    def _clear_selection(self):
        """Deselect the current widget and return the builder form to 'Add New Widget' mode."""
        self.selected_wrapper = None
        self.edit_box.setTitle("Add New Widget")
        self.btn_action.setText("Add Widget")
        self.btn_cancel.hide()
        self.type_combo.setEnabled(True); self.key_input.setEnabled(True)
        for f in self.extra_fields: self._hide_row(f)
        self.key_input.clear(); self.name_input.clear()
        self._populate_color_tab(None)

    def _action_clicked(self):
        """Handle the builder's main button: apply edits if a widget is selected,
        otherwise add a new widget."""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "Create a project first.")
            return
        if self.selected_wrapper: self._apply_edit()
        else: self._add_new()

    def _apply_edit(self):
        """Apply the builder form values (key, name, unit, range, size) to the selected
        widget, move it to free space if the new size overlaps another, and save the project."""
        wrapper = self.selected_wrapper
        if not wrapper: return
        w = wrapper.widget
        
        raw_key = self.key_input.text().strip().upper()
        if not raw_key:
            QMessageBox.warning(self, "Error", "Data Key cannot be empty.")
            return
        keys = self.parse_keys(raw_key)

        if wrapper.gauge_type == "LineGraph":
            w.set_series_keys(keys)
            wrapper.data_key = ",".join(keys)
        else:
            pk = keys[0] if keys else "UNKNOWN"
            wrapper.data_key = pk
            if hasattr(w, "data_key"): w.data_key = pk
            
        name = self.name_input.text().strip()
        if name:
            self._set_widget_name(w, name)
            
        if hasattr(w, "unit"): w.unit = self.unit_input.text().strip()
        if hasattr(w, "_min"): w._min = self.min_input.value()
        if hasattr(w, "_max"): w._max = self.max_input.value()
            
        new_w = self.width_input.value()
        new_h = self.height_input.value()
        
        target_rect = QRect(wrapper.x(), wrapper.y(), new_w, new_h)
        if self._collides_for_wrapper(wrapper, target_rect):
            target_rect = self._find_free_space(wrapper, target_rect)
            
        wrapper.setGeometry(target_rect)
        wrapper._original_size = wrapper.size()
        
        w.update()
        self._clear_selection()
        self._update_signal_list()
        self._save_project(self.current_project)

    def _find_free_grid_spot(self, w_size, h_size):
        """Scan the canvas left-to-right, top-to-bottom to find the first vacant slot."""
        max_x = max(100, self.canvas.width())
        max_y = max(100, self.canvas.height())
        for y in range(20, max_y - h_size, 20):
            for x in range(20, max_x - w_size, 20):
                if not self._collides_for_wrapper(None, QRect(x, y, w_size, h_size)):
                    return x, y
        return None

    def _add_new(self):
        """Create a new widget from the builder form at the first vacant space,
        select it for editing and save the project."""
        g_type = self.type_combo.currentText()
        raw_key = self.key_input.text().strip()
        name = self.name_input.text().strip()
        if not raw_key:
            self._log("Error: Data Key required."); return
        keys = self.parse_keys(raw_key)
        
        w_size = self.width_input.value()
        h_size = self.height_input.value()
        
        pos = self._find_free_grid_spot(w_size, h_size)
        if pos is None:
            QMessageBox.warning(self, "No Space", "No available space on the canvas to add a new widget.")
            return
        sx, sy = pos
                
        w = self.create_widget(g_type, keys, name, sx, sy, w_size, h_size)
        
        if not w:
            QMessageBox.critical(self, "Factory Error", f"Failed to create widget type: {g_type}")
            return
            
        self._log(f"Added {g_type} for '{', '.join(keys)}'")
        self._update_signal_list()
        self.key_input.clear(); self.name_input.clear()
        
        self._select_wrapper(w)
        self._save_project(self.current_project)

    def _show_context_menu(self, wrapper, pos):
        """Show right-click context menu for Duplicate and Delete."""
        if self.is_layout_locked:
            return
            
        menu = QMenu(self)
        act_dup = menu.addAction("Duplicate")
        act_del = menu.addAction("Delete")
        
        action = menu.exec(wrapper.mapToGlobal(pos))
        
        if action == act_dup:
            self._duplicate_widget(wrapper)
        elif action == act_del:
            self.delete_widget(wrapper)

    def _duplicate_widget(self, wrapper):
        """Create an exact copy of the given widget and place it in the nearest vacant space."""
        if not self.current_project: return
        
        # Serialize the source widget to copy all settings
        item = self._serialize_widget(wrapper)
        keys = item["key"].split(",")
        w_size = item["w"]
        h_size = item["h"]
        
        # Find a vacant spot for the duplicate
        pos = self._find_free_grid_spot(w_size, h_size)
        if pos is None:
            QMessageBox.warning(self, "No Space", "No available space on the canvas to duplicate this widget.")
            return
        sx, sy = pos
        
        # Create and apply the exact data
        new_wrap = self.create_widget(item["type"], keys, item["name"], sx, sy, w_size, h_size)
        if new_wrap:
            self._apply_serialized_data(new_wrap, item)
            self._log(f"Duplicated {wrapper.gauge_type} for '{item['key']}'")
            self._update_signal_list()
            self._save_project(self.current_project)
            self._select_wrapper(new_wrap)

    def create_widget(self, g_type, keys, name, x, y, w_size=250, h_size=250):
        """Factory: build a gauge/widget of the given type, wrap it in a draggable wrapper
        placed on the canvas at (x, y), register it in gauge_map and return the wrapper
        (or None for an unknown type)."""
        pk = keys[0] if keys else "UNKNOWN"
        name = name or pk
        
        if g_type == "CircularDial":
            w = CircularDial(data_key=pk, label=name, unit="", width=250, height=250, maximum=100.0,
                             pointer_color="#e63946", face_color="#1e1e24", face_color_outer="#101014",
                             tick_color="#ffffff", tick_label_color="#ffffff", label_color="#ffffff")
        elif g_type == "CylinderGauge":
            w = CylinderGauge(data_key=pk, label=name, unit="", width=250, height=320, maximum=100.0, liquid_color="#118ab2")
        elif g_type == "BarGauge":
            w = BarGauge(data_key=pk, label=name, unit="", width=350, height=80, maximum=100.0, color="#06d6a0")
        elif g_type == "ProgressBar":
            w = ProgressBar(data_key=pk, label=name, unit="", width=350, height=60, maximum=100.0)
        elif g_type == "PlainLabel":
            w = PlainLabel(data_key=pk, text=f"[{name}: 0]", font_size=16, bold=True, color="#06d6a0",
                           width=300, height=40, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            w.label_text_name = name
        elif g_type == "DataInputText":
            w = DataInputText(self, pk, name)
        elif g_type == "LineGraph":
            colors = ["#ef476f", "#06d6a0", "#118ab2", "#ffd166"]
            series = [{"name": k, "color": colors[i % len(colors)]} for i, k in enumerate(keys)]
            w = LineGraph(width=350, height=200, label=name, series=series)
        elif g_type == "SevenSegmentDisplay":
            w = SevenSegmentDisplay(data_key=pk, label=name, unit="", width=w_size, height=h_size)
        elif g_type == "Thermometer":
            w = Thermometer(data_key=pk, label=name, unit="",
                                width=w_size, height=h_size)
        else:
            return None
            
        wrapper = DraggableWrapper(self, w, ",".join(keys), g_type)
        wrapper.setParent(self.canvas)
        
        # Attach right-click menu
        wrapper.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        wrapper.customContextMenuRequested.connect(lambda pos, w=wrapper: self._show_context_menu(w, pos))
        
        wrapper.show()
        wrapper.setGeometry(x, y, w_size, h_size)
        wrapper._original_size = QSize(w_size, h_size)
        self.gauge_map[wrapper.id] = wrapper
        return wrapper

    def _collides_for_wrapper(self, wrapper, rect):
        """Return True if the rectangle overlaps any other widget on the canvas
        (the wrapper itself is ignored)."""
        for other in self.gauge_map.values():
            if other is wrapper: continue
            if rect.intersects(other.geometry()):
                return True
        return False

    def _find_free_space(self, wrapper, rect):
        """Search outward in rings around the rectangle for a nearby position that is inside
        the canvas and overlaps nothing; return the original rect if none is found."""
        for radius in range(10, 1000, 10):
            for angle in range(0, 360, 45):
                dx = int(radius * math.cos(math.radians(angle)))
                dy = int(radius * math.sin(math.radians(angle)))
                test_rect = QRect(rect.x() + dx, rect.y() + dy, rect.width(), rect.height())
                if test_rect.x() >= 0 and test_rect.y() >= 0 and \
                   test_rect.x() + test_rect.width() <= self.canvas.width() and \
                   test_rect.y() + test_rect.height() <= self.canvas.height() and \
                   not self._collides_for_wrapper(wrapper, test_rect):
                    return test_rect
        return rect

    def delete_widget(self, wrapper):
        """Remove a widget from the canvas and registry, then update the signal list and
        save the project."""
        if wrapper.id in self.gauge_map: del self.gauge_map[wrapper.id]
        if self.selected_wrapper == wrapper: self._clear_selection()
        wrapper.close(); wrapper.deleteLater()
        self._log(f"Deleted.")
        self._update_signal_list()
        self._save_project(self.current_project)

    def _clear_canvas(self):
        """Delete every widget on the canvas, clear the selection and empty the signal list."""
        for w in list(self.gauge_map.values()):
            w.close(); w.deleteLater()
        self.gauge_map.clear()
        self._clear_selection()
        self.signal_list.clear()

    def _list_item_clicked(self, item):
        """Select the canvas widget that owns the clicked entry in the signal registry."""
        text = item.text().split("  [")[0].strip()
        for wrap in self.gauge_map.values():
            if text in wrap.data_key.split(","):
                self._select_wrapper(wrap); break

    def _update_signal_list(self):
        """Rebuild the signal registry list: one entry per data key, with graph series
        listed individually."""
        self.signal_list.clear()
        for wrap in self.gauge_map.values():
            name = self._get_widget_name(wrap.widget)
            if isinstance(wrap.widget, LineGraph):
                for k in getattr(wrap.widget, "_series_keys", []):
                    it = QListWidgetItem(f"{k}  [{name}]")
                    it.setForeground(QColor("#ffd166"))
                    self.signal_list.addItem(it)
            else:
                it = QListWidgetItem(f"{wrap.data_key}  [{wrap.gauge_type}]")
                it.setForeground(QColor("#06d6a0" if isinstance(wrap.widget, DataInputText) else "#ffffff"))
                self.signal_list.addItem(it)

    def _populate_color_tab(self, wrapper):
        """Rebuild the Colors tab with a color button for each editable color of the given
        widget (and per-series colors for graphs); show a hint when nothing is selected."""
        while self.color_layout.count():
            item = self.color_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    s = item.layout().takeAt(0)
                    if s.widget(): s.widget().deleteLater()
        self.color_buttons.clear()
        if not wrapper:
            self.color_layout.addWidget(QLabel("Select a widget."))
            self.color_layout.addStretch(); return
        w = wrapper.widget
        color_attrs = []
        if isinstance(w, (CircularDial, CylinderGauge, BarGauge, ProgressBar, LineGraph, SevenSegmentDisplay, Thermometer)):
            color_attrs = ["label_color", "unit_color", "color", "bg_color"]
            if isinstance(w, CircularDial):
                color_attrs += ["pointer_color", "face_color", "face_color_outer", "ring_color", "value_arc_color", "tick_color", "tick_label_color", "center_value_color"]
            elif isinstance(w, CylinderGauge):
                color_attrs += ["body_color", "body_color_bottom", "rim_color", "outline_color", "liquid_color", "scale_color"]
            elif isinstance(w, LineGraph):
                color_attrs += ["border_color"]
            elif isinstance(w, SevenSegmentDisplay):
                color_attrs += ["segment_color"]
        form = QFormLayout()
        for attr in color_attrs:
            if not hasattr(w, attr): continue
            c = QColor(getattr(w, attr))
            btn = QPushButton(c.name())
            btn.setStyleSheet(f"background-color: {c.name()}; color: {'#000' if c.lightness() > 128 else '#fff'};")
            btn.clicked.connect(lambda _, a=attr, b=btn: self._pick_color(w, a, b))
            form.addRow(f"{attr.replace('_', ' ').title()}:", btn)
        if isinstance(w, LineGraph):
            form.addRow(QLabel("<b>Series Colors:</b>"))
            for i, s in enumerate(w.series):
                c = QColor(s["color"])
                btn = QPushButton(c.name())
                btn.setStyleSheet(f"background-color: {c.name()}; color: {'#000' if c.lightness() > 128 else '#fff'};")
                btn.clicked.connect(lambda _, idx=i, b=btn: self._pick_series_color(w, idx, b))
                form.addRow(f"Series {i+1} ({s['name']}):", btn)
        self.color_layout.addLayout(form)
        self.color_layout.addStretch()

    def _pick_color(self, widget, attr, btn):
        """Open a color dialog for one color attribute of a widget and apply the chosen
        color to the widget and its button."""
        c = QColorDialog.getColor(QColor(getattr(widget, attr)), self, f"Choose {attr}")
        if c.isValid():
            setattr(widget, attr, c)
            btn.setText(c.name())
            btn.setStyleSheet(f"background-color: {c.name()}; color: {'#000' if c.lightness() > 128 else '#fff'};")
            widget.update()

    def _pick_series_color(self, widget, idx, btn):
        """Open a color dialog for one LineGraph series and apply the chosen color to the
        graph and its button."""
        c = QColorDialog.getColor(QColor(widget.series[idx]["color"]), self, "Series Color")
        if c.isValid():
            widget.series[idx]["color"] = c.name()
            btn.setText(c.name())
            btn.setStyleSheet(f"background-color: {c.name()}; color: {'#000' if c.lightness() > 128 else '#fff'};")
            widget.update()

    def closeEvent(self, event):
        """On close, save window geometry, panel visibility and the current project."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("tools_geom", self.tools_window.saveGeometry())
        self.settings.setValue("log_geom", self.log_window.saveGeometry())
        self.settings.setValue("tools_visible", self.tools_window.isVisible())
        self.settings.setValue("log_visible", self.log_window.isVisible())
        
        if self.current_project:
            self._save_project(self.current_project)
        super().closeEvent(event)

    def _send_all_tx(self):
        """Send the text of every DataInputText widget over UART as KEY=value commands."""
        n = 0
        for wrap in self.gauge_map.values():
            if isinstance(wrap.widget, DataInputText):
                t = wrap.widget.line.text().strip()
                if t:
                    self.send_uart_command(f"{wrap.widget.data_key}={t}")
                    n += 1
        if n > 0: self._log(f"Bulk TX ({n}).")

    def send_uart_command(self, cmd_str):
        """Log a command, write it to the serial port if connected, and in simulator mode
        loop a 'KEY=value' command back into the widgets as if it were received."""
        self._log(f"TX: {cmd_str}")
        if self.is_connected and self.serial.isOpen():
            self.serial.write((cmd_str + "\n").encode('utf-8'))
        if self.btn_simulate.isChecked() and "=" in cmd_str:
            key, val = cmd_str.split("=", 1)
            key = key.strip().upper()
            try:
                self._apply_rx_value(key, val.strip(), float(val.strip()))
            except ValueError:
                self._apply_text_rx_value(key, val.strip())

    def _refresh_ports(self):
        """Refill the port dropdown with the serial ports currently available."""
        self.port_combo.clear()
        ports = QSerialPortInfo.availablePorts()
        if not ports:
            self.port_combo.addItem("No ports found"); return
        for p in ports:
            self.port_combo.addItem(p.portName(), p)

    def _toggle_connection(self, checked):
        """Open or close the selected serial port at the chosen baud rate and update the
        Connect button, port controls and log."""
        if checked:
            pn = self.port_combo.currentText()
            if pn == "No ports found":
                self.btn_connect.setChecked(False); return
            self.serial.setPortName(pn)
            self.serial.setBaudRate(int(self.baud_combo.currentText()))
            if self.serial.open(QIODevice.OpenModeFlag.ReadWrite):
                self.is_connected = True
                self.btn_connect.setText("Disconnect")
                self.btn_connect.setStyleSheet("background-color: #ef476f; color: white;")
                self.port_combo.setEnabled(False); self.baud_combo.setEnabled(False)
                self.btn_simulate.setChecked(False)
                self._log(f"Connected to {pn}.")
            else:
                self._log(f"Failed to open {pn}.")
                self.btn_connect.setChecked(False)
                self.is_connected = False
        else:
            self.serial.close()
            self.is_connected = False
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("")
            self.port_combo.setEnabled(True); self.baud_combo.setEnabled(True)
            self._log("Disconnected.")

    def _toggle_pause_rx(self, checked):
        """Pause or resume processing of incoming data and update the Pause RX button."""
        self.is_rx_paused = checked
        if checked:
            self.btn_pause_rx.setText("Resume RX")
            self.btn_pause_rx.setStyleSheet("background-color: #06d6a0; color: #1e1e24;")
            self._log("RX processing paused.")
        else:
            self.btn_pause_rx.setText("Pause RX")
            self.btn_pause_rx.setStyleSheet("")
            self._log("RX processing resumed.")

    def _read_serial(self):
        """Serial readyRead handler: read one complete line, log it and parse it."""
        if self.serial.canReadLine():
            line = self.serial.readLine().data().decode('utf-8', errors='ignore').strip()
            if line:
                self._log(f"RX: {line}")
                self._parse_rx_data(line)

    def _toggle_simulation(self, checked):
        """Start or stop the data simulator (disconnecting the serial port when starting)
        and update the Simulate button."""
        if checked:
            if not self.current_project or not self.gauge_map:
                QMessageBox.warning(self, "No Data", "Create a project and add widgets first.")
                self.btn_simulate.setChecked(False)
                return
            if self.is_connected: self.btn_connect.setChecked(False)
            self.sim_timer.start()
            self.btn_simulate.setText("Stop Receive (Sim)")
            self.btn_simulate.setStyleSheet("background-color: #ef476f; color: white;")
            self._log("Simulator started.")
        else:
            self.sim_timer.stop()
            self.btn_simulate.setText("Start Receive (Sim)")
            self.btn_simulate.setStyleSheet("")
            self._log("Simulator stopped.")

    def _simulate_data(self):
        """Simulator timer tick: generate a sine-wave value for every data key (scaled to
        the widget's max, skipping CMD keys) and feed it through the normal RX parser."""
        if not self.gauge_map: return
        self.sim_time += 0.05
        parts = []
        keys = set()
        for wrap in self.gauge_map.values():
            if isinstance(wrap.widget, LineGraph):
                for k in wrap.widget._series_keys: keys.add(k)
            elif hasattr(wrap.widget, "data_key"): keys.add(wrap.widget.data_key)
        for key in keys:
            if key.startswith("CMD"): continue
            h = sum(ord(c) for c in key)
            freq = 0.5 + (h % 100) / 100.0
            phase = (h % 360) * math.pi / 180.0
            ratio = (math.sin(self.sim_time * freq + phase) + 1.0) / 2.0
            mx = 100.0
            for w in self.gauge_map.values():
                if w.data_key == key and hasattr(w.widget, "_max"):
                    mx = w.widget._max; break
            parts.append(f"{key}:{ratio * mx:.1f}")
        if not parts: return
        line = ", ".join(parts)
        if random.random() < 0.05: self._log(f"SIM: {line}")
        self._parse_rx_data(line)

    def _parse_rx_data(self, line):
        """Parse a received line of comma-separated KEY:value pairs and dispatch each to
        the widgets (numeric or text). Ignored while paused or when no data source is active."""
        if self.is_rx_paused: return
        if not self.btn_simulate.isChecked() and not self.is_connected: return
        for part in line.split(","):
            if ":" not in part: continue
            k, v = part.split(":", 1)
            k = k.strip().upper(); v = v.strip()
            try:
                self._apply_rx_value(k, v, float(v))
            except ValueError:
                self._apply_text_rx_value(k, v)

    def _apply_text_rx_value(self, key, val_str):
        """Apply a non-numeric received value to the DataInputText and PlainLabel widgets
        that use the given key."""
        for wrap in self.gauge_map.values():
            w = wrap.widget
            if isinstance(w, DataInputText) and w.data_key == key: w.update_rx(val_str)
            elif isinstance(w, PlainLabel) and getattr(w, "data_key", "") == key:
                name = getattr(w, "label_text_name", "VAL")
                w.text = f"[{name}: {val_str}]"
                w.update()

    def _apply_rx_value(self, key, val_str, val):
        """Apply a numeric received value to every widget bound to the given key: graph
        series, labels, text inputs, and any widget with setValue."""
        for wrap in self.gauge_map.values():
            w = wrap.widget
            if isinstance(w, LineGraph):
                if key in getattr(w, "_series_keys", []):
                    w.set_series_value(w._series_keys.index(key), val)
            elif getattr(w, "data_key", "") == key:
                if isinstance(w, PlainLabel):
                    name = getattr(w, "label_text_name", "VAL")
                    w.text = f"[{name}: {val_str}]"
                    w.update()
                elif isinstance(w, DataInputText):
                    w.update_rx(val_str)
                elif hasattr(w, "setValue"):
                    w.setValue(val)

    def _log(self, text):
        """Append a timestamped line to the Raw UART Log and scroll to the bottom."""
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {text}")
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def parse_keys(self, raw: str) -> list:
        """Turn a raw key string such as '[temp, pres]' into a list of upper-case keys."""
        raw = raw.strip().strip("[]")
        return [k.strip().upper() for k in raw.split(",") if k.strip()]

def main():
    """Create the Qt application with the Fusion style, show the main window and run the
    event loop."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()