# PulseDeck Gauge Rules & How to Add a New Gauge

Every new gauge follows the same standard. The rules are **enforced in code**: a gauge that breaks a hard rule is rejected, and the reason is written to the **📜 Log** window.

## Quick start (one file, nothing else to edit)

1. Copy `src/Dragables/MyGauge.py` (same folder) and rename it.
2. Rename the class (**it must be a new name**, see Rule 1), then edit the three methods below.
3. Restart PulseDeck. Your gauge appears in the **Widget Type** dropdown.

```
UART_CONFIG/
├── main.py
└── src/
    ├── guage/BaseGauge.py        <-- the standard base class (don't edit)
    ├── Dragables/MyGauge.py      <-- your new gauges go here
    └── widget/WidgetRegistry.py  <-- finds and checks everything (don't edit)
```

```python
from PyQt6.QtCore import Qt, QRectF
from src.guage.BaseGauge import BaseGauge

class NewClass(BaseGauge):                         # Rule 1: new class name, inherits BaseGauge

    def _properties(self):                         # Rule 2: declare colors and data
        self._colors = ["label_color", "color", "pointer_color"]
        self._datas  = ["datasource", "min", "max", "unit"]

    def _updateValue(self, data):                  # Rule 3: incoming data -> value
        self.value = data

    def paint_gauge(self, p, rect):                # Rule 4: draw relative to rect
        p.fillRect(rect, self.bg_color)
        p.fillRect(QRectF(rect.x(), rect.y(), rect.width() * self.ratio(), rect.height()), self.color)
        p.setPen(self.label_color)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.label}  {self.value_text()}")
```

---

## The rules for a new class

### Hard rules (broken = the gauge is skipped or not created, and the Log says why)

| # | Rule | Details |
|---|---|---|
| 1 | **The class name must not already exist** among the dashboard widget classes | If it does, add `V2`: `class NewClassV2(BaseGauge)`. If that exists too, use `V3`, and so on. The Log tells you the next free name, e.g. *"class name 'MyGauge' already exists in the dashboard widgets; rename it to 'MyGaugeV2'"* |
| 2 | **Inherit from `BaseGauge`** | `class NewClass(BaseGauge):` |
| 3 | **Define `def _properties(self)`** | Required in every new class. It sets two arrays: `_colors` and `_datas` (Rules 4 and 5) |
| 4 | **`_properties` sets `self._colors`**, an array of color attribute names | e.g. `["label_color", "color", "pointer_color"]`. Every name must be a real `QColor` attribute. The **Colors tab** shows exactly these, and the project file saves them |
| 5 | **`_properties` sets `self._datas`**, an array of the data the gauge needs | Allowed: `"datasource"`, `"min"`, `"max"`, `"unit"`. The **Builder** shows an input for each one (`datasource` is the Data Key, which every gauge has). Anything else is rejected |
| 6 | **Define `def _updateValue(self, data)`** and set `self.value = data` | Every incoming number goes through it. You may convert, scale or clamp first, but the result must end up in `self.value`. A gauge whose `_updateValue` doesn't change `self.value` is rejected |
| 7 | **Implement `paint_gauge(self, p, rect)`** | The only drawing method you write |
| 8 | **The type name is the class name** | No separate type name to keep in sync. (An explicit `WIDGET_TYPE`, if you write one, must equal the class name.) |
| 9 | **The file must load without errors** | A broken file is skipped so it can't stop the app |

`FIELDS` and `COLORS` class attributes are not used any more: `_datas` and `_colors` replace them.

### Soft rules (broken = a warning in the Log, the first time that type is added)

| # | Rule |
|---|---|
| 10 | Draw only relative to `rect` (never fixed pixel sizes), because the user can resize any widget |
| 11 | Don't override `setValue`, `paintEvent` or `sizeHint`. `BaseGauge` handles input checking, repainting and sizing |
| 12 | Keep `data_key`, `label` and the minimum size that `BaseGauge` sets up |
| 13 | Don't rename a class once projects use it. Saved widgets are matched by the class name (use `ALIASES = ("OldName",)` if you must) |

Classes whose names start with `_` are treated as helpers and ignored.

---

## `_properties`: colors and data

Standard colors exist on every gauge: `label_color`, `unit_color`, `color`, `bg_color`. Create any extra ones first, then list them.

```python
from PyQt6.QtGui import QColor

class Thermo(BaseGauge):
    def _properties(self):
        self.pointer_color = QColor("#e63946")                        # your own color
        self._colors = ["label_color", "color", "pointer_color"]      # editable in Colors tab + saved
        self._datas  = ["datasource", "min", "max", "unit"]           # builder inputs this gauge uses
```

- A color not listed in `_colors` can't be edited and is not saved.
- A gauge with no range or unit leaves them out, e.g. `self._datas = ["datasource"]`, and the Builder hides those inputs.

## `_updateValue`: how data becomes the value

```python
def _updateValue(self, data):
    self.value = data                          # simplest form

def _updateValue(self, data):
    self.value = max(0, min(100, data))        # clamp
    
def _updateValue(self, data):
    self.value = data * 1.8 + 32               # convert, e.g. C to F
```

## What `BaseGauge` gives you

| You get | Use it as |
|---|---|
| `self.value` | The current value (set by your `_updateValue`) |
| `self.label`, `self.unit`, `self.data_key` | The Display Name, Unit and Data Key |
| `self._min`, `self._max` | The Min / Max inputs |
| `self.ratio()` | `self.value` as 0.0 to 1.0 between min and max |
| `self.value_text()` | `"42.5 KM/H"`, ready to draw |
| Antialiased `QPainter` | Passed to you as `p` |

Optional class attributes: `MIN_SIZE` (default `(100, 60)`), `ALIASES` (old names that should still load).

---

## Troubleshooting

- **Gauge missing from the dropdown:** open the **📜 Log** window. A rejected file is listed as `Custom widget skipped - <file> (<Class>): <reason>`. Files starting with `_` are ignored.
- **`class name '...' already exists`:** rename the class using the suggested `V2` name.
- **`Rule violation [Name]: ...`:** the gauge loaded but could not be created: `_colors` / `_datas` is not a list, names something that doesn't exist, or `_updateValue` doesn't set `self.value`.
- **`Rule warning [Name]: ...`:** the gauge works but breaks a soft rule.
- **Gauge never moves:** the Data Key must match the incoming `KEY:value` (upper-cased), and **Pause RX** must be off.
- **Colors reset on restart:** the attribute isn't listed in `_colors`.
- **A saved widget vanished:** its file was removed or the class was renamed. Restore the name or use `ALIASES`.

## Advanced: special widgets

Widgets that show several signals (`LineGraph`), show text (`PlainLabel`) or send data (`DataInputText`) use extra hooks on `WidgetSpec`. Register those by hand at the bottom of `WidgetRegistry.py`, using the `LineGraph` block as a template. Ordinary gauges never need this.