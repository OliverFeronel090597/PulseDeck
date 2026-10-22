# PulseDeck — UART Dashboard & Simulator

**Developer:** Oliver Feronel
**Built with:** Python 3+ & PyQt6

PulseDeck is a customizable, drag-and-drop UART dashboard. Design a telemetry layout, connect to a COM port (or use the built-in simulator), watch live values update on gauges and graphs, send commands back to your microcontroller, and auto-generate the matching Arduino sketch.

---

## ✨ Features

- **Drag & drop canvas** – Add, move and resize widgets on a 3000 × 3000 px scrollable canvas with a dotted grid.
- **Smart alignment** – Widgets snap to each other's edges, centers and sizes with yellow dashed guides (similar to MS Word).
- **Collision handling & auto-fit** – Widgets can't overlap. A widget dropped in a tight spot shrinks to fit, and returns to its original size when moved to open space.
- **Keyboard nudging** – Select a widget and use the arrow keys (1 px) or `Shift` + arrow keys (5 px).
- **Widget lock** – Lock a single widget (right-click) or the whole layout (**Lock Layout**).
- **Multi-project support** – Save, switch, import and export multiple layouts, all stored in one `dashboard.json`.
- **Live UART** – Connect to any serial port at 9600 – 115200 baud; incoming lines are parsed and routed to widgets in real time.
- **Data simulator** – No hardware? Sine-wave data is generated for every key on your dashboard.
- **Pause RX** – Freeze incoming updates without disconnecting.
- **Dynamic Builder panel** – The Tools window only shows the fields relevant to the selected widget type, plus a **Colors** tab for per-widget color editing.
- **Floating Tools & Log windows** – Detached windows that fade to 50 % opacity after 5 s of inactivity.
- **Raw UART log** – Timestamped RX/TX log with a clear button.
- **Arduino code generator** – One click produces an Arduino sketch that matches your widgets' keys.
- **Persistent window state** – Window geometry and panel visibility are restored on launch.

---

## 🧩 Widget Types

| Widget | Purpose | Direction |
|---|---|---|
| `CircularDial` | Round gauge with pointer, ticks and center value | RX |
| `CylinderGauge` | Cylinder / tank-style fill gauge | RX |
| `BarGauge` | Bar-style gauge | RX |
| `ProgressBar` | Simple horizontal progress bar | RX |
| `LineGraph` | Multi-signal live line graph (comma-separated signals) | RX |
| `PlainLabel` | Text label showing `[NAME: value]` | RX |
| `DataInputWidget` | Text box + **Send** button for commands | TX (and shows RX text) |

Numeric widgets support **Min**, **Max** and **Unit** settings.

---

## 🔌 Serial Protocol

All messages are plain text, one message per line (`\n` terminated). Keys are case-insensitive and are converted to uppercase.

**Receive (device → PulseDeck)** — comma-separated `KEY:value` pairs:

```text
SPEED:42.5, E:73.0, YY:Hello
```

- Numeric values drive gauges, bars and graphs.
- Non-numeric values are shown on `PlainLabel` and `DataInputWidget`.

**Transmit (PulseDeck → device)** — `KEY=value`:

```text
V=1234
```

Use **Send All TX** to push the current value of every `DataInputWidget` at once.

---

## 🚀 Getting Started

### Requirements

- Python 3.9+
- PyQt6 (includes `QtSerialPort`)

```bash
pip install PyQt6
```

### Run

Run from the project root (the folder containing `main.py` and `dashboard.json`):

```bash
python main.py
```

### Basic workflow

1. Create a project with **New** (or pick an existing one).
2. Open **🛠 Tools** → **Builder**, choose a widget type, set Display Name, Data Key, and Min/Max/Unit, then click **Add Widget**.
3. Drag and resize widgets on the canvas. Select a widget to edit it or change its colors in the **Colors** tab.
4. Choose **Port** and **Baud**, then press **Connect** — or press **Start Receive (Sim)** to test without hardware.
5. Click **Arduino Code** to generate a matching sketch and copy it to your board.
6. Use **Lock Layout** when you're happy with the design.

### Mouse & keyboard

| Action | How |
|---|---|
| Move widget | Left-click and drag |
| Resize widget | Drag the bottom-right grip |
| Edit widget | Double-click, or right-click → *Edit Settings* |
| Lock / unlock widget | Right-click → *Lock Widget* / *Unlock Widget* |
| Delete widget | Right-click → *Delete* |
| Nudge widget | Arrow keys (`Shift` = 5 px) |

---

## 💾 Project Storage

All projects live in a single `dashboard.json`. A `dashboard.json.bak` backup of the previous version is written on every save.

```json
{
  "last_project": "PROJECT 1",
  "projects": {
    "PROJECT 1": {
      "name": "PROJECT 1",
      "widgets": [
        {
          "type": "CircularDial",
          "key": "SPEED",
          "name": "SPEED",
          "x": 1, "y": 0, "w": 250, "h": 250,
          "unit": "KM/H",
          "min": 0.0,
          "max": 100.0,
          "colors": { "pointer_color": "#e63946" }
        }
      ]
    }
  }
}
```

- `key` may contain multiple comma-separated keys (used by `LineGraph` for its signals).
- Use **Export** / **Import** to share a single project as a standalone JSON file.

---

## 📂 Project Structure

```text
UART_CONFIG/
├── projects/                 # Exported JSON project layouts
├── src/
│   ├── guage/                # Gauge and visualization components
│   │   ├── CircularGauge.py
│   │   ├── CylinderGuage.py
│   │   └── MultiTypeGauge.py # CircularDial, CylinderGauge, BarGauge,
│   │                         # ProgressBar, LineGraph, PlainLabel
│   ├── style/                # Application styling
│   │   ├── styles.qss        # Global stylesheet
│   │   └── StyleUtils.py     # apply_stylesheet() helper
│   ├── widget/               # Reusable custom PyQt6 widgets
│   │   ├── ArduinoCodeDialog.py  # Arduino sketch generator dialog
│   │   ├── DashboardCanvas.py    # Grid canvas + alignment guides
│   │   ├── DataInputWidget.py    # TX text box + Send button
│   │   ├── DraggableWrapper.py   # Drag / resize / snap / lock logic
│   │   ├── FloatingWindow.py     # Auto-fading tool & log windows
│   │   └── UpperLineEdit.py      # Auto-uppercase line edit
│   └── PulseDeck.png         # App icon
├── dashboard.json            # Database for all projects & layouts
├── dashboard.json.bak        # Automatic backup of the previous save
├── main.py                   # Application entry point (MainWindow)
└── ReadMe.md
```

---

## 🛠 Troubleshooting

- **No ports listed** – Press the **⟳** button to rescan, and check that no other program (e.g. the Arduino Serial Monitor) is holding the port.
- **Widgets don't update** – Make sure the device sends `KEY:value` (colon) and that the key matches the widget's *Data Key*. Check the **📜 Log** window for raw RX lines, and make sure **Pause RX** is off.
- **Stylesheet not applied / icon missing** – `main.py` loads `src\style\styles.qss` and `src//PulseDeck.png` using paths relative to the working directory, so launch the app from the project root. On Linux/macOS, change the backslash in the stylesheet path to a forward slash (`src/style/styles.qss`).
- **Layout lost after a bad edit** – Restore from `dashboard.json.bak`.

---

## 📜 License

Add your preferred license here (e.g. MIT).