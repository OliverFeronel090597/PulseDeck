"""
WorldMapPad — clickable world map gauge for PulseDeck.
=======================================================
Lives in src/map/. Loads:
    - src/map/worldmap.html                 (UI + JS)
    - src/map/data/ne_110m_land.geojson      (coastlines)
    - src/map/data/ne_110m_admin_0_countries.geojson (borders, optional)

MainWindow contract (same as MapPad):
    data_key, label, unit, _min, _max
    color attrs: bg_color, border_color, pointer_color, outline_color,
                 label_color, center_value_color
    apply_rx_value(key, val)
    keys(), set_keys(keys), values(), setValue(lat, lon), clamp()
    serialize_extra() / deserialize_extra(dict)

Requires: pip install PyQt6-WebEngine
"""

import os
import json
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QColor

from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel


# ---- Resolve paths inside src/map/ ---------------------------------------
HERE          = os.path.dirname(os.path.abspath(__file__))
HTML_FILE     = os.path.join(HERE, "worldmap.html")
LAND_FILE     = os.path.join(HERE, "map", "ne_110m_land.geojson")
BORDERS_FILE  = os.path.join(HERE, "data", "ne_110m_admin_0_countries.geojson")


class _Bridge(QObject):
    """QWebChannel object exposed to JS so the map can call back to Python."""
    markerMoved = pyqtSignal(float, float)

    def __init__(self, pad):
        super().__init__()
        self.pad = pad
        self.markerMoved.connect(pad._on_js_marker_moved)

    @pyqtSlot()
    def ready(self):
        """Called from JS when the QWebChannel handshake completes."""
        self.pad._push_state_to_js()
        self.pad._push_geojson_to_js()


