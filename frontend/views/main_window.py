# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Extracted GUI code from bracket_viewer.py


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
    make_bracket,
    set_bracket_config,
)
from backend.services.database_service import get_database_service  # noqa: E402

from ..services.task_runner import TaskRunner  # noqa: E402
from ..services.bracket_manager import regenerate_stale_ko_brackets  # noqa: E402

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
    draw_pools_on_canvas,
    build_bracket_rounds,
    draw_bracket_on_canvas,
    compute_bracket_rounds,
    calculate_loser_positions,
    draw_loser_connectors,
)

# Import generation method screen
from .generation_method_screen import GenerationMethodScreen  # noqa: E402
from .file_loader_screen import FileLoaderScreen  # noqa: E402
from .group_preview_screen import GroupPreviewScreen  # noqa: E402
from .fight_monitoring_window import FightMonitoringScreen  # noqa: E402
from .rejection_summary_window import RejectionSummaryWindow  # noqa: E402
from .tolerance_config_dialog import ToleranceConfigDialog  # noqa: E402
from ..search_utils import filter_items  # noqa: E402
from ..services.quarantine_service import QuarantineService  # noqa: E402
from ..services.ui_feedback_service import UIFeedbackService  # noqa: E402
from ..services.data_loader_service import DataLoaderService  # noqa: E402

