# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Extracted GUI code from bracket_viewer.py


import os
import sys
import threading

import tkinter as tk
from tkinter import messagebox, filedialog, ttk

import platform
import subprocess

def select_json_files():
    # Linux: use Zenity for native modern dialog
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                [
                    "zenity",
                    "--file-selection",
                    "--multiple",
                    "--separator=|",
                    "--file-filter=JSON files | *.json"
                ],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout.strip().split("|")

        except FileNotFoundError:
            pass  # zenity not installed → fallback

    # Windows / fallback
    return filedialog.askopenfilenames(
        title="Select 2 JSON Files (Male & Female)",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

# Setup sys.path for backend imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger  # noqa: E402
from backend.services.bracket_service import (  # noqa: E402
    set_bracket_config,
)
from backend.services.database_service import get_database_service  # noqa: E402

from utils.task_runner import TaskRunner  # noqa: E402
from ..services.bracket_manager import regenerate_stale_ko_brackets  # noqa: E402

from ..styles import (  # noqa: E402
    COLORS,
    SCROLLBAR_STYLE,
    SCROLLBAR_ACTIVE_STYLE,
    toggle_theme,
)

# Import screen components
from .generation_method_screen import GenerationMethodScreen  # noqa: E402
from .file_loader_screen import FileLoaderScreen  # noqa: E402
from .group_preview_screen import GroupPreviewScreen  # noqa: E402
from .fight_monitoring_window import FightMonitoringScreen  # noqa: E402
from .rejection_summary_window import RejectionSummaryWindow  # noqa: E402
from .tolerance_config_dialog import ToleranceConfigDialog  # noqa: E402
from .table_and_bracket_viewer import TableAndBracketViewer  # noqa: E402
from .results_screen import ResultsScreen  # noqa: E402
from ..services.quarantine_service import QuarantineService  # noqa: E402
from ..services.ui_feedback_service import UIFeedbackService  # noqa: E402
from ..services.data_loader_service import DataLoaderService  # noqa: E402
from ..navigation_bar import NavigationBar  # noqa: E402
from ..screen_manager import ScreenManager  # noqa: E402
from ..data_transformation_pipeline import DataTransformationPipeline  # noqa: E402

# ====================================================================
# Main Application Window
# ====================================================================
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
        self.geometry('520x620')
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
        self.quarantine_service = QuarantineService(task_runner=self.task_runner)

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
        self.locked_age_classes = set()  # {'U15', 'm|U18', ...}

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

        # Create content frame for screens (below nav bar)
        self.content_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        self.content_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.logger.debug("Content frame created")

        # Create screen manager (controls navigation and lifecycle)
        self.screen_manager = ScreenManager(self, self.nav_bar)
        self.logger.debug("Screen manager created")

        # Inject screen manager into nav bar for staleness tracking
        self.nav_bar.set_screen_manager(self.screen_manager)
        self.nav_bar.on_theme_toggle = self._toggle_theme

        # Create data transformation pipeline (orchestrates business logic)
        # headless=False means include UI-only operations (normal mode)
        self.data_pipeline = DataTransformationPipeline(self, headless=False)
        self.screen_manager.set_data_pipeline(self.data_pipeline)
        self.logger.debug("Data transformation pipeline created and wired to ScreenManager")


        # Define factory functions for screens with complex initialization
        def bracket_viewer_factory(main_window):
            """Factory for TableAndBracketViewer - requires main_window reference"""
            return TableAndBracketViewer(self.content_frame, main_window=self)

        def results_factory(main_window):
            return ResultsScreen(self.content_frame, main_window=self)
        
        def fight_monitoring_factory(main_window):
            """Factory for FightMonitoringScreen - requires data from main_window"""
            return FightMonitoringScreen(
                parent=self.content_frame,
                brackets=self.brackets,
                bracket_table_assignment=self.bracket_table_assignment,
                bracket_generation_methods=self.bracket_generation_methods,
                match_results=self.match_results,
                loser_match_results=self.loser_match_results,
                pool_cell_values=self.pool_cell_values,
                ko_bracket_data=self.ko_bracket_data,
                ko_match_results=self.ko_match_results,
                db_service=self.db_service,
                main_window=self,
            )

        def group_preview_factory(main_window):
            """Factory for GroupPreviewScreen - requires main_window reference for reload on stale"""
            return GroupPreviewScreen(
                parent=self.content_frame,
                main_window=self,
                quarantine_service=self.quarantine_service,
                db_service=self.db_service,
                bracket_table_assignment=self.bracket_table_assignment,
                locked_age_classes=self.locked_age_classes,
            )

        def file_loader_factory(main_window):
            """Factory for FileLoaderScreen - requires main_window reference for on_show"""
            return FileLoaderScreen(
                parent=self.content_frame,
                main_window=self,
            )

        def generation_method_factory(main_window):
            """Factory for GenerationMethodScreen - requires main_window reference for reload"""
            return GenerationMethodScreen(
                parent=self.content_frame,
                main_window=self,
            )

        # Register all screens
        self.screen_manager.register_screen(
            'file_loader', None, 'Dateilader', locked=False,
            screen_factory=file_loader_factory
        )
        self.screen_manager.register_screen(
            'group_preview', None, 'Gruppenvorschau', locked=False,
            screen_factory=group_preview_factory
        )
        self.screen_manager.register_screen(
            'generation_method', None, 'Wettkampfsystem', locked=False,
            screen_factory=generation_method_factory
        )
        self.screen_manager.register_screen(
            'bracket_viewer', None, 'Listenansicht', locked=False, 
            screen_factory=bracket_viewer_factory
        )
        self.screen_manager.register_screen(
            'results', None, 'Fertige Kampflisten', locked=False,
            screen_factory=results_factory
        )

        self.logger.debug("All screens registered with ScreenManager")

        # Start with file loading UI
        self.screen_manager.navigate_to('file_loader')

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
            self.locked_age_classes = self.db_service.get_locked_age_classes()
            self.logger.debug(f"Loaded age-class locks: {sorted(self.locked_age_classes)}")
            
            self.logger.debug("Database service initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database service: {e}")
            self.db_service = None

    def wait_for_db_service(self, timeout_ms=10000):
        """
        Wait for database service to be initialized (with timeout to avoid blocking UI forever).
        
        Args:
            timeout_ms: Maximum time to wait in milliseconds
            
        Returns:
            True if db_service is ready, False if timeout or error occurred
        """
        import time
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0
        
        while self.db_service is None:
            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                self.logger.warning(f"Database service initialization timeout after {elapsed:.1f}s")
                return False
            
            # Non-blocking wait - process pending events and sleep briefly
            self.update()
            time.sleep(0.1)
        
        self.logger.debug("Database service is ready")
        return True

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

    def _toggle_theme(self):
        toggle_theme()
        self.configure(bg=COLORS['bg_dark'])
        self.content_frame.configure(bg=COLORS['bg_dark'])
        self.setup_ttk_styles()
        self.nav_bar.refresh_theme()
        current = self.screen_manager.current_screen_key
        if current:
            self.screen_manager.invalidate_all_screens()
            self.screen_manager.navigate_to(current)

    def check_screen_prerequisites(self, screen_key):
        """
        Check if a screen can be navigated to based on available data.
        
        Args:
            screen_key: The screen identifier
            
        Returns:
            True if navigation is allowed, False if prerequisites not met
        """
        # file_loader can always be navigated to
        if screen_key == 'file_loader':
            return True
        
        # All other screens require brackets to be loaded
        if not self.brackets:
            self.logger.warning(f"Cannot navigate to {screen_key}: no brackets loaded")
            self.logger.info("Redirecting to file_loader to load data first")
            # Redirect to file_loader
            if self.screen_manager.current_screen_key != 'file_loader':
                self.screen_manager.navigate_to('file_loader')
            return False
        
        return True

    def setup_screen_callbacks(self, screen_key, screen):
        """
        Wire up callbacks for a screen based on its type.
        Called by ScreenManager after screen creation.
        
        Args:
            screen_key: The screen identifier (e.g., 'file_loader')
            screen: The screen instance
        """
        if screen_key == 'file_loader':
            # FileLoaderScreen callbacks
            screen.on_load_database = self.load_from_database
            screen.on_load_json = self.load_json_and_generate
            screen.on_split_gender = self.split_gender_to_json
            screen.on_flush_database = self._flush_database
            
            # Register UI feedback references
            if hasattr(screen, 'status_var') and hasattr(screen, 'status_label'):
                self.ui_feedback.set_status_label_reference(screen.status_label, screen.status_var)
            if hasattr(screen, 'info_var'):
                self.ui_feedback.set_info_var_reference(screen.info_var)
            self.ui_feedback.set_file_loader_screen_reference(screen)
            
            self.logger.debug("Wired FileLoaderScreen callbacks")
        
        elif screen_key == 'group_preview':
            # GroupPreviewScreen callbacks and data loading
            screen.on_back = lambda: self.screen_manager.navigate_to('file_loader')
            screen.on_continue = lambda: self.screen_manager.navigate_to('generation_method')
            screen.on_resort = lambda edited_fighter: (
                self.quarantine_service.resort_brackets(
                    self.brackets, edited_fighter, screen, self.db_service,
                    self.bracket_table_assignment, self.locked_age_classes
                ),
                self.screen_manager.invalidate_downstream('group_preview')
            )
            
            # Data loading and preparation
            from utils.bracket_utils import merge_u9_u11_pools
            self.brackets = merge_u9_u11_pools(self.brackets)
            self.quarantine_service.restore_quarantine(self.brackets)
            screen.load_data(self.brackets)
            
            # Resize window for this screen
            self.geometry('1000x600')
            
            self.logger.debug("Wired GroupPreviewScreen callbacks and loaded data")
        
        elif screen_key == 'generation_method':
            # GenerationMethodScreen callbacks and data transformation
            self.logger.debug("[SETUP] generation_method setup started")
            screen.on_generation_complete = self.on_generation_methods_selected
            screen.on_back_callback = lambda: self.screen_manager.navigate_to('group_preview')
            
            # Data transformation before showing
            # Wait for database service to be ready before using it
            if self.wait_for_db_service():
                self.db_service.save_groups(self.brackets)
                self.logger.debug("[SETUP] Saved groups to DB")
            
            self.logger.debug("[SETUP] Extracting quarantine brackets...")
            self.quarantine_service.extract_quarantine(self.brackets)
            self.logger.debug(f"[SETUP] Brackets after extract_quarantine: {len(self.brackets)} brackets")
            
            from utils.bracket_utils import split_u9_u11_into_pools
            self.brackets = split_u9_u11_into_pools(self.brackets)
            self.logger.debug(f"[SETUP] Brackets after split_u9_u11_into_pools: {len(self.brackets)} brackets")
            
            # Prepare bracket data for the screen
            brackets_dict = {}
            for bracket_key, bracket_data in self.brackets.items():
                fighters = bracket_data.get('fighters', [])
                cached_method = self.bracket_generation_methods.get(bracket_key)
                brackets_dict[bracket_key] = {
                    'tuple': fighters,
                    'method': cached_method,
                }
                self.logger.debug(f"[SETUP] Added to brackets_dict: {bracket_key} with {len(fighters)} fighters")
            
            self.logger.debug(f"[SETUP] Calling screen.load_data with {len(brackets_dict)} brackets")
            screen.load_data(brackets_dict)
            
            self.logger.debug("Wired GenerationMethodScreen callbacks and loaded data")
        
        elif screen_key == 'bracket_viewer':
            # TableAndBracketViewer - prepare data
            from backend.services.bracket_service import make_bracket
            regenerate_stale_ko_brackets(
                self.brackets, self.bracket_generation_methods, make_bracket)
            
            # Wait for database service to be ready before creating fights
            if self.wait_for_db_service():
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
                
                self.logger.debug(f"Set up BracketViewer with {processed} brackets")
            
            self.geometry('1200x750')
        
        elif screen_key == 'fight_monitoring':
            # FightMonitoringScreen callbacks and data preparation
            screen.on_back = lambda: self.screen_manager.navigate_to('bracket_viewer')
            
            from backend.services.bracket_service import make_bracket
            regenerate_stale_ko_brackets(
                self.brackets, self.bracket_generation_methods, make_bracket)
            
            # Wait for database service to be ready before creating fights
            if self.wait_for_db_service():
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
                
                self.logger.debug(f"Wired FightMonitoringScreen with {processed} brackets")
            
            # Initialize the display by showing matten view
            screen.show_matten_view()
            
            self.geometry('1200x750')

    def show_group_preview_window(self):
        """Navigate to group preview screen."""
        self.screen_manager.navigate_to('group_preview')

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

        # Mark downstream screens as stale (BracketViewer and FightMonitoring need to refresh)
        self.screen_manager.invalidate_downstream('generation_method')

        # Proceed to bracket viewer using new navigation system
        self.screen_manager.navigate_to('bracket_viewer')

    def _flush_database(self):
        """Handle Flush Database button — wipe all tournament data."""
        success = self.db_service.flush_database()
        if success:
            self.brackets = {}
            self.match_results = {}
            self.loser_match_results = {}
            self.locked_age_classes = set()
            self.logger.info("Database flushed successfully")
        else:
            self.logger.error("Failed to flush database")

    def load_and_generate(self):
        """Load participants from XLSX file and generate brackets (wrapper to DataLoaderService)."""
        self.data_loader.load_and_generate(callbacks={
            'on_success': self._on_brackets_loaded
        })

    def _on_brackets_loaded(self, brackets=None, rejected_participants=None, load_mode='fresh', 
                            duplicates_skipped=0, db_available=True, 
                            bracket_generation_methods=None, bracket_table_assignment=None,
                            locked_age_classes=None):
        """Callback when brackets are successfully loaded (called from background thread).

        Args:
            brackets: Dict of generated brackets (already merged if append mode)
            rejected_participants: List of rejected participant dicts with rejection reasons
            load_mode: 'fresh' (replace) or 'append' (merge happened in loader)
            duplicates_skipped: Number of duplicate participants filtered out (append mode)
            db_available: True if DB save succeeded, False if offline
            bracket_generation_methods: Dict of {bracket_key: method_name} loaded from DB (or None to reset)
            bracket_table_assignment: Dict of {bracket_key: mat_id} loaded from DB (or None to reset)
            locked_age_classes: Set of age-class locks loaded from DB or preserved from cache
        """
        # The brackets are already merged (if append mode) by the loader
        if brackets:
            self.brackets = brackets

        if locked_age_classes is not None:
            self.locked_age_classes = set(locked_age_classes)
            self.logger.debug(f"Reloaded {len(self.locked_age_classes)} age-class lock(s)")

        # Reload bracket metadata from DB if provided; otherwise reset to start fresh
        if bracket_generation_methods is not None:
            self.bracket_generation_methods = bracket_generation_methods
            self.logger.debug(f"Reloaded {len(bracket_generation_methods)} bracket generation methods from database")
        elif load_mode == 'append':
            self.bracket_generation_methods = {
                key: value for key, value in self.bracket_generation_methods.items()
                if key in self.brackets
            }
            self.logger.debug("Preserved generation methods for append import")
        else:
            # Reset generation methods when reloading from DB (regenerated brackets need re-assignment)
            self.bracket_generation_methods = {}
            self.logger.debug("Reset bracket generation methods (will need re-assignment)")
        
        if bracket_table_assignment is not None:
            self.bracket_table_assignment = bracket_table_assignment
            self.logger.debug(f"Reloaded {len(bracket_table_assignment)} bracket table assignments from database")
        elif load_mode == 'append':
            self.bracket_table_assignment = {
                key: value for key, value in self.bracket_table_assignment.items()
                if key in self.brackets
            }
            self.logger.debug("Preserved table assignments for append import")
        else:
            # Reset table assignments when reloading from DB (need re-assignment to new brackets)
            self.bracket_table_assignment = {}
            self.logger.debug("Reset bracket table assignments (will need re-assignment)")

        # Mark downstream screens as stale (they need to refresh with new data)
        self.screen_manager.invalidate_downstream('file_loader')

        # Log load mode and status
        if load_mode == 'append':
            self.logger.info(
                f"[LOAD] Append mode complete: {duplicates_skipped} duplicates skipped, "
                f"DB {'available' if db_available else 'offline'}"
            )
        else:
            self.logger.info(f"[LOAD] Fresh import complete, DB {'available' if db_available else 'offline'}")

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
        try:
            self.logger.debug("[JSON] load_json_and_generate called")
            
            # Select 2 JSON files
            self.logger.debug("[JSON] Opening file dialog...")
            filepaths = select_json_files()
            self.logger.debug(f"[JSON] File dialog result: {len(filepaths)} files selected")

            if not filepaths:
                self.logger.debug("[JSON] No files selected, returning")
                return

            if len(filepaths) != 2:
                self.logger.debug(f"[JSON] Wrong number of files: {len(filepaths)}, need 2")
                messagebox.showerror("Invalid Selection",
                                   f"Please select exactly 2 JSON files.\nYou selected {len(filepaths)} file(s).")
                return

            # Delegate to DataLoaderService with current cache state for smart append
            self.logger.debug(f"[JSON] Calling data_loader.load_json_and_generate with {len(filepaths)} files")
            self.data_loader.load_json_and_generate(
                filepaths=filepaths,
                callbacks={
                    'on_success': self._on_brackets_loaded
                },
                existing_brackets=self.brackets if self.brackets else None,
                locked_age_classes=self.locked_age_classes,
            )
            self.logger.debug("[JSON] load_json_and_generate delegated to data_loader")
        except Exception as e:
            self.logger.error(f"[JSON] FATAL ERROR in load_json_and_generate: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load JSON:\n{str(e)}")

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
        self.logger.info("Application closing, shutting down...")
        
        # Let screen manager handle screen cleanup
        self.screen_manager.close_app()
        
        # Shutdown task runner
        self.task_runner.shutdown(wait=False)  # Don't block UI, let tasks finish in background
        self.logger.close()  # Close file handlers for proper cleanup
        self.destroy()

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
