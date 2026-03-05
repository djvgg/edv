# Tournament Bracket Manager - One-Page Cheatsheet

**Quick Reference for Common Tasks** | Version 1.0 | Feb 19, 2026

---

## 📐 Architecture Layers

```
┌─────────────────────────────────────┐
│ UI Layer: frontend/views/*.py       │
│ Tkinter screens & widgets           │
├─────────────────────────────────────┤
│ Styling Layer: frontend/styles.py   │
│ COLORS, FONTS, apply_*_style()      │
├─────────────────────────────────────┤
│ Utils Layer: frontend/utils/        │
│ Renderers, loaders, cache           │
├─────────────────────────────────────┤
│ Service Layer: backend/services/    │
│ Thin wrappers, get_age_group(), etc │
├─────────────────────────────────────┤
│ Data Layer: backend/data/           │
│ Repositories, database access       │
├─────────────────────────────────────┤
│ Core Logic: utils/bracket_utils.py  │
│ Bracket algorithms, config loading  │
└─────────────────────────────────────┘
```

---

## 🎨 Styling (5 minutes setup)

```python
from frontend.styles import COLORS, FONTS, apply_button_style

# Colors
COLORS['bg_dark']        # Main background (#1e1e1e)
COLORS['accent_blue']    # Primary accent (#2d5aa0)
COLORS['accent_green']   # Success (#4ec94e)
COLORS['accent_red']     # Error (#e74c3c)
COLORS['text_primary']   # White text (#ffffff)

# Fonts
FONTS['heading_lg']      # Large headings
FONTS['body_md']         # Body text
FONTS['mono_md']         # Monospace

# Apply styles
apply_button_style(btn, style='primary')    # Blue
apply_button_style(btn, style='success')    # Green
apply_button_style(btn, style='secondary')  # Gray
```

---

## 📊 Frontend Utils (Rendering)

```python
from frontend.utils import *

# BRACKET RENDERING
build_bracket_rounds(bracket, participants)
calculate_box_size(rounds, zoom_level=1.0)
draw_bracket_on_canvas(canvas, rounds, positions, boxWidth, boxHeight, zoom_level, COLORS, FONTS)

# POOL RENDERING
split_into_pools(participants, pool_size=4)
determine_pool_structure(num_pools)
calculate_pool_positions(num_pools, canvas_width, canvas_height, pool_size, zoom_level)
draw_pools_on_canvas(canvas, pools, positions, pool_size, zoom_level, COLORS, FONTS)

# PARTICIPANT LOADING
participants = load_participants_from_xlsx('file.xlsx')
participants = normalize_participants(participants)

# CACHING
save_bracket_to_cache(key, bracket_data)
bracket = load_bracket_from_cache(key)
clear_bracket_cache()
```

---

## ⚙️ Backend Services

```python
from backend.services.bracket_service import *

# Initialize (do once on startup)
set_bracket_config('config/bracket_config.xlsx')

# Use these functions
age_group = get_age_group(13)
weight_class = get_weight_class(65.5, 'male', 'U13')
pool_size = get_pool_size('U9')
bracket = make_bracket(participants, age_group, gender, weight_class)
export_all_brackets(brackets_dict, 'output/')
```

---

## 🗂️ Create a New Screen

```python
# 1. Create: frontend/views/my_screen.py
import tkinter as tk
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from ..styles import COLORS, FONTS, apply_button_style, create_dark_frame

class MyScreen(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = get_logger('my_screen')
        self.init_ui()
    
    def init_ui(self):
        title = tk.Label(self, text="My Screen", 
                        bg=COLORS['bg_dark'], font=FONTS['heading_lg'],
                        fg=COLORS['text_primary'])
        title.pack(pady=10)
        # Add widgets...
    
    def load_data(self):
        pass

# 2. Register in main_window.py
from .my_screen import MyScreen
self.screens['my'] = MyScreen(self)

# 3. Add navigation button
btn = tk.Button(self, text="Go", command=lambda: self.show_screen('my'))
apply_button_style(btn)
```

---

## 🔵 Create Data Form Screen

```python
class FormScreen(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = get_logger('form')
        self.init_ui()
    
    def init_ui(self):
        title = tk.Label(self, text="Form", 
                        bg=COLORS['bg_dark'], font=FONTS['heading_lg'])
        title.pack(pady=10)
        
        form = create_dark_frame(self)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Field
        tk.Label(form, text="Name:", bg=COLORS['bg_panel']).pack(anchor='w')
        name_entry = tk.Entry(form, bg=COLORS['bg_input'], fg=COLORS['text_primary'])
        name_entry.pack(fill=tk.X)
        
        # Submit button
        submit = tk.Button(form, text="Submit", command=self.on_submit)
        apply_button_style(submit, style='primary')
        submit.pack(pady=20)
        
        self.entries = {'name': name_entry}
    
    def on_submit(self):
        data = {k: v.get() for k, v in self.entries.items()}
        self.logger.info(f"Submitted: {data}")
```

