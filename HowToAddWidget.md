# How to Add a New Draggable Widget to PulseDeck

This guide walks through adding a brand-new widget type. As the example we add a **`Thermometer`**.

You do **not** write any drag, resize, snap, lock or save code. Every widget is automatically wrapped in a `DraggableWrapper`, which provides all of that. Your job is only to:

1. write the widget class,
2. register it in `main.py` in four places.

> **Heads-up:** the type name (`"Thermometer"`) is saved in `dashboard.json`. It must be spelled **exactly the same** in the dropdown, in `create_widget`, and in the field list. Renaming it later breaks projects that were saved with the old name.

---

## How it fits together

| Part | What it does | Where |
|---|---|---|
| Widget class | Draws itself and exposes `setValue()` | `src/guage/Thermometer.py` |
| Dropdown entry | Lets the user pick the type in the Builder | `self.type_combo.addItems([...])` in `main.py` |
| Field visibility | Chooses which Builder inputs (Unit / Min / Max) appear | `_show_hide_fields()` in `main.py` |
| Factory | Creates the widget and wraps it in a `DraggableWrapper` | `create_widget()` in `main.py` |
| Colors (optional) | Shows color buttons in the **Colors** tab | `_populate_color_tab()` in `main.py` |

`create_widget()` is used for **both** *Add Widget* and *loading a saved project*, so one `elif` covers both.

---

## The widget contract

`main.py` talks to your widget through a few plain attribute names. Use these exact names and everything (editing, saving, loading, live data) works with no extra code.

