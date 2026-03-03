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
from tkinter import ttk
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from backend.data.repositories.config_repository import ConfigRepository
from ..styles import (
    COLORS, FONTS,
    SCROLLBAR_STYLE, SCROLLBAR_ACTIVE_STYLE,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    create_dark_frame,
)
from ..search_utils import filter_items
from .edit_participant_dialog import Edit_Participants

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

    def __init__(self, parent, quarantine_service=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.quarantine_service = quarantine_service  # Store reference for edit dialog

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
        self.on_resort = None  # Callback to trigger bracket regeneration

        self._setup_scrollbar_style()
        self.init_ui()

    def _setup_scrollbar_style(self):
        """Configure ttk scrollbar style to match the dark theme."""
        style = ttk.Style()
        style.theme_use('default')

        # Vertical scrollbar
        style.configure('Dark.Vertical.TScrollbar',
            background=SCROLLBAR_STYLE['background'],
            troughcolor=SCROLLBAR_STYLE['troughcolor'],
            bordercolor=SCROLLBAR_STYLE['bordercolor'],
            arrowcolor=SCROLLBAR_STYLE['arrowcolor'],
            lightcolor=SCROLLBAR_STYLE['lightcolor'],
            darkcolor=SCROLLBAR_STYLE['darkcolor'],
            width=10,
        )
        style.map('Dark.Vertical.TScrollbar',
            background=[('active', SCROLLBAR_ACTIVE_STYLE['background'])],
            arrowcolor=[('active', SCROLLBAR_ACTIVE_STYLE['arrowcolor'])],
        )

        # Horizontal scrollbar
        style.configure('Dark.Horizontal.TScrollbar',
            background=SCROLLBAR_STYLE['background'],
            troughcolor=SCROLLBAR_STYLE['troughcolor'],
            bordercolor=SCROLLBAR_STYLE['bordercolor'],
            arrowcolor=SCROLLBAR_STYLE['arrowcolor'],
            lightcolor=SCROLLBAR_STYLE['lightcolor'],
            darkcolor=SCROLLBAR_STYLE['darkcolor'],
            width=10,
        )
        style.map('Dark.Horizontal.TScrollbar',
            background=[('active', SCROLLBAR_ACTIVE_STYLE['background'])],
            arrowcolor=[('active', SCROLLBAR_ACTIVE_STYLE['arrowcolor'])],
        ) 
        
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

    # Left panel: Group list
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

    # Right panel: Draw Participant preview
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

        # Placeholder, TODO: Symbole nutzen für mehr Eindeutigkeit und UX, UX bei Edit Participant, Code besser machen
        placeholder = tk.Label( # machen, Neue Klasse auslagern Edit Participant, Window Springen bei Age oder Weigth  
            self.participant_display_frame, # Update weg machen aber neues Blinken bei wieght Group einfügen, Tabsystem einfügen
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

    # Fill in Weight Classes (m | 18+ | -66kg etc..), Left Panel
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

    def _parse_bracket_key(self, bracket_key):
        """Parse bracket key into gender, age_group, weight_class."""
        parts = [p.strip() for p in bracket_key.split('|')]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        return None, None, None

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

        # Create scrollable text widget with auto-hiding styled scrollbars
        text_frame = create_dark_frame(self.participant_display_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # Use grid layout for text + scrollbars
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.NONE,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['list_mono'],  # Monospace font for proper alignment
            padx=10,
            pady=10,
            cursor='arrow',  # Keep normal arrow cursor instead of text cursor
        )
        text_widget.grid(row=0, column=0, sticky='nsew')

        # Styled vertical scrollbar (dark theme)
        v_scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL,
            command=text_widget.yview,
            style='Dark.Vertical.TScrollbar',
        )

        # Styled horizontal scrollbar (dark theme)
        h_scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.HORIZONTAL,
            command=text_widget.xview,
            style='Dark.Horizontal.TScrollbar',
        )

        text_widget.configure(
            yscrollcommand=lambda first, last: self._auto_scroll(v_scrollbar, first, last, 'vertical'),
            xscrollcommand=lambda first, last: self._auto_scroll(h_scrollbar, first, last, 'horizontal'),
        )

        # Shift + Mousewheel for horizontal scrolling
        text_widget.bind('<Shift-MouseWheel>', lambda e: text_widget.xview_scroll(int(-1 * (e.delta / 120)), 'units'))

        # Bind double-click to edit row
        text_widget.bind('<Double-Button-1>', lambda e: self._on_row_double_click(text_widget, bracket_key, count))

        # Column widths (in characters)
        COL_FIRSTNAME = 15
        COL_LAST = 15
        COL_BIRTH = 12
        COL_CLUB = 25
        COL_ASSOCIATION = 15
        COL_WEIGHT = 12
        COL_GENDER = 10
        
        # Calculate total width for separator line
        SEPARATOR_LENGTH = COL_FIRSTNAME + COL_LAST + COL_BIRTH + COL_CLUB + COL_ASSOCIATION + COL_WEIGHT + COL_GENDER + 4

        # Header
        header = f"{'Firstname':<{COL_FIRSTNAME}}{'Lastname':<{COL_LAST}}{'Birthyear':<{COL_BIRTH}}{'Club':<{COL_CLUB}}{'Association':<{COL_ASSOCIATION}}{'Weight':<{COL_WEIGHT}}{'Gender':<{COL_GENDER}}\n"
        text_widget.insert(tk.END, header, 'header')
        text_widget.insert(tk.END, "=" * SEPARATOR_LENGTH + "\n")
        
        # Participant rows
        for idx, fighter in enumerate(fighters, 1): #begin with 1 instead of 0
            first = str(fighter.get('Firstname', fighter.get('name', 'N/A')))
            last = str(fighter.get('Lastname', ''))
            birth = str(fighter.get('Birthyear', fighter.get('BirthYear')))
            club = str(fighter.get('Club', fighter.get('Verein', fighter.get('club', 'N/A'))))
            association = str(fighter.get('Association', ''))
            gender = str(fighter.get('Gender', ''))
            weight = fighter.get('Weight', 'N/A')

            # Format weight
            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.1f}"
            else:
                weight_str = str(weight)

            row = f"{first:<{COL_FIRSTNAME}}{last:<{COL_LAST}}{birth:<{COL_BIRTH}}{club:<{COL_CLUB}}{association:<{COL_ASSOCIATION}}{weight_str:<{COL_WEIGHT}}{gender:<{COL_GENDER}}\n"
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

    def _auto_scroll(self, scrollbar, first, last, orientation):
        """Show/hide scrollbar based on whether content overflows the visible area."""
        if float(first) <= 0.0 and float(last) >= 1.0:
            # Content fits — hide scrollbar
            scrollbar.grid_remove()
        else:
            # Content overflows — show scrollbar
            if orientation == 'vertical':
                scrollbar.grid(row=0, column=1, sticky='ns')
            else:
                scrollbar.grid(row=1, column=0, sticky='ew')
        scrollbar.set(first, last)

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

    def _open_edit_dialog(self, bracket_key, fighter_idx):
        """Open edit dialog for participant."""
        # Use the separate Edit_Participants class to handle the dialog
        Edit_Participants(self, bracket_key, fighter_idx)

    def flash_bracket(self, bracket_key):
        """Visually flash a bracket in the listbox to indicate a participant was moved there."""
        if not hasattr(self, 'group_listbox') or not self.group_listbox.winfo_exists():
            return
            
        lst = self.group_listbox.get(0, tk.END)
        target_idx = -1
        
        # Find the index of the bracket in the current listbox
        for i, display_text in enumerate(lst):
            if self.group_listbox_map.get(display_text, display_text) == bracket_key:
                target_idx = i
                break
                
        if target_idx != -1:
            # Scroll to make sure it's visible
            self.group_listbox.see(target_idx)
            
            # Apply glow
            self.group_listbox.itemconfig(target_idx, background=COLORS['accent_green'], foreground=COLORS['bg_dark'])
            
            # Schedule revert after 3 seconds
            def revert():
                if hasattr(self, 'group_listbox') and self.group_listbox.winfo_exists():
                    try:
                        # Safety check: ensure the item at target_idx is still the same bracket
                        current_text = self.group_listbox.get(target_idx)
                        if self.group_listbox_map.get(current_text, current_text) == bracket_key:
                            # Reverting to default listbox styling from COLORS
                            self.group_listbox.itemconfig(target_idx, background='', foreground='')
                    except tk.TclError:
                        pass
                        
            self.after(3000, revert)

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
        f_name = f"{fighter.get('Firstname', '')} {fighter.get('Lastname', '')}".strip() or fighter.get('Name', 'Unknown')
        self.logger.info(f"Removed {f_name} from {old_bracket_key}")

        # Invalidate the stale KO pairings — they will be regenerated from
        # fighters the next time the bracket is rendered or monitoring opens.
        self.brackets[old_bracket_key]['bracket'] = []

        # Add to new bracket (create if needed)
        if new_bracket_key not in self.brackets:
            self.brackets[new_bracket_key] = {
                'fighters': [],
                'bracket': []
            }

        self.brackets[new_bracket_key]['fighters'].append(fighter)
        self.brackets[new_bracket_key]['bracket'] = []  # Invalidate new bracket too
        f_name = f"{fighter.get('Firstname', '')} {fighter.get('Lastname', '')}".strip() or fighter.get('Name', 'Unknown')
        self.logger.info(f"Added {f_name} to {new_bracket_key}")
        
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
            fm_window = tk.Toplevel(self.main_frame.winfo_toplevel())
        except AttributeError:
            fm_window = tk.Toplevel()  # Fallback
            
        fm_window.title("Friendly Match")
        fm_window.geometry("600x450")
        fm_window.configure(bg=COLORS['bg_dark'])
        fm_window.transient(self.main_frame.winfo_toplevel() if hasattr(self, 'main_frame') else None)
        fm_window.grab_set()

        title_label = tk.Label(fm_window, text="Create Friendly Match", bg=COLORS['bg_dark'], fg=COLORS['text_primary'], font=FONTS['preview_title'])
        title_label.pack(pady=15)

        info_label = tk.Label(fm_window, text="Select exactly 2 fighters from groups with 1-2 participants:", bg=COLORS['bg_dark'], fg=COLORS['text_secondary'], font=FONTS['preview_info'])
        info_label.pack(pady=(0, 10))

        list_frame = tk.Frame(fm_window, bg=COLORS['bg_dark'])
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
            # Don't show already created fm brackets here just in case, or show them if they only have 1 (which shouldn't happen)
            fighters = self.brackets[b_key].get('fighters', [])
            if len(fighters) in [1, 2] and not b_key.startswith("FM |"):
                for f in fighters:
                    eligible_fighters.append((b_key, f))
                    f_name = f"{f.get('Firstname', '')} {f.get('Lastname', '')}".strip() or f.get('Name', 'Unknown')
                    f_weight = f.get('Weight', 'N/A')
                    f_birth = f.get('Birthyear', f.get('age', 'N/A'))
                    f_club = f.get('Club', f.get('Verein', 'N/A'))
                    lb.insert(tk.END, f"{b_key}:   {f_name} ({f_weight}kg, {f_birth}yrs, {f_club})")

        btn_frame = tk.Frame(fm_window, bg=COLORS['bg_dark'])
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        def pair_fighters():
            selections = lb.curselection()
            if len(selections) != 2:
                tk.messagebox.showwarning("Warning", "Please select exactly 2 fighters.", parent=fm_window)
                return
            
            idx1, idx2 = selections
            b_key1, f1 = eligible_fighters[idx1]
            b_key2, f2 = eligible_fighters[idx2]

            # Create new bracket key (Friendly Match)
            name1 = f"{f1.get('Firstname', '')} {f1.get('Lastname', '')}".strip() or f1.get('Name', 'Unknown')
            name2 = f"{f2.get('Firstname', '')} {f2.get('Lastname', '')}".strip() or f2.get('Name', 'Unknown')
            new_bracket_key = f"FM | {name1} vs {name2}"
            
            if new_bracket_key not in self.brackets:
                self.brackets[new_bracket_key] = {'fighters': [], 'bracket': []}

            # Remove from old brackets securely
            for b_key, f in [(b_key1, f1), (b_key2, f2)]:
                try:
                    self.brackets[b_key]['fighters'].remove(f)
                    self.brackets[new_bracket_key]['fighters'].append(f)
                except ValueError:
                    pass

            tk.messagebox.showinfo("Success", f"Friendly match created:\n{f1['Name']} vs {f2['Name']}", parent=fm_window)
            self._populate_group_list()
            fm_window.destroy()

        pair_btn = tk.Button(btn_frame, text="Create Match", command=pair_fighters, bg=COLORS['accent_green'], fg=COLORS['text_primary'], font=('Arial', 11, 'bold'), bd=0, padx=15, pady=8, cursor='hand2')
        pair_btn.pack(side=tk.RIGHT)

        cancel_btn = tk.Button(btn_frame, text="Cancel", command=fm_window.destroy, bg=COLORS['bg_panel'], fg=COLORS['text_secondary'], font=('Arial', 11, 'bold'), bd=0, padx=15, pady=8, cursor='hand2')
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