---

## 🔄 Threading (Long Operations)

```python
import threading

def on_load_bracket(self):
    self.status.config(text="Loading...")
    thread = threading.Thread(target=self.load_worker)
    thread.daemon = True
    thread.start()

def load_worker(self):
    try:
        bracket = make_bracket(self.participants)
        self.master.after(0, lambda: self.on_done(bracket))
    except Exception as e:
        self.logger.error(f"Error: {e}")
        self.master.after(0, lambda: self.on_error(str(e)))

def on_done(self, bracket):
    self.status.config(text="Done!")
    self.bracket = bracket
```

---

## 📝 Logging

```python
from utils.logging import get_logger

logger = get_logger('module_name')
logger.debug("Debug info")
logger.info("Information")
logger.warning("Warning")
logger.error("Error")

# Logs saved to: logs/module_name/
```

---

## 💾 Data Access

```python
from backend.data.repositories.config_repository import ConfigRepository
from backend.data.repositories.participant_repository import fetch_participants_from_db

# Config
config = ConfigRepository('config/bracket_config.xlsx')
age = config.get_age_group(13)

# Participants
participants = fetch_participants_from_db('U13', 'male')
```

---

## 🎯 Common Patterns

### Pattern 1: Load Data Dynamically
```python
def load_data(self, data=None):
    # Called when screen is shown
    self.data = data or self.fetch_from_service()
    self.refresh_ui()

def refresh_ui(self):
    # Update widgets with self.data
    pass
```

### Pattern 2: Modal Dialog
```python
from tkinter import messagebox
result = messagebox.askyesno("Confirm", "Are you sure?")
messagebox.showinfo("Success", "Done!")
messagebox.showerror("Error", "Something went wrong")
```

### Pattern 3: Canvas Drawing
```python
canvas.create_rectangle(x, y, x+w, y+h, outline=COLORS['white'])
canvas.create_text(x+w//2, y+h//2, text="Text", fill=COLORS['text_primary'])
canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=COLORS['white'])
```

---

## 📁 File Structure to Remember

```
edv_backend/
├── frontend/views/main_window.py      ← Create screens here
├── frontend/utils/                    ← Use rendering utils here
├── frontend/styles.py                 ← Import styles from here
├── backend/services/bracket_service.py ← Use services here
└── utils/bracket_utils.py             ← Core logic here
```

---

## ✅ Checklist Before Creating Screen

- [ ] Inherit from `tk.Frame`
- [ ] Import from `frontend.styles`
- [ ] Set `bg=COLORS['bg_dark']`
- [ ] Create logger with `get_logger()`
- [ ] Implement `__init__()` and `init_ui()`
- [ ] Add `load_data()` method
- [ ] Use `apply_*_style()` functions
- [ ] Register in main_window.py
- [ ] Add navigation button
- [ ] Test screen switching

---

## 🚀 Quick Start: 5-Step Process

1. **Read ARCHITECTURE.md** (10 min) - Understand structure
2. **Copy template from QUICK_REFERENCE.md** (2 min) - Find template
3. **Apply styles from this sheet** (3 min) - Style widgets
4. **Register in main_window.py** (2 min) - Add to app
5. **Test and iterate** (5 min) - Verify it works

**Total:** 22 minutes to first working screen

---

## 🔗 Documentation Files

| File | Purpose | Time |
|------|---------|------|
| ARCHITECTURE.md | Full technical docs | 15 min |
| QUICK_REFERENCE.md | Code examples & templates | 5 min |
| DEPENDENCIES.md | Component map & flows | 5 min |
| This Cheatsheet | One-page quick ref | 2 min |

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Import errors | Check sys.path in QUICK_REFERENCE.md |
| Missing colors | Use COLORS dict from frontend/styles.py |
| Widgets look wrong | Apply style with apply_button_style() |
| Long operations freeze UI | Use threading pattern above |
| Data not loading | Implement load_data() method |
| Logging not working | Import get_logger() from utils.logging |

---

## 💡 Remember

- **Don't hardcode colors** → Use COLORS
- **Don't hardcode fonts** → Use FONTS
- **Don't skip styling** → Apply styles immediately
- **Don't forget logging** → Log important operations
- **Don't ignore threading** → Use for long operations
- **Do reuse functions** → Check frontend/utils/
- **Do follow patterns** → Copy templates from QUICK_REFERENCE.md
- **Do test early** → Verify screens work immediately

---

**Save this file and bookmark QUICK_REFERENCE.md for copy-paste coding!**

Created: Feb 19, 2026 | Updated: [Today]