# ====================================================================
# !!!!! CLAUDE: REFACTORING INSTRUCTIONS !!!!!
# ====================================================================
# This file is a GOD CLASS with 44 methods doing 9 different jobs.
# REFACTOR BY EXTRACTING SERVICES - DO NOT hack around in main_window.
#
# Available Infrastructure:
#
# 1. DATABASE ACCESS (use instead of SessionLocal):
#    - self.db_service = get_database_service()
#    - Methods: save_participants(), save_groups_and_brackets(),
#              assign_bracket_to_table(), create_fights_for_bracket()
#    - NEVER call TournamentService or import SessionLocal directly
#
# 2. BACKGROUND THREADING (use instead of manual Thread spawning):
#    - self.task_runner = TaskRunner(num_workers=2)
#    - Submit tasks: self.task_runner.submit_task(
#        task_id='load_xlsx',
#        fn=lambda on_progress: self._perform_load(..., on_progress),
#        on_progress=self.update_progress,
#        on_complete=self.after(500, self.show_next_screen),
#        on_error=self.show_error_dialog
#      )
#    - This enables: parallel DB init + file load, fine-grained progress,
#      task cancellation, centralized error handling
#
# REFACTORING TARGETS (in priority order):
# 1. DataLoaderService    - Extracts: load_and_generate, load_from_database,
#                          load_json_and_generate, split_gender_to_json,
#                          _load_*_thread (all variants), filter_*,
#                          _create_quarantine_bracket (300+ lines)
# 2. BracketManagerService - assign_to_table, unassign_bracket,
#                           auto_assign_tables, resort_brackets,
#                           update_bracket_list, update_table_panels,
#                           calculate_number_of_fights (150+ lines)
# 3. BracketRendererService - render_bracket, _render_pool, zoom_*,
#                            update_zoom_label, _on_mousewheel (200+ lines)
# 4. UIFeedbackService - show_loading_progress, update_progress,
#                       hide_loading_progress, set_status, set_info_text (100+ lines)
# 5. ScreenManagerService - show_* methods (just delegates to new screens)
#
# DO NOT add more logic to main_window. Wire services to callbacks instead.
# ====================================================================

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
        
        self.title('Combat Control')
        self.geometry('520x520')
        self.configure(bg=COLORS['bg_dark'])

        # Configure dark theme for ttk widgets (scrollbars)
        self.setup_ttk_styles()

        # Initialize backend config
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'bracket_config.xlsx')
        try:
            set_bracket_config(config_path)
        except Exception as e:
            self.logger.warning(f"Could not load config: {e}")

        # Initialize database service placeholder (will be set in background thread)
        self.db_service = None

        # Initialize background task runner (for loading, imports, etc.)
        self.task_runner = TaskRunner(num_workers=2)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.logger.debug("TaskRunner initialized with 2 workers for parallel operations")

        # Initialize quarantine service (manages rejected participants)
        self.quarantine_service = QuarantineService()

        # Initialize UI feedback service (handles progress dialogs, status messages)
        self.ui_feedback = UIFeedbackService(self)

        # Initialize data loader service (will be reconfigured when db_service is ready)
        self.data_loader = DataLoaderService(
            ui_feedback=self.ui_feedback,
            quarantine_service=self.quarantine_service,
            db_service=None  # Will be updated after db_service is initialized
        )

        # Start database service initialization in background thread
        self._init_database_service_thread()

        # Data
        self.brackets = {}  # {bracket_key: Bracket data}
        self.bracket_generation_methods = {}  # {bracket_key: method_name}
        self.viewer_shown = False
        self.zoom_level = 1.0  # Zoom level for bracket visualization
        self.current_bracket_key = None  # Track currently displayed bracket

        # Fight monitoring state – persists across window open/close
        # {bracket_key: {(round_idx, match_idx): winner_name}}
        self.match_results = {}
        # {bracket_key: {(lb_round, lb_match): winner_name}}
        self.loser_match_results = {}
        # {bracket_key: {(pool_idx, row, fight_num): score}}
        self.pool_cell_values = {}
        # {bracket_key: {'p0_1st': name, 'p0_2nd': name, ...}}
        self.ko_bracket_data = {}
        # {bracket_key: {(round, match): winner_name}}
        self.ko_match_results = {}

        # Preview window state
        self.group_listbox_map = {}
        self.preview_search_var = None
        self.preview_count_var = None

        # Start with file loading UI
        self.show_file_loader()

    def _init_database_service_thread(self):
        """Initialize database service in a background thread to avoid blocking UI."""
        thread = threading.Thread(target=self._database_init_worker, daemon=True)
        thread.start()
    
    def _database_init_worker(self):
        """Worker thread that initializes the database service."""
        try:
            self.logger.debug("Starting database service initialization in background thread...")
            # Get database service (may take time due to connection pooling)
            self.db_service = get_database_service()
            
            # Update data_loader_service with initialized db_service
            self.data_loader.db_service = self.db_service
            
            self.logger.debug("Database service initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database service: {e}")
            self.db_service = None

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
        loader_screen.on_flush_database = self._flush_database
        
        # Register variables with ui_feedback service if they exist
        if hasattr(loader_screen, 'status_var') and hasattr(loader_screen, 'status_label'):
            self.ui_feedback.set_status_label_reference(loader_screen.status_label, loader_screen.status_var)
        if hasattr(loader_screen, 'info_var'):
            self.ui_feedback.set_info_var_reference(loader_screen.info_var)
        self.ui_feedback.set_file_loader_screen_reference(loader_screen)

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
        preview_screen = GroupPreviewScreen(self, quarantine_service=self.quarantine_service, db_service=self.db_service)
        preview_screen.pack(fill=tk.BOTH, expand=True)

        # Store reference and set up callbacks
        self.group_preview_screen = preview_screen
        preview_screen.on_back = self.show_file_loader
        preview_screen.on_continue = self.show_generation_method_screen
        preview_screen.on_resort = lambda edited_fighter: self.quarantine_service.resort_brackets(
            self.brackets, edited_fighter, preview_screen
        )

        # Re-merge any split U9/U11 pools back into single buckets for the preview
        from utils.bracket_utils import merge_u9_u11_pools
        self.brackets = merge_u9_u11_pools(self.brackets)

        # Load bracket data (QuarantineService restores preserved brackets if available)
        self.quarantine_service.restore_quarantine(self.brackets)
        preview_screen.load_data(self.brackets)

        self.logger.debug("Group preview screen displayed")

    def show_generation_method_screen(self):
        """Show the generation method selection screen."""
        # Sync any group preview edits to DB before proceeding
        self.db_service.save_groups(self.brackets)

        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        # QuarantineService handles extraction and preservation of QUARANTINE bracket
        self.quarantine_service.extract_quarantine(self.brackets)

        # Split U9/U11 single-bucket into individual pools (fighters already sorted by weight)
        from utils.bracket_utils import split_u9_u11_into_pools
        self.brackets = split_u9_u11_into_pools(self.brackets)

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

    def _log_bracket_summary(self):
        """Log a detailed summary of generated brackets."""
        if not self.brackets:
            self.logger.info("No brackets generated")
            return
        
        summary_parts = []
        total_fighters = 0
        quarantine_count = 0
        quarantine_reasons = {}
        
        for bracket_key, bracket_data in sorted(self.brackets.items()):
            fighter_count = len(bracket_data.get('fighters', []))
            total_fighters += fighter_count
            
            if bracket_key.startswith('QUARANTINE_'):
                reason = bracket_key.replace('QUARANTINE_', '')
                quarantine_count += fighter_count
                quarantine_reasons[reason] = fighter_count
                summary_parts.append(f"  [QUARANTINE_{reason}] {fighter_count} rejected participants")
            else:
                summary_parts.append(f"  {bracket_key}: {fighter_count} fighters")
        
        summary_text = "\n".join(summary_parts)
        self.logger.info(f"Bracket generation summary ({len(self.brackets)} brackets, {total_fighters} total fighters):\n{summary_text}")
        if quarantine_count > 0:
            reason_summary = ", ".join([f"{r}({c})" for r, c in quarantine_reasons.items()])
            self.logger.warning(f"⚠️  {quarantine_count} participant(s) in QUARANTINE for manual review ({reason_summary})")


    def show_bracket_viewer(self):
        """Show bracket list and visualization (dark themed)."""
        # Resize and reconfigure window - larger to accommodate loser brackets
        self.geometry('1200x750')
        self.minsize(1000, 600)  # Allow resizing smaller, but set reasonable minimum
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
        
        # Automatically unassign any finished brackets (after all UI is created)
        self.auto_unassign_finished_brackets()


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
        self.db_service.save_brackets(self.brackets, final_assignments)

        # Proceed to bracket viewer
        self.show_bracket_viewer()

    def show_fight_monitoring_screen(self):
        """Switch to the Fight Monitoring screen (in-app, no separate window)."""
        self.logger.info(f"show_fight_monitoring_screen() called with {len(self.brackets)} brackets in self.brackets")
        self.logger.info(f"Bracket table assignments: {self.bracket_table_assignment}")

        # Ensure all KO bracket fields reflect the current fighters lists.
        regenerate_stale_ko_brackets(
            self.brackets, self.bracket_generation_methods, make_bracket)
        self.logger.debug("Regenerated stale KO brackets")

        # Create fight rows in DB for every assigned bracket (idempotent — skips if already created)
        processed = 0
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num and bracket_key in self.brackets:
                bracket_data    = self.brackets[bracket_key]
                bracket_type    = self.bracket_generation_methods.get(bracket_key, 'ko')
                fight_pairs     = bracket_data.get('bracket', [])
                fighters        = bracket_data.get('fighters', [])
                pool_size       = bracket_data.get('pool_size')
                self.logger.info(f"Creating fights for bracket '{bracket_key}' (mat {table_num}) with {len(fight_pairs)} pairs (type={bracket_type})")
                self.db_service.create_fights_for_bracket(
                    bracket_key, fight_pairs,
                    bracket_type=bracket_type,
                    fighters=fighters,
                    pool_size=pool_size,
                )
                processed += 1
            elif table_num:
                self.logger.warning(f"Bracket '{bracket_key}' assigned to table {table_num} but NOT in self.brackets (skipping fight creation)")

        self.logger.info(f"Processed {processed} brackets for fight creation")

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
            loser_match_results=self.loser_match_results,
            pool_cell_values=self.pool_cell_values,
            ko_bracket_data=self.ko_bracket_data,
            ko_match_results=self.ko_match_results,
            db_service=self.db_service,
        )
        screen.pack(fill=tk.BOTH, expand=True)
        screen.on_back = self.show_bracket_viewer
        screen.show_matten_view()

    def show_tables(self):
        """Show table assignment view."""
        self.bracket_view_frame.pack_forget()
        self.tables_frame.pack(fill=tk.BOTH, expand=True)

    def show_bracket_view(self, bracket_key):
        """Show bracket visualization view or group preview for QUARANTINE_* brackets."""
        # For QUARANTINE_* brackets, open group preview for editing
        if bracket_key.startswith('QUARANTINE_'):
            self.show_group_preview_window()
            return
        
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

    def auto_unassign_finished_brackets(self):
        """Automatically unassign brackets where all fights are finished."""
        unassigned_count = 0
        for bracket_key in list(self.bracket_table_assignment.keys()):
            # Skip if not assigned
            if not self.bracket_table_assignment.get(bracket_key):
                continue
            
            # Check if bracket is complete
            if self.is_bracket_complete(bracket_key):
                old_table = self.bracket_table_assignment[bracket_key]
                self.bracket_table_assignment[bracket_key] = None
                unassigned_count += 1
                self.logger.info(f"Auto-unassigned finished bracket '{bracket_key}' from Matte {old_table}")
        
        # Update UI if any were unassigned
        if unassigned_count > 0:
            self.update_bracket_list()
            self.update_table_panels()
            self.logger.info(f"Auto-unassigned {unassigned_count} finished bracket(s)")

    def is_bracket_complete(self, bracket_key):
        """Check if all fights in a bracket have been recorded in monitoring.
        
        Args:
            bracket_key: The bracket identifier
        
        Returns:
            True if all fights recorded, False otherwise
        """
        if bracket_key not in self.brackets:
            return False
        
        assigned_method = self.bracket_generation_methods.get(bracket_key)
        is_u9_u11 = bracket_key in ('U9', 'U11')
        default_method = 'pools' if is_u9_u11 else 'ko'
        method = assigned_method or default_method
        
        total_fights = self.calculate_number_of_fights(bracket_key)
        if total_fights == 0:
            return False
        
        # Check in-memory fight results based on bracket type
        if method in ('pools', 'double'):
            # Pool: check pool_cell_values
            pool_results = self.pool_cell_values.get(bracket_key, {})
            return len(pool_results) >= total_fights
        else:
            # KO: check match_results
            ko_results = self.match_results.get(bracket_key, {})
            return len(ko_results) >= total_fights

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
        
        # QUARANTINE brackets don't have match structures
        if bracket_data.get('is_quarantine', False):
            return 0
        
        fighters = bracket_data.get('fighters', [])
        num_fighters = len(fighters)
        
        if num_fighters == 0:
            return 0
        
        # Determine bracket type from generation method assignment
        assigned_method = self.bracket_generation_methods.get(bracket_key)
        method = assigned_method or 'ko'

        # Calculate fights based on method
        if method in ('pools', 'double'):
            # Round-robin: n * (n-1) / 2 fights
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

        # Assign the bracket (no limit on number of brackets per table)
        self.bracket_table_assignment[bracket_key] = table_num
        bracket_data = self.brackets[bracket_key]
        self.db_service.assign_and_create_fights(
            bracket_key,
            table_num=table_num,
            fight_pairs=bracket_data.get('bracket', []),
            bracket_type=self.bracket_generation_methods.get(bracket_key, 'ko'),
            fighters=bracket_data.get('fighters', []),
            pool_size=bracket_data.get('pool_size'),
        )

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
        self.db_service.unassign_bracket_from_table(bracket_key)
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

        # Assign and create fights for newly assigned brackets
        for bracket_key in unassigned:
            table_num = self.bracket_table_assignment.get(bracket_key)
            if table_num:
                bracket_data = self.brackets[bracket_key]
                self.db_service.assign_and_create_fights(
                    bracket_key,
                    table_num=table_num,
                    fight_pairs=bracket_data.get('bracket', []),
                    bracket_type=self.bracket_generation_methods.get(bracket_key, 'ko'),
                    fighters=bracket_data.get('fighters', []),
                    pool_size=bracket_data.get('pool_size'),
                )

        self.update_bracket_list()
        self.update_table_panels()

    def update_table_panels(self):
        """Update the visual display of table assignments with scrollable content."""
        # Clear all panels
        for panel in self.table_panels.values():
            for widget in panel.winfo_children():
                widget.destroy()

        # Track totals for each table (fighters and fights)
        table_totals = {}  # {table_num: {'fighters': count, 'fights': count}}

        # For each panel, create a scrollable canvas with content
        for table_num, panel in self.table_panels.items():
            # Create canvas for scrollable content
            canvas = tk.Canvas(panel, bg=COLORS['bg_panel'], highlightthickness=0, borderwidth=0)
            scrollbar = ttk.Scrollbar(panel, orient=tk.VERTICAL, command=canvas.yview, style='Vertical.TScrollbar')
            
            # Frame inside canvas to hold content
            content_frame = create_dark_frame(canvas)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas_window = canvas.create_window((0, 0), window=content_frame, anchor='nw')
            
            # Bind canvas resize to expand content frame to full width
            def _on_canvas_configure(event, c=canvas, cf=content_frame, cw=canvas_window):
                # Update the canvas window width to match canvas width
                c.itemconfig(cw, width=event.width)
            
            canvas.bind('<Configure>', _on_canvas_configure)
            
            # Bind mousewheel to canvas
            def _on_panel_wheel(event, c=canvas):
                if event.num == 5 or event.delta < 0:
                    c.yview_scroll(1, "units")
                elif event.num == 4 or event.delta > 0:
                    c.yview_scroll(-1, "units")
            
            canvas.bind('<MouseWheel>', _on_panel_wheel)
            canvas.bind('<Button-4>', _on_panel_wheel)
            canvas.bind('<Button-5>', _on_panel_wheel)
            
            # Pack scrollbar and canvas
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Add assigned brackets to this table
            for bracket_key, assigned_table in self.bracket_table_assignment.items():
                if assigned_table == table_num and len(self.brackets[bracket_key].get('fighters', [])) > 0:
                    # Create row frame for label + unassign button
                    row_frame = create_dark_frame(content_frame)
                    row_frame.pack(fill=tk.X, pady=2, padx=4)

                    # Get fighter count
                    fighter_count = len(self.brackets[bracket_key].get('fighters', []))
                    
                    # Get fight count using standard calculation method
                    fight_count = self.calculate_number_of_fights(bracket_key)
                    
                    # Track totals for this table
                    if table_num not in table_totals:
                        table_totals[table_num] = {'fighters': 0, 'fights': 0}
                    table_totals[table_num]['fighters'] += fighter_count
                    table_totals[table_num]['fights'] += fight_count
                    
                    # Truncate long names
                    display_text = bracket_key[:25] + '...' if len(bracket_key) > 25 else bracket_key
                    display_text = f"{display_text} • {fighter_count} / {fight_count}"
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
            
            # Add totals footer
            fighter_total = table_totals.get(table_num, {}).get('fighters', 0)
            fight_total = table_totals.get(table_num, {}).get('fights', 0)
            
            # Add separator
            separator = tk.Frame(content_frame, height=1, bg=COLORS['border'])
            separator.pack(fill=tk.X, pady=4, padx=4)
            
            # Add total label with both fighters and fights
            total_frame = create_dark_frame(content_frame)
            total_frame.pack(fill=tk.X, pady=2, padx=4)
            
            total_text = f"Table Total: {fighter_total} players • {fight_total} matches"
            total_label = tk.Label(total_frame, text=total_text,
                                  justify='left', anchor='w',
                                  bg=COLORS['bg_panel'], fg=COLORS['accent_orange'],
                                  font=FONTS['heading_sm'])
            total_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Update scroll region
            content_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))


    def _compute_loser_rounds_for_preview(self, wb_rounds):
        """Compute loser bracket structure from winners bracket rounds (for preview).

        This is a simplified version that returns empty loser matches.
        """
        # Need at least 2 WB rounds for a loser bracket to make sense
        # (1 round = only 1 or 2 real participants → no consolation bracket)
        if len(wb_rounds) < 2:
            return []

        def get_loser(match):
            """Extract the loser from a winner/loser match tuple."""
            if match['winner'] and match['winner'] in ('Freilos', 'TBD'):
                return 'TBD'
            if match['winner'] and match['winner'] == match['p1']:
                return match['p2'] if match['p2'] not in ('Freilos', 'TBD') else 'Freilos'
            if match['winner'] and match['winner'] == match['p2']:
                return match['p1'] if match['p1'] not in ('Freilos', 'TBD') else 'Freilos'
            return 'TBD'
        
        loser_rounds = []
        
        # LB R0: pair consecutive losers from WB R0
        wb_r0_losers = [get_loser(m) for m in wb_rounds[0]]
        lb_r0_matches = []
        for i in range(0, len(wb_r0_losers), 2):
            p1 = wb_r0_losers[i]
            p2 = wb_r0_losers[i + 1] if i + 1 < len(wb_r0_losers) else 'Freilos'
            lb_r0_matches.append({'p1': p1, 'p2': p2, 'winner': None})
        loser_rounds.append(lb_r0_matches)
        
        # Remaining LB rounds: add loser from each WB round
        for r in range(1, len(wb_rounds)):
            # Get losers from current WB round
            wb_r_losers = [get_loser(m) for m in wb_rounds[r]]
            # Get winners from previous LB round
            lb_r1_winners = [m['winner'] if m['winner'] else 'TBD' for m in loser_rounds[r - 1]]
            
            if r == len(wb_rounds) - 1:
                # Last round: LB winner vs WB finalist loser (for 3rd place)
                p1 = lb_r1_winners[0] if lb_r1_winners else 'TBD'
                p2 = wb_r_losers[0] if wb_r_losers else 'TBD'
                loser_rounds.append([{'p1': p1, 'p2': p2, 'winner': None}])
            else:
                # Regular round: combine LB winners with WB losers
                lb_matches = []
                prev_count = len(loser_rounds[r - 1])
                curr_wb_losers = len(wb_r_losers)
                
                if curr_wb_losers >= prev_count:
                    # Injection: each LB winner gets matched with a WB loser
                    for i in range(prev_count):
                        p1 = lb_r1_winners[i] if i < len(lb_r1_winners) else 'TBD'
                        p2 = wb_r_losers[i] if i < len(wb_r_losers) else 'Freilos'
                        lb_matches.append({'p1': p1, 'p2': p2, 'winner': None})
                else:
                    # Reduction: LB winners play each other
                    for i in range(0, len(lb_r1_winners), 2):
                        p1 = lb_r1_winners[i] if i < len(lb_r1_winners) else 'TBD'
                        p2 = lb_r1_winners[i + 1] if i + 1 < len(lb_r1_winners) else 'Freilos'
                        lb_matches.append({'p1': p1, 'p2': p2, 'winner': None})
                
                loser_rounds.append(lb_matches)
        
        return loser_rounds

    def on_bracket_double_click(self, event):
        """Handle double-click on bracket - show visualization."""
        selection = self.bracket_listbox.curselection()
        if selection:
            display_text = self.bracket_listbox.get(selection[0])
            bracket_key = self.bracket_listbox_map.get(display_text, display_text)
            self.show_bracket_view(bracket_key)

    def _flush_database(self):
        """Handle Flush Database button — wipe all tournament data."""
        success = self.db_service.flush_database()
        if success:
            self.brackets = {}
            self.match_results = {}
            self.loser_match_results = {}
            if self.file_loader_screen:
                self.file_loader_screen.set_status_text(
                    "Database flushed successfully.", 'status_success'
                )
        else:
            if self.file_loader_screen:
                self.file_loader_screen.set_status_text(
                    "Failed to flush database.", 'status_error'
                )

    def load_and_generate(self):
        """Load participants from XLSX file and generate brackets (wrapper to DataLoaderService)."""
        self.data_loader.load_and_generate(callbacks={
            'on_success': self._on_brackets_loaded
        })

    def _on_brackets_loaded(self, brackets=None, rejected_participants=None):
        """Callback when brackets are successfully loaded (called from background thread).

        Args:
            brackets: Dict of generated brackets (including QUARANTINE_* brackets per reason)
            rejected_participants: List of rejected participant dicts with rejection reasons
        """
        # The brackets are already generated by the service (including QUARANTINE_* per reason)
        if brackets:
            self.brackets = brackets

        # Log bracket generation summary
        self._log_bracket_summary()

        # Schedule UI updates on main thread (callback is called from background thread)
        if rejected_participants:
            # Show rejection window and wait for it to close before showing group preview
            self.after(100, lambda: self._show_rejection_window_and_continue(rejected_participants))
        else:
            # Show group preview window immediately if no rejections
            self.after(500, self.show_group_preview_window)
    
    def _show_rejection_window_and_continue(self, rejected_participants):
        """Show rejection window and continue to group preview after it closes.
        
        This runs on the main thread, so wait_window() won't freeze the entire app.
        """
        self.rejection_window = RejectionSummaryWindow(self, rejected_participants)
        # This will block the main thread until the user closes the rejection window
        # but won't affect other event processing
        self.rejection_window.wait_for_close()
        # After rejection window is closed, show group preview
        self.show_group_preview_window()


    def load_from_database(self):
        """Load participants from PostgreSQL database and generate brackets (wrapper to DataLoaderService)."""
        self.data_loader.load_from_database(callbacks={
            'on_success': self._on_brackets_loaded
        })

    def load_json_and_generate(self):
        """Load 2 JSON files (male/female), merge them, and generate brackets (wrapper to DataLoaderService)."""
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

        # Delegate to DataLoaderService
        self.data_loader.load_json_and_generate(filepaths=filepaths, callbacks={
            'on_success': self._on_brackets_loaded
        })

    def split_gender_to_json(self):
        """Split contestants by gender (M/W) and save to separate JSON files with tolerances.
        
        Delegates to DataLoaderService which handles the file processing and splitting.
        This method manages the UI flow: file selection → tolerance configuration → service call.
        """
        # Select input XLSX file
        input_file = filedialog.askopenfilename(
            title="Select Tournament Registration XLSX File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not input_file:
            return

        try:
            # Verify file exists
            if not os.path.exists(input_file):
                messagebox.showerror("Error", f"File not found: {input_file}")
                return
            
            # Step 1: Show tolerance configuration dialog
            self.ui_feedback.set_status("Configuring weight tolerances...", COLORS['text_secondary'])

            # Build group_keys: mixed categories (U9, U11) + gender-specific (U13+)
            group_keys = []
            # Mixed categories (no gender distinction)
            for age in ['U9', 'U11']:
                group_keys.append(('mixed', age))
            # Gender-specific categories
            for age in ['U13', 'U15', 'U18', '18+']:
                for gender in ['m', 'w']:
                    group_keys.append((gender, age))

            tolerance_dialog = ToleranceConfigDialog(
                self,
                group_keys=group_keys,
                existing_tolerances={}
            )
            configured_tolerances = tolerance_dialog.show()

            if configured_tolerances is None:
                # User cancelled
                self.ui_feedback.set_status("Tolerance configuration cancelled.", COLORS['text_secondary'])
                return
            
            # Step 2: Ask where to save the files
            save_dir = filedialog.askdirectory(
                title="Select Folder to Save Split JSON Files"
            )
            if not save_dir:
                self.ui_feedback.set_status("Save cancelled.", COLORS['text_secondary'])
                return
            
            # Step 3: Pass tolerances to service and execute the split
            success, message = self.data_loader.split_gender_to_json_with_tolerances(
                input_file, 
                save_dir,
                configured_tolerances=configured_tolerances
            )
            
            if success:
                messagebox.showinfo("Success", message)
                self.ui_feedback.set_status("Split complete! Files ready for weighing.", COLORS['accent_green'])
            else:
                messagebox.showerror("Error", message)
                self.ui_feedback.set_status(f"Error: {message}", COLORS['accent_red'])

        except Exception as e:
            self.ui_feedback.set_status(f"Error: {e}", COLORS['accent_red'])
            self.logger.exception(f"Failed to split participants: {e}")
            messagebox.showerror("Error", f"Failed to split participants:\n{str(e)}")


    def on_closing(self):
        """Handle window closing - cleanup resources."""
        self.logger.info("Application closing, shutting down task runner...")
        self.task_runner.shutdown(wait=False)  # Don't block UI, let tasks finish in background
        self.logger.close()  # Close file handlers for proper cleanup
        self.destroy()

    def update_bracket_list(self, *args):
        """Update the bracket list based on search filter - only show unassigned (supports multi-term AND search)."""
        if not hasattr(self, 'search_var'):
            return

        search_term = self.search_var.get()
        self.bracket_listbox.delete(0, tk.END)
        # Store mapping of display text to bracket_key for safe lookup
        self.bracket_listbox_map = {}
        
        # Get unassigned bracket keys — skip empty brackets (fighters moved to another group)
        unassigned_keys = [k for k in sorted(self.brackets.keys())
                           if not self.bracket_table_assignment.get(k)
                           and len(self.brackets[k].get('fighters', [])) > 0]
        
        # Move QUARANTINE_* brackets to front
        quarantine_keys = [k for k in unassigned_keys if k.startswith('QUARANTINE_')]
        normal_keys = [k for k in unassigned_keys if not k.startswith('QUARANTINE_')]
        unassigned_keys = quarantine_keys + normal_keys
        
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
            
            # Check if bracket is complete
            is_complete = self.is_bracket_complete(bracket_key)
            prefix = "[✓] " if is_complete else ""
            
            display_text = f"{prefix}{bracket_key} • {fighter_count} / {fight_count}"
            
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
            method = assigned_method or 'ko'
            self.logger.debug(f"Bracket {bracket_key} method: {method} (assigned: {assigned_method})")

            # Get pool_size from bracket data for decision-making
            pool_size = self.brackets.get(bracket_key, {}).get('pool_size')
            
            # Fallback logic: if pool method but no pool_size and 11+ participants (and not explicit 'double'), use bracket system instead
            should_use_bracket_fallback = (
                method in ('pools', 'double') and
                pool_size is None and
                num_participants > 10 and
                method != 'double'  # 'double' is explicitly user-selected, don't override
            )
            
            if should_use_bracket_fallback:
                self.logger.debug(f"Falling back to bracket system: {num_participants} participants with no pool_size configured")
                method = 'ko'  # Override to bracket system
            
            # Render based on method (pools or bracket/ko)
            if method in ('pools', 'double'):
                title = f"Pool Visualization ({bracket_key})"
                if hasattr(self, 'viz_title_var'):
                    self.viz_title_var.set(title)
                self._render_pool(bracket_key, participants, pool_size, generation_method=method)
                return

            # Default to KO bracket rendering (includes 'ko', 'special', and fallback cases)
            self.logger.debug(f"Rendering as KO bracket (method: {assigned_method})")
            if hasattr(self, 'viz_title_var'):
                self.viz_title_var.set('Bracket Visualization (KO)')

            # Otherwise render bracket (11+ participants)
            self.logger.debug(f"Generating bracket structure for: {bracket_key}")

            # Normalize participants and generate bracket rounds
            normalized_participants = []
            for p in participants:
                if isinstance(p, dict):
                    # Debug: log what keys exist in the participant dict
                    if not normalized_participants:  # Only log first one
                        self.logger.debug(f"Participant keys: {list(p.keys())}")
                        self.logger.debug(f"First participant full object: {p}")
                    
                    normalized_participants.append({
                        'Name': p.get('Name', p.get('name', '')),
                        'Verein': p.get('Club', p.get('Verein', p.get('verein', p.get('club', ''))))  # Try Club first (XLSX loader uses uppercase)
                    })

            if not normalized_participants:
                self.logger.debug("No normalized participants")
                self.bracket_canvas.create_text(400, 300,
                    text="Error: Could not process participants",
                    font=FONTS['heading_md'], fill='red')
                return

            self.logger.debug(f"Normalized {len(normalized_participants)} participants")
            # Debug: log what we extracted
            for i, p in enumerate(normalized_participants[:3]):  # Log first 3
                self.logger.debug(f"  Participant {i}: Name='{p['Name']}', Verein='{p['Verein']}'")

            # Generate bracket visualization
            bracket = make_bracket(normalized_participants)
            self.logger.debug(f"Generated bracket with {len(bracket)} first round matches")

            # Keep stored bracket in sync with what we just rendered,
            # so fight monitoring always uses exactly what the preview shows.
            self.brackets[bracket_key]['bracket'] = bracket

            # Build rounds with club information using bracket_renderer infrastructure
            rounds_with_clubs = build_bracket_rounds(bracket, normalized_participants)
            self.logger.debug(f"Generated bracket structure with {len(rounds_with_clubs)} rounds and club info")

            # Calculate box dimensions using utility function (rounds now include clubs)
            box_width, box_height, x_gap, y_gap = calculate_box_size(rounds_with_clubs, self.zoom_level)

            # Calculate bracket positions
            positions = {}
            y_offsets = {}
            first_total = len(rounds_with_clubs[0])
            start_x = int(60 * self.zoom_level)
            start_y = int(60 * self.zoom_level)

            for m in range(first_total):
                x = start_x
                y = start_y + m * (box_height + y_gap)
                positions[(0, m)] = (x, y)
                y_offsets[(0, m)] = y + box_height // 2

            for r in range(1, len(rounds_with_clubs)):
                matches = rounds_with_clubs[r]
                x = start_x + r * (box_width + x_gap)
                for m in range(len(matches)):
                    prev1 = (r-1, m*2)
                    prev2 = (r-1, m*2+1)
                    y1 = y_offsets.get(prev1, start_y)
                    y2 = y_offsets.get(prev2, y1)
                    y = (y1 + y2) // 2 - box_height // 2
                    positions[(r, m)] = (x, y)
                    y_offsets[(r, m)] = y + box_height // 2

            # Draw bracket using your complete infrastructure (includes club display)
            draw_bracket_on_canvas(
                self.bracket_canvas, 
                rounds_with_clubs, 
                positions, 
                box_width, 
                box_height, 
                self.zoom_level, 
                COLORS, 
                FONTS
            )

            # Draw simplified empty loser bracket below winners bracket
            loser_max_y = self._draw_loser_bracket_on_canvas(
                bracket, bracket_key, positions, box_width, box_height,
                start_x, start_y, self.zoom_level
            )

            # Update scroll region based on bracket size and zoom level
            max_x = max(pos[0] for pos in positions.values()) + box_width + start_x
            max_y = loser_max_y + start_y  # Use actual loser bracket height
            self.bracket_canvas.configure(scrollregion=(0, 0, max_x, max_y))

            self.logger.debug(f"Successfully rendered bracket with {len(rounds_with_clubs)} rounds and club info at {int(self.zoom_level*100)}% zoom")

        except Exception as e:
            self.logger.error(f"Exception rendering bracket: {e}")
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering bracket:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

    def _draw_loser_bracket_on_canvas(self, bracket, bracket_key, wb_positions, 
                                     box_width, box_height, start_x, start_y, zoom_level):
        """Draw a simplified empty loser bracket below the winners bracket on the canvas.
        
        Shows the structure of the loser bracket without any filled-in winners.
        
        Returns:
            The max y coordinate used by the loser bracket (for scroll region calculation)
        """
        try:
            # Compute winners bracket rounds
            wb_rounds = compute_bracket_rounds(bracket, {})
            if not wb_rounds:
                return max(pos[1] for pos in wb_positions.values()) + box_height  # fallback
            
            # Compute loser bracket structure
            loser_rounds = self._compute_loser_rounds_for_preview(wb_rounds)
            if not loser_rounds:
                return max(pos[1] for pos in wb_positions.values()) + box_height  # fallback
            
            # Position loser bracket below winners bracket
            max_wb_y = max(pos[1] for pos in wb_positions.values()) + box_height
            y_offset = max_wb_y + int(40 * zoom_level)  # Gap between brackets
            
            # Calculate positions for loser bracket using utility
            lb_pos, _ = calculate_loser_positions(loser_rounds, zoom_level, y_offset, start_x)
            
            # Draw connectors using utility
            draw_loser_connectors(self.bracket_canvas, lb_pos, loser_rounds, zoom_level, COLORS)
            
            # Draw match boxes (simplified empty boxes)
            LW = max(1, int(2 * zoom_level))
            BW = int(200 * zoom_level)
            BH = int(64 * zoom_level)
            
            for r, matches in enumerate(loser_rounds):
                for m in range(len(matches)):
                    if (r, m) not in lb_pos:
                        continue
                    
                    x, y = lb_pos[(r, m)]
                    x2, y2 = x + BW, y + BH
                    my = y + BH // 2
                    
                    # Draw box outline in orange
                    self.bracket_canvas.create_rectangle(
                        x, y, x2, y2,
                        fill=COLORS['bg_panel'],
                        outline=COLORS['accent_orange'], width=LW)
                    
                    # Draw separator line for the two competitors
                    self.bracket_canvas.create_line(
                        x, my, x2, my,
                        fill=COLORS['border'], width=1, dash=(4, 3))
            
            # Draw loser bracket labels
            nr = len(loser_rounds)
            XG = int(70 * zoom_level)
            label_font = ('Arial', max(8, int(11 * zoom_level)), 'bold')
            
            for r in range(nr):
                lx = start_x + r * (BW + XG) + BW // 2
                label = '3rd Place' if r == nr - 1 else f'Loser R{r + 1}'
                self.bracket_canvas.create_text(
                    lx, y_offset - int(20 * zoom_level),
                    text=label, anchor='c',
                    fill=COLORS['accent_orange'], font=label_font)
            
            # Calculate and return max y used by loser bracket
            if lb_pos:
                max_lb_y = max(pos[1] for pos in lb_pos.values()) + BH
                self.logger.debug(f"Drew loser bracket for '{bracket_key}' with max_y={max_lb_y}")
                return max_lb_y
            else:
                return max_wb_y
        except Exception as e:
            self.logger.debug(f"Error drawing loser bracket for '{bracket_key}': {e}")
            return max(pos[1] for pos in wb_positions.values()) + box_height

    def _render_pool(self, bracket_key, participants, pool_size=None, generation_method=None):
        """Render pool/round-robin visualization on canvas.

        Args:
            bracket_key: The bracket identifier
            participants: List of participant dicts
            pool_size: Configured pool size (max participants per pool).
                      If provided, uses this to calculate number of pools.
                      If None, uses default heuristic.
            generation_method: The generation method ('pools' or 'double').
                              If 'double', forces 2 pools regardless of participant count.
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
                pool_size=pool_size,
                generation_method=generation_method
            )

            # Update scroll region
            self.bracket_canvas.configure(scrollregion=(0, 0, total_width, total_height))

            num_participants = len(normalized_participants)
            assigned_method = self.bracket_generation_methods.get(bracket_key, 'unknown')
            
            # Calculate number of matches in round-robin
            num_matches = (num_participants * (num_participants - 1)) // 2
            
            # Determine pool type for display based on generation method
            if generation_method == 'double':
                pool_type = "Double Pool"
            elif pool_size and num_participants > pool_size:
                pool_type = "Multiple Pools"
            else:
                pool_type = "Single Pool"
            
            self.logger.debug(f"Successfully rendered {pool_type} (method: {assigned_method}) with {num_participants} participants, {num_matches} total matches at {int(self.zoom_level*100)}% zoom")

        except Exception as e:
            self.logger.error(f"Exception rendering pool: {e}")
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering pool:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

def main():
    """
    Launch the Tournament Bracket Manager application.
    
    Initializes the GUI and handles errors gracefully.
    """
    try:
        app = BracketViewerApp()
        app.logger.info("Application started successfully")
        app.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"Fatal error during application startup:\n{str(e)}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        # Try to show a messagebox if tk is available
        try:
            tk.Tk().withdraw()
            tk.messagebox.showerror("Application Error", error_msg)
        except Exception:
            pass


if __name__ == '__main__':
    main()