| Attribute / method | Required? | Used for |
|---|---|---|
| `setValue(v)` | **Yes** | Called for every numeric UART value matching your `data_key` |
| `data_key` | **Yes** | The key `main.py` matches incoming `KEY:value` against |
| `label` | Recommended | Display name (the Builder's **Name** field reads/writes it) |
| `unit` | If you use Unit | Saved/loaded as `"unit"` |
| `_min`, `_max` | If you use Min/Max | Saved/loaded as `"min"` / `"max"` |
| color attributes (`color`, `label_color`, …) | Optional | Saved/loaded under `"colors"` (see Step 6) |
| `setMinimumSize(...)` | Recommended | Stops the wrapper shrinking the widget to nothing |

Rules of thumb:

- Inherit from `QWidget`.
- Call `self.update()` whenever something visible changes (`setValue` does this). Editing the Name, Unit or Min/Max in the Builder also calls `update()`, so drawing in `paintEvent` picks those changes up automatically.
- Draw relative to `self.width()` / `self.height()` so the widget scales when the user resizes it.
- Don't name an attribute `layout`: it overrides `QWidget.layout()`.

---

## Step 1: Create the widget file

Create `src/guage/Thermometer.py`:

```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QRectF, QSize


class Thermometer(QWidget):
    def __init__(self, data_key="", label="TEMP", unit="", width=150, height=250, **kwargs):
        super().__init__()
        self.data_key = data_key      # used by main.py to route incoming UART values
        self.label = label            # display name (Name field in the builder)
        self.unit = unit              # Unit field in the builder
        self._min = 0.0               # Min / Max fields in the builder
        self._max = 100.0
        self._value = 0.0

        # Colors: names listed in _serialize_current() are saved automatically
        self.label_color = QColor("#ffffff")
        self.unit_color = QColor("#00aaff")
        self.color = QColor("#e63946")       # mercury
        self.bg_color = QColor("#2b2b36")    # empty tube

        self.setMinimumSize(80, 120)

    # Required: called by main.py for every numeric UART update
    def setValue(self, v):
        self._value = max(self._min, min(float(v), self._max))
        self.update()

    def sizeHint(self):
        return QSize(150, 250)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Name at the top
        p.setPen(self.label_color)
        p.drawText(QRectF(0, 4, w, 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, str(self.label))

        # Geometry (everything is relative to the current size, so resizing just works)
        bulb_r = max(8.0, min(w, h) * 0.14)
        tube_w = bulb_r * 0.9
        cx = w / 2
        tube_top = 30.0
        bulb_cy = h - 30 - bulb_r
        tube_h = max(1.0, bulb_cy - tube_top)
        tube = QRectF(cx - tube_w / 2, tube_top, tube_w, tube_h)

        span = self._max - self._min
        ratio = 0.0 if span <= 0 else (self._value - self._min) / span
        fill_h = tube_h * ratio
        fill = QRectF(tube.left(), tube.bottom() - fill_h, tube_w, fill_h)

        # Empty tube + bulb
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.bg_color)
        p.drawRoundedRect(tube, tube_w / 2, tube_w / 2)
        p.drawEllipse(QRectF(cx - bulb_r, bulb_cy - bulb_r, bulb_r * 2, bulb_r * 2))

        # Mercury
        p.setBrush(self.color)
        p.drawRect(fill)
        p.drawEllipse(QRectF(cx - bulb_r * 0.8, bulb_cy - bulb_r * 0.8, bulb_r * 1.6, bulb_r * 1.6))

        # Value text at the bottom
        p.setPen(self.unit_color)
        p.drawText(QRectF(0, h - 26, w, 22), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._value:.1f} {self.unit}".strip())
```

---

## Step 2: Import it in `main.py`

Next to the other gauge import near the top of `main.py`:

```python
from src.guage.MultiTypeGauge import (
    CircularDial, CylinderGauge, BarGauge, ProgressBar, LineGraph, PlainLabel
)
from src.guage.Thermometer import Thermometer   # <-- ADD
```

---

## Step 3: Add it to the type dropdown

Find `self.type_combo.addItems([...])` (in the Builder panel) and add the name:

```python
self.type_combo.addItems([
    "CircularDial", "CylinderGauge", "BarGauge", "ProgressBar",
    "PlainLabel", "DataInputWidget", "LineGraph",
    "Thermometer",                                   # <-- ADD
])
```

---

## Step 4: Choose which Builder fields to show

Find `_show_hide_fields(self, g_type)` and add your type to the numeric group so Unit, Min and Max appear:

```python
def _show_hide_fields(self, g_type):
    for f in self.extra_fields: self._hide_row(f)

    if g_type in ["CircularDial", "CylinderGauge", "BarGauge", "ProgressBar",
                  "Thermometer"]:                    # <-- ADD
        self._show_row(self.unit_input)
        self._show_row(self.min_input)
        self._show_row(self.max_input)
    elif g_type == "LineGraph":
        ...
```

If your widget only needs a Unit, copy the `PlainLabel` branch instead. If it needs none of them, skip this step.

---

## Step 5: Add it to the factory

Find `create_widget(self, g_type, keys, name, x, y, w_size=250, h_size=250)` and add an `elif` **before** the final `else: return None`:

```python
elif g_type == "Thermometer":                        # <-- ADD
    w = Thermometer(data_key=pk, label=name, unit="",
                         width=w_size, height=h_size)
else:
    return None
```

`pk` (the primary key) and `name` are already prepared at the top of the function. The code after the chain wraps `w` in a `DraggableWrapper` and registers it for you.

---

## Step 6 (optional): Colors tab and saving

**Show color buttons.** In `_populate_color_tab()`, add your class to the `isinstance` tuple. The common attributes `label_color`, `unit_color`, `color` and `bg_color` are then offered automatically (only those your widget actually has):

```python
if isinstance(w, (CircularDial, CylinderGauge, BarGauge, ProgressBar, LineGraph,
                  Thermometer)):                     # <-- ADD
    color_attrs = ["label_color", "unit_color", "color", "bg_color"]
```

**Saving/loading colors.** `_serialize_current()` saves every attribute from a fixed list of names (`label_color`, `unit_color`, `color`, `bg_color`, `pointer_color`, …), and `_load_project()` restores them. If your widget uses only names that are already in that list, you don't need to change anything. If you invent a new one (e.g. `mercury_color`), add the name to **both**:

- the `for attr in [...]` list in `_serialize_current()`, and
- the `color_attrs` list in `_populate_color_tab()` (so it gets a button).

Use `QColor` values; they are saved as hex strings like `#e63946`.

---

## Quick checklist

- [ ] `src/guage/Thermometer.py` exists, inherits `QWidget`, has `setValue()` and `data_key`
- [ ] Import added in `main.py`
- [ ] Name added to `type_combo.addItems([...])`
- [ ] Name added in `_show_hide_fields()`
- [ ] `elif` added in `create_widget()` before `else`
- [ ] (Optional) Added to `_populate_color_tab()`; new color names added to `_serialize_current()`
- [ ] The spelling is identical everywhere

## Testing it

1. Run the app and select **Thermometer** in the Builder. Unit, Min and Max should appear.
2. Enter a **Data Key** (e.g. `TEMP1`) and click **Add Widget**.
3. Press **Start Receive (Sim)**. The mercury should move.
4. Resize it with the grip, change colors, then switch projects and come back. Size, name, unit, range and colors should all be restored.
5. Or send `TEMP1:42.5` from a real device.

---

## Troubleshooting

**Clicking *Add Widget* does nothing.**
Check the **📜 Log** window first. The usual causes:

1. **Missing `elif` in `create_widget()`**, or a typo in the type name. It falls into `return None` and no widget is created.
2. **Empty Data Key.** The Builder logs *"Data Key required"* and stops.
3. **No free space on the canvas.** Wrappers cannot overlap, so a crowded canvas can prevent placement. Delete or move a few widgets and try again.

**Widget appears but never moves.**
The key doesn't match. Incoming data is `KEY:value` and keys are upper-cased, so check the Data Key and that your class has `data_key` and `setValue()`. Also make sure **Pause RX** is off.

**Name, Unit or Min/Max edits have no effect.**
Your widget probably uses different attribute names. Use `label`, `unit`, `_min`, `_max`, and call `update()` (or draw in `paintEvent`). If you display the name in a child `QLabel`, update that label yourself, because `main.py` only sets `w.label`.

**Saved widgets vanish after restarting.**
The type is saved in `dashboard.json`, and `create_widget()` returned `None` for it on load. The `elif` was removed or the name was changed. Restore the original spelling.

**Colors reset after reload.**
The attribute name isn't in `_serialize_current()`'s list (see Step 6).

**The widget looks squashed or oversized.**
Draw relative to `self.width()` / `self.height()` and set `setMinimumSize(...)`. The wrapper adds a 10 px margin on every side and has its own minimum of 100 × 60.
