# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Extracted GUI code from bracket_viewer.py

import json
import os
import sys
import threading
import traceback

import tkinter as tk
from tkinter import messagebox, filedialog, ttk

# Setup sys.path for backend imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger  # noqa: E402
from backend.services.bracket_service import (  # noqa: E402
    export_all_brackets,
    make_bracket,
    set_bracket_config,
)
from backend.data.repositories.participant_repository import (  # noqa: E402
    fetch_participants_from_db,
)
import backend.data.database as _db_module  # noqa: E402
from backend.data.database import SessionLocal  # noqa: E402
from backend.services.tournament_service import TournamentService  # noqa: E402

from ..styles import (  # noqa: E402
    COLORS,
    FONTS,
    SCROLLBAR_STYLE,
    SCROLLBAR_ACTIVE_STYLE,
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
from .fight_monitoring_window import FightMonitoringScreen  # noqa: E402
from ..search_utils import filter_items  # noqa: E402

# ===== DEBUG CONFIGURATION =====
# Set to True to print debug logs to console; False to only log to file
DEBUG = True
# ==============================


class BracketViewerApp(tk.Tk):
    """Main application window for bracket viewing and management."""

    def __init__(self):
        super().__init__()
        # Initialize logger
        self.logger = get_logger('main_window', debug_verbose=DEBUG)
        
        self.title('Tournament Bracket Manager')
        self.geometry('520x440')  
        self.configure(bg=COLORS['bg_dark'])

        # Configure dark theme for ttk widgets (scrollbars)
        self.setup_ttk_styles()

        # Initialize backend config
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'bracket_config.xlsx')
        try:
            set_bracket_config(config_path)
        except Exception as e:
            self.logger.warning(f"Could not load config: {e}")

        # Data
        self.brackets = {}  # {bracket_key: Bracket data}
        self.bracket_generation_methods = {}  # {bracket_key: method_name}
        self.viewer_shown = False
        self.zoom_level = 1.0  # Zoom level for bracket visualization
        self.current_bracket_key = None  # Track currently displayed bracket

        # Fight monitoring state – persists across window open/close
        # {bracket_key: {(round_idx, match_idx): winner_name}}
        self.match_results = {}

        # Preview window state
        self.group_listbox_map = {}
        self.preview_search_var = None
        self.preview_count_var = None

        # Start with file loading UI
        self.show_file_loader()

    def _with_db(self, fn):
        """
        Create a fresh SQLAlchemy session, run fn(TournamentService(db)), then close.
        Thread-safe: each call owns its own session.
        Errors are logged but never crash the app — DB writes are best-effort.
        If the DB is unavailable, silently returns.
        """
        if not _db_module.DB_AVAILABLE:
            return
        
        db = None
        try:
            db = SessionLocal()
            fn(TournamentService(db))
        except Exception as e:
            # Connection errors or other DB issues - mark DB as unavailable and log
            error_msg = str(e).lower()
            if 'connection refused' in error_msg or 'could not connect' in error_msg:
                _db_module.DB_AVAILABLE = False
                self.logger.warning(f"Database unavailable, disabling DB save: {e}")
            else:
                # Other errors still logged but don't disable DB
                if db:
                    db.rollback()
                self.logger.error(f"DB operation failed: {e}\n{traceback.format_exc()}")
        finally:
            if db:
                db.close()

    def setup_ttk_styles(self):
        """Configure ttk styles for dark theme scrollbars."""
        style = ttk.Style()

        # Configure dark scrollbar
        style.theme_use('clam')  # Use clam theme as base (most customizable)

        # Vertical scrollbar
        style.configure('Vertical.TScrollbar', **SCROLLBAR_STYLE)

        # Horizontal scrollbar
        style.configure('Horizontal.TScrollbar', **SCROLLBAR_STYLE)

        # Active (hover) state
        style.map('Vertical.TScrollbar',
                 background=[('active', SCROLLBAR_ACTIVE_STYLE['background'])],
                 arrowcolor=[('active', SCROLLBAR_ACTIVE_STYLE['arrowcolor'])])

        style.map('Horizontal.TScrollbar',
                 background=[('active', SCROLLBAR_ACTIVE_STYLE['background'])],
                 arrowcolor=[('active', SCROLLBAR_ACTIVE_STYLE['arrowcolor'])])

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

    def filter_unpaid_participants(self, all_participants):
        """Filter out unpaid participants and show a popup if any are found.
        
        Args:
            all_participants: List of participant dicts with 'Paid' field
        
        Returns:
            Tuple of (paid_participants, unpaid_list) where unpaid_list is empty if all paid
        """
        paid_participants = []
        unpaid_participants = []
        
        for p in all_participants:
            # Check if paid field exists and is truthy
            is_paid = p.get('Paid', False)
            
            if is_paid:
                paid_participants.append(p)
            else:
                unpaid_participants.append(p)
        
        # Show popup if there are unpaid participants
        if unpaid_participants:
            unpaid_names = ['{} {}'.format(
                p.get('Firstname', p.get('Vorname', '')),
                p.get('Lastname', p.get('Nachname', ''))
            ).strip() or p.get('Name', 'Unknown') for p in unpaid_participants]
            
            unpaid_text = "\n".join(f"• {name}" for name in unpaid_names)
            
            message = f"The following {len(unpaid_participants)} participant(s) have not paid and will NOT be sorted into brackets:\n\n{unpaid_text}"
            
            messagebox.showwarning("Unpaid Participants", message)
            self.logger.info(f"Filtered out {len(unpaid_participants)} unpaid participant(s): {', '.join(unpaid_names)}")
        
        return paid_participants, unpaid_participants

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

        # Initialize table assignments only on first visit – preserve on return from monitoring
        if not hasattr(self, 'bracket_table_assignment'):
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
            btn = tk.Button(assign_container, text=f'→ Matte {t}',
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

        back_btn = tk.Button(self.bracket_view_frame, text='Back to Matten',
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

        monitor_btn = tk.Button(tables_nav_frame, text='Fight Monitoring',
                                command=self.show_fight_monitoring_screen)
        apply_button_style(monitor_btn, 'primary')
        monitor_btn.pack(side=tk.RIGHT, padx=5)
        
        self.table_panels = {}
        for i, (row, col) in enumerate([(1, 0), (1, 1), (2, 0), (2, 1)]):
            table_num = i + 1
            panel = tk.LabelFrame(self.tables_frame, text=f'Matte {table_num}',
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
        self._with_db(lambda svc, b=self.brackets, m=final_assignments:
                      svc.save_groups_and_brackets(b, m))

        # Proceed to bracket viewer
        self.show_bracket_viewer()

    def show_fight_monitoring_screen(self):
        """Switch to the Fight Monitoring screen (in-app, no separate window)."""
        # Create fight rows in DB for every assigned bracket (idempotent — skips if already created)
        def _create_fights(svc):
            for bracket_key, table_num in self.bracket_table_assignment.items():
                if table_num and bracket_key in self.brackets:
                    fight_pairs = self.brackets[bracket_key].get('bracket', [])
                    try:
                        svc.open_bracket_for_monitoring(bracket_key, fight_pairs)
                    except ValueError:
                        pass  # bracket not yet saved to DB (e.g. loaded from DB path)
        self._with_db(_create_fights)

        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        self.geometry('1200x750')

        screen = FightMonitoringScreen(
            parent=self,
            brackets=self.brackets,
            bracket_table_assignment=self.bracket_table_assignment,
            bracket_generation_methods=self.bracket_generation_methods,
            match_results=self.match_results,
        )
        screen.pack(fill=tk.BOTH, expand=True)
        screen.on_back = self.show_bracket_viewer
        screen.show_matten_view()

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

    def calculate_number_of_fights(self, bracket_key):
        """Calculate the number of fights for a bracket based on its type and structure.
        
        For U9/U11 pools: splits into small pools based on pool_size config, calculates per-pool fights.
        For other pools/KO: calculates based on method.
        
        Args:
            bracket_key: The bracket identifier
        
        Returns:
            Number of fights (matches)
        """
        bracket_data = self.brackets.get(bracket_key, {})
        fighters = bracket_data.get('fighters', [])
        num_fighters = len(fighters)
        
        if num_fighters == 0:
            return 0
        
        # Determine bracket type from generation method assignment
        assigned_method = self.bracket_generation_methods.get(bracket_key)
        is_u9_u11 = bracket_key in ('U9', 'U11')
        default_method = 'pools' if is_u9_u11 else 'ko'
        method = assigned_method or default_method
        
        # Calculate fights based on type
        if method in ('pools', 'double'):
            # Pool/round-robin: n * (n-1) / 2 fights per pool
            pool_size = bracket_data.get('pool_size')
            
            if is_u9_u11 and pool_size:
                # U9/U11 with configured pool_size: split into multiple small pools
                # Calculate number of pools based on pool_size
                num_pools = (num_fighters + pool_size - 1) // pool_size
                # Each pool has up to pool_size fighters
                total_fights = 0
                for pool_idx in range(num_pools):
                    start_idx = pool_idx * pool_size
                    end_idx = min(start_idx + pool_size, num_fighters)
                    pool_fighters = end_idx - start_idx
                    if pool_fighters > 0:
                        fights_in_pool = pool_fighters * (pool_fighters - 1) // 2
                        total_fights += fights_in_pool
                num_fights = total_fights
            else:
                # Single large pool or other method
                num_fights = num_fighters * (num_fighters - 1) // 2
        else:
            # KO/single elimination: n - 1 fights
            num_fights = num_fighters - 1
        
        return num_fights

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
            messagebox.showwarning('Matte Voll',
                                  f'Matte {table_num} already has 2 brackets assigned.')
            return

        # Assign the bracket
        self.bracket_table_assignment[bracket_key] = table_num
        self._with_db(lambda svc, k=bracket_key, t=table_num: svc.assign_mat(k, t))
        self.update_bracket_list()
        self.update_table_panels()
        self.logger.info(f"Assigned '{bracket_key}' to Matte {table_num}")

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
        self.logger.info(f"Unassigned '{bracket_key}' from Matte {old_table}")

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

        # Persist all auto-assignments to DB in one pass
        assignments = {k: v for k, v in self.bracket_table_assignment.items() if v}
        def _save_auto_assignments(svc):
            for bkey, tnum in assignments.items():
                svc.assign_mat(bkey, tnum)
        self._with_db(_save_auto_assignments)

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
                
                # Get fight count
                fight_count = self.calculate_number_of_fights(bracket_key)
                
                # Track total for this table
                if table_num not in table_totals:
                    table_totals[table_num] = 0
                table_totals[table_num] += fighter_count
                
                # Truncate long names
                display_text = bracket_key[:25] + '...' if len(bracket_key) > 25 else bracket_key
                display_text = f"{display_text} ({fighter_count}F, {fight_count}M)"
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
            self._with_db(lambda svc, p=participants: svc.save_participants(p))

            # Filter out unpaid participants
            participants, _ = self.filter_unpaid_participants(participants)

            if not participants:
                self.set_status("Error: No valid paid participants found.", COLORS['accent_red'])
                self.hide_loading_progress()
                return

            total_fighters = len(participants)
            self.set_info_text(f"✓ {total_fighters} participants loaded")
            self.update_progress(50)

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)
            self.update_progress(80)

            self.set_status(f"Success! Generated {len(self.brackets)} brackets.", COLORS['accent_green'])
            self.update_progress(100)

            # Hide progress and show group preview window
            self.hide_loading_progress()
            self.after(500, self.show_group_preview_window)

        except Exception as e:
            self.logger.error(f"Error during load and generate: {e}")
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
                self.set_status("Error: No participants found in database.", COLORS['accent_red'])
                self.hide_loading_progress()
                self.after(500, lambda: messagebox.showwarning("No Data", "No participants found in database."))
                return

            # Filter out unpaid participants
            participants, _ = self.filter_unpaid_participants(participants)

            if not participants:
                self.set_status("Error: No valid paid participants found in database.", COLORS['accent_red'])
                self.hide_loading_progress()
                self.after(500, lambda: messagebox.showwarning("No Data", "No paid participants found in database."))
                return

            total_fighters = len(participants)
            self.set_info_text(f"✓ {total_fighters} participants loaded from database")
            self.update_progress(50)

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)
            self.update_progress(80)

            self.set_status(f"Success! Generated {len(self.brackets)} brackets from database.", COLORS['accent_green'])
            self.update_progress(100)

            # Hide progress and show group preview window
            self.hide_loading_progress()
            self.after(500, self.show_group_preview_window)

        except Exception as e:
            self.logger.error(f"Database error during load: {e}")
            self.set_status(f"Database Error: {e}", COLORS['accent_red'])
            self.hide_loading_progress()
            self.after(500, lambda err=e: messagebox.showerror("Database Error", f"Failed to load from database:\n{str(err)}"))

    def load_json_and_generate(self):
        """Load 2 JSON files (male/female), merge them, and generate brackets.
        
        Expected JSON structure:
        [
          {
            "ID": 1,
            "Firstname": "Leon",
            "Lastname": "Müller",
            "Birthyear": 2018,
            "Club": "JC Sakura Berlin",
            "Association": "JV Berlin",
            "Weight": 28.5,
            "Valid": true,
            "Gender": "male",
            "Paid": true
          },
          ...
        ]
        """
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
            self.logger.info(f"Loading {len(filepaths)} JSON files")

            all_participants = []
            
            # Define expected fields
            required_core_fields = ['Firstname', 'Lastname', 'Birthyear', 'Weight', 'Gender']

            # Load both JSON files
            for file_idx, filepath in enumerate(filepaths, 1):
                filename = os.path.basename(filepath)
                self.logger.info(f"[File {file_idx}] Loading: {filename}")
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate that data is a list
                if not isinstance(data, list):
                    error_msg = f"File must contain a JSON array.\nFile: {filename}\nGot: {type(data).__name__}"
                    self.logger.error(error_msg)
                    messagebox.showerror("Invalid JSON Format", error_msg)
                    return

                self.logger.debug(f"[File {file_idx}] Found {len(data)} entries")
                
                valid_count = 0

                # Validate each participant
                for idx, participant in enumerate(data, 1):
                    if not isinstance(participant, dict):
                        error_msg = f"Participant {idx} is not a valid object (got {type(participant).__name__}).\nFile: {filename}"
                        self.logger.error(error_msg)
                        messagebox.showerror("Invalid Participant", error_msg)
                        return

                    # Check for required core fields
                    missing_fields = [field for field in required_core_fields if field not in participant]

                    if missing_fields:
                        error_msg = f"Participant {idx} is missing required fields: {', '.join(missing_fields)}\nFile: {filename}"
                        self.logger.error(error_msg)
                        messagebox.showerror("Missing Required Fields", error_msg)
                        return

                    # Validate field types and values
                    validation_errors = []
                    
                    # Check Firstname/Lastname are strings
                    if not isinstance(participant.get('Firstname'), str) or not participant.get('Firstname', '').strip():
                        validation_errors.append("Firstname must be non-empty string")
                    if not isinstance(participant.get('Lastname'), str) or not participant.get('Lastname', '').strip():
                        validation_errors.append("Lastname must be non-empty string")
                    
                    # Check Birthyear is integer or null
                    birthyear = participant.get('Birthyear')
                    if birthyear is not None and not isinstance(birthyear, int):
                        try:
                            participant['Birthyear'] = int(birthyear)
                        except (ValueError, TypeError):
                            validation_errors.append(f"Birthyear must be integer, got: {birthyear}")
                    
                    # Check Weight is number
                    weight = participant.get('Weight')
                    if weight is not None:
                        try:
                            participant['Weight'] = float(weight)
                        except (ValueError, TypeError):
                            validation_errors.append(f"Weight must be number, got: {weight}")
                    
                    # Check Gender is male/female
                    gender = str(participant.get('Gender', '')).strip().lower()
                    if gender not in ['male', 'female']:
                        validation_errors.append(f"Gender must be 'male' or 'female', got: {gender}")
                    
                    if validation_errors:
                        error_msg = f"Participant {idx} validation failed:\n" + "\n".join(f"  • {err}" for err in validation_errors) + f"\nFile: {filename}"
                        self.logger.error(error_msg)
                        messagebox.showerror("Validation Error", error_msg)
                        return

                    # Construct Name field from Firstname + Lastname if not present
                    if 'Name' not in participant:
                        participant['Name'] = f"{participant['Firstname']} {participant['Lastname']}".strip()
                    
                    # Ensure Age field exists (use Birthyear)
                    if 'Age' not in participant:
                        participant['Age'] = participant.get('Birthyear')

                    self.logger.debug(f"[File {file_idx}] Participant {idx}: {participant['Name']} (Age: {participant.get('Birthyear')}, Weight: {participant.get('Weight', 0.0)}kg, Gender: {gender})")
                    
                    valid_count += 1
                    all_participants.append(participant)

                self.logger.info(f"[File {file_idx}] Successfully validated {valid_count} participants")

            if not all_participants:
                error_msg = "No valid participants found in JSON files."
                self.logger.error(error_msg)
                self.set_status(error_msg, COLORS['accent_red'])
                return

            # Filter out unpaid participants
            all_participants, _ = self.filter_unpaid_participants(all_participants)

            if not all_participants:
                error_msg = "No paid participants found in JSON files."
                self.logger.error(error_msg)
                self.set_status(error_msg, COLORS['accent_red'])
                return

            total_fighters = len(all_participants)
            self.logger.info(f"Total paid participants loaded: {total_fighters}")
            self.set_info_text(f"✓ {total_fighters} paid participants loaded from JSON files")

            self.set_status("Generating brackets...", COLORS['text_secondary'])
            self.logger.info("Starting bracket generation...")

            # Generate brackets using backend service
            self.brackets = export_all_brackets(all_participants)

            self.logger.info(f"Successfully generated {len(self.brackets)} brackets")
            self.set_status(f"Success! Generated {len(self.brackets)} brackets from JSON files.", COLORS['accent_green'])

            # Wait a moment then show group preview window
            self.after(800, self.show_group_preview_window)

        except json.JSONDecodeError as e:
            error_msg = f"JSON Parse Error: {e}"
            self.logger.error(error_msg)
            self.set_status(error_msg, COLORS['accent_red'])
            messagebox.showerror("JSON Error", f"Failed to parse JSON file:\n{str(e)}")
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self.logger.error(error_msg)
            self.set_status(error_msg, COLORS['accent_red'])
            messagebox.showerror("File Error", f"Could not find file:\n{str(e)}")
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.logger.exception(error_msg)
            self.set_status(error_msg, COLORS['accent_red'])
            messagebox.showerror("Error", f"Failed to load JSON files:\n{str(e)}")

    def split_gender_to_json(self):
        """Split contestants by gender (M/W) and save to separate JSON files with English field names.
        
        Reads tournament registration XLSX, extracts all available data, and outputs
        separate JSON files for male and female participants with all fields populated
        that are available at registration time (Weight will be filled during weighing).
        """
        # Import here to avoid circular dependency
        from frontend.utils.participant_loader import load_participants_from_xlsx
        
        # Select input XLSX file
        input_file = filedialog.askopenfilename(
            title="Select Tournament Registration XLSX File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not input_file:
            return

        try:
            self.set_status("Reading tournament XLSX file...", COLORS['text_secondary'])

            # Load participants using the tournament format parser
            raw_participants = load_participants_from_xlsx(input_file)

            if not raw_participants:
                self.set_status("Error: No participants found.", COLORS['accent_red'])
                messagebox.showerror("Error", "No participants found in the file.")
                return
            
            # Debug: Check what fields are in raw_participants
            if raw_participants:
                first_p = raw_participants[0]
                self.logger.debug(f"First participant fields: {list(first_p.keys())}")
                self.logger.debug(f"First participant: {first_p}")

            self.set_status("Splitting by gender and converting to English format...", COLORS['text_secondary'])

            # Split by gender and convert to English field names
            male_contestants = []
            female_contestants = []
            skipped_participants = []

            for idx, p in enumerate(raw_participants, 1):
                # Extract gender (should be 'm' or 'w' from parser)
                gender = str(p.get('Gender', '')).strip().lower()
                
                # Try alternative gender field names
                if not gender:
                    for gender_field in ['Geschlecht', 'gender']:
                        if gender_field in p and p[gender_field]:
                            gender = str(p[gender_field]).strip().lower()
                            break
                
                # Normalize gender to 'male' or 'female'
                if gender in ['m', 'male', 'männlich', 'maennlich']:
                    gender_normalized = 'male'
                elif gender in ['w', 'female', 'weiblich', 'f']:
                    gender_normalized = 'female'
                else:
                    # Skip participants with missing gender (cannot split without it)
                    participant_name = p.get('Name', f"ID {idx}")
                    skipped_participants.append({
                        'name': participant_name,
                        'gender': gender if gender else '(empty)',
                        'id': idx
                    })
                    self.logger.warning(f"Skipping participant with missing/invalid gender '{gender}': {participant_name}")
                    continue

                # Convert to English field names (CamelCase for code)
                # Split full name into Firstname and Lastname
                full_name = p.get('Name', '')
                name_parts = full_name.split(' ', 1)
                firstname = name_parts[0] if len(name_parts) > 0 else ''
                lastname = name_parts[1] if len(name_parts) > 1 else ''

                # Extract birthyear (try multiple field names)
                birthyear = None
                for year_field in ['BirthYear', 'Jahrgang', 'Age']:
                    if year_field in p and p[year_field]:
                        try:
                            birthyear = int(p[year_field])
                            break
                        except (ValueError, TypeError):
                            pass

                # Extract club (Verein in German)
                club = p.get('Verein', p.get('Club', ''))

                # Extract association (Verband in German)
                association = p.get('Verband', p.get('Association', ''))

                # Extract weight (initially 0.0, will be filled during weighing)
                # Don't use pre-translated weight from XLSX, start fresh
                weight = 0.0

                # Extract paid status (Bezahlt in German)
                paid_str = str(p.get('Bezahlt', p.get('Paid', ''))).strip().lower()
                paid = paid_str in ['true', 'ja', 'yes', '1', 'y']

                # Create contestant record with English field names
                contestant = {
                    'ID': idx,
                    'Firstname': firstname,
                    'Lastname': lastname,
                    'Name': f"{firstname} {lastname}".strip(),  # Combined name
                    'Birthyear': birthyear,
                    'Club': club,
                    'Association': association,
                    'Weight': weight,
                    'Valid': False,  # Will be set during weighing validation
                    'Gender': gender_normalized,
                    'Paid': paid
                }

                # Add to appropriate list
                if gender_normalized == 'male':
                    male_contestants.append(contestant)
                else:
                    female_contestants.append(contestant)

            # Show split results
            male_count = len(male_contestants)
            female_count = len(female_contestants)
            skipped = len(skipped_participants)

            result_msg = f"Split complete:\n• Male: {male_count}\n• Female: {female_count}"
            if skipped > 0:
                result_msg += f"\n• Skipped (unknown gender): {skipped}"
                if skipped_participants:
                    result_msg += "\n\nSkipped participants:"
                    for sp in skipped_participants[:5]:
                        result_msg += f"\n  - {sp['name']} (gender: '{sp['gender']}')"
                    if len(skipped_participants) > 5:
                        result_msg += f"\n  ... and {len(skipped_participants) - 5} more"

            messagebox.showinfo("Split Results", result_msg)

            if male_count == 0 and female_count == 0:
                self.set_status("No valid contestants to save.", COLORS['accent_red'])
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
                success_msg += f"• contestants_female.json ({female_count} entries)\n"
            success_msg += "\nFiles are ready for external weighing process.\n"
            success_msg += "After weighing, reimport JSON files to generate brackets."

            messagebox.showinfo("Success", success_msg)
            self.set_status("Split complete! Files ready for weighing.", COLORS['accent_green'])

        except Exception as e:
            self.set_status(f"Error: {e}", COLORS['accent_red'])
            self.logger.exception(f"Failed to split participants: {e}")
            messagebox.showerror("Error", f"Failed to split participants:\n{str(e)}")

    def on_closing(self):
        """Handle window closing."""
        self.destroy()

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
            fight_count = self.calculate_number_of_fights(bracket_key)
            display_text = f"{bracket_key} ({fighter_count}F, {fight_count}M)"
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

            # Get user's generation method assignment from generation screen
            assigned_method = self.bracket_generation_methods.get(bracket_key)
            
            # Determine default method based on bracket type
            is_u9_u11 = bracket_key in ('U9', 'U11')
            default_method = 'pools' if is_u9_u11 else 'ko'
            
            method = assigned_method or default_method
            self.logger.debug(f"Bracket {bracket_key} method: {method} (assigned: {assigned_method}, default: {default_method})")

            # Render based on assigned or default method
            if method in ('pools', 'double'):
                title = f"Pool Visualization ({bracket_key})"
                if hasattr(self, 'viz_title_var'):
                    self.viz_title_var.set(title)
                # Get pool_size from bracket data
                pool_size = self.brackets.get(bracket_key, {}).get('pool_size')
                self._render_pool(bracket_key, participants, pool_size)
                return

            # Default to KO bracket rendering (includes 'ko', 'special', and unassigned)
            self.logger.debug(f"Rendering as KO bracket (method: {assigned_method})")
            if hasattr(self, 'viz_title_var'):
                self.viz_title_var.set('Bracket Visualization (KO)')

            # Otherwise render bracket (11+ participants)
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

            self.logger.debug(f"Generated bracket structure with {len(rounds)} rounds")

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
            self.logger.error(f"Exception rendering bracket: {e}")
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering bracket:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

    def _render_pool(self, bracket_key, participants, pool_size=None):
        """Render pool/round-robin visualization on canvas.

        Args:
            bracket_key: The bracket identifier
            participants: List of participant dicts
            pool_size: Configured pool size (max participants per pool).
                      If provided, uses this to calculate number of pools.
                      If None, uses default heuristic.
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

            total_width, total_height, _cell_positions, _ko_boxes = draw_pools_on_canvas(
                self.bracket_canvas,
                normalized_participants,
                self.zoom_level,
                COLORS,
                FONTS,
                start_x,
                start_y,
                pool_size=pool_size
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
            self.logger.error(f"Exception rendering pool: {e}")
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering pool:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

def main():
    app = BracketViewerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
