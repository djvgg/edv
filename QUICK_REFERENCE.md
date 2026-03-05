# Quick Reference Guide - Helper Methods & Screen Templates

**Last Updated:** February 19, 2026

---

## Quick Links

- **Complete Architecture:** See `ARCHITECTURE.md`
- **Component Examples:** See sections below
- **Styling Guide:** See `frontend/STYLES_GUIDE.md`

---

## 🎨 Styling Quick Reference

### Import Styles
```python
from frontend.styles import COLORS, FONTS, apply_button_style, apply_label_style, create_dark_frame
```

### Common Colors
```python
COLORS['bg_dark']           # #1e1e1e (main background)
COLORS['bg_panel']          # #252525 (panel background)
COLORS['text_primary']      # #ffffff (white text)
COLORS['accent_blue']       # #2d5aa0 (primary accent)
COLORS['accent_green']      # #4ec94e (success)
COLORS['accent_red']        # #e74c3c (error)
COLORS['border']            # #3a3a3a (borders)
```

### Common Fonts
```python
FONTS['heading_xl']         # Large heading (Consolas, 18, bold)
FONTS['heading_lg']         # Medium heading (Consolas, 16, bold)
FONTS['heading_md']         # Small heading (Arial, 12, bold)
FONTS['body_lg']            # Large body (Consolas, 12)
FONTS['body_md']            # Medium body (Consolas, 11)
FONTS['body_sm']            # Small body (Consolas, 10)
FONTS['mono_md']            # Monospace (Consolas, 10)
```

### Button Styles
```python
apply_button_style(button, style='primary')     # Blue, main action
apply_button_style(button, style='success')     # Green, success state
apply_button_style(button, style='secondary')   # Gray, secondary
apply_button_style(button, style='small')       # Small action button
```

---

## 📊 Frontend Utilities Reference

### Bracket Rendering
```python
from frontend.utils import (
    build_bracket_rounds,
    calculate_box_size,
    draw_bracket_on_canvas
)

# 1. Build rounds from bracket data
rounds = build_bracket_rounds(
    bracket=[('Player1', 'Player2'), ('Player3', 'Player4')],
    normalized_participants=[
        {'Name': 'Player1', 'Verein': 'Club A'},
        {'Name': 'Player2', 'Verein': 'Club B'},
    ]
)

# 2. Calculate optimal box sizing
boxWidth, boxHeight, xGap, yGap = calculate_box_size(
    rounds=rounds,
    zoom_level=1.0  # 1.0 = normal, 2.0 = 2x zoom
)

# 3. Draw bracket on canvas
draw_bracket_on_canvas(
    canvas=my_canvas,
    rounds=rounds,
    positions={(0, 0): (100, 50), (0, 1): (100, 150)},  # Map (round, match) to (x, y)
    boxWidth=boxWidth,
    boxHeight=boxHeight,
    zoom_level=1.0,
    colors=COLORS,
    fonts=FONTS
)
```

### Pool Rendering
```python
from frontend.utils import (
    split_into_pools,
    determine_pool_structure,
    calculate_pool_positions,
    draw_pools_on_canvas,
    draw_pool_table
)

# 1. Split participants into pools
pool_size = 4
pools = split_into_pools(
    participants=normalized_participants,
    pool_size=pool_size
)
# Returns: [['Player1', 'Player2', 'Player3', 'Player4'], ['Player5', ...], ...]

# 2. Determine layout (rows x cols)
rows, cols = determine_pool_structure(num_pools=len(pools))

# 3. Calculate positions for each pool
positions = calculate_pool_positions(
    num_pools=len(pools),
    canvas_width=800,
    canvas_height=600,
    pool_size=pool_size,
    zoom_level=1.0
)

# 4. Draw pools on canvas
draw_pools_on_canvas(
    canvas=my_canvas,
    pools=pools,
    positions=positions,
    pool_size=pool_size,
    zoom_level=1.0,
    colors=COLORS,
    fonts=FONTS
)

# 5. Draw individual pool table (alternative view)
draw_pool_table(
    canvas=pool_canvas,
    pool=['Player1', 'Player2', 'Player3', 'Player4'],
    positions=positions,
    pool_size=4,
    zoom_level=1.0,
    colors=COLORS,
    fonts=FONTS
)
```

