<!-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
SPDX-License-Identifier: GPL-3.0-or-later-->

# Drag & Drop Implementation Plan for Tournament Bracket Manager

## Current State (Click-based Assignment)

**How it works now:**
1. User selects bracket from list
2. Clicks "→ Table 1/2/3/4" button
3. Bracket moves to that table panel
4. Can click "← Unassign" to move back to unassigned list

**Limitations:**
- Requires multiple clicks (select + assign button)
- Not intuitive
- Can't directly move between tables
- Can't see what you're assigning while dragging

---

## Proposed Drag & Drop System

### Vision
Drag brackets directly from the list to table panels, between tables, or back to the list.

### User Actions

```
┌─────────────────────┬─────────────────────────┐
│  Bracket List       │   Tables               │
│  [Bracket 1] ←──┐   │  ┌──────┐  ┌──────┐   │
│  [Bracket 2]    │   │  │Tab 1 │  │Tab 2 │   │
│  [Bracket 3] ─────→ │  │      │  │      │   │
│                 │   │  └──────┘  └──────┘   │
└─────────────────┼───┴─────────────────────────┘
                  │
              Drag & Drop
```

**Supported Drag Operations:**
1. **List → Table**: Drag from unassigned list to any table (if not full)
2. **Table → List**: Drag from table back to unassigned list
3. **Table → Table**: Drag between tables to reorganize
4. **Visual Feedback**: Highlight drop targets, show ghost/preview

---

## Tkinter Drag & Drop Implementation

### Libraries/Approaches

**Option 1: Native Tkinter DND (tkdnd)**
- Package: `tkinterdnd2` (third-party)
- Pros: Native OS drag & drop support, works with external apps
- Cons: Requires external library installation

**Option 2: Custom Tkinter Implementation**
- Uses built-in Tkinter events: `<Button-1>`, `<B1-Motion>`, `<ButtonRelease-1>`
- Pros: No external dependencies, full control
- Cons: More code, manual implementation

**Recommended: Option 2 (Custom Implementation)**
- No external dependencies (keeps it simple)
- Full control over behavior and appearance
- More portable

### Technical Implementation

#### Step 1: Make Listbox Items Draggable

```python
class DraggableListbox(tk.Listbox):
    def __init__(self, parent, on_drag_start, on_drag_end, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_drag_start = on_drag_start
        self.on_drag_end = on_drag_end

        # Bind drag events
        self.bind('<Button-1>', self._start_drag)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._end_drag)

        self.drag_data = None

    def _start_drag(self, event):
        # Get clicked item
        index = self.nearest(event.y)
        if index >= 0:
            item = self.get(index)
            self.drag_data = {'item': item, 'index': index}
            self.on_drag_start(self.drag_data)

    def _on_drag(self, event):
        # Show visual feedback (cursor change, ghost image)
        if self.drag_data:
            # Update cursor position, show preview
            pass

    def _end_drag(self, event):
        # Determine drop target and execute drop
        if self.drag_data:
            drop_target = self._find_drop_target(event)
            self.on_drag_end(self.drag_data, drop_target)
            self.drag_data = None
```

#### Step 2: Make Table Panels Drop Targets

```python
class DropTargetPanel(tk.LabelFrame):
    def __init__(self, parent, table_num, on_drop, **kwargs):
        super().__init__(parent, **kwargs)
        self.table_num = table_num
        self.on_drop = on_drop
        self.is_hover = False

        # Bind drop events
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event):
        # Highlight panel when dragging over it
        self.is_hover = True
        self.config(bg=COLORS['accent_blue'])  # Highlight

    def _on_leave(self, event):
        # Remove highlight
        self.is_hover = False
        self.config(bg=COLORS['bg_panel'])  # Normal

    def accept_drop(self, drag_data):
        # Called when item dropped on this panel
        self.on_drop(self.table_num, drag_data)
```

#### Step 3: Drag & Drop Manager

