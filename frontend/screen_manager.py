# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Screen Manager - Centralized navigation controller

Manages screen transitions, state, lifecycle hooks, and navigation bar updates.
"""

import tkinter as tk
from tkinter import messagebox
import sys
import os

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402

# Debug flag
DEBUG = True
logger = get_logger('screen_manager', debug_verbose=DEBUG)


class ScreenManager:
    """
    Manages screen transitions, state, and navigation.
    
    Responsibilities:
    - Maintain screen registry and history
    - Execute lifecycle hooks (on_show, on_hide, can_navigate_from, can_navigate_to)
    - Update navigation bar
    - Track screen state and staleness
    - Handle screen transitions with validation
    """
    
    def __init__(self, main_window, nav_bar, data_pipeline=None):
        """
        Initialize ScreenManager.
        
        Args:
            main_window: The main application window (BracketViewerApp)
            nav_bar: The NavigationBar component
            data_pipeline: Optional DataTransformationPipeline instance.
                          If None, will be created later or not used.
        """
        self.main_window = main_window
        self.nav_bar = nav_bar
        self.data_pipeline = data_pipeline
        self.logger = logger
        
        # Screen management
        self.screen_registry = {}  # {screen_key: {'class': ScreenClass, 'label': str, 'locked': bool}}
        self.current_screen_key = None  # Currently active screen
        self.screen_instances = {}  # {screen_key: screen_instance}
        self.screen_state = {}  # {screen_key: state_dict}
        self.screen_staleness = {}  # {screen_key: is_stale}
        self.screen_history = []  # Stack of visited screen keys
        
        # Screen dependency graph (for staleness propagation)
        # {screen_key: [downstream_screen_keys]}
        self.screen_dependencies = {
            'file_loader': ['group_preview', 'generation_method', 'bracket_viewer', 'fight_monitoring'],
            'group_preview': ['generation_method', 'bracket_viewer', 'fight_monitoring'],
            'generation_method': ['bracket_viewer', 'fight_monitoring'],
            'bracket_viewer': ['fight_monitoring'],
            'fight_monitoring': [],
        }
        
        # Wire NavigationBar tab clicks to navigation
        self.nav_bar.on_tab_click = self.navigate_to
        
        self.logger.debug("ScreenManager initialized")
    
    def set_data_pipeline(self, data_pipeline):
        """
        Set the data transformation pipeline.
        Called by main_window after pipeline is created.
        
        Args:
            data_pipeline: DataTransformationPipeline instance
        """
        self.data_pipeline = data_pipeline
        self.logger.debug("DataTransformationPipeline attached to ScreenManager")
    
    
    def register_screen(self, screen_key, screen_class, label, locked=False, screen_factory=None):
        """
        Register a screen that can be navigated to.
        
        Args:
            screen_key: Unique identifier (e.g., 'file_loader')
            screen_class: The screen class (subclass of tk.Frame) or None if using screen_factory
            label: Display label for the tab
            locked: Whether screen starts locked
            screen_factory: Optional factory function(main_window) -> screen_instance
                           If provided, used instead of screen_class(main_window)
        """
        self.screen_registry[screen_key] = {
            'class': screen_class,
            'factory': screen_factory,
            'label': label,
            'locked': locked,
        }
        self.screen_staleness[screen_key] = False
        self.logger.info(f"Registered screen: {screen_key} ({label})")
    
    def navigate_to(self, screen_key, **kwargs) -> bool:
        """
        Navigate to a screen.
        
        Steps:
        1. Validate screen exists
        2. Check data prerequisites (delegate to main_window if needed)
        3. Call current_screen.can_navigate_from() if exists
        4. Call new_screen.can_navigate_to()
        5. Call current_screen.on_hide() if exists
        6. Restore or create new_screen
        7. Call new_screen.on_show()
        8. Update nav bar
        9. Mark screen as not stale
        
        Returns:
            True if navigation succeeded, False if blocked
        """
        # Validate screen exists
        if screen_key not in self.screen_registry:
            self.logger.error(f"Cannot navigate to unregistered screen: {screen_key}")
            return False
        
        # Check data prerequisites before creating screen
        if hasattr(self.main_window, 'check_screen_prerequisites'):
            if not self.main_window.check_screen_prerequisites(screen_key):
                self.logger.info(f"Navigation to {screen_key} blocked due to missing prerequisites")
                return False
        
        # Get current screen if exists
        current_screen = None
        if self.current_screen_key:
            current_screen = self.screen_instances.get(self.current_screen_key)
        
        # Check if current screen allows navigation away
        if current_screen and hasattr(current_screen, 'can_navigate_from'):
            try:
                if not current_screen.can_navigate_from():
                    self.logger.warning(f"Navigation blocked: {self.current_screen_key} does not allow navigate_from")
                    return False
            except Exception as e:
                self.logger.error(f"Error in can_navigate_from(): {e}")
                return False
        
        # Create or get target screen
        if screen_key not in self.screen_instances:
            try:
                # Get the parent frame (content_frame if available, otherwise main_window)
                parent_frame = getattr(self.main_window, 'content_frame', self.main_window)
                
                # Use factory function if provided, otherwise use screen_class
                factory = self.screen_registry[screen_key].get('factory')
                if factory:
                    # Factories are responsible for creating with correct parent
                    # For now, they still take main_window but will need updating
                    new_screen = factory(self.main_window)
                    self.logger.debug(f"Created new screen instance using factory: {screen_key}")
                else:
                    screen_class = self.screen_registry[screen_key]['class']
                    # Create screen as child of content_frame, not main_window
                    new_screen = screen_class(parent_frame)
                    self.logger.debug(f"Created new screen instance: {screen_key} (parent: content_frame)")
                
                self.screen_instances[screen_key] = new_screen
                
                # Set up screen callbacks (hook for main_window to configure)
                if hasattr(self.main_window, 'setup_screen_callbacks'):
                    self.main_window.setup_screen_callbacks(screen_key, new_screen)
                    self.logger.debug(f"Set up callbacks for screen: {screen_key}")
                
            except Exception as e:
                self.logger.error(f"Failed to create screen {screen_key}: {e}")
                messagebox.showerror("Error", f"Failed to create screen {screen_key}: {e}")
                return False
        else:
            new_screen = self.screen_instances[screen_key]
            self.logger.debug(f"Reusing existing screen instance: {screen_key}")
        
        # Check if new screen allows navigation to it
        if hasattr(new_screen, 'can_navigate_to'):
            try:
                if not new_screen.can_navigate_to():
                    self.logger.warning(f"Navigation blocked: {screen_key} does not allow navigate_to")
                    return False
            except Exception as e:
                self.logger.error(f"Error in can_navigate_to(): {e}")
                return False
        
        # Call on_hide on current screen
        if current_screen and hasattr(current_screen, 'on_hide'):
            try:
                result = current_screen.on_hide()
                if result is False:
                    self.logger.warning(f"Navigation blocked: {self.current_screen_key}.on_hide() returned False")
                    return False
                self.logger.debug(f"Called on_hide: {self.current_screen_key}")
            except Exception as e:
                self.logger.error(f"Error in on_hide(): {e}")
                return False
        
        # Execute data transformations before showing new screen
        if self.data_pipeline:
            try:
                wait_for_db = getattr(self.main_window, 'wait_for_db_service', None)
                success = self.data_pipeline.transform_before_entering(screen_key, wait_for_db)
                if not success:
                    self.logger.warning(f"Data transformations failed for {screen_key}")
                    # Don't block navigation, just warn - allow screen to handle missing data
            except Exception as e:
                self.logger.error(f"Error in data transformations for {screen_key}: {e}")
                # Don't block navigation for transformation errors
        
        # Hide current screen content (don't destroy it - just unpack)
        if current_screen:
            try:
                current_screen.pack_forget()
                self.logger.debug(f"Unpacked screen: {self.current_screen_key}")
            except Exception as e:
                self.logger.error(f"Error unpacking screen: {e}")

        
        # Show new screen (pack into content_frame)
        try:
            new_screen.pack(fill=tk.BOTH, expand=True)
            self.logger.debug(f"Packed screen: {screen_key}")
        except Exception as e:
            self.logger.error(f"Error packing new screen: {e}")
            return False
        
        # Check if screen was stale (before we mark it clean)
        was_stale = self.screen_staleness.get(screen_key, False)
        
        # Call on_show on new screen - pass staleness info so it can reload if needed
        if hasattr(new_screen, 'on_show'):
            try:
                # Try calling on_show with force_reload parameter (for staleness-aware screens)
                try:
                    new_screen.on_show(force_reload=was_stale)
                    self.logger.debug(f"Called on_show(force_reload={was_stale}): {screen_key}")
                except TypeError:
                    # Screen doesn't accept force_reload parameter, call without it
                    new_screen.on_show()
                    self.logger.debug(f"Called on_show: {screen_key} (was_stale={was_stale} but screen doesn't support force_reload)")
            except Exception as e:
                self.logger.error(f"Error in on_show(): {e}")
        
        # Update tracking
        self.current_screen_key = screen_key
        if screen_key not in self.screen_history:
            self.screen_history.append(screen_key)
        self.screen_staleness[screen_key] = False
        
        # Update nav bar - ensure tab exists before activating
        label = self.screen_registry[screen_key]['label']
        locked = self.screen_registry[screen_key]['locked']
        self.nav_bar.add_tab(screen_key, label, locked=locked)
        self.nav_bar.set_active_tab(screen_key)
        
        self.logger.info(f"Navigation successful: {screen_key}")
        return True
    
    def invalidate_downstream(self, screen_key):
        """
        Mark all downstream screens as stale.
        Called when upstream data changes.
        
        Args:
            screen_key: The upstream screen that changed
        """
        if screen_key not in self.screen_dependencies:
            self.logger.warning(f"Screen not in dependency graph: {screen_key}")
            return
        
        downstream = self.screen_dependencies.get(screen_key, [])
        for ds_key in downstream:
            self.screen_staleness[ds_key] = True
            self.logger.info(f"Marked as stale: {ds_key} (due to change in {screen_key})")
        
        # If currently viewing a stale screen, trigger refresh
        if self.current_screen_key in downstream:
            current_screen = self.screen_instances.get(self.current_screen_key)
            if current_screen and hasattr(current_screen, 'on_show'):
                self.logger.info(f"Refreshing current stale screen: {self.current_screen_key}")
                try:
                    current_screen.on_show()
                except Exception as e:
                    self.logger.error(f"Error refreshing screen: {e}")
    
    def is_screen_stale(self, screen_key) -> bool:
        """
        Check if a screen is marked as stale (needs data refresh).
        
        Args:
            screen_key: The screen to check
            
        Returns:
            True if screen is stale (has out-of-date data), False otherwise
        """
        return self.screen_staleness.get(screen_key, False)
    
    def mark_screen_stale(self, screen_key):
        """
        Mark a screen as stale.
        
        Args:
            screen_key: The screen to mark as stale
        """
        self.screen_staleness[screen_key] = True
        self.logger.debug(f"Marked as stale: {screen_key}")
    
    def mark_screen_clean(self, screen_key):
        """
        Mark a screen as clean (not stale).
        
        Args:
            screen_key: The screen to mark
        """
        self.screen_staleness[screen_key] = False
        self.logger.debug(f"Marked as clean: {screen_key}")
    
    def get_screen_state(self, screen_key) -> dict:
        """
        Get saved state for a screen.
        
        Args:
            screen_key: The screen key
            
        Returns:
            State dictionary
        """
        return self.screen_state.get(screen_key, {})
    
    def save_screen_state(self, screen_key, state):
        """
        Save state for a screen.
        
        Args:
            screen_key: The screen key
            state: State dictionary to save
        """
        self.screen_state[screen_key] = state
        self.logger.debug(f"Saved state for screen: {screen_key}")
    
    def unlock_screen(self, screen_key):
        """
        Unlock a screen (make it accessible).
        
        Args:
            screen_key: The screen to unlock
        """
        if screen_key in self.screen_registry:
            self.screen_registry[screen_key]['locked'] = False
            self.nav_bar.enable_tab(screen_key)
            self.logger.info(f"Unlocked screen: {screen_key}")
    
    def lock_screen(self, screen_key):
        """
        Lock a screen (make it inaccessible).
        
        Args:
            screen_key: The screen to lock
        """
        if screen_key in self.screen_registry:
            self.screen_registry[screen_key]['locked'] = True
            self.nav_bar.disable_tab(screen_key)
            self.logger.info(f"Locked screen: {screen_key}")
    
    def close_app(self):
        """
        Close the application.
        
        Called by main_window.on_closing().
        Ensures all screens are properly cleaned up.
        """
        self.logger.info("Closing application via ScreenManager")
        
        # Call on_hide on current screen for final cleanup
        if self.current_screen_key:
            current_screen = self.screen_instances.get(self.current_screen_key)
            if current_screen and hasattr(current_screen, 'on_hide'):
                try:
                    current_screen.on_hide()
                    self.logger.debug("Called on_hide for cleanup")
                except Exception as e:
                    self.logger.error(f"Error during cleanup: {e}")
        
        # Could add more cleanup here if needed
        self.logger.info("Application closed")