### Participant Loading
```python
from frontend.utils import load_participants_from_xlsx, normalize_participants

# 1. Load from XLSX (tries judgefrontend, falls back to pandas)
raw_data = load_participants_from_xlsx('path/to/participants.xlsx')

# 2. Normalize field names
normalized = normalize_participants(raw_data)
# Result: [
#     {'Name': 'John Doe', 'Verein': 'Club X', 'Gender': 'M', 'Age': 13, 'Weight': 65},
#     ...
# ]
```

### Bracket Caching
```python
from frontend.utils import (
    save_bracket_to_cache,
    load_bracket_from_cache,
    clear_bracket_cache
)

# Save bracket to cache
save_bracket_to_cache(
    key='u13_male_65kg',
    bracket_data={'rounds': [...], 'metadata': {...}}
)

# Load from cache
cached_bracket = load_bracket_from_cache('u13_male_65kg')
if cached_bracket:
    bracket = cached_bracket
else:
    bracket = make_bracket(...)  # Generate new

# Clear cache
clear_bracket_cache()
```

---

## ⚙️ Backend Service Reference

### Bracket Service Functions
```python
from backend.services.bracket_service import (
    set_bracket_config,
    get_age_group,
    get_weight_class,
    get_pool_size,
    make_bracket,
    export_all_brackets
)

# Initialize configuration (do this once on startup)
set_bracket_config('path/to/bracket_config.xlsx')

# Get age group from age
age_group = get_age_group(age=13)  # Returns 'U13'

# Get weight class
weight_class = get_weight_class(
    weight=65.5,
    gender='male',
    age_group='U13'  # Optional
)  # Returns '-67kg'

# Get pool size for age group
pool_size = get_pool_size('U9')  # Returns 4

# Generate bracket
bracket = make_bracket(
    participants=normalized_participants,
    age_group='U13',
    gender='male',
    weight_class='-67kg'
)

# Export all brackets
export_all_brackets(
    brackets_dict=all_brackets,
    output_dir='output/'
)
```

---

## 📋 Repository Pattern Reference

### Configuration Repository
```python
from backend.data.repositories.config_repository import ConfigRepository

config = ConfigRepository('path/to/bracket_config.xlsx')

# Get age group
age_group = config.get_age_group(age=13)

# Get weight class
weight_class = config.get_weight_class(65.5, 'male', 'U13')

# Get pool size
pool_size = config.get_pool_size('U9')
```

### Participant Repository
```python
from backend.data.repositories.participant_repository import fetch_participants_from_db

# Query participants from database
participants = fetch_participants_from_db(
    age_group='U13',
    gender='male',
    weight_class='-67kg'
)
```

---

## 🔧 Logging Reference

### Setup Logger
```python
from utils.logging import get_logger

# Create module-specific logger
logger = get_logger('my_module')

# Log at different levels
logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

**Logs are saved to:** `logs/<module_name>/`

---

## 📱 Screen Template (Minimal)

```python
# frontend/views/my_screen.py
import tkinter as tk
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from ..styles import COLORS, FONTS, apply_button_style, create_dark_frame

logger = get_logger('my_screen')

