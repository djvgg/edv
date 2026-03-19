# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Reusable UI styles for Tournament Management frontend.
Dark theme with modern, clean aesthetics based on an 8px grid.
"""

import tkinter as tk

# ============================================================================
# DESIGN TOKENS
# ============================================================================

# SPACING SYSTEM (8px Grid)
SPACING = {
    'xs': 4,
    'sm': 8,
    'md': 16,
    'lg': 24,
    'xl': 32,
    'xxl': 48,
}

# ============================================================================
# COLOR PALETTE
# ============================================================================

COLORS = {
    # Dark theme colors
    'bg_dark': '#292C34',           # Main background (shadow grey)
    'bg_darker': '#6D737C',         # Darker variant (slate grey)
    'bg_panel': '#252525',          # Panel background
    'bg_input': '#2d2d2d',          # Input fields

    # Text colors
    'text_primary': '#ffffff',      # Primary text (white)
    'text_secondary': '#ADB0B8',    # Secondary text (pale slate)
    'text_muted': '#ADB0B8',        # Muted text (light gray)
    'text_disabled': '#B58B82',     # Disabled text (pink)

    # Accent colors
    'accent_blue': '#7F85C5',       # Primary blue (soft periwinkle)
    'accent_blue_hover': '#22AAF0', # Fresh sky
    'accent_purple': '#9F80F8',     # Bright lavender
    'accent_violet': '#E590E8',     # Light violet
    'accent_green': '#4CCD70',      # Emerald
    'accent_red': '#B58B82',        # Rosy taupe
    'accent_orange': '#F5CA74',     # Jasmine

    # Neutral colors
    'border': '#3a3a3a',            # Border color
    'border_light': '#ADB0B8',      # Light border (pale slate)
    'white': '#ffffff',
    'black': '#000000',
}

# ============================================================================
# TYPOGRAPHY (Rubik Scale)
# ============================================================================

FONTS = {
    'heading_xl': ('Rubik', 22, 'bold'),    # Section Headers
    'heading_lg': ('Rubik', 18, 'bold'),    # Sub-sections
    'heading_md': ('Rubik', 16, 'bold'),    # Panel Titles
    'heading_sm': ('Rubik', 12, 'bold'),

    'body_lg': ('Rubik', 12),
    'body_md': ('Rubik', 11),               # Standard Body Text
    'body_sm': ('Rubik', 10),
    'body_xs': ('Rubik', 9),

    'mono_md': ('Consolas', 10),              # Standard monospaced for technical data
    'mono_sm': ('Consolas', 9),
    
    # Aliases for clarity
    'data_table': ('Consolas', 10),
    
    # Legacy fallbacks
    'list_mono': ('Consolas', 10),
    'list_mono_bold': ('Consolas', 10, 'bold'),
    'preview_title': ('Rubik', 16, 'bold'), # Alias for heading_md
    'preview_text': ('Rubik', 11),           # Alias for body_md (entry fields)
    'preview_label': ('Rubik', 10),          # Alias for body_sm (warning labels)
    'preview_small': ('Rubik', 9),           # Alias for body_xs (small info)
    'preview_info': ('Rubik', 10),           # Alias for body_sm
    'preview_hint': ('Rubik', 9),            # Alias for body_xs
}

# ============================================================================
# COMPONENT STYLES
# ============================================================================

BUTTON_STYLES = {
    'primary': {
        'bg': COLORS['accent_blue'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_lg'],
        'relief': 'flat',
        'padx': SPACING['md'],
        'pady': SPACING['sm'],
        'activebackground': COLORS['accent_blue_hover'],
        'activeforeground': COLORS['text_primary'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
    'success': {
        'bg': COLORS['accent_green'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_lg'],
        'relief': 'flat',
        'padx': SPACING['md'],
        'pady': SPACING['sm'],
        'activebackground': COLORS['accent_green'],
        'activeforeground': COLORS['white'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
    'secondary': {
        'bg': COLORS['border'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_lg'],
        'relief': 'flat',
        'padx': SPACING['md'],
        'pady': SPACING['sm'],
        'activebackground': COLORS['border_light'],
        'activeforeground': COLORS['white'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
    'small': {
        'bg': COLORS['accent_blue'],
        'fg': COLORS['text_primary'],
        'font': FONTS['body_sm'],
        'relief': 'flat',
        'padx': SPACING['sm'],
        'pady': SPACING['xs'],
        'activebackground': COLORS['accent_blue_hover'],
        'activeforeground': COLORS['text_primary'],
        'cursor': 'hand2',
        'borderwidth': 0,
    },
}

FRAME_STYLES = {
    'dark': {
        'bg': COLORS['bg_dark'],
    },
    'panel': {
        'bg': COLORS['bg_panel'],
        'relief': 'flat',
        'borderwidth': 0,
        'padx': SPACING['md'],
        'pady': SPACING['md'],
    },
}

LABEL_STYLES = {
    'heading_xl': {
        'font': FONTS['heading_xl'],
        'fg': COLORS['text_primary'],
    },
    'heading_md': {
        'font': FONTS['heading_md'],
        'fg': COLORS['text_primary'],
    },
    'body': {
        'font': FONTS['body_md'],
        'fg': COLORS['text_primary'],
    },
    'subtitle': {
        'font': FONTS['body_md'],
        'fg': COLORS['text_secondary'],
    },
    'info': {
        'font': FONTS['body_xs'],
        'fg': COLORS['text_muted'],
    },
    'status_success': {
        'font': FONTS['body_sm'],
        'fg': COLORS['accent_green'],
    },
    'status_error': {
        'font': FONTS['body_sm'],
        'fg': COLORS['accent_red'],
    },
}

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

ENTRY_STYLE = {
    'bg': COLORS['bg_input'],
    'fg': COLORS['text_primary'],
    'font': FONTS['body_sm'],
    'insertbackground': COLORS['text_primary'],
    'borderwidth': 1,
    'relief': 'solid',
    'highlightthickness': 0,
}

SCROLLBAR_STYLE = {
    'background': COLORS['bg_panel'],
    'troughcolor': COLORS['bg_dark'],
    'bordercolor': COLORS['bg_dark'],
    'arrowcolor': COLORS['text_secondary'],
    'lightcolor': COLORS['bg_panel'],
    'darkcolor': COLORS['bg_panel'],
}

SCROLLBAR_ACTIVE_STYLE = {
    'background': COLORS['bg_input'],
    'arrowcolor': COLORS['text_primary'],
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def apply_button_style(button, style='primary'):
    """Apply a predefined button style."""
    if style in BUTTON_STYLES:
        button.config(**BUTTON_STYLES[style])
    else:
        raise ValueError(f"Unknown button style: {style}")

def apply_label_style(label, style='heading_md'):
    """Apply a predefined label style."""
    if style in LABEL_STYLES:
        # Start by assuming background of parent (pseudo-transparency)
        try:
            parent_bg = label.master.cget('bg')
            label.config(bg=parent_bg)
        except Exception:
            label.config(bg=COLORS['bg_dark'])
            
        # Apply style foreground and font
        label.config(**LABEL_STYLES[style])
    else:
        raise ValueError(f"Unknown label style: {style}")

def apply_listbox_style(listbox):
    """Apply dark theme styling to a Listbox."""
    listbox.config(**LISTBOX_STYLE)

def apply_entry_style(entry):
    """Apply dark theme styling to an Entry."""
    entry.config(**ENTRY_STYLE)

def create_dark_frame(parent, **kwargs):
    """Create a frame with dark theme background."""
    defaults = FRAME_STYLES['dark'].copy()
    defaults.update(kwargs)
    return tk.Frame(parent, **defaults)

def create_panel_frame(parent, **kwargs):
    """Create a card-like panel frame."""
    defaults = FRAME_STYLES['panel'].copy()
    defaults.update(kwargs)
    return tk.Frame(parent, **defaults)

# ============================================================================
# SPECIALIZED STYLES
# ============================================================================

TABLE_PANEL_STYLE = {
    'bg': COLORS['bg_panel'],
    'fg': COLORS['text_primary'],
    'font': FONTS['heading_md'],
    'borderwidth': 1,
    'relief': 'solid',
    'labelanchor': 'n',
    'padx': SPACING['md'],
    'pady': SPACING['md'],
}

def apply_table_panel_style(labelframe):
    """Apply styling to table assignment panels."""
    labelframe.config(**TABLE_PANEL_STYLE)

