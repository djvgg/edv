# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Reusable UI styles for Tournament Management frontend.
Dark theme with modern, clean aesthetics.

Usage:
    from frontend.styles import COLORS, FONTS, apply_button_style

    button = tk.Button(root, text="Click Me")
    apply_button_style(button, style='primary')
"""

import tkinter as tk

# ============================================================================
# COLOR PALETTE
# ============================================================================

COLORS = {
    # Dark theme colors
    'bg_dark': '#1e1e1e',           # Main background (dark gray)
    'bg_darker': '#141414',         # Darker variant
    'bg_panel': '#252525',          # Panel background
    'bg_input': '#2d2d2d',          # Input fields

    # Text colors
    'text_primary': '#ffffff',      # Primary text (white)
    'text_secondary': '#aaaaaa',    # Secondary text (light gray)
    'text_muted': '#888888',        # Muted text (medium gray)
    'text_disabled': '#555555',     # Disabled text

    # Accent colors
    'accent_blue': '#2d5aa0',       # Primary blue
    'accent_blue_hover': '#3a6bc5', # Blue hover state
    'accent_green': '#4ec94e',      # Success green
    'accent_red': '#e74c3c',        # Error red
    'accent_orange': '#f39c12',     # Warning orange

    # Neutral colors
    'border': '#3a3a3a',            # Border color
    'border_light': '#555555',      # Light border
    'white': '#ffffff',
    'black': '#000000',
}

# ============================================================================
# TYPOGRAPHY
# ============================================================================

FONTS = {
    'heading_xl': ('Consolas', 18, 'bold'),
    'heading_lg': ('Consolas', 16, 'bold'),
    'heading_md': ('Arial', 12, 'bold'),
    'heading_sm': ('Arial', 10, 'bold'),

    'body_lg': ('Consolas', 12),
    'body_md': ('Consolas', 11),
    'body_sm': ('Consolas', 10),
    'body_xs': ('Consolas', 9),

    'mono_md': ('Consolas', 10),
    'mono_sm': ('Consolas', 9),
    
    # Custom fonts for Group Preview Screen and Editor
    'preview_title': ('Arial', 14, 'bold'),
    'preview_label': ('Arial', 9, 'bold'),
    'preview_text': ('Arial', 11),
    'preview_small': ('Arial', 9),
    'preview_info': ('Arial', 10),
    'preview_hint': ('Arial', 8),
    
    # Custom lists
    'list_mono': ('Courier', 10),
    'list_mono_bold': ('Courier', 10, 'bold'),
    'list_ui': ('Segoe UI', 11),
}

# ============================================================================
# BUTTON STYLES
# ============================================================================

BUTTON_STYLES = {
    'primary': {
        'bg': COLORS['accent_blue'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_lg'],
        'relief': 'flat',
        'padx': 20,
        'pady': 8,
        'activebackground': COLORS['accent_blue_hover'],
        'activeforeground': COLORS['text_primary'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
    'success': {
        'bg': COLORS['accent_green'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_md'],
        'relief': 'flat',
        'padx': 15,
        'pady': 6,
        'activebackground': COLORS['accent_green'],
        'activeforeground': COLORS['text_primary'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
    'secondary': {
        'bg': COLORS['border'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_md'],
        'relief': 'flat',
        'padx': 15,
        'pady': 6,
        'activebackground': COLORS['border_light'],
        'activeforeground': COLORS['text_primary'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
    'small': {
        'bg': COLORS['accent_blue'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_sm'],
        'relief': 'flat',
        'padx': 10,
        'pady': 4,
        'activebackground': COLORS['accent_blue_hover'],
        'activeforeground': COLORS['text_primary'],
        'cursor': 'hand2',
        'borderwidth': 0,
        'width': 3,
    },
}

# ============================================================================
# FRAME STYLES
# ============================================================================

FRAME_STYLES = {
    'dark': {
        'bg': COLORS['bg_dark'],
    },
    'panel': {  # UNUSED - create_panel_frame not called
        'bg': COLORS['bg_panel'],
        'relief': 'flat',
        'borderwidth': 1,
    },
    'light': {
        'bg': '#f0f0f0',
    },
}

# ============================================================================
# LABEL STYLES
# ============================================================================

LABEL_STYLES = {
    'heading_xl': {
        'font': FONTS['heading_xl'],
        'bg': COLORS['bg_dark'],
        'fg': COLORS['text_primary'],
    },
    'heading_md': {
        'font': FONTS['heading_md'],
        'bg': COLORS['bg_dark'],
        'fg': COLORS['text_primary'],
    },
    'subtitle': {
        'font': FONTS['body_md'],
        'bg': COLORS['bg_dark'],
        'fg': COLORS['text_secondary'],
    },
    'info': {
        'font': FONTS['body_xs'],
        'bg': COLORS['bg_dark'],
        'fg': COLORS['text_muted'],
    },
    'status_success': {
        'font': FONTS['body_sm'],
        'bg': COLORS['bg_dark'],
        'fg': COLORS['accent_green'],
    },
    'status_error': {
        'font': FONTS['body_sm'],
        'bg': COLORS['bg_dark'],
        'fg': COLORS['accent_red'],
    },
}

# ============================================================================
# LISTBOX STYLES
# ============================================================================

LISTBOX_STYLE = {
    'bg': COLORS['bg_input'],
    'fg': COLORS['text_primary'],
    'selectbackground': COLORS['accent_blue'],
    'selectforeground': COLORS['text_primary'],
    'font': FONTS['body_sm'],
    'borderwidth': 1,
    'relief': 'solid',
    'highlightthickness': 0,
}

# ============================================================================
# ENTRY STYLES
# ============================================================================

ENTRY_STYLE = {
    'bg': COLORS['bg_input'],
    'fg': COLORS['text_primary'],
    'font': FONTS['body_sm'],
    'insertbackground': COLORS['text_primary'],
    'borderwidth': 1,
    'relief': 'solid',
    'highlightthickness': 0,
}

# ============================================================================
# SCROLLBAR STYLES (ttk.Scrollbar)
# ============================================================================

SCROLLBAR_STYLE = {
    'background': COLORS['bg_panel'],      # Scrollbar thumb
    'troughcolor': COLORS['bg_dark'],      # Scrollbar track/trough
    'bordercolor': COLORS['bg_dark'],      # Border
    'arrowcolor': COLORS['text_secondary'], # Arrow buttons
    'lightcolor': COLORS['bg_panel'],      # Light edge
    'darkcolor': COLORS['bg_panel'],       # Dark edge
}

SCROLLBAR_ACTIVE_STYLE = {
    'background': COLORS['bg_input'],      # Thumb on hover
    'arrowcolor': COLORS['text_primary'],  # Arrow on hover
}

# ============================================================================
# CANVAS STYLES
# ============================================================================

CANVAS_STYLE = {  # UNUSED - apply_canvas_style not called
    'bg': COLORS['white'],
    'highlightthickness': 0,
    'borderwidth': 1,
    'relief': 'solid',
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def apply_button_style(button, style='primary'):
    """
    Apply a predefined button style.

    Args:
        button: tk.Button widget
        style: Style name ('primary', 'success', 'secondary', 'small')

    Example:
        btn = tk.Button(root, text="Click Me")
        apply_button_style(btn, 'primary')
    """
    if style in BUTTON_STYLES:
        button.config(**BUTTON_STYLES[style])
    else:
        raise ValueError(f"Unknown button style: {style}")


def apply_label_style(label, style='heading_md'):
    """
    Apply a predefined label style.

    Args:
        label: tk.Label widget
        style: Style name from LABEL_STYLES

    Example:
        lbl = tk.Label(root, text="Title")
        apply_label_style(lbl, 'heading_xl')
    """
    if style in LABEL_STYLES:
        label.config(**LABEL_STYLES[style])
    else:
        raise ValueError(f"Unknown label style: {style}")


def apply_listbox_style(listbox):
    """
    Apply dark theme styling to a Listbox.

    Args:
        listbox: tk.Listbox widget
    """
    listbox.config(**LISTBOX_STYLE)


def apply_entry_style(entry):
    """
    Apply dark theme styling to an Entry.

    Args:
        entry: tk.Entry widget
    """
    entry.config(**ENTRY_STYLE)


def apply_canvas_style(canvas):  # UNUSED - not imported or called
    """
    Apply styling to a Canvas.

    Args:
        canvas: tk.Canvas widget
    """
    canvas.config(**CANVAS_STYLE)


def create_dark_frame(parent, **kwargs):
    """
    Create a frame with dark theme background.

    Args:
        parent: Parent widget
        **kwargs: Additional tk.Frame arguments

    Returns:
        tk.Frame with dark styling
    """
    defaults = FRAME_STYLES['dark'].copy()
    defaults.update(kwargs)
    return tk.Frame(parent, **defaults)


def create_panel_frame(parent, **kwargs):  # UNUSED - not imported or called
    """
    Create a panel frame with darker background.

    Args:
        parent: Parent widget
        **kwargs: Additional tk.LabelFrame arguments

    Returns:
        tk.LabelFrame with panel styling
    """
    defaults = FRAME_STYLES['panel'].copy()
    defaults.update(kwargs)
    return tk.LabelFrame(parent, **defaults)


# ============================================================================
# TABLE PANEL STYLES (for bracket assignment)
# ============================================================================

TABLE_PANEL_STYLE = {
    'bg': COLORS['bg_panel'],
    'fg': COLORS['text_primary'],
    'font': FONTS['heading_md'],
    'borderwidth': 2,
    'relief': 'solid',
    'labelanchor': 'n',
}

def apply_table_panel_style(labelframe):
    """Apply styling to table assignment panels."""
    labelframe.config(**TABLE_PANEL_STYLE)


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

"""
Example usage in a tkinter application:

    import tkinter as tk
    from frontend.styles import (
        COLORS, FONTS,
        apply_button_style,
        apply_label_style,
        create_dark_frame
    )

    root = tk.Tk()
    root.configure(bg=COLORS['bg_dark'])

    # Create styled frame
    frame = create_dark_frame(root)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Create styled label
    title = tk.Label(frame, text="Welcome")
    apply_label_style(title, 'heading_xl')
    title.pack(pady=10)

    # Create styled button
    btn = tk.Button(frame, text="Get Started")
    apply_button_style(btn, 'primary')
    btn.pack(pady=10)

    root.mainloop()
"""
