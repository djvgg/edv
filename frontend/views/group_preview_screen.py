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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
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

        # Data
        self.brackets = {}  # {bracket_key: bracket_data}
        self.group_listbox_map = {}  # {display_text: bracket_key}

        # UI References
        self.group_listbox = None
        self.participant_display_frame = None
        self.preview_title_var = None
        self.preview_search_var = None
        self.preview_count_var = None

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

        continue_btn = tk.Button(
            button_frame,
            text='Continue to Generation Setup →',
            command=self._on_continue,
        )
        apply_button_style(continue_btn, 'primary')
        continue_btn.pack(side=tk.RIGHT, padx=5)

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
            font=FONTS['body_sm'],
            padx=10,
            pady=10,
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        # Header
        header = f"{'Name':<35}             {'Weight (kg)':<15}             {'Club/Verein':<30}                  {'Age':<10}\n"
        text_widget.insert(tk.END, header, 'header')
        text_widget.insert(tk.END, "=" * 100 + "\n\n")

        # Participant rows
        for fighter in fighters:
            name = fighter.get('Name', fighter.get('name', 'N/A'))
            weight = fighter.get('Weight', fighter.get('weight', 'N/A'))
            club = fighter.get('Verein', fighter.get('verein', fighter.get('club', 'N/A')))
            age = fighter.get('Age', fighter.get('age', 'N/A'))

            # Format weight
            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.1f}"
            else:
                weight_str = str(weight)

            row = f"{str(name):<35} {weight_str:<15} {str(club):<30} {str(age):<10}\n"
            text_widget.insert(tk.END, row)

        # Style header
        text_widget.tag_configure('header', font=FONTS['heading_sm'], foreground=COLORS['accent_blue'])

        # Read-only
        text_widget.config(state=tk.DISABLED)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Text widget created with {count} rows")
        self.logger.debug(f"Displayed {count} participants for {bracket_key}")

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