```python
class DragDropManager:
    """Coordinates drag & drop between listbox and table panels."""

    def __init__(self, app):
        self.app = app
        self.current_drag = None
        self.ghost_window = None

    def start_drag(self, drag_data):
        """Called when drag starts from listbox."""
        self.current_drag = drag_data
        self.create_ghost_image(drag_data['item'])

    def create_ghost_image(self, text):
        """Create semi-transparent preview window."""
        self.ghost_window = tk.Toplevel()
        self.ghost_window.wm_overrideredirect(True)
        self.ghost_window.wm_attributes('-alpha', 0.7)

        label = tk.Label(self.ghost_window, text=text,
                        bg=COLORS['accent_blue'], fg='white',
                        padx=10, pady=5)
        label.pack()

    def update_ghost_position(self, x, y):
        """Move ghost image with cursor."""
        if self.ghost_window:
            self.ghost_window.geometry(f'+{x+10}+{y+10}')

    def end_drag(self, drop_target):
        """Called when drag ends."""
        if self.ghost_window:
            self.ghost_window.destroy()
            self.ghost_window = None

        if self.current_drag and drop_target:
            self.app.handle_drop(self.current_drag, drop_target)

        self.current_drag = None

    def find_drop_target_at(self, x, y):
        """Determine what's under the cursor."""
        # Use winfo_containing to find widget at cursor position
        widget = self.app.winfo_containing(x, y)

        # Check if it's a valid drop target
        if isinstance(widget, DropTargetPanel):
            return widget

        # Check if it's the unassigned list
        if widget == self.app.bracket_listbox:
            return 'unassigned'

        return None
```

#### Step 4: Integration with Main App

```python
class BracketViewerApp(tk.Tk):
    def setup_drag_drop(self):
        """Initialize drag & drop system."""
        self.dnd_manager = DragDropManager(self)

        # Make listbox draggable
        self.bracket_listbox.bind('<Button-1>', self.on_drag_start)
        self.bracket_listbox.bind('<B1-Motion>', self.on_drag_motion)
        self.bracket_listbox.bind('<ButtonRelease-1>', self.on_drag_end)

        # Make table panels drop targets
        for table_num, panel in self.table_panels.items():
            panel.bind('<Enter>', lambda e, t=table_num: self.on_drop_target_enter(t))
            panel.bind('<Leave>', lambda e, t=table_num: self.on_drop_target_leave(t))

    def on_drag_start(self, event):
        index = self.bracket_listbox.nearest(event.y)
        if index >= 0:
            bracket_key = self.bracket_listbox.get(index)
            self.dnd_manager.start_drag({'bracket_key': bracket_key, 'source': 'list'})

    def on_drag_motion(self, event):
        # Update ghost position
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        self.dnd_manager.update_ghost_position(x, y)

    def on_drag_end(self, event):
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        drop_target = self.dnd_manager.find_drop_target_at(x, y)
        self.dnd_manager.end_drag(drop_target)

    def handle_drop(self, drag_data, drop_target):
        """Execute the drop action."""
        bracket_key = drag_data['bracket_key']

        if isinstance(drop_target, DropTargetPanel):
            # Dropped on a table
            self.assign_to_table_dnd(bracket_key, drop_target.table_num)

        elif drop_target == 'unassigned':
            # Dropped back on unassigned list
            self.unassign_bracket_dnd(bracket_key)
```

---

## Visual Feedback Features

### 1. Drag Ghost/Preview
- Semi-transparent window showing bracket name
- Follows cursor during drag
- Disappears on drop

### 2. Drop Target Highlighting
- Table panels highlight (blue border/background) when hovering
- Invalid targets show red highlight (e.g., full table)
- Valid targets show green/blue highlight

### 3. Cursor Changes
- **Grabbing hand** when picking up item
- **Move cursor** while dragging
- **No-drop cursor** over invalid targets
- **Drop cursor** over valid targets

### 4. Animations (Optional)
- Smooth slide animation when item moves to table
- Bounce effect if drop is invalid
- Fade in/out effects

