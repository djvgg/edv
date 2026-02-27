# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Extracted GUI code from bracket_viewer.py

import datetime
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
    get_age_group,
)
from backend.services.database_service import get_database_service  # noqa: E402

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
    build_bracket_rounds,
    draw_bracket_on_canvas,
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

        # Initialize database service (handles all DB operations)
        self.db_service = get_database_service()

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
        preview_screen.on_resort = self.resort_brackets

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
            Tuple of (paid_participants, unpaid_list) where unpaid_list contains full
            participant dicts with 'rejection_reason' field added
        """
        paid_participants = []
        unpaid_participants = []
        
        for p in all_participants:
            # Check if paid field exists and is truthy
            is_paid = p.get('Paid', False)
            
            if is_paid:
                paid_participants.append(p)
            else:
                # Add full participant data with rejection reason
                unpaid_entry = dict(p)
                unpaid_entry['rejection_reason'] = 'unpaid'
                unpaid_participants.append(unpaid_entry)
        
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

    def filter_invalid_ages(self, all_participants, min_age=6, max_age=120):
        """Filter out participants with invalid ages and show popups for each rejection reason.
        
        Args:
            all_participants: List of participant dicts with 'Age' or birthyear fields
            min_age: Minimum valid age (configurable, default 6)
            max_age: Maximum valid age (configurable, default 120)
        
        Returns:
            Tuple of (valid_participants, invalid_list) where invalid_list contains dicts 
            with name, age, and rejection reason
        """
        import datetime
        
        valid_participants = []
        invalid_participants = []
        current_year = datetime.datetime.now().year
        
        for p in all_participants:
            name = p.get('Name', 'Unknown')
            age = None
            
            # Get age value from 'Age' field
            age_value = p.get('Age')
            
            try:
                if age_value is not None:
                    age_value = int(age_value)
                    # Age field contains birthyear, convert to actual age
                    age = current_year - age_value
            except (ValueError, TypeError):
                pass
            
            # Fall back to Birthyear field if Age didn't work
            if age is None and 'Birthyear' in p:
                try:
                    birthyear = int(p.get('Birthyear'))
                    age = current_year - birthyear
                except (ValueError, TypeError):
                    pass
            
            # Rejection reasons
            rejection_reason = None
            
            if age is None:
                rejection_reason = "missing birth year/age"
            elif age < min_age:
                rejection_reason = f"too young ({age} years, minimum {min_age})"
            elif age > max_age:
                rejection_reason = f"too old ({age} years, maximum {max_age})"
            else:
                # Check if age maps to a valid age group
                try:
                    age_group = get_age_group(age)
                    if age_group is None:
                        rejection_reason = f"no valid age group for age {age}"
                except Exception as e:
                    rejection_reason = f"age validation error: {e}"
            
            if rejection_reason:
                # Include full participant data + rejection reason
                invalid_entry = dict(p)  # Copy original participant
                invalid_entry['rejection_reason'] = rejection_reason
                invalid_entry['calculated_age'] = age
                invalid_participants.append(invalid_entry)
            else:
                valid_participants.append(p)
        
        # Show popup if there are invalid ages
        if invalid_participants:
            invalid_text = "\n".join(
                f"• {p.get('Name', 'Unknown')} (age {p.get('calculated_age', '?')}) — {p.get('rejection_reason', 'unknown')}"
                for p in invalid_participants
            )
            
            message = f"The following {len(invalid_participants)} participant(s) have invalid ages and will NOT be sorted into brackets:\n\n{invalid_text}"
            
            messagebox.showwarning("Invalid Ages", message)
            self.logger.info(f"Filtered out {len(invalid_participants)} participant(s) with invalid ages:\n{invalid_text}")
        
        return valid_participants, invalid_participants

    def _log_bracket_summary(self):
        """Log a detailed summary of generated brackets."""
        if not self.brackets:
            self.logger.info("No brackets generated")
            return
        
        summary_parts = []
        total_fighters = 0
        quarantine_count = 0
        
        for bracket_key, bracket_data in sorted(self.brackets.items()):
            fighter_count = len(bracket_data.get('fighters', []))
            total_fighters += fighter_count
            
            if bracket_key == 'QUARANTINE':
                quarantine_count = fighter_count
                summary_parts.append(f"  [QUARANTINE] {fighter_count} rejected participants")
            else:
                summary_parts.append(f"  {bracket_key}: {fighter_count} fighters")
        
        summary_text = "\n".join(summary_parts)
        self.logger.info(f"Bracket generation summary ({len(self.brackets)} brackets, {total_fighters} total fighters):\n{summary_text}")
        if quarantine_count > 0:
            self.logger.warning(f"⚠️  {quarantine_count} participant(s) in QUARANTINE for manual review")

    def _create_quarantine_bracket(self, invalid_participants):
        """Create a QUARANTINE bracket with all rejected participants for manual review.
        
        Args:
            invalid_participants: List of full participant dicts with 'rejection_reason' and 'calculated_age' added
        
        Returns:
            List of fighter dicts (participant format)
        """
        if not invalid_participants:
            return []
        
        # Convert invalid participant dicts to fighter format
        fighters = []
        for i, invalid_p in enumerate(invalid_participants, 1):
            # Copy all original fields from the participant
            fighter = dict(invalid_p)
            
            # Add rejection tracking fields
            fighter['ID'] = invalid_p.get('ID', f"QUARANTINE_{i}")
            fighter['RejectionReason'] = invalid_p.get('rejection_reason', 'Unknown reason')
            
            # Ensure Age field contains the original age/birthyear value
            # (calculated_age is the computed age, Age is the original field)
            if 'Age' not in fighter or fighter.get('Age') is None:
                # If Age is missing, try Birthyear
                if 'Birthyear' in invalid_p:
                    fighter['Age'] = invalid_p['Birthyear']
            
            fighters.append(fighter)
        
        # Create quarantine bracket entry
        if 'QUARANTINE' not in self.brackets:
            self.brackets['QUARANTINE'] = {
                'fighters': fighters,
                'bracket': [],  # No bracket structure; people manually reviewed here
                'pool_size': None,
                'is_quarantine': True,  # Flag to identify as quarantine
            }
        else:
            # Append to existing quarantine if it exists
            self.brackets['QUARANTINE']['fighters'].extend(fighters)
        
        self.logger.info(f"Created QUARANTINE bracket with {len(fighters)} rejected participant(s)")
        return fighters

    def resort_brackets(self, edited_fighter=None):
        """Re-sort brackets after changes in QUARANTINE.
        
        Args:
            edited_fighter: Optional dict of the fighter that was just edited.
                          If provided, only that fighter is checked for re-sorting.
                          If None, all QUARANTINE fighters are checked.
        
        This method:
        1. Extracts valid participants from QUARANTINE
        2. Removes them from QUARANTINE
        3. Re-generates brackets with all valid participants
        4. Updates the group preview display
        """
        self.logger.debug("RESORT: resort_brackets() called")
        
        if 'QUARANTINE' not in self.brackets:
            self.logger.debug("RESORT: QUARANTINE bracket not found in self.brackets, returning early")
            return
        
        quarantine_fighters = self.brackets['QUARANTINE'].get('fighters', [])
        self.logger.debug(f"RESORT: Found {len(quarantine_fighters)} fighters in QUARANTINE")
        
        if not quarantine_fighters:
            self.logger.debug("RESORT: QUARANTINE bracket is empty, returning early")
            return
        
        # If a specific fighter was edited, only check that one
        if edited_fighter is not None:
            fighters_to_check = [edited_fighter]
            self.logger.debug(f"RESORT: Checking only the edited fighter: {edited_fighter.get('Name', 'Unknown')}")
        else:
            fighters_to_check = quarantine_fighters
            self.logger.debug(f"RESORT: Checking all {len(quarantine_fighters)} fighters in QUARANTINE")
        
        # Separate valid and still-invalid participants
        valid_from_quarantine = []
        still_invalid = []
        
        current_year = datetime.datetime.now().year
        for fighter in fighters_to_check:
            fighter_name = fighter.get('Name', f"Unknown ({fighter.get('ID', '?')})")
            is_valid = True
            invalid_reason = None
            
            # Check paid status
            if not fighter.get('Paid', False):
                is_valid = False
                invalid_reason = "unpaid"
            else:
                # Check age validity
                age = None
                age_value = fighter.get('Age')
                try:
                    if age_value is not None:
                        age_value = int(age_value)
                        age = current_year - age_value
                except (ValueError, TypeError):
                    pass
                
                if age is None and 'Birthyear' in fighter:
                    try:
                        birthyear = int(fighter.get('Birthyear'))
                        age = current_year - birthyear
                    except (ValueError, TypeError):
                        pass
                
                # Check age bounds
                if age is None:
                    is_valid = False
                    invalid_reason = "no age/birthyear"
                elif age < 6:
                    is_valid = False
                    invalid_reason = f"too young ({age} years)"
                elif age > 120:
                    is_valid = False
                    invalid_reason = f"too old ({age} years)"
                else:
                    # Check age group mapping
                    try:
                        age_group = get_age_group(age)
                        if age_group is None:
                            is_valid = False
                            invalid_reason = f"no age group for age {age}"
                    except Exception as e:
                        is_valid = False
                        invalid_reason = f"age validation error: {e}"
            
            if is_valid:
                valid_from_quarantine.append(fighter)
                self.logger.debug(f"RESORT: {fighter_name} now valid (fixed)")
            else:
                still_invalid.append(fighter)
                self.logger.debug(f"RESORT: {fighter_name} remains invalid ({invalid_reason})")
        
        # If we only checked the edited fighter, we need to keep the OTHER quarantine fighters unchanged
        if edited_fighter is not None:
            # Add back all the quarantine fighters that weren't checked
            other_quarantine = [f for f in quarantine_fighters if f.get('ID') != edited_fighter.get('ID')]
            still_invalid.extend(other_quarantine)
            self.logger.debug(f"RESORT: Keeping {len(other_quarantine)} other quarantine fighters unchanged")
        
        # Update QUARANTINE with only still-invalid fighters
        if still_invalid:
            self.brackets['QUARANTINE']['fighters'] = still_invalid
            self.logger.info(f"Re-sorted from QUARANTINE: {len(valid_from_quarantine)} now valid, {len(still_invalid)} remain invalid")
        else:
            # Remove QUARANTINE if empty
            del self.brackets['QUARANTINE']
            self.logger.info(f"Re-sorted all {len(valid_from_quarantine)} from QUARANTINE - now valid")
        
        # Re-generate brackets with valid participants
        if valid_from_quarantine:
            # Save current brackets (excluding QUARANTINE)
            temp_brackets = {k: v for k, v in self.brackets.items() if k != 'QUARANTINE'}
            
            # Re-generate with valid fighters added
            self.brackets = export_all_brackets(valid_from_quarantine)
            
            # Merge back the manually-assigned brackets
            for key, bracket_data in temp_brackets.items():
                if key not in self.brackets:
                    self.brackets[key] = bracket_data
            
            # Log where each fighter was placed
            for fighter in valid_from_quarantine:
                fighter_id = fighter.get('ID')
                fighter_name = fighter.get('Name', f"Unknown ({fighter_id})")
                
                # Find which bracket contains this fighter
                new_bracket_key = None
                for bracket_key, bracket_data in self.brackets.items():
                    if bracket_key == 'QUARANTINE':
                        continue
                    fighters = bracket_data.get('fighters', [])
                    for f in fighters:
                        if f.get('ID') == fighter_id:
                            new_bracket_key = bracket_key
                            break
                    if new_bracket_key:
                        break
                
                if new_bracket_key:
                    self.logger.debug(f"RESORT: {fighter_name} → new bracket: {new_bracket_key}")
                else:
                    self.logger.warning(f"RESORT: {fighter_name} could not find assigned bracket after re-sort")
            
            self._log_bracket_summary()
            
            # Re-add QUARANTINE if there are still-invalid
            if still_invalid:
                self.brackets['QUARANTINE'] = {
                    'fighters': still_invalid,
                    'bracket': [],
                    'pool_size': None,
                    'is_quarantine': True,
                }
        
        # Refresh the group preview display
        if hasattr(self, 'group_preview_screen') and self.group_preview_screen.winfo_exists():
            self.group_preview_screen.load_data(self.brackets)
            self.logger.info("Group preview refreshed after resort")
        else:
            self.logger.debug("RESORT: No group_preview_screen to refresh")
        
        self.logger.debug("RESORT: resort_brackets() completed")

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
        self.db_service.save_groups_and_brackets(self.brackets, final_assignments)

        # Proceed to bracket viewer
        self.show_bracket_viewer()

    def show_fight_monitoring_screen(self):
        """Switch to the Fight Monitoring screen (in-app, no separate window)."""
        # Create fight rows in DB for every assigned bracket (idempotent — skips if already created)
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num and bracket_key in self.brackets:
                fight_pairs = self.brackets[bracket_key].get('bracket', [])
                self.db_service.create_fights_for_bracket(bracket_key, fight_pairs)

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
        """Show bracket visualization view or group preview for QUARANTINE."""
        # For QUARANTINE bracket, open group preview for editing
        if bracket_key == 'QUARANTINE':
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
        self.db_service.assign_bracket_to_table(bracket_key, table_num)
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
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num:
                self.db_service.assign_bracket_to_table(bracket_key, table_num)

        self.update_bracket_list()
        self.update_table_panels()

    def update_table_panels(self):
        """Update the visual display of table assignments."""
        # Clear all panels
        for panel in self.table_panels.values():
            for widget in panel.winfo_children():
                widget.destroy()

        # Track totals for each table (fighters and fights)
        table_totals = {}  # {table_num: {'fighters': count, 'fights': count}}

        # Add assigned brackets to panels — skip empty brackets
        for bracket_key, table_num in self.bracket_table_assignment.items():
            if table_num and len(self.brackets[bracket_key].get('fighters', [])) > 0:
                panel = self.table_panels[table_num]

                # Create row frame for label + unassign button
                row_frame = create_dark_frame(panel)
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

        # Add totals footer to each table
        for table_num, panel in self.table_panels.items():
            fighter_total = table_totals.get(table_num, {}).get('fighters', 0)
            fight_total = table_totals.get(table_num, {}).get('fights', 0)
            
            # Add separator
            separator = tk.Frame(panel, height=1, bg=COLORS['border'])
            separator.pack(fill=tk.X, pady=4, padx=4)
            
            # Add total label with both fighters and fights
            total_frame = create_dark_frame(panel)
            total_frame.pack(fill=tk.X, pady=2, padx=4)
            
            total_text = f"Table Total: {fighter_total} players • {fight_total} matches"
            total_label = tk.Label(total_frame, text=total_text,
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
            self.db_service.save_participants(participants)

            # Filter out unpaid participants
            participants, unpaid = self.filter_unpaid_participants(participants)

            # Filter out participants with invalid ages
            participants, invalid_ages = self.filter_invalid_ages(participants)
            
            # Create QUARANTINE bracket with all rejected participants (unpaid + invalid ages)
            all_rejected = unpaid + invalid_ages
            if all_rejected:
                self._create_quarantine_bracket(all_rejected)

            if not participants:
                self.set_status("Error: No valid participants found.", COLORS['accent_red'])
                self.hide_loading_progress()
                return

            total_fighters = len(participants)
            self.set_info_text(f"✓ {total_fighters} participants loaded")
            self.update_progress(50)

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Save QUARANTINE bracket if it exists (it gets overwritten by export_all_brackets)
            quarantine_bracket = self.brackets.pop('QUARANTINE', None)
            
            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)
            self.update_progress(80)
            
            # Restore QUARANTINE bracket if it existed
            if quarantine_bracket is not None:
                self.brackets['QUARANTINE'] = quarantine_bracket
            
            # Log bracket generation summary
            self._log_bracket_summary()

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
            participants, unpaid = self.filter_unpaid_participants(participants)

            # Filter out participants with invalid ages
            participants, invalid_ages = self.filter_invalid_ages(participants)
            
            # Create QUARANTINE bracket with all rejected participants (unpaid + invalid ages)
            all_rejected = unpaid + invalid_ages
            if all_rejected:
                self._create_quarantine_bracket(all_rejected)

            if not participants:
                self.set_status("Error: No valid participants found in database.", COLORS['accent_red'])
                self.hide_loading_progress()
                self.after(500, lambda: messagebox.showwarning("No Data", "No valid participants found in database."))
                return

            total_fighters = len(participants)
            self.set_info_text(f"✓ {total_fighters} participants loaded from database")
            self.update_progress(50)

            self.set_status("Generating brackets...", COLORS['text_secondary'])

            # Save QUARANTINE bracket if it exists (it gets overwritten by export_all_brackets)
            quarantine_bracket = self.brackets.pop('QUARANTINE', None)
            
            # Generate brackets using backend service
            self.brackets = export_all_brackets(participants)
            self.update_progress(80)
            
            # Restore QUARANTINE bracket if it existed
            if quarantine_bracket is not None:
                self.brackets['QUARANTINE'] = quarantine_bracket
            
            # Log bracket generation summary
            self._log_bracket_summary()

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

        # Show loading progress dialog
        self.show_loading_progress("Loading and generating brackets from JSON...")
        
        # Run loading in background thread
        thread = threading.Thread(target=self._load_json_and_generate_thread, args=(filepaths,), daemon=True)
        thread.start()

    def _load_json_and_generate_thread(self, filepaths):
        """Background thread for loading JSON files and generating brackets."""
        try:
            self.set_status("Reading JSON files...", COLORS['text_secondary'])
            self.update_progress(10)
            self.logger.info(f"Loading {len(filepaths)} JSON files")

            all_participants = []
            
            # Define expected fields
            required_core_fields = ['Firstname', 'Lastname', 'Birthyear', 'Weight', 'Gender']

            # Load both JSON files
            for file_idx, filepath in enumerate(filepaths, 1):
                filename = os.path.basename(filepath)
                self.logger.info(f"[File {file_idx}] Loading: {filename}")
                
                # Update progress (20% for first file, 50% for second file)
                progress = 20 + (file_idx - 1) * 30
                self.update_progress(progress)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate that data is a list
                if not isinstance(data, list):
                    error_msg = f"File must contain a JSON array.\nFile: {filename}\nGot: {type(data).__name__}"
                    self.logger.error(error_msg)
                    self.hide_loading_progress()
                    self.set_status(error_msg, COLORS['accent_red'])
                    self.after(500, lambda msg=error_msg: messagebox.showerror("Invalid JSON Format", msg))
                    return

                self.logger.debug(f"[File {file_idx}] Found {len(data)} entries")
                
                valid_count = 0

                # Validate each participant
                for idx, participant in enumerate(data, 1):
                    if not isinstance(participant, dict):
                        error_msg = f"Participant {idx} is not a valid object (got {type(participant).__name__}).\nFile: {filename}"
                        self.logger.error(error_msg)
                        self.hide_loading_progress()
                        self.set_status(error_msg, COLORS['accent_red'])
                        self.after(500, lambda msg=error_msg: messagebox.showerror("Invalid Participant", msg))
                        return

                    # Check for required core fields
                    missing_fields = [field for field in required_core_fields if field not in participant]

                    if missing_fields:
                        error_msg = f"Participant {idx} is missing required fields: {', '.join(missing_fields)}\nFile: {filename}"
                        self.logger.error(error_msg)
                        self.hide_loading_progress()
                        self.set_status(error_msg, COLORS['accent_red'])
                        self.after(500, lambda msg=error_msg: messagebox.showerror("Missing Required Fields", msg))
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
                        self.hide_loading_progress()
                        self.set_status(error_msg, COLORS['accent_red'])
                        self.after(500, lambda msg=error_msg: messagebox.showerror("Validation Error", msg))
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

            self.update_progress(60)

            if not all_participants:
                error_msg = "No valid participants found in JSON files."
                self.logger.error(error_msg)
                self.hide_loading_progress()
                self.set_status(error_msg, COLORS['accent_red'])
                return

            self.set_status("Filtering participants...", COLORS['text_secondary'])
            self.update_progress(65)

            # Filter out unpaid participants
            all_participants, unpaid = self.filter_unpaid_participants(all_participants)

            self.update_progress(70)

            # Filter out participants with invalid ages
            all_participants, invalid_ages = self.filter_invalid_ages(all_participants)
            
            self.update_progress(75)

            # Create QUARANTINE bracket with all rejected participants (unpaid + invalid ages)
            all_rejected = unpaid + invalid_ages
            if all_rejected:
                self._create_quarantine_bracket(all_rejected)

            if not all_participants:
                error_msg = "No valid participants found in JSON files."
                self.logger.error(error_msg)
                self.hide_loading_progress()
                self.set_status(error_msg, COLORS['accent_red'])
                return

            total_fighters = len(all_participants)
            self.logger.info(f"Total valid participants loaded: {total_fighters}")
            self.set_info_text(f"✓ {total_fighters} valid participants loaded from JSON files")

            self.set_status("Generating brackets...", COLORS['text_secondary'])
            self.update_progress(85)
            self.logger.info("Starting bracket generation...")

            # Save QUARANTINE bracket if it exists (it gets overwritten by export_all_brackets)
            quarantine_bracket = self.brackets.pop('QUARANTINE', None)
            
            # Generate brackets using backend service
            self.brackets = export_all_brackets(all_participants)
            self.update_progress(95)
            
            # Restore QUARANTINE bracket if it existed
            if quarantine_bracket is not None:
                self.brackets['QUARANTINE'] = quarantine_bracket
            
            # Log bracket generation summary
            self._log_bracket_summary()

            self.set_status(f"Success! Generated {len(self.brackets)} brackets from JSON files.", COLORS['accent_green'])
            self.update_progress(100)

            # Hide progress and show group preview window
            self.hide_loading_progress()
            self.after(500, self.show_group_preview_window)

        except json.JSONDecodeError as e:
            error_msg = f"JSON Parse Error: {e}"
            self.logger.error(error_msg)
            self.set_status(error_msg, COLORS['accent_red'])
            self.hide_loading_progress()
            self.after(500, lambda err=e: messagebox.showerror("JSON Error", f"Failed to parse JSON file:\n{str(err)}"))
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self.logger.error(error_msg)
            self.set_status(error_msg, COLORS['accent_red'])
            self.hide_loading_progress()
            self.after(500, lambda err=e: messagebox.showerror("File Error", f"Could not find file:\n{str(err)}"))
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.logger.exception(error_msg)
            self.set_status(error_msg, COLORS['accent_red'])
            self.hide_loading_progress()
            self.after(500, lambda err=e: messagebox.showerror("Error", f"Failed to load JSON files:\n{str(err)}"))

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
        
        # Get unassigned bracket keys — skip empty brackets (fighters moved to another group)
        unassigned_keys = [k for k in sorted(self.brackets.keys())
                           if not self.bracket_table_assignment.get(k)
                           and len(self.brackets[k].get('fighters', [])) > 0]
        
        # Move QUARANTINE to front if it exists
        if 'QUARANTINE' in unassigned_keys:
            unassigned_keys.remove('QUARANTINE')
            unassigned_keys.insert(0, 'QUARANTINE')
        
        # Use shared search utility
        filtered_keys, matched_count, search_terms = filter_items(unassigned_keys, search_term)
        
        if search_terms:
            self.logger.debug(f"Bracket search: {search_terms}, found {matched_count} brackets")
        
        # Calculate total unassigned participants
        total_unassigned = 0

        # Display filtered brackets
        for bracket_key in filtered_keys:
            fighter_count = len(self.brackets[bracket_key].get('fighters', []))
            
            # For QUARANTINE bracket, show rejection count instead of fight count
            is_quarantine = self.brackets[bracket_key].get('is_quarantine', False)
            if is_quarantine:
                display_text = f"[⚠️ QUARANTINE] • {fighter_count} rejected"
            else:
                fight_count = self.calculate_number_of_fights(bracket_key)
                display_text = f"{bracket_key} • {fighter_count} / {fight_count}"
            
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

            # Update scroll region based on bracket size and zoom level
            max_x = max(pos[0] for pos in positions.values()) + box_width + start_x
            max_y = max(pos[1] for pos in positions.values()) + box_height + start_y
            self.bracket_canvas.configure(scrollregion=(0, 0, max_x, max_y))

            self.logger.debug(f"Successfully rendered bracket with {len(rounds_with_clubs)} rounds and club info at {int(self.zoom_level*100)}% zoom")

        except Exception as e:
            self.logger.error(f"Exception rendering bracket: {e}")
            traceback.print_exc()
            # Show error on canvas
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering bracket:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

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
        except:
            pass


if __name__ == '__main__':
    main()
