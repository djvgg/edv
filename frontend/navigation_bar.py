# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Navigation Bar - Browser-style tab navigation for screens

Displays a horizontal tab bar showing available screens.
Each tab can be clicked to navigate to that screen.
"""

import tkinter as tk
import sys
import os

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from .styles import COLORS, FONTS, SPACING  # noqa: E402

# Debug flag
DEBUG = True
logger = get_logger('navigation_bar', debug_verbose=DEBUG)


class NavigationBar(tk.Frame):
    """
    Browser-style tab navigation bar.
    
    Displays tabs for each visited screen. User can click any tab to navigate.
    Supports tab scrolling if too many tabs to fit.
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'], height=60)
        self.pack_propagate(False)
        
        self.logger = logger
        
        # Store tab data: {screen_key: {'label': str, 'widget': tk.Frame, 'locked': bool}}
        self.tabs = {}
        self.active_tab = None
        self.screen_manager = None  # Will be injected later

        
        # Callback for tab clicks (will be set by ScreenManager)
        self.on_tab_click = None
        
        # UI state
        self.scroll_offset = 0  # For scrolling if too many tabs
        self.tab_width = 120  # Base width per tab
        
        # Create main container frame
        self.container = tk.Frame(self, bg=COLORS['bg_dark'])
        self.container.pack(fill=tk.X, expand=True, padx=SPACING['sm'], pady=SPACING['sm'])
        
        # Left arrow button (for scrolling)
        self.left_arrow = tk.Button(
            self.container,
            text='<',
            width=2,
            height=1,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['body_sm'],
            relief=tk.FLAT,
            command=self._scroll_left
        )
        self.left_arrow.pack(side=tk.LEFT, padx=SPACING['xs'])
        
        # Tabs container frame
        self.tabs_frame = tk.Frame(self.container, bg=COLORS['bg_dark'])
        self.tabs_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=SPACING['sm'])
        
        # Right arrow button (for scrolling)
        self.right_arrow = tk.Button(
            self.container,
            text='>',
            width=2,
            height=1,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['body_sm'],
            relief=tk.FLAT,
            command=self._scroll_right
        )
        self.right_arrow.pack(side=tk.LEFT, padx=SPACING['xs'])
        
        self.logger.debug("NavigationBar initialized")
    
    def set_screen_manager(self, screen_manager):
        """Inject screen manager reference for staleness tracking.
        
        Args:
            screen_manager: ScreenManager instance to query staleness status
        """
        self.screen_manager = screen_manager
        self.logger.debug("Screen manager injected into NavigationBar")
    
    def add_tab(self, screen_key, label, locked=False):
        """
        Add a new tab to the navigation bar.
        
        Args:
            screen_key: Unique identifier for the screen (e.g., 'file_loader')
            label: Display label for the tab (e.g., 'File Loader')
            locked: Whether this tab is locked/disabled
        """
        if screen_key in self.tabs:
            self.logger.warning(f"Tab {screen_key} already exists, updating label")
            self.tabs[screen_key]['label'] = label
            self.tabs[screen_key]['locked'] = locked
            self._render_tabs()
            return
        
        # Store tab info
        self.tabs[screen_key] = {
            'label': label,
            'locked': locked,
            'widget': None  # Will be created during render
        }
        
        self.logger.info(f"Added tab: {screen_key} = '{label}' (locked={locked})")
        self._render_tabs()
    
    def set_active_tab(self, screen_key):
        """
        Highlight a tab as active.
        
        Args:
            screen_key: The screen key to activate
        """
        if screen_key not in self.tabs:
            self.logger.warning(f"Cannot activate non-existent tab: {screen_key}")
            return
        
        self.active_tab = screen_key
        self.logger.debug(f"Active tab set to: {screen_key}")
        self._render_tabs()
    
    def _render_tabs(self):
        """Render all tabs in the tabs_frame."""
        # Clear existing widgets
        for widget in self.tabs_frame.winfo_children():
            widget.destroy()
        
        # Create tab widgets
        for i, (screen_key, tab_info) in enumerate(self.tabs.items()):
            self._create_tab_widget(screen_key, tab_info, i)
    
    def _create_tab_widget(self, screen_key, tab_info, index):
        """
        Create a single tab widget.
        
        Args:
            screen_key: The screen key
            tab_info: Dict with 'label' and 'locked' keys
            index: Tab index
        """
        is_active = (screen_key == self.active_tab)
        is_locked = tab_info['locked']
        
        # Determine colors based on state
        if is_active:
            bg_color = COLORS['accent_blue']
            fg_color = COLORS['text_primary']
        elif is_locked:
            bg_color = COLORS['bg_darker']
            fg_color = COLORS['text_secondary']
        else:
            bg_color = COLORS['bg_panel']
            fg_color = COLORS['text_primary']
        # Create tab frame
        tab_frame = tk.Frame(
            self.tabs_frame,
            bg=bg_color,
            relief=tk.FLAT,
            borderwidth=0,
            height=30
        )
        tab_frame.pack(side=tk.LEFT, padx=SPACING['xs'], fill=tk.Y)
        
        # Create label
        label = tk.Label(
            tab_frame,
            text=tab_info['label'],
            bg=bg_color,
            fg=fg_color,
            font=FONTS['body_sm'],
            padx=SPACING['md'],
            pady=SPACING['xs']
        )
        label.pack(fill=tk.BOTH, expand=True)
        
        # Store reference
        tab_info['widget'] = tab_frame
        
        # Bind click event (will be connected to callback later)
        for widget in [tab_frame, label]:
            widget.bind('<Button-1>', 
                       lambda e, key=screen_key: self._on_tab_click(key) 
                       if not is_locked else None)
        
        # Get staleness status from screen manager if available
        is_stale = False
        if self.screen_manager:
            is_stale = self.screen_manager.is_screen_stale(screen_key)
        
        self.logger.debug(
            f"Created tab widget: {screen_key} (active={is_active}, locked={is_locked}, stale={is_stale})"
        )
    
    def _on_tab_click(self, screen_key):
        """Handle tab click - navigate to the clicked screen."""
        self.logger.debug(f"Tab clicked: {screen_key}")
        
        # Call the callback if it's set (by ScreenManager)
        if self.on_tab_click and callable(self.on_tab_click):
            try:
                self.on_tab_click(screen_key)
            except Exception as e:
                self.logger.error(f"Error in tab click callback: {e}")
        else:
            self.logger.warning(f"No callback set for tab click on {screen_key}")
    
    def _scroll_left(self):
        """Scroll tabs left (for when too many tabs)."""
        self.scroll_offset = max(0, self.scroll_offset - 1)
        self.logger.debug(f"Scroll left: offset={self.scroll_offset}")
        self._render_tabs()
    
    def _scroll_right(self):
        """Scroll tabs right (for when too many tabs)."""
        max_offset = max(0, len(self.tabs) - 3)
        self.scroll_offset = min(max_offset, self.scroll_offset + 1)
        self.logger.debug(f"Scroll right: offset={self.scroll_offset}")
        self._render_tabs()
    
    def enable_tab(self, screen_key):
        """Unlock a tab (make it clickable)."""
        if screen_key in self.tabs:
            self.tabs[screen_key]['locked'] = False
            self.logger.info(f"Tab enabled: {screen_key}")
            self._render_tabs()
    
    def disable_tab(self, screen_key):
        """Lock a tab (make it unclickable)."""
        if screen_key in self.tabs:
            self.tabs[screen_key]['locked'] = True
            self.logger.info(f"Tab disabled: {screen_key}")
            self._render_tabs()