---

## Validation Rules

### Drop Validation
```python
def can_drop(bracket_key, target_table):
    """Check if drop is valid."""

    # Rule 1: Table can't have more than 2 brackets
    if count_assignments(target_table) >= 2:
        return False, "Table is full (max 2 brackets)"

    # Rule 2: Bracket can't be in multiple tables
    if is_assigned(bracket_key) and get_assignment(bracket_key) != target_table:
        return False, "Bracket already assigned elsewhere"

    # Rule 3: Can't drop on same location
    if get_assignment(bracket_key) == target_table:
        return False, "Already in this table"

    return True, "OK"
```

### Visual Feedback for Invalid Drops
- Red border on target panel
- Show tooltip: "Table Full" or "Invalid Drop"
- Cursor changes to "no-drop" symbol
- Snap back animation (item returns to original position)

---

## Implementation Phases

### Phase 1: Basic Drag from List to Tables
- ✅ Detect drag start from listbox
- ✅ Create ghost preview
- ✅ Detect drop on table panels
- ✅ Update assignment and UI

### Phase 2: Drag from Tables Back to List
- ✅ Make table items draggable
- ✅ Detect drop on unassigned list area
- ✅ Remove from table, add to list

### Phase 3: Drag Between Tables
- ✅ Drag from one table to another
- ✅ Validate capacity (max 2 per table)
- ✅ Update assignments

### Phase 4: Visual Polish
- ✅ Drop target highlighting
- ✅ Cursor changes
- ✅ Smooth animations
- ✅ Invalid drop feedback

### Phase 5: Advanced Features
- Multi-select drag (drag multiple brackets at once)
- Keyboard shortcuts (Ctrl+drag for copy, etc.)
- Undo/redo for assignments
- Drag to reorder within same table

---

## Code Structure

```
frontend/
├── components/
│   ├── draggable_listbox.py      # DraggableListbox class
│   ├── drop_target_panel.py      # DropTargetPanel class
│   └── drag_drop_manager.py      # DragDropManager class
└── views/
    └── main_window.py             # Integration point
```

---

## Testing Checklist

- [ ] Drag from list to Table 1
- [ ] Drag from list to Table 2, 3, 4
- [ ] Drag to full table (should reject)
- [ ] Drag from table back to list
- [ ] Drag between tables (Table 1 → Table 2)
- [ ] Visual feedback appears on hover
- [ ] Ghost preview follows cursor
- [ ] Invalid drops show feedback
- [ ] Assignment state updates correctly
- [ ] Unassigned list updates after drag
- [ ] Table panels update after drag
- [ ] No crashes or errors during drag
- [ ] Works after window resize

---

## Alternatives Considered

### Alternative 1: Right-click Context Menu
- Right-click bracket → "Assign to Table 1/2/3/4"
- Simpler to implement
- Less intuitive than drag & drop

### Alternative 2: Double-click to Assign
- Double-click assigns to next available table
- Very simple
- Less control over which table

### Alternative 3: Keyboard Shortcuts
- Select + press 1/2/3/4 to assign to table
- Fastest for power users
- Not discoverable for new users

**Recommendation: Implement Drag & Drop + Keep Button Interface**
- Drag & drop for visual users
- Buttons for precision/accessibility
- Best of both worlds

---

## Benefits of Drag & Drop

✅ **Intuitive**: Matches real-world behavior
✅ **Visual**: See what you're moving
✅ **Fast**: One smooth motion instead of click-select-click
✅ **Flexible**: Can reorganize easily
✅ **Professional**: Modern UX expected in desktop apps

---

## Next Steps After Approval

1. Create draggable_listbox.py component
2. Create drop_target_panel.py component
3. Create drag_drop_manager.py coordinator
4. Integrate into main_window.py
5. Add visual feedback (highlights, cursors)
6. Test all drag scenarios
7. Add animations and polish
8. User testing and refinement

**Estimated Effort**: 1-2 weeks for full implementation with polish
