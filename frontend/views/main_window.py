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
from .file_loader_screen import FileLoaderScreen  # noqa: E402
from .group_preview_screen import GroupPreviewScreen  # noqa: E402
from ..search_utils import filter_items  # noqa: E402

# ===== DEBUG CONFIGURATION =====
# Set to True to print debug logs to console; False to only log to file
DEBUG = True
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
        self.logger = get_logger('main_window', debug_verbose=DEBUG)
        
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
        """Show file loading screen."""
        # Clear any existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Create the file loader screen
        loader_screen = FileLoaderScreen(self)
        loader_screen.pack(fill=tk.BOTH, expand=True)

        # Store reference and set up callbacks
        self.file_loader_screen = loader_screen
        loader_screen.on_load_xlsx = self.load_and_generate
        loader_screen.on_load_database = self.load_from_database
        loader_screen.on_load_json = self.load_json_and_generate
        loader_screen.on_split_gender = self.split_gender_to_json

        self.logger.debug("File loader screen displayed")

    def show_group_preview_window(self):
        """Show group preview screen."""
        # Resize window
        self.geometry('1000x600')
        self.configure(bg=COLORS['bg_dark'])

        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # Create and display preview screen
        preview_screen = GroupPreviewScreen(self)
        preview_screen.pack(fill=tk.BOTH, expand=True)

        # Store reference and set up callbacks
        self.group_preview_screen = preview_screen
        preview_screen.on_back = self.show_file_loader
        preview_screen.on_continue = self.show_generation_method_screen

        # Load bracket data
        preview_screen.load_data(self.brackets)

        self.logger.debug("Group preview screen displayed")

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
        # Merge with cached assignments if they exist
        brackets_dict = {}
        for bracket_key, bracket_data in self.brackets.items():
            fighters = bracket_data.get('fighters', [])
            # Use cached assignment if available, otherwise None
            cached_method = self.bracket_generation_methods.get(bracket_key)
            brackets_dict[bracket_key] = {
                'tuple': fighters,
                'method': cached_method,  # Load cached assignment or None
            }

        # Load the data into the screen
        gen_screen.load_data(brackets_dict)

        # Set up callback for when generation methods are selected
        gen_screen.on_generation_complete = self.on_generation_methods_selected

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
        
        # Also update file loader screen if it exists and is displayed
        if hasattr(self, 'file_loader_screen') and self.file_loader_screen.winfo_exists():
            style = 'status_success'
            if color and color == COLORS['accent_red']:
                style = 'status_error'
            elif color and color == COLORS['text_secondary']:
                style = 'info'
            self.file_loader_screen.set_status_text(msg, style)

    def set_info_text(self, text):
        """Update info text on file loader screen if available."""
        if hasattr(self, 'info_var'):
            self.info_var.set(text)
        if hasattr(self, 'file_loader_screen') and self.file_loader_screen.winfo_exists():
            self.file_loader_screen.set_info_text(text)

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
            self.set_info_text(f"✓ {total_fighters} participants loaded")
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
            self.set_info_text(f"✓ {total_fighters} participants loaded from database")
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
            self.set_info_text(f"✓ {total_fighters} participants loaded from JSON files")

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
        """Update the bracket list based on search filter - only show unassigned (supports multi-term AND search)."""
        if not hasattr(self, 'search_var'):
            return

        search_term = self.search_var.get()
        self.bracket_listbox.delete(0, tk.END)
        # Store mapping of display text to bracket_key for safe lookup
        self.bracket_listbox_map = {}
        
        # Get unassigned bracket keys
        unassigned_keys = [k for k in sorted(self.brackets.keys()) if not self.bracket_table_assignment.get(k)]
        
        # Use shared search utility
        filtered_keys, matched_count, search_terms = filter_items(unassigned_keys, search_term)
        
        if search_terms:
            self.logger.debug(f"Bracket search: {search_terms}, found {matched_count} brackets")
        
        # Calculate total unassigned participants
        total_unassigned = 0

        # Display filtered brackets
        for bracket_key in filtered_keys:
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

            # Check user's assigned method from generation screen
            assigned_method = self.bracket_generation_methods.get(bracket_key)
            self.logger.debug(f"Bracket {bracket_key} assigned method: {assigned_method}")

            # Determine rendering method: pools or KO (default)
            if assigned_method == 'pools':
                self.logger.debug("Using assigned 'pools' method")
                if hasattr(self, 'viz_title_var'):
                    self.viz_title_var.set('Pool Visualization (Single Pool)')
                self._render_pool(bracket_key, participants)
                return
            elif assigned_method == 'double':
                self.logger.debug("Using assigned 'double' method")
                if hasattr(self, 'viz_title_var'):
                    self.viz_title_var.set('Pool Visualization (Double Pool)')
                self._render_pool(bracket_key, participants)
                return

            # Default to KO bracket rendering (includes 'ko', 'special', and unassigned)
            self.logger.debug(f"Rendering as KO bracket (method: {assigned_method})")
            if hasattr(self, 'viz_title_var'):
                self.viz_title_var.set('Bracket Visualization (KO)')

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
                    next_round = []
                    for i in range(0, len(current), 2):
                        p1 = f"Winner {i+1}"
                        p2 = f"Winner {i+2}" if i+1 < len(current) else 'BYE'
                        next_round.append((p1, p2))
                    current = next_round
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
            assigned_method = self.bracket_generation_methods.get(bracket_key, 'unknown')
            
            # Calculate number of matches in round-robin
            num_matches = (num_participants * (num_participants - 1)) // 2
            
            # Determine pool type for display
            pool_type = "Single Pool" if num_participants <= 5 else "Double Pool"
            
            self.logger.debug(f"Successfully rendered {pool_type} (method: {assigned_method}) with {num_participants} participants, {num_matches} total matches at {int(self.zoom_level*100)}% zoom")

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
