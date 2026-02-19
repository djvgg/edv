# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Extracted GUI code from bracket_viewer.py

import json
import os
import sys
import threading
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import pandas as pd

# Setup sys.path for backend imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
_judgefrontend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'judgefrontend')
if os.path.exists(_judgefrontend_path):
    sys.path.insert(0, _judgefrontend_path)

from utils.logging import get_logger  # noqa: E402
from backend.services.bracket_service import (  # noqa: E402
    export_all_brackets,
    make_bracket,
    set_bracket_config,
)
from backend.data.repositories.participant_repository import (  # noqa: E402
    fetch_participants_from_db,
)

from ..styles import (  # noqa: E402
    COLORS,
    FONTS,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    apply_table_panel_style,
    create_dark_frame,
)

# Import frontend utilities
from ..utils import (  # noqa: E402
    calculate_box_size,
    load_participants_from_xlsx,
    normalize_participants,
    draw_pools_on_canvas,
)

# Import generation method screen
from .generation_method_screen import GenerationMethodScreen  # noqa: E402

# ===== DEBUG CONFIGURATION =====
# Set to True to print debug logs to console; False to only log to file
DEBUG_VERBOSE = True
# ==============================

# Import from judgefrontend for flexible xlsx handling
judgefrontend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'judgefrontend')
if os.path.exists(judgefrontend_path):
    sys.path.insert(0, judgefrontend_path)
    try:
        from src.xlsxHandler import processXlsx
    except ImportError:
        processXlsx = None
else:
    processXlsx = None


