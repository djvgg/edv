# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Extracted GUI code from bracket_viewer.py


import os
import sys
import threading

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

from utils.task_runner import TaskRunner  # noqa: E402
from ..services.bracket_manager import regenerate_stale_ko_brackets  # noqa: E402

from ..styles import (  # noqa: E402
    COLORS,
    SCROLLBAR_STYLE,
    SCROLLBAR_ACTIVE_STYLE,
    create_dark_frame,
)

# Import screen components
from .generation_method_screen import GenerationMethodScreen  # noqa: E402
from .file_loader_screen import FileLoaderScreen  # noqa: E402
from .group_preview_screen import GroupPreviewScreen  # noqa: E402
from .fight_monitoring_window import FightMonitoringScreen  # noqa: E402
from .rejection_summary_window import RejectionSummaryWindow  # noqa: E402
from .tolerance_config_dialog import ToleranceConfigDialog  # noqa: E402
from .table_and_bracket_viewer import TableAndBracketViewer  # noqa: E402
from ..services.quarantine_service import QuarantineService  # noqa: E402
from ..services.ui_feedback_service import UIFeedbackService  # noqa: E402
from ..services.data_loader_service import DataLoaderService  # noqa: E402
from ..navigation_bar import NavigationBar  # noqa: E402

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

    # Scrollbar style name constants
    SCROLLBAR_VERTICAL = 'Vertical.TScrollbar'
    SCROLLBAR_HORIZONTAL = 'Horizontal.TScrollbar'

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
            db_service=None,  # Will be updated after db_service is initialized
            task_runner=self.task_runner
        )

        # Start database service initialization in background thread
        self._init_database_service_thread()

        # Data
        self.brackets = {}  # {bracket_key: Bracket data}
        self.bracket_generation_methods = {}  # {bracket_key: method_name}
        self.bracket_table_assignment = {}  # {bracket_key: table_number or None}

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

        # Create navigation bar (will display at top of window)
        self.nav_bar = NavigationBar(self)
        self.nav_bar.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
        self.logger.debug("Navigation bar created")

        # Add initial tab for file loader
        self.nav_bar.add_tab('file_loader', 'File Loader')
        self.nav_bar.set_active_tab('file_loader')

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
            
            # Update data_loader_service with initialized db_service and task_runner
            self.data_loader.db_service = self.db_service
            self.data_loader.task_runner = self.task_runner
            
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
        style.configure(self.SCROLLBAR_VERTICAL, **SCROLLBAR_STYLE)

        # Horizontal scrollbar
        style.configure(self.SCROLLBAR_HORIZONTAL, **SCROLLBAR_STYLE)

        # Active (hover) state
        style.map(self.SCROLLBAR_VERTICAL,
                 background=[('active', SCROLLBAR_ACTIVE_STYLE['background'])],
                 arrowcolor=[('active', SCROLLBAR_ACTIVE_STYLE['arrowcolor'])])

        style.map(self.SCROLLBAR_HORIZONTAL,
                 background=[('active', SCROLLBAR_ACTIVE_STYLE['background'])],
                 arrowcolor=[('active', SCROLLBAR_ACTIVE_STYLE['arrowcolor'])])

    def show_file_loader(self):
        """Show file loading screen."""
        # Update nav bar
        self.nav_bar.set_active_tab('file_loader')

        # Clear any existing widgets (except nav bar)
        for widget in self.winfo_children():
            if widget != self.nav_bar:
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

        # Update nav bar
        self.nav_bar.add_tab('group_preview', 'Group Preview')
        self.nav_bar.set_active_tab('group_preview')

        # Clear existing widgets (except nav bar)
        for widget in self.winfo_children():
            if widget != self.nav_bar:
                widget.destroy()

        # Create and display preview screen
        preview_screen = GroupPreviewScreen(self, quarantine_service=self.quarantine_service, db_service=self.db_service)
        preview_screen.pack(fill=tk.BOTH, expand=True)

        # Set up callbacks
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

        # Update nav bar
        self.nav_bar.add_tab('generation_method', 'Generation Method')
        self.nav_bar.set_active_tab('generation_method')

        # Clear existing widgets (except nav bar)
        for widget in self.winfo_children():
            if widget != self.nav_bar:
                widget.destroy()

        # QuarantineService handles extraction and preservation of QUARANTINE bracket
        self.quarantine_service.extract_quarantine(self.brackets)

        # Split U9/U11 single-bucket into individual pools (fighters already sorted by weight)
        from utils.bracket_utils import split_u9_u11_into_pools
        self.brackets = split_u9_u11_into_pools(self.brackets)

        # Create the generation method screen
        gen_screen = GenerationMethodScreen(self)
        gen_screen.pack(fill=tk.BOTH, expand=True)

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
        """Show bracket viewer - delegates to TableAndBracketViewer implementation."""
        self.show_new_bracket_viewer()


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

    def show_tables(self):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def show_bracket_view(self, bracket_key):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def show_new_bracket_viewer(self):
        """Show the NEW TableAndBracketViewer implementation (full screen)."""
        self.logger.info("Switching to NEW implementation (TableAndBracketViewer)")
        
        # Update nav bar
        self.nav_bar.add_tab('bracket_viewer', 'Bracket Viewer')
        self.nav_bar.set_active_tab('bracket_viewer')
        
        # Prepare data
        regenerate_stale_ko_brackets(
            self.brackets, self.bracket_generation_methods, make_bracket)
        
        processed = 0
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num and bracket_key in self.brackets:
                bracket_data = self.brackets[bracket_key]
                bracket_type = self.bracket_generation_methods.get(bracket_key, 'ko')
                fight_pairs = bracket_data.get('bracket', [])
                fighters = bracket_data.get('fighters', [])
                pool_size = bracket_data.get('pool_size')
                self.db_service.create_fights_for_bracket(
                    bracket_key, fight_pairs, bracket_type=bracket_type,
                    fighters=fighters, pool_size=pool_size)
                processed += 1

        self.logger.info(f"Processed {processed} brackets for NEW viewer")
        self.geometry('1200x750')
        
        # Clear existing widgets (except nav bar)
        for widget in self.winfo_children():
            if widget != self.nav_bar:
                widget.destroy()
        
        # Create the new viewer and store as instance variable to prevent garbage collection
        self.current_viewer = TableAndBracketViewer(self, main_window=self)
        self.current_viewer.pack(fill=tk.BOTH, expand=True)

    def show_fight_monitoring_comparison(self):
        """Show OLD vs NEW implementation side by side for comparison."""
        self.logger.info("Showing comparison: OLD implementation (left) vs NEW (right)")
        
        # Prepare data
        regenerate_stale_ko_brackets(
            self.brackets, self.bracket_generation_methods, make_bracket)
        
        processed = 0
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num and bracket_key in self.brackets:
                bracket_data = self.brackets[bracket_key]
                bracket_type = self.bracket_generation_methods.get(bracket_key, 'ko')
                fight_pairs = bracket_data.get('bracket', [])
                fighters = bracket_data.get('fighters', [])
                pool_size = bracket_data.get('pool_size')
                self.db_service.create_fights_for_bracket(
                    bracket_key, fight_pairs, bracket_type=bracket_type,
                    fighters=fighters, pool_size=pool_size)
                processed += 1

        self.logger.info(f"Processed {processed} brackets for comparison view")
        self.geometry('1800x800')
        
        for widget in self.winfo_children():
            if widget != self.nav_bar:
                widget.destroy()
        
        # Create paned window for left/right split
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                              bg=COLORS['bg_dark'], sashwidth=4,
                              sashrelief=tk.FLAT, showhandle=False)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # LEFT: Old implementation (FightMonitoringScreen - original main_window code)
        left_frame = create_dark_frame(paned)
        paned.add(left_frame, width=800, minsize=600) 
        
        left_label = tk.Label(left_frame, text='← OLD: FightMonitoringScreen', 
                            font=('Arial', 10, 'bold'), fg='#FF6B6B')
        left_label.pack(pady=5)
        
        old_screen = FightMonitoringScreen(
            parent=left_frame,
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
        old_screen.pack(fill=tk.BOTH, expand=True)
        old_screen.show_matten_view()
        
        # RIGHT: New implementation (TableAndBracketViewer)
        right_frame = create_dark_frame(paned)
        paned.add(right_frame, minsize=600)
        
        right_label = tk.Label(right_frame, text='NEW: TableAndBracketViewer →', 
                             font=('Arial', 10, 'bold'), fg='#4CAF50')
        right_label.pack(pady=5)
        
        new_viewer = TableAndBracketViewer(right_frame, main_window=self)
        new_viewer.pack(fill=tk.BOTH, expand=True)
        
        # Back button
        def _go_back():
            for w in self.winfo_children():
                w.destroy()
            self.show_bracket_viewer()
        
        old_screen.on_back = _go_back

    def show_fight_monitoring_screen(self):
        """Switch to the Fight Monitoring screen."""
        self.logger.info("show_fight_monitoring_screen() called")

        # Prepare data
        regenerate_stale_ko_brackets(
            self.brackets, self.bracket_generation_methods, make_bracket)
        self.logger.debug("Regenerated stale KO brackets")

        # Create fight rows in DB for every assigned bracket
        processed = 0
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num and bracket_key in self.brackets:
                bracket_data = self.brackets[bracket_key]
                bracket_type = self.bracket_generation_methods.get(bracket_key, 'ko')
                fight_pairs = bracket_data.get('bracket', [])
                fighters = bracket_data.get('fighters', [])
                pool_size = bracket_data.get('pool_size')
                self.db_service.create_fights_for_bracket(
                    bracket_key, fight_pairs, bracket_type=bracket_type,
                    fighters=fighters, pool_size=pool_size)
                processed += 1

        self.logger.info(f"Processed {processed} brackets for fight monitoring")

        # Update nav bar
        self.nav_bar.add_tab('fight_monitoring', 'Fight Monitoring')
        self.nav_bar.set_active_tab('fight_monitoring')

        # Show fight monitoring screen fullscreen
        self.geometry('1200x750')
        
        for widget in self.winfo_children():
            if widget != self.nav_bar:
                widget.destroy()

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
        
        # Back button goes back to bracket viewer
        def _go_back_to_bracket_viewer():
            for widget in self.winfo_children():
                widget.destroy()
            self.show_bracket_viewer()
        
        screen.on_back = _go_back_to_bracket_viewer
        screen.show_matten_view()

    def auto_unassign_finished_brackets(self):
        """Automatically unassign brackets where all fights are finished."""
        unassigned_count = 0
        for bracket_key in self.bracket_table_assignment.keys():
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
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def unassign_bracket(self, bracket_key=None):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def auto_assign_tables(self):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def update_table_panels(self):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _get_loser_from_match(self, match):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _compute_first_loser_round(self, wb_rounds):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _create_injection_matches(self, lb_prev_winners, wb_losers):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _create_reduction_matches(self, lb_prev_winners):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _compute_regular_loser_round(self, wb_losers, lb_prev_winners):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _compute_final_loser_round(self, lb_prev_winners, wb_losers):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _compute_loser_rounds_for_preview(self, wb_rounds):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def on_bracket_double_click(self, event):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

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
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def render_bracket(self, bracket_key):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _draw_loser_bracket_on_canvas(self, bracket, bracket_key, wb_positions, 
                                     box_height, start_x, zoom_level):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

    def _render_pool(self, bracket_key, participants, pool_size=None, generation_method=None):
        """DEPRECATED: This method has been moved to TableAndBracketViewer component."""
        pass

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
