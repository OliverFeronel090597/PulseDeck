import math
from PyQt6.QtWidgets import QFrame, QMenu, QVBoxLayout
from PyQt6.QtCore import Qt, QSize, QPoint, QRect


class DraggableWrapper(QFrame):
    def __init__(self, main_window, widget, data_key, gauge_type):
        super().__init__()
        self.main = main_window
        self.widget = widget
        self.data_key = data_key
        self.gauge_type = gauge_type
        self.is_locked = False
        self.id = str(id(self))

        # Get the minimum size required by the child widget
        child_min = self._get_min_child_size()
        self.setMinimumSize(max(100, child_min.width()),
                            max(60,  child_min.height()))

        self.setStyleSheet(
            "background-color: #1e1e24; "
            "border: 1px solid #3f3f4e; border-radius: 4px;"
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._original_size = QSize(250, 250)
        self._dragging = False
        self._resizing = False
        self._drag_offset = QPoint()
        self._resize_start = QPoint()
        self._start_geo = QRect()
        self._edge = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(widget, 1)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Minimum size helper
    # ------------------------------------------------------------------
    def _get_min_child_size(self):
        """Returns the minimum size the child widget needs
        (including the 10px wrapper padding on each side)."""
        if not self.widget:
            return QSize(100, 60)

        min_size = self.widget.minimumSizeHint()
        if not min_size.isValid() or min_size.isNull():
            min_size = self.widget.minimumSize()
        if min_size.width() <= 0:
            min_size = self.widget.size()

        # 20px total for left + right layout margins
        return QSize(min_size.width() + 20, min_size.height() + 20)

    # ------------------------------------------------------------------
    # Cursor feedback
    # ------------------------------------------------------------------
    def _update_cursor(self, pos):
        margin = 12
        l = pos.x() < margin
        r = pos.x() > self.width()  - margin
        t = pos.y() < margin
        b = pos.y() > self.height() - margin

        if (t and l) or (b and r):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (t and r) or (b and l):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif t or b:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif l or r:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # Mouse move
    # ------------------------------------------------------------------
    def mouseMoveEvent(self, event):
        if self.is_locked or self.main.is_layout_locked:
            return super().mouseMoveEvent(event)

        pos = event.pos()

        if not self._dragging and not self._resizing:
            self._update_cursor(pos)

        if self._resizing:
            self._handle_resize(event)
        elif self._dragging:
            self._handle_drag(event)
        else:
            super().mouseMoveEvent(event)

    # ------------------------------------------------------------------
    # Resize handling (edge drag with snapping + boundary clamp)
    # ------------------------------------------------------------------
    def _handle_resize(self, event):
        delta = event.globalPosition().toPoint() - self._resize_start
        dx = delta.x()
        dy = delta.y()

        x, y = self._start_geo.x(), self._start_geo.y()
        w, h = self._start_geo.width(), self._start_geo.height()

        if "left" in self._edge:
            w -= dx
            x += dx
        elif "right" in self._edge:
            w += dx

        if "top" in self._edge:
            h -= dy
            y += dy
        elif "bottom" in self._edge:
            h += dy

        GAP = 2
        snap_threshold = 8
        best_dx = snap_threshold
        best_dy = snap_threshold
        target_x, target_y = x, y
        target_w, target_h = w, h
        guide_x, guide_y = None, None

        for other in self.main.gauge_map.values():
            if other is self:
                continue

            # Horizontal snapping
            if "left" in self._edge:
                dist = abs(x - other.x())
                if dist < best_dx:
                    best_dx = dist
                    target_x, target_w = other.x(), (x + w) - other.x()
                    guide_x = other.x()

                dist = abs(x - (other.x() + other.width() + GAP))
                if dist < best_dx:
                    best_dx = dist
                    target_x = other.x() + other.width() + GAP
                    target_w = (x + w) - target_x
                    guide_x = other.x() + other.width()

                dist = abs(w - other.width())
                if dist < best_dx:
                    best_dx = dist
                    target_w = other.width()
                    target_x = (x + w) - target_w
                    guide_x = target_x

            elif "right" in self._edge:
                dist = abs((x + w) - (other.x() + other.width()))
                if dist < best_dx:
                    best_dx = dist
                    target_w = (other.x() + other.width()) - x
                    guide_x = other.x() + other.width()

                dist = abs((x + w) - (other.x() - GAP))
                if dist < best_dx:
                    best_dx = dist
                    target_w = (other.x() - GAP) - x
                    guide_x = other.x()

                dist = abs(w - other.width())
                if dist < best_dx:
                    best_dx = dist
                    target_w = other.width()
                    guide_x = x + target_w

            # Vertical snapping
            if "top" in self._edge:
                dist = abs(y - other.y())
                if dist < best_dy:
                    best_dy = dist
                    target_y, target_h = other.y(), (y + h) - other.y()
                    guide_y = other.y()

                dist = abs(y - (other.y() + other.height() + GAP))
                if dist < best_dy:
                    best_dy = dist
                    target_y = other.y() + other.height() + GAP
                    target_h = (y + h) - target_y
                    guide_y = other.y() + other.height()

                dist = abs(h - other.height())
                if dist < best_dy:
                    best_dy = dist
                    target_h = other.height()
                    target_y = (y + h) - target_h
                    guide_y = target_y

            elif "bottom" in self._edge:
                dist = abs((y + h) - (other.y() + other.height()))
                if dist < best_dy:
                    best_dy = dist
                    target_h = (other.y() + other.height()) - y
                    guide_y = other.y() + other.height()

                dist = abs((y + h) - (other.y() - GAP))
                if dist < best_dy:
                    best_dy = dist
                    target_h = (other.y() - GAP) - y
                    guide_y = other.y()

                dist = abs(h - other.height())
                if dist < best_dy:
                    best_dy = dist
                    target_h = other.height()
                    guide_y = y + target_h

        if best_dx < snap_threshold:
            x, w = target_x, target_w
            if guide_x is not None:
                self.main.canvas.guides.append((
                    int(guide_x), 0,
                    int(guide_x), int(self.main.canvas.height())
                ))

        if best_dy < snap_threshold:
            y, h = target_y, target_h
            if guide_y is not None:
                self.main.canvas.guides.append((
                    0, int(guide_y),
                    int(self.main.canvas.width()), int(guide_y)
                ))

        # --- Minimum size enforcement ---
        child_min = self._get_min_child_size()
        min_w = child_min.width()
        min_h = child_min.height()

        if w < min_w:
            if "left" in self._edge:
                x -= (min_w - w)
            w = min_w
        if h < min_h:
            if "top" in self._edge:
                y -= (min_h - h)
            h = min_h

        # --- Canvas boundary clamp (all four edges) ---
        canvas_w = self.main.canvas.width()
        canvas_h = self.main.canvas.height()

        # Left / top
        if x < GAP:
            if "left" in self._edge:
                w += x - GAP
            x = GAP
        if y < GAP:
            if "top" in self._edge:
                h += y - GAP
            y = GAP

        # Right / bottom — prevent overflow past canvas
        if x + w > canvas_w - GAP:
            if "right" in self._edge:
                w = canvas_w - GAP - x
            else:
                w = canvas_w - GAP - x
                if w < min_w:
                    w = min_w
                    x = canvas_w - GAP - w
        if y + h > canvas_h - GAP:
            if "bottom" in self._edge:
                h = canvas_h - GAP - y
            else:
                h = canvas_h - GAP - y
                if h < min_h:
                    h = min_h
                    y = canvas_h - GAP - h

        # Re-enforce minimum in case the boundary clamp shrank us too far
        if w < min_w:
            w = min_w
            if x + w > canvas_w - GAP:
                x = max(GAP, canvas_w - GAP - w)
        if h < min_h:
            h = min_h
            if y + h > canvas_h - GAP:
                y = max(GAP, canvas_h - GAP - h)

        self.main.canvas.update()

        # Force integer math for Qt
        x, y, w, h = int(x), int(y), int(w), int(h)

        new_rect = QRect(x, y, w, h)
        if not self._collides(new_rect):
            self.setGeometry(new_rect)
        else:
            if not self._collides(QRect(x, self.y(), w, self.height())):
                self.setGeometry(x, self.y(), w, self.height())
            elif not self._collides(QRect(self.x(), y, self.width(), h)):
                self.setGeometry(self.x(), y, self.width(), h)

        if self.main.selected_wrapper == self:
            self.main.width_input.setValue(self.width())
            self.main.height_input.setValue(self.height())

        event.accept()

    # ------------------------------------------------------------------
    # Drag handling (snapping + boundary clamp)
    # ------------------------------------------------------------------
    def _handle_drag(self, event):
        pos = self.mapToParent(event.pos() - self._drag_offset)
        nx, ny = pos.x(), pos.y()

        GAP = 2
        nx = max(GAP, min(nx, self.main.canvas.width()  - self.width()  - GAP))
        ny = max(GAP, min(ny, self.main.canvas.height() - self.height() - GAP))

        snap_threshold = 8
        best_dx = snap_threshold
        best_dy = snap_threshold
        target_nx, target_ny = nx, ny
        guide_x, guide_y = None, None

        for other in self.main.gauge_map.values():
            if other is self:
                continue

            checks_x = [
                (nx, other.x(), other.x()),
                (nx + self.width(), other.x() + other.width(),
                    other.x() + other.width()),
                (nx + self.width(), other.x() - GAP, other.x()),
                (nx, other.x() + other.width() + GAP,
                    other.x() + other.width()),
                (int(nx + self.width() / 2),
                 int(other.x() + other.width() / 2),
                 int(other.x() + other.width() / 2)),
            ]
            for val, target, guide in checks_x:
                dist = abs(val - target)
                if dist < best_dx:
                    best_dx = dist
                    target_nx = nx + (target - val)
                    guide_x = guide

            checks_y = [
                (ny, other.y(), other.y()),
                (ny + self.height(), other.y() + other.height(),
                    other.y() + other.height()),
                (ny + self.height(), other.y() - GAP, other.y()),
                (ny, other.y() + other.height() + GAP,
                    other.y() + other.height()),
                (int(ny + self.height() / 2),
                 int(other.y() + other.height() / 2),
                 int(other.y() + other.height() / 2)),
            ]
            for val, target, guide in checks_y:
                dist = abs(val - target)
                if dist < best_dy:
                    best_dy = dist
                    target_ny = ny + (target - val)
                    guide_y = guide

        self.main.canvas.guides = []
        if best_dx < snap_threshold:
            nx = target_nx
            if guide_x is not None:
                self.main.canvas.guides.append((
                    int(guide_x), 0,
                    int(guide_x), int(self.main.canvas.height())
                ))

        if best_dy < snap_threshold:
            ny = target_ny
            if guide_y is not None:
                self.main.canvas.guides.append((
                    0, int(guide_y),
                    int(self.main.canvas.width()), int(guide_y)
                ))

        nx = max(GAP, min(int(nx), self.main.canvas.width()  - self.width()  - GAP))
        ny = max(GAP, min(int(ny), self.main.canvas.height() - self.height() - GAP))

        self.main.canvas.update()

        # Force integer math for Qt
        if not self._collides(QRect(int(nx), int(ny), self.width(), self.height())):
            self.move(int(nx), int(ny))
        else:
            if not self._collides(QRect(int(nx), self.y(),
                                        self.width(), self.height())):
                self.move(int(nx), self.y())
            elif not self._collides(QRect(self.x(), int(ny),
                                          self.width(), self.height())):
                self.move(self.x(), int(ny))

        event.accept()

    # ------------------------------------------------------------------
    # Mouse press / release
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if self.is_locked or self.main.is_layout_locked:
            return super().mousePressEvent(event)

        pos = event.pos()
        margin = 12

        l = pos.x() < margin
        r = pos.x() > self.width()  - margin
        t = pos.y() < margin
        b = pos.y() > self.height() - margin

        self._edge = ""
        if t: self._edge += "top"
        if b: self._edge += "bottom"
        if l: self._edge += "left"
        if r: self._edge += "right"

        if self._edge:
            self._resizing = True
            self._resize_start = event.globalPosition().toPoint()
            self._start_geo = self.geometry()
            self.raise_()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._original_size = self.size()
            self._drag_offset = event.pos()
            self.raise_()
            self.setFocus()
            self.main._select_wrapper(self)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        moved = False

        if self._dragging and not self.is_locked and not self.main.is_layout_locked:
            self._snap_to_free_space()
            moved = True

        if self._resizing:
            self._original_size = self.size()
            moved = True

        self._resizing = False
        self._dragging = False
        self._edge = ""
        self.main.canvas.guides = []
        self.main.canvas.update()
        super().mouseReleaseEvent(event)

        # Persist new geometry AFTER everything has settled.
        # This is what fixes LineGraph (and every other widget) losing
        # its position when the project is reopened.
        if moved and self.main.current_project:
            self.main._save_project(self.main.current_project)

    # ------------------------------------------------------------------
    # Keyboard nudge
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        if self.is_locked or self.main.is_layout_locked:
            super().keyPressEvent(event)
            return

        step = 1 if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 5
        x, y = self.x(), self.y()

        if   event.key() == Qt.Key.Key_Left:  nx, ny = x - step, y
        elif event.key() == Qt.Key.Key_Right: nx, ny = x + step, y
        elif event.key() == Qt.Key.Key_Up:    nx, ny = x, y - step
        elif event.key() == Qt.Key.Key_Down:  nx, ny = x, y + step
        else:
            super().keyPressEvent(event)
            return

        GAP = 2
        nx = max(GAP, min(nx, self.main.canvas.width()  - self.width()  - GAP))
        ny = max(GAP, min(ny, self.main.canvas.height() - self.height() - GAP))

        new_rect = QRect(nx, ny, self.width(), self.height())
        if not self._collides(new_rect):
            self.move(nx, ny)
            if self.main.current_project:
                self.main._save_project(self.main.current_project)
        event.accept()

    # ------------------------------------------------------------------
    # Collision / placement helpers
    # ------------------------------------------------------------------
    def _collides(self, new_rect):
        for other in self.main.gauge_map.values():
            if other is self:
                continue
            if new_rect.intersects(other.geometry()):
                return True
        return False

    def _snap_to_free_space(self):
        rect = self.geometry()
        orig_w = self._original_size.width()
        orig_h = self._original_size.height()
        GAP = 2

        test_rect = QRect(rect.x(), rect.y(), orig_w, orig_h)
        if (not self._collides(test_rect)
                and test_rect.x() >= GAP
                and test_rect.y() >= GAP
                and test_rect.x() + test_rect.width()  <= self.main.canvas.width()  - GAP
                and test_rect.y() + test_rect.height() <= self.main.canvas.height() - GAP):
            self.setGeometry(test_rect)
            return

        for radius in range(10, 1000, 10):
            for angle in range(0, 360, 45):
                dx = int(radius * math.cos(math.radians(angle)))
                dy = int(radius * math.sin(math.radians(angle)))
                new_rect = QRect(rect.x() + dx, rect.y() + dy, orig_w, orig_h)

                if (new_rect.x() >= GAP
                        and new_rect.y() >= GAP
                        and new_rect.x() + new_rect.width()  <= self.main.canvas.width()  - GAP
                        and new_rect.y() + new_rect.height() <= self.main.canvas.height() - GAP
                        and not self._collides(new_rect)):
                    self.setGeometry(new_rect)
                    return

        self.setGeometry(rect.x(), rect.y(), orig_w, orig_h)

    # ------------------------------------------------------------------
    # Double click / context menu
    # ------------------------------------------------------------------
    def mouseDoubleClickEvent(self, event):
        if not self.is_locked and not self.main.is_layout_locked:
            self.main._select_wrapper(self)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        act_lock = menu.addAction("Unlock Widget" if self.is_locked else "Lock Widget")
        act_lock.triggered.connect(self._toggle_lock)

        if not self.is_locked:
            menu.addSeparator()
            act_edit = menu.addAction("Edit Settings")
            act_edit.triggered.connect(lambda: self.main._select_wrapper(self))
            menu.addSeparator()
            act_del = menu.addAction("Delete")
            act_del.triggered.connect(self._delete_self)

        menu.exec(self.mapToGlobal(pos))

    def _toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.setStyleSheet(
                "background-color: #1e1e24; "
                "border: 2px solid #ef476f; border-radius: 4px;"
            )
        else:
            self.setStyleSheet(
                "background-color: #1e1e24; "
                "border: 1px solid #3f3f4e; border-radius: 4px;"
            )

    def _delete_self(self):
        self.main.delete_widget(self)