class BracketViewerApp(tk.Tk):
    """Main application window for bracket viewing and management."""

    def __init__(self):
        super().__init__()
        # Initialize logger
        self.logger = get_logger('main_window')
        
        self.title('Tournament Bracket Manager')
        self.geometry('520x440')  
        self.configure(bg="#1e1e1e")

        # Configure dark theme for ttk widgets (scrollbars)
        self.setup_ttk_styles()

        # Setup window close handler to cleanup cache
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize backend config
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'bracket_config.xlsx')
        try:
            set_bracket_config(config_path)
        except Exception as e:
            self.logger.warning(f"Could not load config: {e}")

        # Data
        self.brackets = {}  # {bracket_key: Bracket data}
        self.bracket_cache_file = None
        self.bracket_generation_methods = {}  # {bracket_key: method_name}
        self.viewer_shown = False
        self.zoom_level = 1.0  # Zoom level for bracket visualization
        self.current_bracket_key = None  # Track currently displayed bracket

        # Preview window state
        self.group_listbox_map = {}
        self.preview_search_var = None
        self.preview_count_var = None

        # Rendering cache - stores pre-computed bracket structures
        self.bracket_structure_cache = {}  # {bracket_key: rounds}
        self.bracket_render_cache = {}  # {(bracket_key, zoom_level): rendered canvas items}

        # Start with file loading UI (judgefrontend style)
        self.show_file_loader()

    def setup_ttk_styles(self):
        """Configure ttk styles for dark theme scrollbars."""
        style = ttk.Style()

        # Configure dark scrollbar
        style.theme_use('clam')  # Use clam theme as base (most customizable)

        # Vertical scrollbar
        style.configure('Vertical.TScrollbar',
                       background=COLORS['bg_panel'],
                       troughcolor=COLORS['bg_dark'],
                       bordercolor=COLORS['bg_dark'],
                       arrowcolor=COLORS['text_secondary'],
                       lightcolor=COLORS['bg_panel'],
                       darkcolor=COLORS['bg_panel'])

        # Horizontal scrollbar
        style.configure('Horizontal.TScrollbar',
                       background=COLORS['bg_panel'],
                       troughcolor=COLORS['bg_dark'],
                       bordercolor=COLORS['bg_dark'],
                       arrowcolor=COLORS['text_secondary'],
                       lightcolor=COLORS['bg_panel'],
                       darkcolor=COLORS['bg_panel'])

        # Active (hover) state
        style.map('Vertical.TScrollbar',
                 background=[('active', COLORS['bg_input'])],
                 arrowcolor=[('active', COLORS['text_primary'])])

        style.map('Horizontal.TScrollbar',
                 background=[('active', COLORS['bg_input'])],
                 arrowcolor=[('active', COLORS['text_primary'])])

    def show_file_loader(self):
        """Show initial file loading UI (judgefrontend style)."""
        # Clear any existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Header
        title = tk.Label(self, text="Tournament Bracket Manager")
        apply_label_style(title, 'heading_xl')
        title.pack(pady=(20, 5))

        subtitle = tk.Label(self, text="Bracket Generator & Viewer")
        apply_label_style(subtitle, 'subtitle')
        subtitle.pack(pady=(0, 5))

        # Info label
        self.info_var = tk.StringVar(value="[Waiting for XLSX file...]")
        info_label = tk.Label(self, textvariable=self.info_var)
        apply_label_style(info_label, 'info')
        info_label.pack(pady=(0, 20))

        # Status label (bottom)
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = tk.Label(self, textvariable=self.status_var, wraplength=480)
        apply_label_style(self.status_label, 'status_success')
        self.status_label.pack(side="bottom", pady=15)

        # Main buttons
        load_btn = tk.Button(self, text="Load Participant List (XLSX) & Generate Brackets",
                            command=self.load_and_generate)
        apply_button_style(load_btn, 'primary')
        load_btn.pack(pady=8, fill="x", padx=40)

        # Database load button
        db_btn = tk.Button(self, text="Load from Database & Generate Brackets",
                          command=self.load_from_database)
        apply_button_style(db_btn, 'primary')
        db_btn.pack(pady=8, fill="x", padx=40)

        # Load JSON files button
        json_btn = tk.Button(self, text="Load M/W JSON Files & Generate Brackets",
                            command=self.load_json_and_generate)
        apply_button_style(json_btn, 'primary')
        json_btn.pack(pady=8, fill="x", padx=40)

        # Split M/W button
        split_btn = tk.Button(self, text="Split M/W Contestants (XLSX → JSON)",
                             command=self.split_gender_to_json)
        apply_button_style(split_btn, 'secondary')
        split_btn.pack(pady=8, fill="x", padx=40)

    def show_group_preview_window(self):
        """Show group preview window with participant details before bracket viewer."""
        # Resize window to match bracket viewer
        self.geometry('1000x600')
        self.configure(bg=COLORS['bg_dark'])

        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Create main layout with frame
        main_frame = create_dark_frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create PanedWindow for resizable split
        paned = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL,
                              bg=COLORS['bg_dark'],
                              sashwidth=4,
                              sashrelief=tk.FLAT,
                              showhandle=False)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel: Group list sidebar
        self._create_group_list_panel(paned)

        # Right panel: Participant preview area
        self._create_participant_preview_panel(paned)

        # Bottom navigation buttons
        self._create_preview_navigation_buttons(main_frame)

        # Populate the group list
        self._populate_group_list()

    def show_generation_method_screen(self):
        """Show the generation method selection screen."""
        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Create the generation method screen
        gen_screen = GenerationMethodScreen(self)
        gen_screen.pack(fill=tk.BOTH, expand=True)

        # Store reference for access
        self.generation_method_screen = gen_screen

        # Prepare bracket data for the screen
        # Convert brackets to the format expected by GenerationMethodScreen
        brackets_dict = {}
        for bracket_key, bracket_data in self.brackets.items():
            fighters = bracket_data.get('fighters', [])
            # Create a bracket tuple from fighters list
            # For now, use fighters list as the tuple
            brackets_dict[bracket_key] = {
                'tuple': fighters,
                'method': None,  # Not assigned yet
            }

        # Load the data into the screen
        gen_screen.load_data(brackets_dict)

        # Set up callback for when generation methods are selected
        gen_screen.on_generation_complete = self.on_generation_methods_selected

    def _create_group_list_panel(self, parent_paned):
        """Create the left panel with group list and search."""
        left_frame = create_dark_frame(parent_paned)
        parent_paned.add(left_frame, width=300, minsize=250)

        # Title with count
        title_frame = create_dark_frame(left_frame)
        title_frame.pack(fill=tk.X, pady=(0, 5))

        title_label = tk.Label(title_frame, text='Weight Groups')
        apply_label_style(title_label, 'heading_md')
        title_label.pack(side=tk.LEFT)

        # Total participant counter
        self.preview_count_var = tk.StringVar(value="(0)")
        count_label = tk.Label(title_frame, textvariable=self.preview_count_var)
        apply_label_style(count_label, 'info')
        count_label.pack(side=tk.RIGHT)

        # Search box
        search_frame = create_dark_frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        search_label = tk.Label(search_frame, text='Search:')
        apply_label_style(search_label, 'info')
        search_label.pack(side=tk.LEFT)

        self.preview_search_var = tk.StringVar()
        self.preview_search_var.trace('w', self._filter_group_list)
        search_entry = tk.Entry(search_frame, textvariable=self.preview_search_var, fg=COLORS['text_muted'])
        search_entry.insert(0, "M, W, age, or kg")
        search_entry.bind('<FocusIn>', lambda e: self._on_search_focus_in(search_entry))
        apply_entry_style(search_entry)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Group listbox
        self.group_listbox = tk.Listbox(left_frame, width=30, height=20)
        apply_listbox_style(self.group_listbox)
        self.group_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        # Bind double-click to show preview
        self.group_listbox.bind('<Double-Button-1>', self._on_group_double_click)

        # Store mapping for display text to bracket key
        self.group_listbox_map = {}

    def _create_participant_preview_panel(self, parent_paned):
        """Create the right panel for participant preview."""
        right_frame = create_dark_frame(parent_paned)
        parent_paned.add(right_frame, minsize=450)

        # Title area (will be updated when group is selected)
        self.preview_title_var = tk.StringVar(value="Participant Preview")
        title_label = tk.Label(right_frame, textvariable=self.preview_title_var)
        apply_label_style(title_label, 'heading_md')
        title_label.pack(pady=(0, 10))

        # Create container for participant display
        self.participant_display_frame = create_dark_frame(right_frame)
        self.participant_display_frame.pack(fill=tk.BOTH, expand=True)

        # Initial placeholder message
        placeholder = tk.Label(self.participant_display_frame,
                              text="Double-click a group to preview participants")
        apply_label_style(placeholder, 'info')
        placeholder.pack(expand=True)

    def _create_preview_navigation_buttons(self, parent_frame):
        """Create navigation buttons at bottom of preview window."""
        button_frame = create_dark_frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # Back button (left side)
        back_btn = tk.Button(button_frame, text='← Back to File Loader',
                            command=self.show_file_loader)
        apply_button_style(back_btn, 'secondary')
        back_btn.pack(side=tk.LEFT, padx=5)

        # Continue button (right side) - goes to generation method selection
        continue_btn = tk.Button(button_frame, text='Continue to Generation Setup →',
                                command=self.show_generation_method_screen)
        apply_button_style(continue_btn, 'primary')
        continue_btn.pack(side=tk.RIGHT, padx=5)

    def _populate_group_list(self):
        """Populate the group list with all non-empty brackets."""
        if not hasattr(self, 'group_listbox') or not self.group_listbox.winfo_exists():
            return
        self.group_listbox.delete(0, tk.END)
        self.group_listbox_map.clear()

        total_participants = 0

        # Filter out empty groups and sort
        for bracket_key in sorted(self.brackets.keys()):
            fighters = self.brackets[bracket_key].get('fighters', [])
            if fighters:  # Only show groups with participants
                count = len(fighters)
                total_participants += count

                # Format: "M | U13 | -50kg (12)"
                display_text = f"{bracket_key} ({count})"
                self.group_listbox.insert(tk.END, display_text)
                self.group_listbox_map[display_text] = bracket_key

        # Update total counter
        self.preview_count_var.set(f"({total_participants})")

    def _on_search_focus_in(self, search_entry):
        """Clear placeholder text on focus."""
        if search_entry.get() == "M, W, age, or kg":
            search_entry.delete(0, tk.END)
            search_entry.config(fg=COLORS['text_primary'])

    def _filter_group_list(self, *args):
        """Filter the group list based on search term (supports multiple parameters)."""
        if not hasattr(self, 'group_listbox') or not self.group_listbox.winfo_exists():
            return
        
        search_term = self.preview_search_var.get().lower().strip()
        
        # Skip placeholder text
        if search_term == "m, w, age, or kg" or not search_term:
            self.logger.debug("Search cleared or placeholder - showing all groups")
            self._populate_group_list()
            return
        
        self.logger.debug(f"Filtering groups with search term: '{search_term}'")
        self.group_listbox.delete(0, tk.END)
        total_filtered = 0
        matched_brackets = []

        for bracket_key in sorted(self.brackets.keys()):
            fighters = self.brackets[bracket_key].get('fighters', [])
            if not fighters:
                continue
            
            bracket_key_lower = bracket_key.lower()
            
            # Split search into individual terms, filter out empty strings
            search_terms = [term for term in search_term.split() if term]
            self.logger.debug(f"Search terms: {search_terms}")
            
            # Check if ALL search terms match in the bracket key
            if search_terms and all(term in bracket_key_lower for term in search_terms):
                count = len(fighters)
                total_filtered += count
                matched_brackets.append(bracket_key)
                display_text = f"{bracket_key} ({count})"
                self.group_listbox.insert(tk.END, display_text)

        # Update counter with filtered count
        self.logger.debug(f"Search results: {len(matched_brackets)} brackets matched, {total_filtered} total fighters")
        if matched_brackets:
            self.logger.debug(f"Matched brackets: {', '.join(matched_brackets)}")
        self.preview_count_var.set(f"({total_filtered})")

    def _on_group_double_click(self, event):
        """Handle double-click on a group - show participant details."""
        selection = self.group_listbox.curselection()
        if not selection:
            return

        display_text = self.group_listbox.get(selection[0])
        bracket_key = self.group_listbox_map.get(display_text, display_text)

        # Display participants for this group
        self._display_participants(bracket_key)

    def _display_participants(self, bracket_key):
        """Display participant details for the selected group."""
        # Clear previous content
        for widget in self.participant_display_frame.winfo_children():
            widget.destroy()

        # Get fighters for this bracket
        fighters = self.brackets[bracket_key].get('fighters', [])
        count = len(fighters)

        print(f"[DEBUG] Displaying {count} fighters for bracket: {bracket_key}")

        # Update title
        self.preview_title_var.set(f"{bracket_key} - {count} participants")

        # Create a Text widget with scrollbar (much simpler!)
        text_frame = create_dark_frame(self.participant_display_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(text_frame,
                             wrap=tk.NONE,
                             yscrollcommand=scrollbar.set,
                             bg=COLORS['bg_panel'],
                             fg=COLORS['text_primary'],
                             font=FONTS['body_sm'],
                             padx=10,
                             pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        # Add header line - headers positioned more to the right within columns
        header = f"{'Name':<35}             {'Weight (kg)':<15}             {'Club/Verein':<30}                  {'Age':<10}\n"
        text_widget.insert(tk.END, header, 'header')
        text_widget.insert(tk.END, "=" * 100 + "\n\n")

        # Add participant rows with original spacing
        for i, fighter in enumerate(fighters):
            # Extract data with fallbacks
            name = fighter.get('Name', fighter.get('name', 'N/A'))
            weight = fighter.get('Weight', fighter.get('weight', 'N/A'))
            club = fighter.get('Verein', fighter.get('verein', fighter.get('club', 'N/A')))
            age = fighter.get('Age', fighter.get('age', 'N/A'))

            # Format weight
            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.1f}"
            else:
                weight_str = str(weight)

            # Create row text with original fixed-width spacing
            row = f"{str(name):<35} {weight_str:<15} {str(club):<30} {str(age):<10}\n"
            text_widget.insert(tk.END, row)

            if i < 3:
                print(f"[DEBUG] Fighter {i}: {name}, {weight_str}kg, {club}, Age {age}")

        # Style the header
        text_widget.tag_configure('header', font=FONTS['heading_sm'], foreground=COLORS['accent_blue'])

        # Make text widget read-only
        text_widget.config(state=tk.DISABLED)

        print(f"[DEBUG] Text widget created with {count} fighters")

    def show_loading_progress(self, message):
        """Show a loading progress dialog."""
        # Create a loading window
        self.loading_window = tk.Toplevel(self)
        self.loading_window.title("Loading...")
        self.loading_window.geometry("400x150")
        self.loading_window.configure(bg=COLORS['bg_dark'])
        self.loading_window.resizable(False, False)
        
        # Make it modal
        self.loading_window.transient(self)
        self.loading_window.grab_set()
        
        # Center on parent window
        self.loading_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        self.loading_window.geometry(f"+{x}+{y}")
        
        # Message label
        msg_label = tk.Label(self.loading_window, text=message)
        apply_label_style(msg_label, 'heading_md')
        msg_label.pack(pady=(20, 10))
        
        # Progress bar
        self.progress_var = tk.IntVar(value=0)
        progress_bar = ttk.Progressbar(self.loading_window, variable=self.progress_var,
                                       maximum=100, length=350, mode='determinate')
        progress_bar.pack(pady=10, padx=20)
        
        # Percentage label
        self.progress_label = tk.Label(self.loading_window, text="0%")
        apply_label_style(self.progress_label, 'info')
        self.progress_label.pack(pady=(0, 10))
        
        self.loading_window.update_idletasks()

    def update_progress(self, value):
        """Update the progress bar."""
        if hasattr(self, 'progress_var') and hasattr(self, 'loading_window'):
            self.progress_var.set(value)
            self.progress_label.config(text=f"{value}%")
            self.loading_window.update_idletasks()

    def hide_loading_progress(self):
        """Hide the loading progress dialog."""
        if hasattr(self, 'loading_window') and self.loading_window.winfo_exists():
            self.loading_window.destroy()

    def show_bracket_viewer(self):
        """Show bracket list and visualization (dark themed)."""
        # Resize and reconfigure window
        self.geometry('1000x600')
        self.configure(bg=COLORS['bg_dark'])
        self.viewer_shown = True

        # Initialize table assignments
        self.bracket_table_assignment = {k: None for k in self.brackets.keys()}

        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Main layout with resizable paned window
        main_frame = create_dark_frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Bind Escape to return to tables view
        self.bind('<Escape>', lambda e: self.show_tables())

        # Create PanedWindow for resizable split
        paned = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL,
                              bg=COLORS['bg_dark'],
                              sashwidth=4,
                              sashrelief=tk.FLAT,
                              showhandle=False)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Unassigned brackets with search
        left_frame = create_dark_frame(paned)
        paned.add(left_frame, width=250, minsize=200)

        title_frame = create_dark_frame(left_frame)
        title_frame.pack(fill=tk.X, pady=(0, 5))

        title_label = tk.Label(title_frame, text='Unassigned Brackets')
        apply_label_style(title_label, 'heading_md')
        title_label.pack(side=tk.LEFT)

        # Counter for unassigned participants
        self.unassigned_count_var = tk.StringVar(value="(0)")
        count_label = tk.Label(title_frame, textvariable=self.unassigned_count_var)
        apply_label_style(count_label, 'info')
        count_label.pack(side=tk.RIGHT)

        search_frame = create_dark_frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        search_label = tk.Label(search_frame, text='Search:')
        apply_label_style(search_label, 'info')
        search_label.pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.update_bracket_list)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        apply_entry_style(search_entry)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Compact listbox - leave room for buttons below
        self.bracket_listbox = tk.Listbox(left_frame, width=26, height=16)
        apply_listbox_style(self.bracket_listbox)
        self.bracket_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.bracket_listbox.bind('<<ListboxSelect>>', self.on_bracket_select)
        self.bracket_listbox.bind('<Double-Button-1>', self.on_bracket_double_click)

        # Assignment buttons - VERTICAL LAYOUT
        assign_container = create_dark_frame(left_frame)
        assign_container.pack(pady=8, fill=tk.X, padx=5)

        assign_label = tk.Label(assign_container, text='Assign Selected:')
        apply_label_style(assign_label, 'info')
        assign_label.pack(anchor=tk.W, pady=(0, 3))

        # Table assignment buttons - one per line
        for t in range(1, 5):
            btn = tk.Button(assign_container, text=f'→ Table {t}',
                          command=lambda t=t: self.assign_to_table(t))
            apply_button_style(btn, 'secondary')
            btn.pack(fill=tk.X, pady=1)

        # Auto-assign button
        auto_btn = tk.Button(assign_container, text='Auto-assign All',
                           command=self.auto_assign_tables)
        apply_button_style(auto_btn, 'primary')
        auto_btn.pack(fill=tk.X, pady=(5, 0))

        # Right: Container for tables OR bracket view
        self.right_frame = create_dark_frame(paned)
        paned.add(self.right_frame, minsize=400)

        # Create bracket visualization frame (hidden initially)
        self.bracket_view_frame = create_dark_frame(self.right_frame)

        # Top bar with title and zoom controls
        top_bar = create_dark_frame(self.bracket_view_frame)
        top_bar.pack(fill=tk.X, pady=(0, 5))

        self.viz_title_var = tk.StringVar(value='Bracket Visualization')
        viz_title = tk.Label(top_bar, textvariable=self.viz_title_var)
        apply_label_style(viz_title, 'heading_md')
        viz_title.pack(side=tk.LEFT, pady=0)

        # Zoom controls on the right
        zoom_frame = create_dark_frame(top_bar)
        zoom_frame.pack(side=tk.RIGHT, padx=5)

        self.zoom_label = tk.Label(zoom_frame, text='100%')
        apply_label_style(self.zoom_label, 'info')
        self.zoom_label.pack(side=tk.LEFT, padx=5)

        zoom_out_btn = tk.Button(zoom_frame, text='−', width=3,
                                command=self.zoom_out)
        apply_button_style(zoom_out_btn, 'secondary')
        zoom_out_btn.pack(side=tk.LEFT, padx=2)

        zoom_in_btn = tk.Button(zoom_frame, text='+', width=3,
                               command=self.zoom_in)
        apply_button_style(zoom_in_btn, 'secondary')
        zoom_in_btn.pack(side=tk.LEFT, padx=2)

        zoom_reset_btn = tk.Button(zoom_frame, text='100%', width=4,
                                   command=self.zoom_reset)
        apply_button_style(zoom_reset_btn, 'secondary')
        zoom_reset_btn.pack(side=tk.LEFT, padx=2)

        canvas_frame = create_dark_frame(self.bracket_view_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Black background for bracket visualization (inverted colors)
        self.bracket_canvas = tk.Canvas(canvas_frame, bg=COLORS['bg_dark'],
                                        scrollregion=(0, 0, 2000, 2000),
                                        highlightthickness=0,
                                        borderwidth=0)

        # Scrollbars using ttk for better dark theme support
        x_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.bracket_canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.bracket_canvas.yview)

        self.bracket_canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

        # Mouse wheel scrolling
        self.bracket_canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.bracket_canvas.bind('<Button-4>', self._on_mousewheel)  # Linux scroll up
        self.bracket_canvas.bind('<Button-5>', self._on_mousewheel)  # Linux scroll down

        # Pack scrollbars properly
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.bracket_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        back_btn = tk.Button(self.bracket_view_frame, text='Back to Tables',
                            command=self.show_tables)
        apply_button_style(back_btn, 'secondary')
        back_btn.pack(pady=5)

        # Create table panels frame (shown initially)
        self.tables_frame = create_dark_frame(self.right_frame)
        
        # Add navigation row at the top
        tables_nav_frame = create_dark_frame(self.tables_frame)
        tables_nav_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=18, pady=10)
        
        back_to_gen_btn = tk.Button(tables_nav_frame, text='← Back to Generation Setup',
                                    command=self.show_generation_method_screen)
        apply_button_style(back_to_gen_btn, 'secondary')
        back_to_gen_btn.pack(side=tk.LEFT, padx=5)
        
        self.table_panels = {}
        for i, (row, col) in enumerate([(1, 0), (1, 1), (2, 0), (2, 1)]):
            table_num = i + 1
            panel = tk.LabelFrame(self.tables_frame, text=f'Table {table_num}',
                                 width=180, height=120, labelanchor='n')
            apply_table_panel_style(panel)
            panel.grid(row=row, column=col, padx=18, pady=18, sticky='nsew')
            panel.grid_propagate(False)
            self.table_panels[table_num] = panel

        self.tables_frame.grid_rowconfigure(0, weight=0)
        self.tables_frame.grid_rowconfigure(1, weight=1)
        self.tables_frame.grid_rowconfigure(2, weight=1)
        self.tables_frame.grid_columnconfigure(0, weight=1)
        self.tables_frame.grid_columnconfigure(1, weight=1)

        # Show tables view by default
        self.show_tables()
        self.update_bracket_list()
        self.update_table_panels()


    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling on canvas."""
        if event.num == 5 or event.delta < 0:
            self.bracket_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.bracket_canvas.yview_scroll(-1, "units")

    def on_generation_methods_selected(self, final_assignments):
        """
        Callback when generation methods have been assigned to all brackets.
        
        Args:
            final_assignments: Dict of {bracket_key: method_name}
        """
        self.logger.info(f"Generation methods assigned: {final_assignments}")
        
        # Store the assignments for use in bracket viewer
        self.bracket_generation_methods = final_assignments
        
        # Proceed to bracket viewer
        self.show_bracket_viewer()

    def show_tables(self):
        """Show table assignment view."""
        self.bracket_view_frame.pack_forget()
        self.tables_frame.pack(fill=tk.BOTH, expand=True)

    def show_bracket_view(self, bracket_key):
        """Show bracket visualization view."""
        self.tables_frame.pack_forget()
        self.bracket_view_frame.pack(fill=tk.BOTH, expand=True)
        self.current_bracket_key = bracket_key
        self.render_bracket(bracket_key)

    def zoom_in(self):
        """Zoom in on bracket visualization."""
        self.zoom_level = min(self.zoom_level * 1.2, 3.0)  # Max 300%
        self.update_zoom_label()
        if self.current_bracket_key:
            self.render_bracket(self.current_bracket_key)

    def zoom_out(self):
        """Zoom out on bracket visualization."""
        self.zoom_level = max(self.zoom_level / 1.2, 0.3)  # Min 30%
        self.update_zoom_label()
        if self.current_bracket_key:
            self.render_bracket(self.current_bracket_key)

    def zoom_reset(self):
        """Reset zoom to 100%."""
        self.zoom_level = 1.0
        self.update_zoom_label()
        if self.current_bracket_key:
            self.render_bracket(self.current_bracket_key)

    def update_zoom_label(self):
        """Update the zoom percentage label."""
        zoom_percent = int(self.zoom_level * 100)
        self.zoom_label.config(text=f'{zoom_percent}%')

    def assign_to_table(self, table_num):
        """Assign selected bracket to a table."""
        selection = self.bracket_listbox.curselection()
        if not selection:
            messagebox.showinfo('No Selection', 'Please select a bracket first.')
            return

        display_text = self.bracket_listbox.get(selection[0])
        bracket_key = self.bracket_listbox_map.get(display_text, display_text)

        # Check if table is full (max 2 brackets per table)
        assigned = [k for k, v in self.bracket_table_assignment.items() if v == table_num]
        if len(assigned) >= 2:
            messagebox.showwarning('Table Full',
                                  f'Table {table_num} already has 2 brackets assigned.')
            return

        # Assign the bracket
        self.bracket_table_assignment[bracket_key] = table_num
        self.update_bracket_list()
        self.update_table_panels()
        self.logger.info(f"Assigned '{bracket_key}' to Table {table_num}")

    def unassign_bracket(self, bracket_key=None):
        """Unassign bracket from its table (can be called directly or from selection)."""
        # If no bracket_key provided, get from selection
        if bracket_key is None:
            selection = self.bracket_listbox.curselection()
            if not selection:
                messagebox.showinfo('No Selection', 'Please select a bracket first.')
                return
            bracket_key = self.bracket_listbox.get(selection[0])

        # Check if this bracket is even assigned
        if not self.bracket_table_assignment.get(bracket_key):
            messagebox.showinfo('Not Assigned', 'This bracket is not assigned to any table.')
            return

        # Unassign it
        old_table = self.bracket_table_assignment[bracket_key]
        self.bracket_table_assignment[bracket_key] = None
        self.update_bracket_list()
        self.update_table_panels()
        self.logger.info(f"Unassigned '{bracket_key}' from Table {old_table}")

    def auto_assign_tables(self):
        """Automatically distribute unassigned brackets across tables."""
        unassigned = [k for k in self.brackets.keys()
                     if not self.bracket_table_assignment.get(k)]

        if not unassigned:
            messagebox.showinfo('Auto-assign', 'No unassigned brackets to assign.')
            return

        # Count current assignments per table
        assigned_count = {t: len([k for k, v in self.bracket_table_assignment.items() if v == t])
                         for t in range(1, 5)}

        table = 1
        for bracket_key in unassigned:
            # Find next table with space
            for _ in range(4):
                if assigned_count[table] < 2:
                    self.bracket_table_assignment[bracket_key] = table
                    assigned_count[table] += 1
                    table = table % 4 + 1
                    break
                table = table % 4 + 1

        self.update_bracket_list()
        self.update_table_panels()

    def update_table_panels(self):
        """Update the visual display of table assignments."""
        # Clear all panels
        for panel in self.table_panels.values():
            for widget in panel.winfo_children():
                widget.destroy()

        # Track totals for each table
        table_totals = {}

        # Add assigned brackets to panels
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num:
                panel = self.table_panels[table_num]

                # Create row frame for label + unassign button
                row_frame = create_dark_frame(panel)
                row_frame.pack(fill=tk.X, pady=2, padx=4)

                # Get fighter count
                fighter_count = len(self.brackets[bracket_key].get('fighters', []))
                
                # Track total for this table
                if table_num not in table_totals:
                    table_totals[table_num] = 0
                table_totals[table_num] += fighter_count
                
                # Truncate long names
                display_text = bracket_key[:25] + '...' if len(bracket_key) > 25 else bracket_key
                display_text = f"{display_text} ({fighter_count})"
                label = tk.Label(row_frame, text=display_text, wraplength=110,
                               justify='left', anchor='w', cursor='hand2',
                               bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                               font=FONTS['body_xs'])
                label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                label.bind('<Button-1>', lambda e, k=bracket_key: self.show_bracket_view(k))

                # Add unassign button
                unassign_btn = tk.Button(row_frame, text='✕', width=3,
                                       command=lambda k=bracket_key: self.unassign_bracket(k))
                apply_button_style(unassign_btn, 'secondary')
                unassign_btn.pack(side=tk.RIGHT, padx=2)

        # Add totals footer to each table
        for table_num, panel in self.table_panels.items():
            total = table_totals.get(table_num, 0)
            
            # Add separator
            separator = tk.Frame(panel, height=1, bg=COLORS['border'])
            separator.pack(fill=tk.X, pady=4, padx=4)
            
            # Add total label
            total_frame = create_dark_frame(panel)
            total_frame.pack(fill=tk.X, pady=2, padx=4)
            
            total_label = tk.Label(total_frame, text=f"Total Players: {total}",
                                  justify='left', anchor='w',
                                  bg=COLORS['bg_panel'], fg=COLORS['accent_orange'],
                                  font=FONTS['heading_sm'])
            total_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def on_bracket_double_click(self, event):
        """Handle double-click on bracket - show visualization."""
        selection = self.bracket_listbox.curselection()
        if selection:
            display_text = self.bracket_listbox.get(selection[0])
            bracket_key = self.bracket_listbox_map.get(display_text, display_text)
            self.show_bracket_view(bracket_key)

    def set_status(self, msg, color=None):
        """Update status label."""
        if hasattr(self, 'status_var'):
            self.status_var.set(msg)
            if color:
                self.status_label.config(fg=color)
            self.update_idletasks()

    def load_and_generate(self):
        """Load participants from XLSX file and generate brackets."""
        filepath = filedialog.askopenfilename(
            title="Select Participant XLSX File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not filepath:
            return

        # Show loading progress dialog
        self.show_loading_progress("Loading and generating brackets...")
        
        # Run loading in background thread
        thread = threading.Thread(target=self._load_and_generate_thread, args=(filepath,), daemon=True)
        thread.start()

    def _load_and_generate_thread(self, filepath):
        """Background thread for loading XLSX and generating brackets."""
        try:
            self.set_status("Reading XLSX file...", COLORS['text_secondary'])
            self.update_progress(10)

            # Load and normalize participants from XLSX using utility function
            raw_participants = load_participants_from_xlsx(filepath)
            self.update_progress(30)
            
            participants = normalize_participants(raw_participants)
            self.update_progress(40)

            if not participants:
                self.set_status("Error: No valid participants found.", COLORS['accent_red'])
                self.hide_loading_progress()
                return

            total_fighters = len(participants)
            self.info_var.set(f"✓ {total_fighters} participants loaded")
            self.update_progress(50)

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)
            self.update_progress(80)

            # Clear rendering caches for new brackets
            self.bracket_structure_cache.clear()
            self.bracket_render_cache.clear()

            # Save to JSON cache
            self.save_brackets_to_cache(filepath)
            self.update_progress(95)

            self.set_status(f"Success! Generated {len(self.brackets)} brackets (cached for fast viewing).", COLORS['accent_green'])
            self.update_progress(100)

            # Hide progress and show group preview window
            self.hide_loading_progress()
            self.after(500, self.show_group_preview_window)

        except Exception as e:
            self.logger.error(f"Error during load and generate: {e}", exc_info=True)
            self.set_status(f"Error: {e}", COLORS['accent_red'])
            self.hide_loading_progress()

    def load_from_database(self):
        """Load participants from PostgreSQL database and generate brackets."""
        # Show loading progress dialog
        self.show_loading_progress("Loading from database...")
        
        # Run loading in background thread
        thread = threading.Thread(target=self._load_from_database_thread, daemon=True)
        thread.start()

    def _load_from_database_thread(self):
        """Background thread for loading from database and generating brackets."""
        try:
            self.set_status("Connecting to database...", COLORS['text_secondary'])
            self.update_progress(10)

            # Fetch participants from database
            participants = fetch_participants_from_db()
            self.update_progress(30)

            if not participants:
                self.set_status("Error: No valid participants found in database.", COLORS['accent_red'])
                self.hide_loading_progress()
                self.after(500, lambda: messagebox.showwarning("No Data", "No valid and paid participants found in database."))
                return

            total_fighters = len(participants)
            self.info_var.set(f"✓ {total_fighters} participants loaded from database")
            self.update_progress(50)

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)
            self.update_progress(80)

            # Clear rendering caches for new brackets
            self.bracket_structure_cache.clear()
            self.bracket_render_cache.clear()

            # Save to JSON cache
            self.save_brackets_to_cache("database")
            self.update_progress(95)

            self.set_status(f"Success! Generated {len(self.brackets)} brackets from database (cached for fast viewing).", COLORS['accent_green'])
            self.update_progress(100)

            # Hide progress and show group preview window
            self.hide_loading_progress()
            self.after(500, self.show_group_preview_window)

        except Exception as e:
            self.logger.error(f"Database error during load: {e}", exc_info=True)
            self.set_status(f"Database Error: {e}", COLORS['accent_red'])
            self.hide_loading_progress()
            self.after(500, lambda err=e: messagebox.showerror("Database Error", f"Failed to load from database:\n{str(err)}"))

            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)

            # Clear rendering caches for new brackets
            self.bracket_structure_cache.clear()
            self.bracket_render_cache.clear()

            # Save to JSON cache
            self.save_brackets_to_cache("database")

            self.set_status(f"Success! Generated {len(self.brackets)} brackets from database (cached for fast viewing).", COLORS['accent_green'])

            # Wait a moment then show bracket viewer
            self.after(800, self.show_bracket_viewer)

        except Exception as e:
            self.set_status(f"Database Error: {e}", COLORS['accent_red'])
            messagebox.showerror("Database Error", f"Failed to load from database:\n{str(e)}")

    def load_json_and_generate(self):
        """Load 2 JSON files (male/female), merge them, and generate brackets."""
        # Select 2 JSON files
        filepaths = filedialog.askopenfilenames(
            title="Select 2 JSON Files (Male & Female)",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not filepaths:
            return

        if len(filepaths) != 2:
            messagebox.showerror("Invalid Selection",
                               f"Please select exactly 2 JSON files.\nYou selected {len(filepaths)} file(s).")
            return

        try:
            self.set_status("Reading JSON files...", COLORS['text_secondary'])

            all_participants = []

            # Load both JSON files
            for filepath in filepaths:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate that data is a list
                if not isinstance(data, list):
                    messagebox.showerror("Invalid JSON Format",
                                       f"File must contain a JSON array.\nFile: {os.path.basename(filepath)}")
                    return

                # Validate each participant has required fields
                for i, participant in enumerate(data):
                    if not isinstance(participant, dict):
                        messagebox.showerror("Invalid Participant",
                                           f"Participant {i+1} is not a valid object.\nFile: {os.path.basename(filepath)}")
                        return

                    # Check for required fields
                    required_fields = ['Name', 'Gender', 'Age', 'Weight']
                    missing_fields = [field for field in required_fields if field not in participant]

                    if missing_fields:
                        messagebox.showerror("Missing Fields",
                                           f"Participant {i+1} is missing fields: {', '.join(missing_fields)}\nFile: {os.path.basename(filepath)}")
                        return

                # Add all participants from this file
                all_participants.extend(data)
                print(f"[INFO] Loaded {len(data)} participants from: {os.path.basename(filepath)}")

            if not all_participants:
                self.set_status("Error: No valid participants found.", COLORS['accent_red'])
                return

            total_fighters = len(all_participants)
            self.info_var.set(f"✓ {total_fighters} participants loaded from JSON files")

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Generate brackets using backend service
            self.brackets = export_all_brackets(all_participants)

            # Clear rendering caches for new brackets
            self.bracket_structure_cache.clear()
            self.bracket_render_cache.clear()

            # Save to JSON cache
            self.save_brackets_to_cache("json_files")

            self.set_status(f"Success! Generated {len(self.brackets)} brackets from JSON files (cached for fast viewing).", COLORS['accent_green'])

            # Wait a moment then show group preview window
            self.after(800, self.show_group_preview_window)

        except json.JSONDecodeError as e:
            self.set_status(f"JSON Parse Error: {e}", COLORS['accent_red'])
            messagebox.showerror("JSON Error", f"Failed to parse JSON file:\n{str(e)}")
        except Exception as e:
            self.set_status(f"Error: {e}", COLORS['accent_red'])
            messagebox.showerror("Error", f"Failed to load JSON files:\n{str(e)}")

    def split_gender_to_json(self):
        """Split contestants by gender (M/W) and save to separate JSON files."""
        # Select input XLSX file
        input_file = filedialog.askopenfilename(
            title="Select Participant XLSX File to Split",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not input_file:
            return

        try:
            self.set_status("Reading XLSX file...", COLORS['text_secondary'])

            # Read participants from XLSX with new column structure
            # Columns: A=id, B=verein, C=verband, D=name, E=vorname, F=kyu/dan,
            #          G=jahrgang, H=geschlecht, I=altersklasse, J=gewicht u9+u11,
            #          K=gewichtsklasse ab u13, L=telefonnummer, M=email
            df = pd.read_excel(input_file)

            participants = []
            for index, row in df.iterrows():
                # Read from new column structure
                participant_id = row.iloc[0] if len(row) > 0 else index + 1  # Column A: id
                verein = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""  # Column B: verein
                # verband = row.iloc[2]  # Column C: verband (not used in output)
                nachname = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""  # Column D: name (nachname)
                vorname = str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else ""  # Column E: vorname
                # kyu_dan = row.iloc[5]  # Column F: kyu/dan grad (not used)
                jahrgang = row.iloc[6] if len(row) > 6 and pd.notna(row.iloc[6]) else None  # Column G: jahrgang
                geschlecht = str(row.iloc[7]).strip() if len(row) > 7 and pd.notna(row.iloc[7]) else ""  # Column H: geschlecht
                # altersklasse = row.iloc[8]  # Column I: altersklasse (not used)
                # gewicht_u9_u11 = row.iloc[9]  # Column J: gewicht u9 + u11 (ignored)
                # gewichtsklasse_ab_u13 = row.iloc[10]  # Column K: gewichtsklasse ab u13 (ignored)
                # telefonnummer = row.iloc[11]  # Column L: telefonnummer (not used)
                # email = row.iloc[12]  # Column M: email (not used)

                # Skip header rows (ID is "#" or similar header indicators)
                participant_id_str = str(participant_id).strip()
                if participant_id_str in ['#', 'ID', 'id', 'Nr', 'Nr.', 'Number']:
                    continue

                # Skip rows where all fields except ID (column A) are empty
                if not verein and not nachname and not vorname and jahrgang is None and not geschlecht:
                    continue

                # Construct full Name as Vorname + Nachname
                full_name = f"{vorname} {nachname}".strip()

                # Convert jahrgang to int if possible
                try:
                    jahrgang = int(jahrgang) if jahrgang is not None else None
                except (ValueError, TypeError):
                    jahrgang = None

                # Convert geschlecht: m → maennlich, w → weiblich
                geschlecht_lower = geschlecht.lower()
                if geschlecht_lower == 'm':
                    geschlecht_normalized = 'maennlich'
                elif geschlecht_lower == 'w':
                    geschlecht_normalized = 'weiblich'
                else:
                    geschlecht_normalized = geschlecht_lower

                participants.append({
                    'ID': participant_id,
                    'Vorname': vorname,
                    'Nachname': nachname,
                    'Name': full_name,
                    'Geburtsjahr': jahrgang,
                    'Verein': verein,
                    'Gewicht (kg)': 0.0,
                    'Gueltigkeit': False,
                    'Geschlecht': geschlecht_normalized,
                    'Bezahlt': False,
                    'Geburtsdatum': ""
                })

            if not participants:
                self.set_status("Error: No participants found.", COLORS['accent_red'])
                messagebox.showerror("Error", "No participants found in the file.")
                return

            self.set_status("Splitting by gender...", COLORS['text_secondary'])

            # Split by gender - should already be normalized to "maennlich" or "weiblich"
            male_contestants = []
            female_contestants = []
            skipped_participants = []

            for p in participants:
                gender = str(p.get('Geschlecht', '')).strip().lower()
                if gender in ['maennlich', 'm', 'male', 'männlich']:
                    male_contestants.append(p)
                elif gender in ['weiblich', 'w', 'f', 'female']:
                    female_contestants.append(p)
                else:
                    # Track skipped participant with gender info
                    skipped_participants.append({
                        'name': p.get('Name', 'Unknown'),
                        'gender': p.get('Geschlecht', ''),
                        'id': p.get('ID', '')
                    })
                    self.logger.warning(f"Unknown gender '{gender}' (original: '{p.get('Geschlecht', '')}') for participant ID {p.get('ID')}: {p.get('Name')}")

            # Show split results
            total = len(participants)
            male_count = len(male_contestants)
            female_count = len(female_contestants)
            skipped = total - (male_count + female_count)

            result_msg = f"Split complete:\n• Male: {male_count}\n• Female: {female_count}"
            if skipped > 0:
                result_msg += f"\n• Skipped (unknown gender): {skipped}"
                if skipped_participants:
                    result_msg += "\n\nSkipped participants:"
                    for sp in skipped_participants[:5]:  # Show max 5
                        result_msg += f"\n  - ID {sp['id']}: {sp['name']} (gender: '{sp['gender']}')"
                    if len(skipped_participants) > 5:
                        result_msg += f"\n  ... and {len(skipped_participants) - 5} more"

            messagebox.showinfo("Split Results", result_msg)

            if male_count == 0 and female_count == 0:
                self.set_status("No contestants to save.", COLORS['accent_red'])
                return

            # Ask user where to save the files
            save_dir = filedialog.askdirectory(
                title="Select Folder to Save Split JSON Files"
            )
            if not save_dir:
                self.set_status("Save cancelled.", COLORS['text_secondary'])
                return

            self.set_status("Saving JSON files...", COLORS['text_secondary'])

            # Save male contestants if any
            if male_count > 0:
                male_file = os.path.join(save_dir, 'contestants_male.json')
                with open(male_file, 'w', encoding='utf-8') as f:
                    json.dump(male_contestants, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Saved {male_count} male contestants to: {male_file}")

            # Save female contestants if any
            if female_count > 0:
                female_file = os.path.join(save_dir, 'contestants_female.json')
                with open(female_file, 'w', encoding='utf-8') as f:
                    json.dump(female_contestants, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Saved {female_count} female contestants to: {female_file}")

            success_msg = f"Successfully saved split files to:\n{save_dir}\n\n"
            if male_count > 0:
                success_msg += f"• contestants_male.json ({male_count} entries)\n"
            if female_count > 0:
                success_msg += f"• contestants_female.json ({female_count} entries)"

            messagebox.showinfo("Success", success_msg)
            self.set_status("Split complete!", COLORS['accent_green'])

        except Exception as e:
            self.set_status(f"Error: {e}", COLORS['accent_red'])
            messagebox.showerror("Error", f"Failed to split contestants:\n{str(e)}")

    def save_brackets_to_cache(self, source_file):
        """Save generated brackets to JSON cache file."""
        cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'cache')
        os.makedirs(cache_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.bracket_cache_file = os.path.join(cache_dir, f'brackets_{timestamp}.json')

        cache_data = {
            'source_file': source_file,
            'generated_at': datetime.now().isoformat(),
            'brackets': {}
        }

        for key, bracket_data in self.brackets.items():
            cache_data['brackets'][key] = {
                'fighters': bracket_data.get('fighters', []),
                'bracket': bracket_data.get('bracket', [])
            }

        with open(self.bracket_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved brackets to cache: {self.bracket_cache_file}")

    def update_bracket_list(self, *args):
        """Update the bracket list based on search filter - only show unassigned."""
        if not hasattr(self, 'search_var'):
            return

        search_term = self.search_var.get().lower()
        self.bracket_listbox.delete(0, tk.END)
        # Store mapping of display text to bracket_key for safe lookup
        self.bracket_listbox_map = {}
        
        # Calculate total unassigned participants
        total_unassigned = 0

        # Only show unassigned brackets
        for bracket_key in sorted(self.brackets.keys()):
            if not self.bracket_table_assignment.get(bracket_key):
                if search_term in bracket_key.lower():
                    fighter_count = len(self.brackets[bracket_key].get('fighters', []))
                    display_text = f"{bracket_key} ({fighter_count})"
                    self.bracket_listbox.insert(tk.END, display_text)
                    # Store the mapping
                    self.bracket_listbox_map[display_text] = bracket_key
                    # Add to total
                    total_unassigned += fighter_count
        
        # Update counter
        if hasattr(self, 'unassigned_count_var'):
            self.unassigned_count_var.set(f"({total_unassigned})")

    def on_bracket_select(self, event):
        """Called when user clicks a bracket in the list."""
        # Just select, don't show yet (use double-click or table assignment)
        pass

    def render_bracket(self, bracket_key):
        """Render bracket or pool visualization on canvas."""
        try:
            self.bracket_canvas.delete('all')

            bracket_data = self.brackets.get(bracket_key)
            if not bracket_data:
                self.logger.debug(f'No bracket data found for key: {bracket_key}')
                self.bracket_canvas.create_text(400, 300,
                    text="No bracket data available",
                    font=FONTS['heading_md'], fill='red')
                return

            participants = bracket_data.get('fighters', [])
            if not participants:
                self.logger.debug("No participants in bracket")
                self.bracket_canvas.create_text(400, 300,
                    text="No participants in this bracket",
                    font=FONTS['heading_md'], fill='red')
                return

            num_participants = len(participants)
            self.logger.debug(f"Found {num_participants} participants")

            # Check if this should be a pool (3-10 participants)
            if 3 <= num_participants <= 10:
                self.logger.debug(f"Rendering pool for {num_participants} participants")
                pool_type = "Single Pool" if num_participants <= 5 else "Double Pool"
                if hasattr(self, 'viz_title_var'):
                    self.viz_title_var.set(f'Pool Visualization ({pool_type})')
                self._render_pool(bracket_key, participants)
                return

            # Update title for bracket view
            if hasattr(self, 'viz_title_var'):
                self.viz_title_var.set('Bracket Visualization')

            # Otherwise render bracket (11+ participants)
            # Check if we have cached bracket structure
            if bracket_key not in self.bracket_structure_cache:
                self.logger.debug(f"Generating bracket structure for: {bracket_key}")

                # Normalize participants and generate bracket rounds
                normalized_participants = []
                for p in participants:
                    if isinstance(p, dict):
                        normalized_participants.append({
                            'Name': p.get('Name', p.get('name', '')),
                            'Verein': p.get('Verein', p.get('verein', p.get('club', '')))
                        })

                if not normalized_participants:
                    self.logger.debug("No normalized participants")
                    self.bracket_canvas.create_text(400, 300,
                        text="Error: Could not process participants",
                        font=FONTS['heading_md'], fill='red')
                    return

                self.logger.debug(f"Normalized {len(normalized_participants)} participants")

                # Generate bracket visualization
                bracket = make_bracket(normalized_participants)
                self.logger.debug(f"Generated bracket with {len(bracket)} first round matches")

                # Build rounds for single-elimination tree
                rounds = []
                current = [(p1, p2) for p1, p2 in bracket]
                rounds.append(current)

                while len(current) > 1:
                    nextRound = []
                    for i in range(0, len(current), 2):
                        p1 = f"Winner {i+1}"
                        p2 = f"Winner {i+2}" if i+1 < len(current) else 'BYE'
                        nextRound.append((p1, p2))
                    current = nextRound
                    rounds.append(current)

                # Cache the bracket structure
                self.bracket_structure_cache[bracket_key] = rounds
                self.logger.debug(f"Cached bracket structure with {len(rounds)} rounds")
            else:
                rounds = self.bracket_structure_cache[bracket_key]
                self.logger.debug(f"Using cached bracket structure for: {bracket_key} ({len(rounds)} rounds)")

            # Calculate box dimensions using utility function
            box_width, box_height, x_gap, y_gap = calculate_box_size(rounds, self.zoom_level)

            # Calculate bracket positions
            positions = {}
            y_offsets = {}
            first_total = len(rounds[0])
            start_x = int(60 * self.zoom_level)
            start_y = int(60 * self.zoom_level)

            for m in range(first_total):
                x = start_x
                y = start_y + m * (box_height + y_gap)
                positions[(0, m)] = (x, y)
                y_offsets[(0, m)] = y + box_height // 2

            for r in range(1, len(rounds)):
                matches = rounds[r]
                x = start_x + r * (box_width + x_gap)
                for m in range(len(matches)):
                    prev1 = (r-1, m*2)
                    prev2 = (r-1, m*2+1)
                    y1 = y_offsets.get(prev1, start_y)
                    y2 = y_offsets.get(prev2, y1)
                    y = (y1 + y2) // 2 - box_height // 2
                    positions[(r, m)] = (x, y)
                    y_offsets[(r, m)] = y + box_height // 2

            # Draw rounds (INVERTED COLORS - white on black)
            for r, matches in enumerate(rounds):
                for m, (p1, p2) in enumerate(matches):
                    x, y = positions[(r, m)]

                    # Draw box (white outline) - scale line width too
                    line_width = max(1, int(2 * self.zoom_level))
                    self.bracket_canvas.create_rectangle(x, y, x + box_width, y + box_height,
                                                         outline=COLORS['white'], width=line_width)
                    self.bracket_canvas.create_line(x, y + box_height // 2, x + box_width, y + box_height // 2,
                                                   fill=COLORS['text_secondary'], dash=(2, 2))

                    # Draw text (white) - scale font size
                    font_size = max(6, int(10 * self.zoom_level))
                    scaled_font = ('Consolas', font_size)
                    vs_font = ('Arial', max(6, int(10 * self.zoom_level)), 'bold')

                    self.bracket_canvas.create_text(x + box_width // 2, y + box_height // 4,
                                                   text=p1, anchor='c',
                                                   fill=COLORS['white'], font=scaled_font)
                    self.bracket_canvas.create_text(x + box_width // 2, y + 3 * box_height // 4,
                                                   text=p2, anchor='c',
                                                   fill=COLORS['white'], font=scaled_font)
                    # "vs" in red for visibility
                    self.bracket_canvas.create_text(x + box_width // 2, y + box_height // 2,
                                                   text='vs', anchor='c',
                                                   font=vs_font,
                                                   fill=COLORS['accent_red'])

                    # Draw connector to next round (white arrows)
                    if r < len(rounds) - 1:
                        next_match_idx = m // 2
                        nx, ny = positions[(r + 1, next_match_idx)]
                        self.bracket_canvas.create_line(
                            x + box_width, y + box_height // 2,
                            nx, ny + box_height // 2,
                            arrow=tk.LAST, width=line_width,
                            fill=COLORS['white']
                        )

            # Update scroll region based on bracket size and zoom level
            max_x = max(pos[0] for pos in positions.values()) + box_width + start_x
            max_y = max(pos[1] for pos in positions.values()) + box_height + start_y
            self.bracket_canvas.configure(scrollregion=(0, 0, max_x, max_y))

            self.logger.debug(f"Successfully rendered bracket with {len(rounds)} rounds at {int(self.zoom_level*100)}% zoom")

        except Exception as e:
            self.logger.error(f"Exception rendering bracket: {e}", exc_info=True)
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering bracket:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

    def _render_pool(self, bracket_key, participants):
        """Render pool/round-robin visualization on canvas.

        Args:
            bracket_key: The bracket identifier
            participants: List of participant dicts
        """
        try:
            # Normalize participants for pool rendering
            normalized_participants = []
            for p in participants:
                if isinstance(p, dict):
                    normalized_participants.append({
                        'Name': p.get('Name', p.get('name', '')),
                        'Verein': p.get('Verein', p.get('verein', p.get('club', '')))
                    })

            if not normalized_participants:
                self.logger.debug("No normalized participants for pool")
                self.bracket_canvas.create_text(400, 300,
                    text="Error: Could not process participants",
                    font=FONTS['heading_md'], fill='red')
                return

            # Draw pools on canvas
            start_x = int(50 * self.zoom_level)
            start_y = int(80 * self.zoom_level)

            total_width, total_height = draw_pools_on_canvas(
                self.bracket_canvas,
                normalized_participants,
                self.zoom_level,
                COLORS,
                FONTS,
                start_x,
                start_y
            )

            # Update scroll region
            self.bracket_canvas.configure(scrollregion=(0, 0, total_width, total_height))

            num_participants = len(normalized_participants)
            pool_type = "Single Pool" if num_participants <= 5 else "Double Pool"
            self.logger.debug(f"Successfully rendered {pool_type} with {num_participants} participants at {int(self.zoom_level*100)}% zoom")

        except Exception as e:
            self.logger.error(f"Exception rendering pool: {e}", exc_info=True)
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering pool:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

    def on_closing(self):
        """Handle window close event - cleanup cache file."""
        try:
            # Delete the bracket cache file if it exists
            if self.bracket_cache_file and os.path.exists(self.bracket_cache_file):
                os.remove(self.bracket_cache_file)
                self.logger.info(f"Deleted cache file: {self.bracket_cache_file}")
        except Exception as e:
            self.logger.warning(f"Could not delete cache file: {e}")
        finally:
            # Close the application
            self.destroy()


def main():
    app = BracketViewerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
