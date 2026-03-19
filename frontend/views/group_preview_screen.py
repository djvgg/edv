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

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger, DEBUG_VERBOSE  # noqa: E402
from utils.helpers import parse_bracket_key as _parse_bracket_key_helper  # noqa: E402
from backend.data.repositories.config_repository import ConfigRepository  # noqa: E402
from ..styles import (  # noqa: E402
    COLORS, FONTS, SPACING,
    SCROLLBAR_STYLE, SCROLLBAR_ACTIVE_STYLE,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    create_dark_frame,
)
from ..utils.search_utils import filter_items  # noqa: E402
from .edit_participant_dialog import Edit_Participants  # noqa: E402
from .friendly_match_dialog import FriendlyMatchDialog  # noqa: E402
from ._group_preview_tolerance import _ToleranceMixin  # noqa: E402

logger = get_logger('group_preview_screen', debug_verbose=DEBUG_VERBOSE)


class GroupPreviewScreen(_ToleranceMixin, tk.Frame):
    """
    Screen for previewing bracket groups and participants.
    
    Displays:
    - Left: searchable list of weight groups
    - Right: detailed participant list for selected group
    - Bottom: Back and Continue buttons
    """

    # Debug flag - set to True for verbose logging
    DEBUG = DEBUG_VERBOSE

    def __init__(self, parent, main_window=None, quarantine_service=None, db_service=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.main_window = main_window              # Store reference to main app for reload
        self.quarantine_service = quarantine_service  # Store reference for edit dialog
        self.db_service = db_service                  # DB service for persisting edits

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
        self.tolerances = {}  # {(gender, age_group): float} — per-group clothing tolerance in kg

        # UI References
        self.group_listbox = None # left listbox
        self.participant_display_frame = None # right listbox of participants
        self.preview_title_var = None # Title of the right listbox
        self.preview_search_var = None # Search field of the left listbox
        self.preview_count_var = None # Number of participants in the left listbox
        self.ui_initialized = False  # Track if UI has been built

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
        
    def on_show(self, force_reload=False):
        """Called when screen is shown. Reload data if marked as stale.
        
        Args:
            force_reload: True if screen was marked as stale and needs data refresh
        """
        if force_reload:
            # Get fresh brackets from main_window's cache
            if self.main_window and hasattr(self.main_window, 'brackets'):
                self.logger.info("[RELOAD] Group Preview detected stale data, reloading from cache")
                self.load_data(self.main_window.brackets)
            else:
                self.logger.warning("[RELOAD] Cannot reload: main_window or main_window.brackets not found")
        
    def load_data(self, brackets):
        """Load bracket data."""
        self.brackets = brackets
        self.logger.info(f"Loaded {len(brackets)} brackets for preview")
        if self.DEBUG:
            self.logger.debug(f"DEBUG: Bracket keys: {list(brackets.keys())}")
        self._populate_group_list()    

    def init_ui(self):
        """Initialize the user interface. Only build once."""
        if self.ui_initialized:
            self.logger.debug("UI already initialized, skipping rebuild")
            return
        
        try:
            # Main layout with resizable split
            main_frame = create_dark_frame(self)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=SPACING['md'], pady=SPACING['md'])

            # Window Frame / Panel Window
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
            
            # Mark as initialized ONLY after successful build
            self.ui_initialized = True
            self.logger.debug("UI initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize UI: {e}", exc_info=True)
            # Don't set ui_initialized, allow retry on next call
            raise

    # Left panel: Group list
    def _create_group_list_panel(self, parent_paned):
        """Create the left panel with group list and search."""
        left_frame = create_dark_frame(parent_paned)
        parent_paned.add(left_frame, width=300, minsize=250)

        # Title with count
        title_frame = create_dark_frame(left_frame)
        title_frame.pack(fill=tk.X, pady=(0, SPACING['sm']))

        title_label = tk.Label(title_frame, text='Gewichtsklassen')
        apply_label_style(title_label, 'heading_md')
        title_label.pack(side=tk.LEFT)

        # Participant counter
        self.preview_count_var = tk.StringVar(value="(0)")
        count_label = tk.Label(title_frame, textvariable=self.preview_count_var)
        apply_label_style(count_label, 'info')
        count_label.pack(side=tk.RIGHT)

        # Search box
        search_frame = create_dark_frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, SPACING['sm']))

        search_label = tk.Label(search_frame, text='Suche:')
        apply_label_style(search_label, 'info')
        search_label.pack(side=tk.LEFT)

        self.preview_search_var = tk.StringVar()
        self.preview_search_var.trace('w', self._on_search_changed)
        search_entry = tk.Entry(search_frame, textvariable=self.preview_search_var, fg=COLORS['text_muted'])
        search_entry.insert(0, "m, w, Alter oder kg")
        search_entry.bind('<FocusIn>', lambda e: self._on_search_focus_in(search_entry))
        apply_entry_style(search_entry)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=SPACING['sm'])

        # Group listbox
        self.group_listbox = tk.Listbox(left_frame, width=30, height=20)
        apply_listbox_style(self.group_listbox)
        self.group_listbox.pack(fill=tk.BOTH, expand=True, pady=SPACING['sm'])
        self.group_listbox.bind('<Double-Button-1>', self._on_group_double_click)

    # Right panel: Draw Participant preview
    def _create_participant_preview_panel(self, parent_paned):
        """Create the right panel for participant preview."""
        right_frame = create_dark_frame(parent_paned)
        parent_paned.add(right_frame, minsize=450)

        # Title
        self.preview_title_var = tk.StringVar(value="Teilnehmer-Vorschau")
        title_label = tk.Label(right_frame, textvariable=self.preview_title_var)
        apply_label_style(title_label, 'heading_md')
        title_label.pack(pady=(0, SPACING['md']))

        # Participant display container
        self.participant_display_frame = create_dark_frame(right_frame)
        self.participant_display_frame.pack(fill=tk.BOTH, expand=True)

        placeholder = tk.Label( 
            self.participant_display_frame, 
            text="Doppelklick zur Vorschau",
        )
        apply_label_style(placeholder, 'info')
        placeholder.pack(expand=True)

    def _create_navigation_buttons(self, parent_frame):
        """Create bottom navigation buttons."""
        button_frame = create_dark_frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        back_btn = tk.Button(button_frame, text='← Zurück zum Dateilader', command=self._on_back)
        apply_button_style(back_btn, 'secondary')
        back_btn.pack(side=tk.LEFT, padx=SPACING['sm'])

        merge_btn = tk.Button(button_frame, text='⧉ Freundschaftskampf-Modus', command=self._on_friendly_match)
        apply_button_style(merge_btn, 'secondary')
        merge_btn.pack(side=tk.LEFT, padx=SPACING['sm'])

        continue_btn = tk.Button(
            button_frame,
            text='Weiter zur Erstellung →',
            command=self._on_continue,
        )
        apply_button_style(continue_btn, 'primary')
        continue_btn.pack(side=tk.RIGHT, padx=SPACING['sm'])

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

                display_key = bracket_key
                if bracket_key.startswith("QUARANTINE_"):
                    reason = bracket_key.replace("QUARANTINE_", "")
                    t_map = {"marked_invalid": "Ungültig", "unpaid": "Unbezahlt", "age_too_young": "Zu jung"}
                    display_key = f"QUARANTÄNE_{t_map.get(reason, reason)}"
                
                display_text = f"{display_key} ({count})"
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
            
            display_key = bracket_key
            if bracket_key.startswith("QUARANTINE_"):
                reason = bracket_key.replace("QUARANTINE_", "")
                t_map = {"marked_invalid": "Ungültig", "unpaid": "Unbezahlt", "age_too_young": "Zu jung"}
                display_key = f"QUARANTÄNE_{t_map.get(reason, reason)}"
            
            display_text = f"{display_key} ({count})"
            self.group_listbox.insert(tk.END, display_text)
            self.group_listbox_map[display_text] = bracket_key

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
        """Parse bracket key into (gender, age_group, weight_class).
        Returns (None, None, None) for non-standard keys like 'U9' or 'QUARANTINE_...'."""
        try:
            return _parse_bracket_key_helper(bracket_key)
        except ValueError:
            return None, None, None

    def _display_participants(self, bracket_key):
        """Display participant details for the selected group."""
        for widget in self.participant_display_frame.winfo_children():
            widget.destroy()

        self.current_bracket_key = bracket_key

        # U9/U11: always show fighters sorted by weight (also persists order for the split later)
        if bracket_key in ('U9', 'U11'):
            self.brackets[bracket_key]['fighters'].sort(key=lambda x: x.get('Weight', 0))

        fighters = self.brackets[bracket_key].get('fighters', [])
        count = len(fighters)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Displaying {count} fighters for {bracket_key}")
            if fighters:
                self.logger.debug(f"DEBUG: First fighter: {fighters[0]}")

        display_key = bracket_key
        if bracket_key.startswith("QUARANTINE_"):
            reason = bracket_key.replace("QUARANTINE_", "")
            t_map = {"marked_invalid": "Ungültig", "unpaid": "Unbezahlt", "age_too_young": "Zu jung"}
            display_key = f"QUARANTÄNE_{t_map.get(reason, reason)}"

        self.preview_title_var.set(f"{display_key} - {count} Teilnehmer")

        gender, age_group, weight_class = self._parse_bracket_key(bracket_key)
        self._create_tolerance_bar(self.participant_display_frame, gender, age_group)

        text_widget = self._build_scrollable_text(self.participant_display_frame)
        text_widget.bind('<Double-Button-1>', lambda e: self._on_row_double_click(text_widget, bracket_key, count))

        self._render_participant_rows(text_widget, fighters, count)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Text widget created with {count} rows")
        self.logger.debug(f"Displayed {count} participants for {bracket_key}")

    def _build_scrollable_text(self, parent) -> tk.Text:
        """Create a read/write Text widget inside parent with auto-hiding styled scrollbars.

        Returns the Text widget so the caller can populate it and add bindings.
        The widget is left in NORMAL state — callers must set DISABLED when done.
        """
        text_frame = create_dark_frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True)
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.NONE,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['list_mono'],
            padx=10,
            pady=10,
            cursor='arrow',
        )
        text_widget.grid(row=0, column=0, sticky='nsew')

        v_scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL,
            command=text_widget.yview,
            style='Dark.Vertical.TScrollbar',
        )
        h_scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.HORIZONTAL,
            command=text_widget.xview,
            style='Dark.Horizontal.TScrollbar',
        )

        text_widget.configure(
            yscrollcommand=lambda first, last: self._auto_scroll(v_scrollbar, first, last, 'vertical'),
            xscrollcommand=lambda first, last: self._auto_scroll(h_scrollbar, first, last, 'horizontal'),
        )
        text_widget.bind('<Shift-MouseWheel>', lambda e: text_widget.xview_scroll(int(-1 * (e.delta / 120)), 'units'))

        return text_widget

    def _render_participant_rows(self, text_widget: tk.Text, fighters: list, count: int):
        """Populate text_widget with the participant table (header + rows) and configure tags.

        Leaves the widget in DISABLED (read-only) state when done.
        """
        COL_FIRSTNAME   = 15
        COL_LAST        = 15
        COL_BIRTH       = 12
        COL_CLUB        = 25
        COL_ASSOCIATION = 15
        COL_WEIGHT      = 12
        COL_GENDER      = 10
        SEPARATOR_LENGTH = (
            COL_FIRSTNAME + COL_LAST + COL_BIRTH + COL_CLUB
            + COL_ASSOCIATION + COL_WEIGHT + COL_GENDER + 4
        )

        header = (
            f"{'Vorname':<{COL_FIRSTNAME}}{'Nachname':<{COL_LAST}}"
            f"{'Jahrgang':<{COL_BIRTH}}{'Verein':<{COL_CLUB}}"
            f"{'Verband':<{COL_ASSOCIATION}}{'Gewicht':<{COL_WEIGHT}}"
            f"{'Geschl.':<{COL_GENDER}}\n"
        )
        text_widget.insert(tk.END, header, 'header')
        text_widget.insert(tk.END, "─" * SEPARATOR_LENGTH + "\n")

        for idx, fighter in enumerate(fighters, 1):
            first       = str(fighter.get('Firstname', fighter.get('name', 'N/A')))
            last        = str(fighter.get('Lastname', ''))
            birth       = str(fighter.get('Birthyear', fighter.get('BirthYear')))
            club        = str(fighter.get('Club', fighter.get('Verein', fighter.get('club', 'N/A'))))
            association = str(fighter.get('Association', ''))
            gender_val  = str(fighter.get('Gender', ''))
            weight      = fighter.get('Weight', 'N/A')

            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.4f}".rstrip('0')
                if weight_str.endswith('.'):
                    weight_str += '0'
            else:
                weight_str = str(weight)

            if gender_val.lower() == 'female':
                gender_display = 'weiblich'
            elif gender_val.lower() == 'male':
                gender_display = 'männlich'
            else:
                gender_display = gender_val

            row = (
                f"{first:<{COL_FIRSTNAME}}{last:<{COL_LAST}}{birth:<{COL_BIRTH}}"
                f"{club:<{COL_CLUB}}{association:<{COL_ASSOCIATION}}"
                f"{weight_str:<{COL_WEIGHT}}{gender_display:<{COL_GENDER}}\n"
            )
            text_widget.insert(tk.END, row, f'row_{idx}')

        text_widget.tag_configure('header', font=FONTS['list_mono_bold'], foreground=COLORS['accent_blue'])
        text_widget.tag_configure('row_selected', background=COLORS['accent_blue'], foreground=COLORS['text_primary'])

        for i in range(1, count + 1):
            text_widget.tag_bind(f'row_{i}', '<Button-1>', lambda e, row_num=i: self._on_row_click(text_widget, row_num, count))

        text_widget.config(state=tk.DISABLED)

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
        """Open the friendly match dialog."""
        parent = self.main_frame.winfo_toplevel() if hasattr(self, 'main_frame') else self
        FriendlyMatchDialog(parent, self.brackets, on_success=self._populate_group_list)

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
