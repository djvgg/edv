# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Reusable UI styles for Tournament Management frontend.
Supports dark and light themes with modern, clean aesthetics based on an 8px grid.
"""

import tkinter as tk
import json
import os
import platform


def _mono_family():
    """Return a monospace family that actually exists on the host.

    ``Consolas`` is Windows-only — on macOS Tk silently substitutes a
    *proportional* font, which breaks the space-padded table alignment in the
    Gruppenvorschau (columns drift). Pick a real monospace per OS so the padding
    lines up.
    """
    system = platform.system()
    if system == "Darwin":
        return "Menlo"            # macOS system monospace
    if system == "Windows":
        return "Consolas"
    return "DejaVu Sans Mono"     # common Linux monospace


_MONO = _mono_family()

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
# COLOR PALETTES
# ============================================================================

_COLORS_DARK = {
    'bg_dark': '#292C34',
    'bg_darker': '#6D737C',
    'bg_panel': '#252525',
    'bg_input': '#2d2d2d',

    'text_primary': '#ffffff',
    'text_secondary': '#ADB0B8',
    'text_muted': '#ADB0B8',
    'text_disabled': '#B58B82',

    'accent_blue': '#6068B0',
    'accent_blue_hover': '#1E90D0',
    'accent_purple': '#9F80F8',
    'accent_violet': '#E590E8',
    'accent_green': '#38A85A',
    'accent_red': '#E8ADA3',
    'accent_orange': '#F5CA74',

    'border': '#3a3a3a',
    'border_light': '#ADB0B8',
    'white': '#ffffff',
    'black': '#000000',
}

_COLORS_LIGHT = {
    'bg_dark': '#F0F2F5',
    'bg_darker': '#D5D8DC',
    'bg_panel': '#FFFFFF',
    'bg_input': '#FFFFFF',

    'text_primary': '#1A1A2E',
    'text_secondary': '#5A5E6B',
    'text_muted': '#7A7E8B',
    'text_disabled': '#B0A8A4',

    'accent_blue': '#5B63B7',
    'accent_blue_hover': '#1A8FD0',
    'accent_purple': '#7B5FD4',
    'accent_violet': '#C06CC4',
    'accent_green': '#2EA84E',
    'accent_red': '#C0766A',
    'accent_orange': '#D4A840',

    'border': '#D0D3D8',
    'border_light': '#B0B4BC',
    'white': '#ffffff',
    'black': '#000000',
}

_THEME_PREFS_PATH = os.path.join(os.path.dirname(__file__), '..', '.theme_preference')
_current_theme = 'dark'

def _load_saved_theme():
    try:
        with open(_THEME_PREFS_PATH) as f:
            data = json.load(f)
            return data.get('theme', 'dark')
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 'dark'

_current_theme = _load_saved_theme()

COLORS = dict(_COLORS_LIGHT if _current_theme == 'light' else _COLORS_DARK)

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

    'mono_md': (_MONO, 10),              # Standard monospaced for technical data
    'mono_sm': (_MONO, 9),

    # Aliases for clarity
    'data_table': (_MONO, 10),

    # Legacy fallbacks
    'list_mono': (_MONO, 10),
    'list_mono_bold': (_MONO, 10, 'bold'),
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
        'highlightthickness': 0,
        'highlightbackground': COLORS['accent_blue'],
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
        'highlightthickness': 0,
        'highlightbackground': COLORS['accent_green'],
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
        'highlightthickness': 0,
        'highlightbackground': COLORS['border'],
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
        'highlightthickness': 0,
        'highlightbackground': COLORS['accent_blue'],
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


# ============================================================================
# THEME SWITCHING
# ============================================================================

def get_theme():
    return _current_theme


def set_theme(theme_name):
    global _current_theme
    if theme_name not in ('dark', 'light'):
        raise ValueError(f"Unknown theme: {theme_name}")

    _current_theme = theme_name
    source = _COLORS_LIGHT if theme_name == 'light' else _COLORS_DARK
    COLORS.update(source)
    _rebuild_component_styles()

    try:
        with open(_THEME_PREFS_PATH, 'w') as f:
            json.dump({'theme': theme_name}, f)
    except OSError:
        pass


def toggle_theme():
    set_theme('light' if _current_theme == 'dark' else 'dark')


def _rebuild_component_styles():
    BUTTON_STYLES['primary'].update({
        'bg': COLORS['accent_blue'],
        'fg': COLORS['text_primary'],
        'activebackground': COLORS['accent_blue_hover'],
        'activeforeground': COLORS['text_primary'],
    })
    BUTTON_STYLES['success'].update({
        'bg': COLORS['accent_green'],
        'fg': COLORS['text_primary'],
        'activebackground': COLORS['accent_green'],
        'activeforeground': COLORS['white'],
    })
    BUTTON_STYLES['secondary'].update({
        'bg': COLORS['border'],
        'fg': COLORS['text_primary'],
        'activebackground': COLORS['border_light'],
        'activeforeground': COLORS['white'],
    })
    BUTTON_STYLES['small'].update({
        'bg': COLORS['accent_blue'],
        'fg': COLORS['text_primary'],
        'activebackground': COLORS['accent_blue_hover'],
        'activeforeground': COLORS['text_primary'],
    })

    FRAME_STYLES['dark'].update({'bg': COLORS['bg_dark']})
    FRAME_STYLES['panel'].update({'bg': COLORS['bg_panel']})

    for key in LABEL_STYLES:
        if 'fg' in LABEL_STYLES[key]:
            if key.startswith('status_'):
                continue
            LABEL_STYLES[key]['fg'] = COLORS['text_primary'] if key.startswith('heading') or key == 'body' else COLORS['text_secondary'] if key == 'subtitle' else COLORS['text_muted']

    LABEL_STYLES['status_success']['fg'] = COLORS['accent_green']
    LABEL_STYLES['status_error']['fg'] = COLORS['accent_red']

    LISTBOX_STYLE.update({
        'bg': COLORS['bg_input'],
        'fg': COLORS['text_primary'],
        'selectbackground': COLORS['accent_blue'],
        'selectforeground': COLORS['text_primary'],
    })
    ENTRY_STYLE.update({
        'bg': COLORS['bg_input'],
        'fg': COLORS['text_primary'],
        'insertbackground': COLORS['text_primary'],
    })
    SCROLLBAR_STYLE.update({
        'background': COLORS['bg_panel'],
        'troughcolor': COLORS['bg_dark'],
        'bordercolor': COLORS['bg_dark'],
        'arrowcolor': COLORS['text_secondary'],
        'lightcolor': COLORS['bg_panel'],
        'darkcolor': COLORS['bg_panel'],
    })
    SCROLLBAR_ACTIVE_STYLE.update({
        'background': COLORS['bg_input'],
        'arrowcolor': COLORS['text_primary'],
    })
    TABLE_PANEL_STYLE.update({
        'bg': COLORS['bg_panel'],
        'fg': COLORS['text_primary'],
    })

