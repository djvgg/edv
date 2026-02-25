<!-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
SPDX-License-Identifier: GPL-3.0-or-later-->

# Frontend Styles Guide

Reusable dark-themed UI components for Python Tkinter applications.

## Quick Start

```python
import tkinter as tk
from frontend.styles import COLORS, apply_button_style, create_dark_frame

root = tk.Tk()
root.configure(bg=COLORS['bg_dark'])

# Create styled button
btn = tk.Button(root, text="Click Me")
apply_button_style(btn, 'primary')
btn.pack()

root.mainloop()
```

## Available Styles

### Colors
```python
from frontend.styles import COLORS

# Dark theme
COLORS['bg_dark']         # #1e1e1e - Main background
COLORS['bg_panel']        # #252525 - Panel backgrounds
COLORS['bg_input']        # #2d2d2d - Input fields

# Text
COLORS['text_primary']    # #ffffff - White text
COLORS['text_secondary']  # #aaaaaa - Light gray
COLORS['text_muted']      # #888888 - Muted text

# Accents
COLORS['accent_blue']     # #2d5aa0 - Primary blue
COLORS['accent_green']    # #4ec94e - Success green
COLORS['accent_red']      # #e74c3c - Error red
```

### Fonts
```python
from frontend.styles import FONTS

FONTS['heading_xl']       # ('Consolas', 18, 'bold')
FONTS['heading_lg']       # ('Consolas', 16, 'bold')
FONTS['heading_md']       # ('Arial', 12, 'bold')
FONTS['body_lg']          # ('Consolas', 12)
FONTS['body_md']          # ('Consolas', 11)
```

## Button Styles

### Primary Button (Blue)
```python
btn = tk.Button(root, text="Primary Action")
apply_button_style(btn, 'primary')
```

### Success Button (Green)
```python
btn = tk.Button(root, text="Confirm")
apply_button_style(btn, 'success')
```

### Secondary Button (Gray)
```python
btn = tk.Button(root, text="Cancel")
apply_button_style(btn, 'secondary')
```

### Small Button
```python
btn = tk.Button(root, text="1")
apply_button_style(btn, 'small')
```

## Label Styles

```python
from frontend.styles import apply_label_style

# Large heading
title = tk.Label(root, text="Welcome")
apply_label_style(title, 'heading_xl')

# Section heading
section = tk.Label(root, text="Settings")
apply_label_style(section, 'heading_md')

# Subtitle
subtitle = tk.Label(root, text="Configure options")
apply_label_style(subtitle, 'subtitle')

# Info text
info = tk.Label(root, text="Additional information")
apply_label_style(info, 'info')

# Success status
status = tk.Label(root, text="Success!")
apply_label_style(status, 'status_success')

# Error status
error = tk.Label(root, text="Error occurred")
apply_label_style(error, 'status_error')
```

## Listbox Styling

```python
from frontend.styles import apply_listbox_style

listbox = tk.Listbox(root)
apply_listbox_style(listbox)
```

## Entry Styling

```python
from frontend.styles import apply_entry_style

entry = tk.Entry(root)
apply_entry_style(entry)
```

## Frame Helpers

### Dark Frame
```python
from frontend.styles import create_dark_frame

frame = create_dark_frame(root)
frame.pack(fill=tk.BOTH, expand=True)
```

### Custom Frame
```python
from frontend.styles import COLORS

frame = tk.Frame(root, bg=COLORS['bg_panel'])
```

## Table Panels (for bracket assignment)

```python
from frontend.styles import apply_table_panel_style

panel = tk.LabelFrame(root, text="Table 1")
apply_table_panel_style(panel)
```

## Complete Example

```python
import tkinter as tk
from frontend.styles import (
    COLORS, FONTS,
    apply_button_style,
    apply_label_style,
    apply_entry_style,
    create_dark_frame
)

class MyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("My App")
        self.configure(bg=COLORS['bg_dark'])
        self.geometry("600x400")

        # Main container
        main_frame = create_dark_frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title = tk.Label(main_frame, text="Welcome to My App")
        apply_label_style(title, 'heading_xl')
        title.pack(pady=(0, 10))

        # Subtitle
        subtitle = tk.Label(main_frame, text="Enter your information")
        apply_label_style(subtitle, 'subtitle')
        subtitle.pack(pady=(0, 20))

        # Input field
        entry = tk.Entry(main_frame)
        apply_entry_style(entry)
        entry.pack(fill=tk.X, pady=10)

        # Buttons
        btn_frame = create_dark_frame(main_frame)
        btn_frame.pack(pady=20)

        submit_btn = tk.Button(btn_frame, text="Submit")
        apply_button_style(submit_btn, 'primary')
        submit_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = tk.Button(btn_frame, text="Cancel")
        apply_button_style(cancel_btn, 'secondary')
        cancel_btn.pack(side=tk.LEFT, padx=5)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(main_frame, textvariable=self.status_var)
        apply_label_style(status, 'status_success')
        status.pack(side=tk.BOTTOM, pady=10)

if __name__ == '__main__':
    app = MyApp()
    app.mainloop()
```

## Customizing Styles

You can access style dictionaries directly:

```python
from frontend.styles import BUTTON_STYLES

# Get primary button style and modify
custom_style = BUTTON_STYLES['primary'].copy()
custom_style['bg'] = '#ff0000'  # Red background

btn = tk.Button(root, text="Custom", **custom_style)
```

## Color Palette Reference

| Color Variable | Hex Code | Usage |
|---------------|----------|-------|
| `bg_dark` | #1e1e1e | Main background |
| `bg_darker` | #141414 | Darker variant |
| `bg_panel` | #252525 | Panel backgrounds |
| `bg_input` | #2d2d2d | Input fields |
| `text_primary` | #ffffff | Primary text |
| `text_secondary` | #aaaaaa | Secondary text |
| `text_muted` | #888888 | Muted text |
| `accent_blue` | #2d5aa0 | Primary actions |
| `accent_green` | #4ec94e | Success states |
| `accent_red` | #e74c3c | Error states |
| `border` | #3a3a3a | Border color |

## Tips

1. **Consistency**: Always use `create_dark_frame()` for containers instead of plain `tk.Frame()`
2. **Labels**: Use `apply_label_style()` instead of manual font/color configuration
3. **Colors**: Use `COLORS` constants instead of hardcoded hex values
4. **Buttons**: Always apply a style to buttons for consistent appearance

## Copying to Other Projects

To use these styles in another project:

1. Copy `frontend/styles.py` to your project
2. Import and use:
   ```python
   from your_module.styles import COLORS, apply_button_style
   ```

That's it! The styles are completely self-contained.
