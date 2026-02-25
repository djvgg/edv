# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Group Preview Screen - Display and preview bracket groups before generation

Shows bracket groups (weight categories) with participant details:
- Left panel: searchable list of groups
- Right panel: detailed participant info for selected group
- Bottom: navigation buttons
"""

import tkinter as tk
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from backend.data.repositories.config_repository import ConfigRepository
from ..styles import (
    COLORS, FONTS,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    create_dark_frame,
)
from ..search_utils import filter_items

# Debug flag - set to True for verbose logging
DEBUG = True

logger = get_logger('group_preview_screen', debug_verbose=DEBUG)


class GroupPreviewScreen(tk.Frame):
    """
    Screen for previewing bracket groups and participants.
    
    Displays:
    - Left: searchable list of weight groups
    - Right: detailed participant list for selected group
    - Bottom: Back and Continue buttons
    """

    # Debug flag - set to True for verbose logging
    DEBUG = DEBUG

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger

        # Initialize config repository for weight classes
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'bracket_config.xlsx')
            self.config_repo = ConfigRepository(config_path)
            self.logger.debug(f"Loaded ConfigRepository from {config_path}")
        except Exception as e:
            self.logger.warning(f"Could not load ConfigRepository: {e}")
            self.config_repo = None

        # Data
        self.brackets = {}  # {bracket_key: bracket_data} - Dictionary of weight classes
        self.group_listbox_map = {}  # Headings of the left sidebar
        self.current_bracket_key = None  # Which group is being edited/selected in the left sidebar

        # UI References
        self.group_listbox = None # left listbox
        self.participant_display_frame = None # right listbox of participants
        self.preview_title_var = None # Title of the right listbox
        self.preview_search_var = None # Search field of the left listbox
        self.preview_count_var = None # Number of participants in the left listbox

        # Callbacks
        self.on_continue = None
        self.on_back = None

        self.init_ui()

    def load_data(self, brackets):
        """Load bracket data."""
        self.brackets = brackets
        self.logger.info(f"Loaded {len(brackets)} brackets for preview")
        if self.DEBUG:
            self.logger.debug(f"DEBUG: Bracket keys: {list(brackets.keys())}")
        self._populate_group_list()

    def init_ui(self):
        """Initialize the user interface."""
        # Main layout with resizable split
        main_frame = create_dark_frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        #Fenster Rahmen / Panel Window
        paned = tk.PanedWindow( 
            main_frame,
            orient=tk.HORIZONTAL,
            bg=COLORS['bg_dark'],
            sashwidth=4,
            sashrelief=tk.FLAT,
            showhandle=False,
        )
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel: Group list
        self._create_group_list_panel(paned)

        # Right panel: Participant preview
        self._create_participant_preview_panel(paned)

        # Bottom navigation buttons
        self._create_navigation_buttons(main_frame)

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

        # Participant counter
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
        self.preview_search_var.trace('w', self._on_search_changed)
        search_entry = tk.Entry(search_frame, textvariable=self.preview_search_var, fg=COLORS['text_muted'])
        search_entry.insert(0, "M, W, age, or kg")
        search_entry.bind('<FocusIn>', lambda e: self._on_search_focus_in(search_entry))
        apply_entry_style(search_entry)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Group listbox
        self.group_listbox = tk.Listbox(left_frame, width=30, height=20)
        apply_listbox_style(self.group_listbox)
        self.group_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.group_listbox.bind('<Double-Button-1>', self._on_group_double_click)

    # draw Participants Window
    def _create_participant_preview_panel(self, parent_paned):
        """Create the right panel for participant preview."""
        right_frame = create_dark_frame(parent_paned)
        parent_paned.add(right_frame, minsize=450)

        # Title
        self.preview_title_var = tk.StringVar(value="Participant Preview")
        title_label = tk.Label(right_frame, textvariable=self.preview_title_var)
        apply_label_style(title_label, 'heading_md')
        title_label.pack(pady=(0, 10))

        # Participant display container
        self.participant_display_frame = create_dark_frame(right_frame)
        self.participant_display_frame.pack(fill=tk.BOTH, expand=True)

        # Placeholder
        placeholder = tk.Label(
            self.participant_display_frame,
            text="Double-click a group to preview participants",
        )
        apply_label_style(placeholder, 'info')
        placeholder.pack(expand=True)

    def _create_navigation_buttons(self, parent_frame):
        """Create bottom navigation buttons."""
        button_frame = create_dark_frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        back_btn = tk.Button(button_frame, text='← Back to File Loader', command=self._on_back)
        apply_button_style(back_btn, 'secondary')
        back_btn.pack(side=tk.LEFT, padx=5)

        merge_btn = tk.Button(button_frame, text='⧉ Friendly Match', command=self._on_friendly_match)
        apply_button_style(merge_btn, 'secondary')
        merge_btn.pack(side=tk.LEFT, padx=5)

        continue_btn = tk.Button(
            button_frame,
            text='Continue to Generation Setup →',
            command=self._on_continue,
        )
        apply_button_style(continue_btn, 'primary')
        continue_btn.pack(side=tk.RIGHT, padx=5)

    # Fill in Weight Classes (m | 18+ | -66kg etc..)
    def _populate_group_list(self):
        """Populate the group list with all non-empty brackets."""
        if not self.group_listbox or not self.group_listbox.winfo_exists():
            return

        self.group_listbox.delete(0, tk.END)
        self.group_listbox_map.clear()

        total_participants = 0
        groups_added = []

        for bracket_key in sorted(self.brackets.keys()):
            fighters = self.brackets[bracket_key].get('fighters', [])
            if fighters:
                count = len(fighters)
                total_participants += count
                groups_added.append(bracket_key)

                display_text = f"{bracket_key} ({count})"
                self.group_listbox.insert(tk.END, display_text)
                self.group_listbox_map[display_text] = bracket_key

        self.preview_count_var.set(f"({total_participants})")
        if self.DEBUG:
            self.logger.debug(f"DEBUG: Populated {len(groups_added)} groups: {groups_added}")

    def _on_search_focus_in(self, search_entry):
        """Clear placeholder text on focus."""
        if search_entry.get() == "M, W, age, or kg":
            search_entry.delete(0, tk.END)
            search_entry.config(fg=COLORS['text_primary'])

    def _on_search_changed(self, *args):
        """Handle search term changes (supports multiple terms with AND logic)."""
        if not self.group_listbox or not self.group_listbox.winfo_exists():
            return

        search_term = self.preview_search_var.get().lower().strip()

        # Skip placeholder or empty
        if search_term == "m, w, age, or kg" or not search_term:
            self.logger.debug("Search cleared - showing all groups")
            self._populate_group_list()
            return

        # Use shared search utility to filter bracket keys
        bracket_keys = [k for k in self.brackets.keys() if self.brackets[k].get('fighters', [])]
        filtered_keys, matched_count, search_terms = filter_items(bracket_keys, search_term)
        
        self.logger.debug(f"Search terms: {search_terms}, found {len(filtered_keys)} groups")
        
        # Display filtered groups with participant counts
        self.group_listbox.delete(0, tk.END)
        total_filtered = 0
        
        for bracket_key in sorted(filtered_keys):
            fighters = self.brackets[bracket_key].get('fighters', [])
            count = len(fighters)
            total_filtered += count
            
            display_text = f"{bracket_key} ({count})"
            self.group_listbox.insert(tk.END, display_text)

        self.preview_count_var.set(f"({total_filtered})")
        if self.DEBUG:
            self.logger.debug(f"DEBUG: Search terms parsed: {search_terms}")

    def _on_group_double_click(self, event):
        """Handle group selection."""
        selection = self.group_listbox.curselection()
        if not selection:
            return

        display_text = self.group_listbox.get(selection[0])
        bracket_key = self.group_listbox_map.get(display_text, display_text)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Double-clicked group index {selection[0]}: {display_text}")
        self.logger.info(f"Previewing group: {bracket_key}")
        self._display_participants(bracket_key)

    def _display_participants(self, bracket_key):
        """Display participant details for the selected group."""
        # Clear previous content
        for widget in self.participant_display_frame.winfo_children():
            widget.destroy()

        fighters = self.brackets[bracket_key].get('fighters', [])
        count = len(fighters)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Displaying {count} fighters for {bracket_key}")
            if fighters:
                self.logger.debug(f"DEBUG: First fighter: {fighters[0]}")

        # Update title
        self.preview_title_var.set(f"{bracket_key} - {count} participants")

        # Create scrollable text widget
        text_frame = create_dark_frame(self.participant_display_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.NONE,
            yscrollcommand=scrollbar.set,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['list_mono'],  # Monospace font for proper alignment
            padx=10,
            pady=10,
            cursor='arrow',  # Keep normal arrow cursor instead of text cursor
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        # Bind double-click to edit row
        text_widget.bind('<Double-Button-1>', lambda e: self._on_row_double_click(text_widget, bracket_key, count))

        # Column widths (in characters)
        COL_NUM = 6
        COL_NAME = 30
        COL_WEIGHT = 15
        COL_CLUB = 30
        COL_AGE = 10
        
        # Calculate total width for separator line
        SEPARATOR_LENGTH = COL_NUM + COL_NAME + COL_WEIGHT + COL_CLUB + COL_AGE + 4

        # Header
        header = f"{'#':<{COL_NUM}}{'Name':<{COL_NAME}}{'Weight (kg)':<{COL_WEIGHT}}{'Club/Verein':<{COL_CLUB}}{'Age':<{COL_AGE}}\n"
        text_widget.insert(tk.END, header, 'header')
        text_widget.insert(tk.END, "=" * SEPARATOR_LENGTH + "\n")
        
        # Participant rows
        for idx, fighter in enumerate(fighters, 1): #begin with 1 instead of 0
            name = fighter.get('Name', fighter.get('name', 'N/A'))
            weight = fighter.get('Weight', fighter.get('weight', 'N/A'))
            club = fighter.get('Verein', fighter.get('verein', fighter.get('club', 'N/A')))
            age = fighter.get('Age', fighter.get('age', 'N/A'))

            # Format weight
            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.1f}"
            else:
                weight_str = str(weight)

            row = f"{idx:<{COL_NUM}}{str(name):<{COL_NAME}}{weight_str:<{COL_WEIGHT}}{str(club):<{COL_CLUB}}{str(age):<{COL_AGE}}\n"
            text_widget.insert(tk.END, row, f'row_{idx}')

        # Style header
        text_widget.tag_configure('header', font=FONTS['list_mono_bold'], foreground=COLORS['accent_blue'])
        
        # Configure row tags for selection styling
        text_widget.tag_configure('row_selected', background=COLORS['accent_blue'], foreground=COLORS['text_primary'])
        
        # Configure all row tags
        for i in range(1, count + 1):
            text_widget.tag_bind(f'row_{i}', '<Button-1>', lambda e, row_num=i: self._on_row_click(text_widget, row_num, count))

        # Read-only
        text_widget.config(state=tk.DISABLED)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Text widget created with {count} rows")
        self.logger.debug(f"Displayed {count} participants for {bracket_key}")

    def _on_row_click(self, text_widget, row_num, total_rows):
        """Handle row selection click."""
        text_widget.config(state=tk.NORMAL)
        
        # Remove previous selection
        for i in range(1, total_rows + 1):
            text_widget.tag_remove('row_selected', f'{i+2}.0', f'{i+2}.end')
        
        # Select clicked row (add 2 because of header and separator line)
        text_widget.tag_add('row_selected', f'{row_num+2}.0', f'{row_num+2}.end')
        
        text_widget.config(state=tk.DISABLED)
        
        if self.DEBUG:
            self.logger.debug(f"DEBUG: Row {row_num} selected")

    def _on_row_double_click(self, text_widget, bracket_key, total_rows):
        """Handle row double-click to edit participant."""
        # Get line number under mouse cursor
        try:
            index = text_widget.index(f"@{text_widget.winfo_pointerx() - text_widget.winfo_rootx()}, {text_widget.winfo_pointery() - text_widget.winfo_rooty()}")
            line_num = int(index.split('.')[0])
            
            # Skip header (lines 1-2) and separator
            if line_num <= 2:
                return
            
            # Calculate fighter index (subtract header and separator)
            fighter_idx = line_num - 3
            
            if 0 <= fighter_idx < total_rows:
                self._open_edit_dialog(bracket_key, fighter_idx)
        except (ValueError, tk.TclError):
            pass

    def _parse_bracket_key(self, bracket_key):
        """Parse bracket key into gender, age_group, weight_class."""
        parts = [p.strip() for p in bracket_key.split('|')]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        return None, None, None

    def _get_available_age_classes(self, gender, current_age_group):
        """Get all available age classes for gender that are higher than current_age_group."""
        available_classes = set()
        
        for bracket_key in self.brackets.keys():
            parts = [p.strip() for p in bracket_key.split('|')]
            if len(parts) >= 3:
                bck_gender = parts[0]
                bck_age = parts[1]
                
                if bck_gender == gender:
                    available_classes.add(bck_age)
                    
        def get_age_key(age_str):
            m = re.search(r'\d+', age_str)
            num = int(m.group()) if m else 999
            is_plus = 1 if '+' in age_str else 0
            return (num, is_plus)
            
        current_key = get_age_key(current_age_group)
        
        higher_classes = [ac for ac in available_classes if get_age_key(ac) > current_key]
        higher_classes.sort(key=get_age_key)
        
        return higher_classes

    def _get_available_weight_classes(self, gender, age_group):
        """Get all available weight classes for gender and age_group - ONLY ones that exist in brackets."""
        # Collect only the weight classes that actually exist in the brackets
        available_classes = []
        
        for bracket_key in self.brackets.keys():
            parts = [p.strip() for p in bracket_key.split('|')]
            if len(parts) >= 3:
                bck_gender = parts[0]
                bck_age = parts[1]
                bck_weight = parts[2]
                
                if bck_gender == gender and bck_age == age_group:
                    if bck_weight not in available_classes:
                        available_classes.append(bck_weight)
        
        if self.DEBUG:
            self.logger.debug(f"DEBUG: Available weight classes for {gender} {age_group}: {available_classes}")
        
        # Sort: first by numeric value, then "-" before "+"
        def sort_key(x):
            if x == 'no-class':
                return (0, 0)
            # Extract number
            num_str = x.replace('kg', '').replace('-', '').replace('+', '')
            try:
                num = float(num_str)
            except ValueError:
                return (999, 0)
            # Return tuple: (number, 0 if starts with "-" else 1)
            is_plus = 1 if x.startswith('+') else 0
            return (num, is_plus)
        
        available_classes.sort(key=sort_key)
        
        return available_classes

    def _open_edit_dialog(self, bracket_key, fighter_idx):
        """Open edit dialog for participant."""
        try:
            fighters = self.brackets[bracket_key].get('fighters', [])
            if not (0 <= fighter_idx < len(fighters)):
                return
            
            fighter = fighters[fighter_idx]
            gender, age_group, current_weight_class = self._parse_bracket_key(bracket_key)
            if gender is None:
                gender = ""
            if age_group is None:
                age_group = ""
            if current_weight_class is None:
                current_weight_class = ""
            
            name = fighter.get('Name', fighter.get('name', ''))
            weight = fighter.get('Weight', fighter.get('weight', ''))
            club = fighter.get('Verein', fighter.get('verein', fighter.get('club', '')))
            age = fighter.get('Age', fighter.get('age', ''))
            
            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.1f}"
            else:
                weight_str = str(weight)
            
            available_weight_classes = self._get_available_weight_classes(gender, age_group)
            
            # Create edit window
            edit_window = tk.Toplevel(self)
            edit_window.title("Edit Participant")
            edit_window.geometry("500x680")
            edit_window.configure(bg=COLORS['bg_dark'])
            edit_window.transient(self.master)
            edit_window.resizable(False, False)
            edit_window.grab_set()
            
            # Center window on screen
            self.update_idletasks()
            width = 500
            height = 680
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            edit_window.geometry(f"{width}x{height}+{x}+{y}")
            
            # Header with participant name
            header_frame = tk.Frame(edit_window, bg=COLORS['bg_darker'], height=70)
            header_frame.pack(fill=tk.X)
            header_frame.pack_propagate(False)
            
            tk.Frame(header_frame, bg=COLORS['accent_blue'], width=5).pack(side=tk.LEFT, fill=tk.Y)
            
            title_label = tk.Label(header_frame, text=f"Participant: {name}", bg=COLORS['bg_darker'], fg=COLORS['text_primary'], font=FONTS['preview_title'])
            title_label.pack(side=tk.LEFT, padx=20, pady=20)
            
            # Main container with better padding
            container = tk.Frame(edit_window, bg=COLORS['bg_dark'])
            container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
            
            # Helper function to create form fields with subtle borders
            def create_field(parent, label_text, entry_var=None, is_readonly=False):
                """Create a nicely styled form field"""
                field_frame = tk.Frame(parent, bg=COLORS['bg_dark'])
                field_frame.pack(fill=tk.X, pady=(0, 18))
                
                label = tk.Label(field_frame, text=label_text.upper(), bg=COLORS['bg_dark'], fg=COLORS['accent_blue'], font=FONTS['preview_label'])
                label.pack(anchor=tk.W, pady=(0, 6))
                
                # Wrapper for border effect
                border_frame = tk.Frame(field_frame, bg=COLORS['border'], padx=1, pady=1)
                border_frame.pack(fill=tk.X)
                
                entry = tk.Entry(border_frame, bg=COLORS['bg_input'], fg=COLORS['text_primary'], font=FONTS['preview_text'], bd=0, relief=tk.FLAT)
                entry.pack(fill=tk.X, ipady=10, ipadx=10)
                
                if is_readonly:
                    entry.config(state=tk.DISABLED, fg=COLORS['text_muted'])
                    border_frame.config(bg=COLORS['bg_panel'])
                
                # Highlight on focus
                def on_focus_in(e, b=border_frame):
                    if not is_readonly:
                        b.config(bg=COLORS['accent_blue'])
                def on_focus_out(e, b=border_frame):
                    if not is_readonly:
                        b.config(bg=COLORS['border'])
                
                entry.bind("<FocusIn>", on_focus_in)
                entry.bind("<FocusOut>", on_focus_out)
                
                return entry
            
            # Name field
            name_entry = create_field(container, "Full Name")
            name_entry.insert(0, name)
            
            # Weight and Age in a row
            row_frame = tk.Frame(container, bg=COLORS['bg_dark'])
            row_frame.pack(fill=tk.X)
            
            weight_col = tk.Frame(row_frame, bg=COLORS['bg_dark'])
            weight_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            weight_entry = create_field(weight_col, "Weight (kg)")
            weight_entry.insert(0, weight_str)
            
            age_col = tk.Frame(row_frame, bg=COLORS['bg_dark'])
            age_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            age_entry = create_field(age_col, "Age")
            age_entry.insert(0, str(age))
            
            # Club field
            club_entry = create_field(container, "Club / Verein")
            club_entry.insert(0, club)
            
            # Weight Class / Age Class section
            is_fk = str(bracket_key).startswith("FK |")
            is_adult = age_group == "18+"
            label_text = "WEIGHT CLASS ASSIGNMENT" if is_adult else "AGE CLASS UPGRADE"
            
            wc_frame = tk.Frame(container, bg=COLORS['bg_dark'])
            if not is_fk:
                wc_frame.pack(fill=tk.X, pady=(0, 14))
                
                wc_label = tk.Label(wc_frame, text=label_text, bg=COLORS['bg_dark'], fg=COLORS['accent_blue'], font=FONTS['preview_label'])
                wc_label.pack(anchor=tk.W, pady=(0, 6))
            
            weight_class_var = tk.StringVar(value=current_weight_class)
            age_class_var = tk.StringVar(value=age_group)
            
            def get_weight_key(wc_str):
                """Returns (numeric_value, is_plus) for sorting."""
                num_str = wc_str.replace('kg', '').replace('-', '').replace('+', '')
                try:
                    num = float(num_str)
                except ValueError:
                    return (999, 0)
                is_plus = 1 if wc_str.startswith('+') else 0
                return (num, is_plus)
            
            current_weight_key = get_weight_key(current_weight_class)
            
            options_to_show = []
            selected_var = None
            
            if not is_fk:
                if is_adult:
                    # Only the next heavier weight class
                    heavier_classes = [wc for wc in available_weight_classes if get_weight_key(wc) > current_weight_key]
                    if heavier_classes:
                        next_class = heavier_classes[0]
                        options_to_show = [current_weight_class, next_class]
                    selected_var = weight_class_var
                else:
                    available_age_classes = self._get_available_age_classes(gender, age_group)
                    if available_age_classes:
                        next_class = available_age_classes[0]
                        options_to_show = [age_group, next_class]
                    selected_var = age_class_var
                
            if not is_fk:
                if options_to_show:
                    # CUSTOM DROPDOWN REPLACEMENT (Using a Frame-based layout to prevent draw collisions)
                    dropdown_border = tk.Frame(wc_frame, bg=COLORS['border'], padx=1, pady=1)
                    dropdown_border.pack(fill=tk.X)
                    
                    # The clickable button container
                    dropdown_btn = tk.Frame(dropdown_border, bg=COLORS['bg_input'], cursor='hand2')
                    dropdown_btn.pack(fill=tk.BOTH, expand=True)
                    
                    # Left side: Text label bound to the variable
                    text_label = tk.Label(
                        dropdown_btn, 
                        textvariable=selected_var,
                        bg=COLORS['bg_input'], 
                        fg=COLORS['text_primary'], 
                        font=FONTS['preview_text'],
                        anchor=tk.W,
                        padx=10,
                        pady=8
                    )
                    text_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    
                    # Right side: The arrow symbol
                    arrow_label = tk.Label(
                        dropdown_btn, 
                        text="▼", 
                        bg=COLORS['bg_input'], 
                        fg=COLORS['accent_blue'], 
                        font=FONTS['preview_small'],
                        padx=10
                    )
                    arrow_label.pack(side=tk.RIGHT, fill=tk.Y)
                    
                    def show_dropdown_menu():
                        # Create a custom popup for the dropdown
                        popup = tk.Toplevel(edit_window)
                        popup.withdraw()
                        popup.overrideredirect(True)
                        popup.configure(bg=COLORS['border'])
                        
                        # List container
                        list_frame = tk.Frame(popup, bg=COLORS['bg_input'])
                        list_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
                        
                        scrollbar = None
                        if len(options_to_show) > 8:
                            scrollbar = tk.Scrollbar(list_frame, width=10)
                            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                        
                        lb = tk.Listbox(
                            list_frame, 
                            bg=COLORS['bg_input'], 
                            fg=COLORS['text_primary'],
                            font=FONTS['preview_text'],
                            bd=0,
                            highlightthickness=0,
                            selectbackground=COLORS['accent_blue'],
                            selectforeground=COLORS['text_primary'],
                            activestyle='none',
                            yscrollcommand=scrollbar.set if scrollbar else None,
                            cursor='hand2'
                        )
                        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        if scrollbar:
                            scrollbar.config(command=lb.yview)
                        
                        for opt in options_to_show:
                            lb.insert(tk.END, f"  {opt}")
                            if opt == selected_var.get():
                                lb.selection_set(lb.size()-1)
                                lb.see(lb.size()-1)
                        
                        edit_window.update_idletasks()
                        width = dropdown_btn.winfo_width()
                        
                        max_visible_items = 8
                        visible_items = min(len(options_to_show), max_visible_items)
                        lb.config(height=visible_items)
                        
                        # Update widget geometry properties to accurately fetch reqheight
                        popup.update_idletasks()
                        
                        # Compute pixel-perfect height from Listbox's own font rendering
                        req_height = lb.winfo_reqheight()
                        if req_height > 10:
                            height = req_height + 2  # +2 for list_frame (padx=1, pady=1)
                        else:
                            height = visible_items * 22 + 4  # Safe fallback if window hasn't mapped
                        
                        root_x = dropdown_btn.winfo_rootx()
                        root_y = dropdown_btn.winfo_rooty()
                        btn_height = dropdown_btn.winfo_height()
                        
                        screen_height = edit_window.winfo_screenheight()
                        if root_y + btn_height + height > screen_height - 50:
                            pos_y = root_y - height
                        else:
                            pos_y = root_y + btn_height
                            
                        popup.geometry(f"{width}x{height}+{root_x}+{pos_y}")
                        popup.deiconify()
                        popup.lift()
                        popup.focus_force()
                        
                        def on_select(event):
                            selection = lb.curselection()
                            if selection:
                                selected_var.set(options_to_show[selection[0]].strip())
                                popup.destroy()
                                dropdown_border.config(bg=COLORS['border'])
                                # Ensure the arrow label stays on top when the button is redrawn
                                arrow_label.lift()
                        
                        def on_motion(event):
                            idx = lb.nearest(event.y)
                            lb.selection_clear(0, tk.END)
                            lb.selection_set(idx)
                            lb.activate(idx)
    
                        lb.bind("<ButtonRelease-1>", on_select)
                        lb.bind("<Motion>", on_motion)
                        lb.bind("<FocusOut>", lambda e: popup.destroy())
                        lb.bind("<Escape>", lambda e: popup.destroy())
                        
                        dropdown_border.config(bg=COLORS['accent_blue'])
                    
                    # Bind click events to both labels and the container
                    def handle_click(e):
                        # Force remove hover effect when opening menu
                        on_leave(None)
                        show_dropdown_menu()
                    
                    for widget in (dropdown_btn, text_label, arrow_label):
                        widget.bind("<Button-1>", handle_click)
                    
                    # Hover effects
                    def on_enter(e):
                        if popup and popup.winfo_exists() and popup.winfo_viewable():
                            return
                        dropdown_border.config(bg=COLORS['accent_blue'])
                        dropdown_btn.config(bg=COLORS['bg_panel'])
                        text_label.config(bg=COLORS['bg_panel'])
                        arrow_label.config(bg=COLORS['bg_panel'])
                        
                    def on_leave(e):
                        # Prevent flickering when moving between child widgets of the button
                        if e and e.widget != dropdown_btn and e.widget.winfo_containing(e.x_root, e.y_root) in (dropdown_btn, text_label, arrow_label):
                            return
                        dropdown_border.config(bg=COLORS['border'])
                        dropdown_btn.config(bg=COLORS['bg_input'])
                        text_label.config(bg=COLORS['bg_input'])
                        arrow_label.config(bg=COLORS['bg_input'])
                    
                    # Use a dummy popup variable reference so on_enter can check if menu is open
                    popup = None
                    
                    for widget in (dropdown_btn, text_label, arrow_label):
                        widget.bind("<Enter>", on_enter)
                        widget.bind("<Leave>", on_leave)
                else:
                    status_frame = tk.Frame(wc_frame, bg=COLORS['bg_panel'], padx=1, pady=1)
                    status_frame.pack(fill=tk.X)
                    status_text = f"● {current_weight_class} (Highest class)" if is_adult else f"● {age_group} (Highest class)"
                    status_label = tk.Label(status_frame, text=status_text, bg=COLORS['bg_input'], fg=COLORS['text_muted'], font=FONTS['preview_text'], anchor=tk.W, padx=10, pady=10)
                    status_label.pack(fill=tk.X)
            
            # Separator
            tk.Frame(container, bg=COLORS['border'], height=1).pack(fill=tk.X, pady=25)
            
            # Buttons
            button_frame = tk.Frame(container, bg=COLORS['bg_dark'])
            button_frame.pack(fill=tk.X)
            
            def save():
                try:
                    fighter['Name'] = name_entry.get()
                    fighter['Weight'] = float(weight_entry.get())
                    fighter['Verein'] = club_entry.get()
                    fighter['Age'] = int(age_entry.get())
                    
                    # Track which bracket to display after save
                    display_bracket_key = bracket_key
                    
                    if not is_fk:
                        if is_adult:
                            new_wc = weight_class_var.get()
                            if new_wc != current_weight_class:
                                display_bracket_key = self._move_participant_to_bracket(bracket_key, fighter_idx, gender, age_group, new_wc)
                        else:
                            new_ac = age_class_var.get()
                            if new_ac != age_group:
                                new_weight = float(weight_entry.get())
                                new_wc = 'unknown'
                                if self.config_repo:
                                    new_wc = self.config_repo.get_weight_class(new_weight, gender, new_ac)
                                display_bracket_key = self._move_participant_to_bracket(bracket_key, fighter_idx, gender, new_ac, new_wc)
                    
                    self._display_participants(display_bracket_key)
                    edit_window.destroy()
                except ValueError:
                    tk.messagebox.showerror("Error", "Invalid weight or age. Please enter numbers.")
                except Exception as e:
                    self.logger.error(f"Save error: {e}", exc_info=True)
            
            btn_save = tk.Button(button_frame, text="SAVE CHANGES", command=save, bg=COLORS['accent_green'], fg=COLORS['text_primary'], font=FONTS['heading_sm'], bd=0, relief=tk.FLAT, padx=25, pady=12, cursor='hand2')
            btn_save.pack(side=tk.RIGHT)
            
            btn_cancel = tk.Button(button_frame, text="CANCEL", command=edit_window.destroy, bg=COLORS['bg_panel'], fg=COLORS['text_secondary'], font=FONTS['heading_sm'], bd=0, relief=tk.FLAT, padx=25, pady=12, cursor='hand2')
            btn_cancel.pack(side=tk.RIGHT, padx=10)
            
        except Exception as e:
            self.logger.error(f"Error opening edit dialog: {e}", exc_info=True)

    def _move_participant_to_bracket(self, old_bracket_key, fighter_idx, new_gender, new_age_group, new_weight_class):
        """Move a participant from one bracket to another when weight class or age class changes."""
        old_fighters = self.brackets[old_bracket_key].get('fighters', [])
        
        if not (0 <= fighter_idx < len(old_fighters)):
            return old_bracket_key
        
        # Get the fighter to move
        fighter = old_fighters[fighter_idx]
        
        # Construct new bracket key
        new_bracket_key = f"{new_gender} | {new_age_group} | {new_weight_class}"
        
        # Remove from old bracket
        old_fighters.pop(fighter_idx)
        self.logger.info(f"Removed {fighter['Name']} from {old_bracket_key}")
        
        # Add to new bracket (create if needed)
        if new_bracket_key not in self.brackets:
            self.brackets[new_bracket_key] = {
                'fighters': [],
                'bracket': []
            }
        
        self.brackets[new_bracket_key]['fighters'].append(fighter)
        self.logger.info(f"Added {fighter['Name']} to {new_bracket_key}")
        
        # Refresh group list
        self._populate_group_list()
        
        # Re-apply search filter if active
        if self.preview_search_var and self.preview_search_var.get() and self.preview_search_var.get() != "M, W, age, or kg":
            self._on_search_changed()
        
        # Return the new bracket key so caller knows which bracket to display
        return new_bracket_key

    def _on_friendly_match(self):
        """Open a window to pair two participants into a friendly match."""
        try:
            fk_window = tk.Toplevel(self.main_frame.winfo_toplevel())
        except AttributeError:
            fk_window = tk.Toplevel()  # Fallback
            
        fk_window.title("Friendly Match")
        fk_window.geometry("600x450")
        fk_window.configure(bg=COLORS['bg_dark'])
        fk_window.transient(self.main_frame.winfo_toplevel() if hasattr(self, 'main_frame') else None)
        fk_window.grab_set()

        title_label = tk.Label(fk_window, text="Create Friendly Match", bg=COLORS['bg_dark'], fg=COLORS['text_primary'], font=FONTS['preview_title'])
        title_label.pack(pady=15)

        info_label = tk.Label(fk_window, text="Select exactly 2 fighters from groups with 1-2 participants:", bg=COLORS['bg_dark'], fg=COLORS['text_secondary'], font=FONTS['preview_info'])
        info_label.pack(pady=(0, 10))

        list_frame = tk.Frame(fk_window, bg=COLORS['bg_dark'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        lb = tk.Listbox(
            list_frame, 
            bg=COLORS['bg_input'], 
            fg=COLORS['text_primary'],
            font=FONTS['list_ui'],
            selectmode=tk.MULTIPLE,
            yscrollcommand=scrollbar.set,
            bd=0, highlightthickness=1, highlightbackground=COLORS['border'],
            selectbackground=COLORS['accent_blue'],
            selectforeground=COLORS['text_primary'],
            exportselection=False,
            activestyle='none'
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=lb.yview)

        # Collect eligible fighters
        eligible_fighters = [] # list of (bracket_key, fighter_dict)
        for b_key in sorted(self.brackets.keys()):
            # Don't show already created FK brackets here just in case, or show them if they only have 1 (which shouldn't happen)
            fighters = self.brackets[b_key].get('fighters', [])
            if len(fighters) in [1, 2] and not b_key.startswith("FK |"):
                for f in fighters:
                    eligible_fighters.append((b_key, f))
                    lb.insert(tk.END, f"{b_key}:   {f['Name']} ({f['Weight']}kg, {f['Age']}yrs, {f['Verein']})")

        btn_frame = tk.Frame(fk_window, bg=COLORS['bg_dark'])
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        def pair_fighters():
            selections = lb.curselection()
            if len(selections) != 2:
                tk.messagebox.showwarning("Warning", "Please select exactly 2 fighters.", parent=fk_window)
                return
            
            idx1, idx2 = selections
            b_key1, f1 = eligible_fighters[idx1]
            b_key2, f2 = eligible_fighters[idx2]

            # Create new bracket key (Friendly Match)
            new_bracket_key = f"FK | {f1['Name']} vs {f2['Name']}"
            
            if new_bracket_key not in self.brackets:
                self.brackets[new_bracket_key] = {'fighters': [], 'bracket': []}

            # Remove from old brackets securely
            for b_key, f in [(b_key1, f1), (b_key2, f2)]:
                try:
                    self.brackets[b_key]['fighters'].remove(f)
                    self.brackets[new_bracket_key]['fighters'].append(f)
                except ValueError:
                    pass

            tk.messagebox.showinfo("Success", f"Friendly match created:\n{f1['Name']} vs {f2['Name']}", parent=fk_window)
            self._populate_group_list()
            fk_window.destroy()

        pair_btn = tk.Button(btn_frame, text="Create Match", command=pair_fighters, bg=COLORS['accent_green'], fg=COLORS['text_primary'], font=('Arial', 11, 'bold'), bd=0, padx=15, pady=8, cursor='hand2')
        pair_btn.pack(side=tk.RIGHT)

        cancel_btn = tk.Button(btn_frame, text="Cancel", command=fk_window.destroy, bg=COLORS['bg_panel'], fg=COLORS['text_secondary'], font=('Arial', 11, 'bold'), bd=0, padx=15, pady=8, cursor='hand2')
        cancel_btn.pack(side=tk.RIGHT, padx=10)

    def _on_back(self):
        """Navigate back."""
        self.logger.info("User clicked: Back to File Loader")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_back callback")
        if self.on_back:
            self.on_back()

    def _on_continue(self):
        """Navigate to generation method screen."""
        self.logger.info("User clicked: Continue to Generation Setup")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_continue callback")
        if self.on_continue:
            self.on_continue()