class MyScreen(tk.Frame):
    """Description of this screen's purpose."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.init_ui()
    
    def init_ui(self):
        """Build the UI."""
        # Title
        title = tk.Label(self, text="Screen Title", 
                        bg=COLORS['bg_dark'], font=FONTS['heading_lg'],
                        fg=COLORS['text_primary'])
        title.pack(pady=10)
        
        # Content
        content = create_dark_frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Your widgets here...
    
    def load_data(self):
        """Load data when screen is shown."""
        pass
    
    def on_close(self):
        """Cleanup when screen is hidden."""
        pass
```

---

## 📱 Screen Template (Data Form)

```python
# frontend/views/form_screen.py
import tkinter as tk
from tkinter import messagebox
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from ..styles import (COLORS, FONTS, apply_button_style, 
                     apply_entry_style, apply_label_style, create_dark_frame)
from backend.services.bracket_service import get_age_group, get_weight_class

logger = get_logger('form_screen')

class FormScreen(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.data = {}
        self.init_ui()
    
    def init_ui(self):
        # Title
        title = tk.Label(self, text="Data Entry Form", 
                        bg=COLORS['bg_dark'], font=FONTS['heading_lg'],
                        fg=COLORS['text_primary'])
        title.pack(pady=10)
        
        # Form frame
        form = create_dark_frame(self)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Name field
        name_label = tk.Label(form, text="Name:", 
                             bg=COLORS['bg_panel'], fg=COLORS['text_primary'])
        apply_label_style(name_label, 'body_md')
        name_label.pack(anchor='w', pady=5)
        
        name_entry = tk.Entry(form, bg=COLORS['bg_input'],
                             fg=COLORS['text_primary'], width=30)
        apply_entry_style(name_entry)
        name_entry.pack(fill=tk.X, pady=5)
        
        # Age field
        age_label = tk.Label(form, text="Age:", 
                            bg=COLORS['bg_panel'], fg=COLORS['text_primary'])
        apply_label_style(age_label, 'body_md')
        age_label.pack(anchor='w', pady=5)
        
        age_entry = tk.Entry(form, bg=COLORS['bg_input'],
                            fg=COLORS['text_primary'], width=30)
        apply_entry_style(age_entry)
        age_entry.pack(fill=tk.X, pady=5)
        
        # Buttons
        button_frame = tk.Frame(form, bg=COLORS['bg_panel'])
        button_frame.pack(fill=tk.X, pady=20)
        
        submit_btn = tk.Button(button_frame, text="Submit",
                              command=self.on_submit)
        apply_button_style(submit_btn, style='primary')
        submit_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="Cancel",
                              command=self.on_cancel)
        apply_button_style(cancel_btn, style='secondary')
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Store references
        self.entries = {'name': name_entry, 'age': age_entry}
    
    def on_submit(self):
        """Handle form submission."""
        try:
            data = {k: v.get() for k, v in self.entries.items()}
            
            # Validate
            if not data['name'].strip():
                messagebox.showerror("Error", "Name is required")
                return
            
            # Process
            self.logger.info(f"Submitted: {data}")
            age_group = get_age_group(int(data['age']))
            self.logger.info(f"Age group: {age_group}")
            
            messagebox.showinfo("Success", "Data saved!")
            
        except Exception as e:
            self.logger.error(f"Submission error: {e}")
            messagebox.showerror("Error", str(e))
    
    def on_cancel(self):
        """Clear form."""
        for entry in self.entries.values():
            entry.delete(0, tk.END)
```

---

## 📱 Screen Template (List View)

```python
# frontend/views/list_screen.py
import tkinter as tk
from tkinter import ttk
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from ..styles import (COLORS, FONTS, apply_button_style, 
                     apply_label_style, apply_listbox_style, create_dark_frame)

logger = get_logger('list_screen')

class ListScreen(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.items = []
        self.init_ui()
    
    def init_ui(self):
        # Title
        title = tk.Label(self, text="Event List", 
                        bg=COLORS['bg_dark'], font=FONTS['heading_lg'],
                        fg=COLORS['text_primary'])
        title.pack(pady=10)
        
        # Control buttons
        control_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        control_frame.pack(fill=tk.X, padx=10)
        
        refresh_btn = tk.Button(control_frame, text="Refresh",
                               command=self.load_data)
        apply_button_style(refresh_btn, style='secondary')
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # List frame
        list_frame = create_dark_frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollbar + Listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(list_frame,
                                 bg=COLORS['bg_input'],
                                 fg=COLORS['text_primary'],
                                 yscrollcommand=scrollbar.set,
                                 font=FONTS['body_md'])
        apply_listbox_style(self.listbox)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Bind double-click
        self.listbox.bind('<Double-Button-1>', lambda e: self.on_select())
    
    def load_data(self):
        """Load items into list."""
        self.listbox.delete(0, tk.END)
        
        # Example: Load from service
        items = ['Event 1', 'Event 2', 'Event 3']
        
        for item in items:
            self.listbox.insert(tk.END, item)
        
        self.logger.info(f"Loaded {len(items)} items")
    
    def on_select(self):
        """Handle item selection."""
        sel = self.listbox.curselection()
        if sel:
            item = self.listbox.get(sel[0])
            self.logger.info(f"Selected: {item}")
```

---

## 🔄 Multi-Threading Template

```python
# For long-running operations
import threading

class MyScreen(tk.Frame):
    def on_load_bracket(self):
        """Load bracket in background."""
        # Show loading state
        self.status_label.config(text="Loading...")
        
        # Run in background thread
        thread = threading.Thread(target=self.load_bracket_worker)
        thread.daemon = True
        thread.start()
    
    def load_bracket_worker(self):
        """Background worker for bracket loading."""
        try:
            # Long operation
            bracket = make_bracket(self.participants)
            
            # Update UI from main thread
            self.master.after(0, lambda: self.on_bracket_loaded(bracket))
            
        except Exception as e:
            self.logger.error(f"Bracket loading failed: {e}")
            self.master.after(0, lambda: self.on_load_error(str(e)))
    
    def on_bracket_loaded(self, bracket):
        """Called when bracket is loaded."""
        self.status_label.config(text="Bracket loaded!")
        self.bracket = bracket
        self.render_bracket()
    
    def on_load_error(self, error):
        """Called when loading fails."""
        self.status_label.config(text=f"Error: {error}")
```

---

## 🎯 Common Patterns

### Pattern 1: Load Data on Screen Show
```python
class MyScreen(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.data = None
    
    def load_data(self):
        """Called when screen is shown."""
        self.data = fetch_data_from_service()
        self.refresh_ui()
    
    def refresh_ui(self):
        """Update UI with loaded data."""
        # Update widgets with self.data
        pass
```

### Pattern 2: Screen Communication
```python
# In main_window.py
class BracketViewerApp(tk.Tk):
    def show_screen(self, screen_name, data=None):
        """Switch screen and pass data."""
        screen = self.screens[screen_name]
        if hasattr(screen, 'load_data'):
            screen.load_data(data)
        screen.pack(fill=tk.BOTH, expand=True)
```

### Pattern 3: Dialog Pattern
```python
class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, message, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("300x150")
        self.configure(bg=COLORS['bg_dark'])
        self.callback = callback
        
        # Message
        label = tk.Label(self, text=message, bg=COLORS['bg_dark'],
                        fg=COLORS['text_primary'], wraplength=280)
        label.pack(pady=10)
        
        # Buttons
        button_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        button_frame.pack(pady=10)
        
        ok_btn = tk.Button(button_frame, text="OK",
                          command=lambda: self.finish(True))
        apply_button_style(ok_btn, style='primary')
        ok_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="Cancel",
                              command=lambda: self.finish(False))
        apply_button_style(cancel_btn, style='secondary')
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def finish(self, result):
        self.callback(result)
        self.destroy()
```

---

## 💡 Best Practices Checklist

Before creating a new screen:

- [ ] Import styles from `frontend.styles`
- [ ] Create logger with `get_logger()`
- [ ] Inherit from `tk.Frame`
- [ ] Set background to `COLORS['bg_dark']`
- [ ] Implement `load_data()` for dynamic content
- [ ] Implement `on_close()` for cleanup
- [ ] Use repositories for data access
- [ ] Handle exceptions with try/except
- [ ] Use threading for long operations
- [ ] Add to main window's screen dictionary
- [ ] Test with multiple data sizes

---

## 🚀 Quick Start: Creating Your First Screen

1. **Create file:** `frontend/views/new_screen.py`
2. **Copy template:** Use one of the templates above
3. **Add to main window:** Edit `frontend/views/main_window.py`
4. **Register screen:**
   ```python
   from .new_screen import NewScreen
   self.screens['new'] = NewScreen(self)
   ```
5. **Add navigation button:**
   ```python
   btn = tk.Button(self, text="Go to New Screen",
                   command=lambda: self.show_screen('new'))
   apply_button_style(btn)
   ```

---

## 📚 File Reference

| File | Purpose | Key Functions |
|------|---------|---|
| `frontend/styles.py` | Styling system | `COLORS`, `FONTS`, `apply_*_style()` |
| `frontend/utils/bracket_renderer.py` | Bracket visualization | `build_bracket_rounds()`, `calculate_box_size()`, `draw_bracket_on_canvas()` |
| `frontend/utils/pool_renderer.py` | Pool visualization | `split_into_pools()`, `draw_pools_on_canvas()`, `draw_pool_table()` |
| `frontend/utils/participant_loader.py` | Data loading | `load_participants_from_xlsx()`, `normalize_participants()` |
| `frontend/utils/bracket_cache.py` | Caching | `save_bracket_to_cache()`, `load_bracket_from_cache()` |
| `backend/services/bracket_service.py` | Service layer | `get_age_group()`, `get_weight_class()`, `make_bracket()` |
| `utils/bracket_utils.py` | Core logic | Bracket algorithms, configuration |
| `utils/logging/__init__.py` | Logging | `get_logger()` |

---

**Happy coding! 🎉**