class WorldMapPad(QWidget):
    def __init__(self, parent=None, keys=None, label="Position",
                 unit="", width=560, height=340,
                 minimum=0.0, maximum=100.0,
                 bg_color="#101014",
                 border_color="#3a3a45",
                 pointer_color="#ef476f",
                 outline_color="#ffffff",
                 label_color="#ffffff",
                 center_value_color="#06d6a0"):
        super().__init__(parent)

        # --- Axis keys ---
        if keys is None:
            keys = ["LAT", "LON"]
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split(",") if k.strip()]
        if not keys:
            keys = ["LAT", "LON"]
        elif len(keys) == 1:
            keys = [keys[0], keys[0] + "_LON"]
        self._keys = [keys[0], keys[1]]
        self.data_key = ",".join(self._keys)

        # --- Required attributes ---
        self.label = label
        self.unit  = unit
        self._min  = float(minimum)
        self._max  = float(maximum)
        self._lat  = 0.0
        self._lon  = 0.0

        # --- Colors ---
        self.bg_color           = QColor(bg_color)
        self.border_color       = QColor(border_color)
        self.pointer_color      = QColor(pointer_color)
        self.outline_color      = QColor(outline_color)
        self.label_color        = QColor(label_color)
        self.center_value_color = QColor(center_value_color)

        # --- Web view ---
        self._view = QWebEngineView(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._channel = QWebChannel(self._view.page())
        self._bridge  = _Bridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # Load HTML from the file (works with relative asset paths)
        self._view.setUrl(QUrl.fromLocalFile(HTML_FILE))

        self.resize(width, height)
        self.setMinimumSize(240, 160)

    # ----------------------------------------------------------------
    # Public API (called by MainWindow)
    # ----------------------------------------------------------------
    def keys(self):
        return list(self._keys)

    def set_keys(self, keys):
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split(",") if k.strip()]
        if len(keys) >= 2:
            self._keys = [keys[0], keys[1]]
        elif len(keys) == 1:
            self._keys = [keys[0], keys[0] + "_LON"]
        self.data_key = ",".join(self._keys)

    def values(self):
        return (self._lat, self._lon)

    def setValue(self, lat, lon):
        try:
            self._lat = max(-90.0,  min(90.0,  float(lat)))
            self._lon = max(-180.0, min(180.0, float(lon)))
        except (TypeError, ValueError):
            return
        self._push_position_to_js()

    def apply_rx_value(self, key, val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return
        if   key == self._keys[0]: self._lat = max(-90.0,  min(90.0,  v))
        elif key == self._keys[1]: self._lon = max(-180.0, min(180.0, v))
        else: return
        self._push_position_to_js()

    def clamp(self):
        self._lat = max(-90.0,  min(90.0,  self._lat))
        self._lon = max(-180.0, min(180.0, self._lon))
        self._push_position_to_js()

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------
    def serialize_extra(self):
        return {"map_lat": self._lat, "map_lon": self._lon}

    def deserialize_extra(self, d):
        if not d:
            return
        if "map_lat" in d: self._lat = float(d["map_lat"])
        if "map_lon" in d: self._lon = float(d["map_lon"])
        self._push_position_to_js()

    # ----------------------------------------------------------------
    # JS <-> Python bridge
    # ----------------------------------------------------------------
    def _on_js_marker_moved(self, lat, lon):
        self._lat = max(-90.0,  min(90.0,  float(lat)))
        self._lon = max(-180.0, min(180.0, float(lon)))
        self._emit_tx()

    def _emit_tx(self):
        win = self.window()
        if hasattr(win, "send_uart_command"):
            win.send_uart_command(f"{self._keys[0]}={self._lat:.4f}")
            win.send_uart_command(f"{self._keys[1]}={self._lon:.4f}")
        elif hasattr(self, "on_tx") and callable(self.on_tx):
            self.on_tx(self._keys[0], self._lat)
            self.on_tx(self._keys[1], self._lon)

    def _push_position_to_js(self):
        self._view.page().runJavaScript(
            f"window.setPosition({self._lat:.6f}, {self._lon:.6f});")

    def _push_state_to_js(self):
        self._push_position_to_js()
        self._view.page().runJavaScript(
            f"window.setTitle({json.dumps(self.label)});")
        colors = {
            "marker": self.pointer_color.name(),
            "label":  self.label_color.name(),
            "bg":     self.bg_color.name(),
            "border": self.border_color.name(),
            "ocean":  self.bg_color.darker(115).name(),
        }
        self._view.page().runJavaScript(
            f"window.setColors({json.dumps(colors)});")

    def _push_geojson_to_js(self):
        """Read GeoJSON files from disk and inject them into the page.
        Done via runJavaScript to avoid file:// CORS restrictions in Chromium."""
        for name, path in (("loadLand", LAND_FILE),
                           ("loadBorders", BORDERS_FILE)):
            if not os.path.exists(path):
                print(f"[WorldMapPad] missing: {path}")
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = f.read()
                self._view.page().runJavaScript(
                    f"window.{name}({json.dumps(payload)});")
            except Exception as e:
                print(f"[WorldMapPad] failed to load {path}: {e}")


# ======================================================================
# STANDALONE DEMO
# ======================================================================
def _demo():
    import sys, math
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QHBoxLayout, QVBoxLayout,
        QGroupBox, QFormLayout, QLabel, QPushButton, QDoubleSpinBox
    )
    from PyQt6.QtCore import QTimer

    class DemoWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("WorldMapPad — src/map demo")
            self.resize(1040, 660)

            self.pad = WorldMapPad(self, keys=["LAT", "LON"],
                                   label="World Position",
                                   width=780, height=460)
            self.pad.on_tx = self._on_tx

            ctrl = QGroupBox("Controls")
            cl = QFormLayout(ctrl)
            self.lat = QDoubleSpinBox(); self.lat.setRange(-90, 90)
            self.lon = QDoubleSpinBox(); self.lon.setRange(-180, 180)
            btn_set = QPushButton("Set Value")
            btn_set.clicked.connect(
                lambda: self.pad.setValue(self.lat.value(), self.lon.value()))
            btn_home = QPushButton("Reset 0,0")
            btn_home.clicked.connect(lambda: self.pad.setValue(0, 0))
            self.btn_sim = QPushButton("Start Sim (orbit)")
            self.btn_sim.setCheckable(True)
            self.btn_sim.toggled.connect(self._toggle_sim)
            self.timer = QTimer(self); self.timer.setInterval(50)
            self.timer.timeout.connect(self._tick)
            self.t = 0.0
            cl.addRow("Latitude:",  self.lat)
            cl.addRow("Longitude:", self.lon)
            cl.addRow(btn_set); cl.addRow(btn_home); cl.addRow(self.btn_sim)

            self.log = QLabel("Ready.")
            self.log.setStyleSheet(
                "QLabel{background:#1e1e24;color:#06d6a0;"
                "font-family:Consolas;padding:8px;border-radius:4px;}")
            self.log.setWordWrap(True)

            right = QWidget(); rl = QVBoxLayout(right)
            rl.addWidget(ctrl)
            rl.addWidget(QLabel("TX (simulated serial):"))
            rl.addWidget(self.log, 1)

            central = QWidget(); h = QHBoxLayout(central)
            h.addWidget(self.pad, 1); h.addWidget(right, 0)
            self.setCentralWidget(central)

        def send_uart_command(self, cmd):
            self.log.setText(f"TX: {cmd}\n" + self.log.text())

        def _on_tx(self, key, val):
            self.log.setText(f"{key}={val:.4f}\n" + self.log.text())

        def _toggle_sim(self, on):
            if on: self.timer.start(); self.btn_sim.setText("Stop Sim")
            else:  self.timer.stop();  self.btn_sim.setText("Start Sim (orbit)")

        def _tick(self):
            self.t += 0.04
            self.pad.apply_rx_value("LAT", 45.0 * math.sin(self.t))
            self.pad.apply_rx_value("LON", 170.0 * math.cos(self.t * 0.7))

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = DemoWindow(); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _demo()