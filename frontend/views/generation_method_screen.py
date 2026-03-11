# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Generation Method Screen - Assign brackets to generation methods (Pools, Double Pools, KO, Special)

This screen allows users to choose which generation method each bracket will use.
Displays unassigned brackets on the left and 4 method tables on the right in a 2x2 grid.
"""

import tkinter as tk
from tkinter import messagebox, ttk
import sys
import os
import threading

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger, DEBUG_VERBOSE  # noqa: E402
from backend.data.repositories.config_repository import ConfigRepository  # noqa: E402
from ..utils.search_utils import filter_items  # noqa: E402
from ..styles import (  # noqa: E402
    COLORS, FONTS,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    create_dark_frame,
)
logger = get_logger('generation_method_screen', debug_verbose=DEBUG_VERBOSE)


class GenerationMethodScreen(tk.Frame):
    """
    Screen for assigning brackets to generation methods.
    
    Displays unassigned brackets and 4 tables for different generation strategies:
    - Pools (≤5 fighters)
    - Double Pools (6-10 fighters)
    - KO Brackets (11+ fighters)
    - Special Cases (edge cases)
    """

    # Debug flag - set to True for verbose logging
    DEBUG = DEBUG_VERBOSE

    # Method constants
    METHOD_POOLS = 'pools'
    METHOD_DOUBLE = 'double'
    METHOD_KO = 'ko'
    METHOD_SPECIAL = 'special'

    def __init__(self, parent, main_window=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.main_window = main_window

        # Data
        self.brackets = {}  # {bracket_key: {"tuple": bracket_tuple, "method": method_name}}
        self.unassigned = []  # List of bracket keys
        self.filtered_keys = []  # Current filtered list
        self.selected_unassigned = None  # Currently selected in unassigned list
        self.selected_in_tables = {}  # {method: selected_key}

        # UI references
        self.main_frame = None
        self.unassigned_listbox = None
        self.search_entry = None
        self.tables = {}  # {method: {listbox, unassign_btn}}
        self.ui_initialized = False  # Track if UI has been built
        
        # Callbacks (for new navigation system)
        self.on_back_callback = None  # Callback when back button clicked
        self.on_generation_complete = None  # Callback when generation complete with final assignments
        
        # Load method labels from config
        self.method_labels = {}  # {method_key: {'ButtonLabel': str, 'DisplayLabel': str}}
        self._load_method_labels()
        
        # Initialize UI only once
        self.init_ui()
    
    def _load_method_labels(self):
        """Load generation method labels from config."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'bracket_config.xlsx')
            if os.path.exists(config_path):
                config = ConfigRepository(config_path)
                methods = config.get_generation_methods()
                self.method_labels = methods
                if self.DEBUG:
                    self.logger.debug(f"DEBUG: Loaded {len(methods)} generation methods from config")
        except Exception as e:
            self.logger.warning(f"Could not load generation methods from config: {e}")
            # Fall back to empty labels
            self.method_labels = {}
    
    def _get_button_label(self, method_key):
        """Get button label for a method key."""
        if method_key in self.method_labels:
            return self.method_labels[method_key].get('ButtonLabel', method_key)
        return method_key
    
    def _get_display_label(self, method_key):
        """Get display label for a method key (for table titles)."""
        if method_key in self.method_labels:
            return self.method_labels[method_key].get('DisplayLabel', method_key)
        return method_key

    def load_data(self, brackets_dict=None):
        """
        Load bracket data and initialize UI.
        
        Args:
            brackets_dict: Dict of {bracket_key: bracket_tuple} or 
                          {bracket_key: {"tuple": bracket_tuple, "method": method_name, ...}}
        """
        self.logger.debug(f"[GEN_METHOD] load_data called with brackets_dict={type(brackets_dict)} (len={len(brackets_dict) if brackets_dict else 0})")
        
        if brackets_dict:
            self.brackets = {}
            self.unassigned = []
            assigned_brackets = {}  # Track pre-assigned brackets

            # Normalize bracket data
            for key, data in brackets_dict.items():
                if isinstance(data, dict) and "tuple" in data:
                    bracket_tuple = data["tuple"]
                    method = data.get("method", None)
                else:
                    bracket_tuple = data
                    method = None

                self.brackets[key] = {
                    "tuple": bracket_tuple,
                    "method": method,
                }

                # Skip empty brackets (0 fighters) — they were merged away
                fighter_count = len(bracket_tuple) if isinstance(bracket_tuple, list) else 0
                if fighter_count == 0:
                    self.logger.debug(f"[GEN_METHOD] Skipping empty bracket: {key}")
                    continue

                if method is None:
                    self.unassigned.append(key)
                else:
                    assigned_brackets[key] = method

            self.filtered_keys = self.unassigned.copy()
            self.logger.info(f"[GEN_METHOD] Loaded {len(self.brackets)} brackets, {len(self.unassigned)} unassigned, {len(assigned_brackets)} cached")
            if self.DEBUG:
                self.logger.debug(f"DEBUG: Bracket keys: {list(self.brackets.keys())}")
                self.logger.debug(f"DEBUG: Unassigned keys: {self.unassigned}")
                if assigned_brackets:
                    self.logger.debug(f"DEBUG: Cached assignments: {assigned_brackets}")
        else:
            self.logger.warning("[GEN_METHOD] load_data called with None or empty brackets_dict!")
        
        # Refresh all displays with loaded data
        self.logger.debug(f"[GEN_METHOD] Refreshing displays with {len(self.unassigned)} unassigned brackets")
        self._refresh_all_displays()

    def init_ui(self):
        """Initialize the user interface. Only build once."""
        if self.ui_initialized:
            self.logger.debug("UI already initialized, skipping rebuild")
            return

        # --- TITLE ---
        title = tk.Label(
            self,
            text="Assign Generation Method to Brackets",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            font=FONTS['heading_lg'],
        )
        title.pack(pady=10)

        # --- SEARCH & CONTROL BAR ---
        control_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        back_btn = tk.Button(
            control_frame,
            text="← Back",
            command=self.on_back,
        )
        apply_button_style(back_btn, style='secondary')
        back_btn.pack(side=tk.LEFT, padx=5)

        search_label = tk.Label(control_frame, text="Search:", bg=COLORS['bg_dark'], fg=COLORS['text_primary'])
        search_label.pack(side=tk.LEFT, padx=5)

        self.search_entry = tk.Entry(control_frame, width=30, bg=COLORS['bg_input'], fg=COLORS['text_primary'])
        apply_entry_style(self.search_entry)
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind('<KeyRelease>', lambda e: self.on_search())

        auto_assign_btn = tk.Button(
            control_frame,
            text="Auto-Assign",
            command=self.on_auto_assign,
        )
        apply_button_style(auto_assign_btn, style='primary')
        auto_assign_btn.pack(side=tk.LEFT, padx=5)

        close_btn = tk.Button(
            control_frame,
            text="Proceed",
            command=self.on_close,
        )
        apply_button_style(close_btn, style='success')
        close_btn.pack(side=tk.LEFT, padx=5)

        # --- MAIN CONTENT FRAME ---
        self.main_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT PANEL: Unassigned Brackets
        left_panel = create_dark_frame(self.main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        # Left title
        left_title = tk.Label(
            left_panel,
            text="Unassigned Brackets",
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['heading_md'],
        )
        apply_label_style(left_title, 'heading_md')
        left_title.pack(pady=5)

        # Unassigned list with scrollbar
        list_frame = tk.Frame(left_panel, bg=COLORS['bg_panel'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.unassigned_listbox = tk.Listbox(
            list_frame,
            bg=COLORS['bg_input'],
            fg=COLORS['text_primary'],
            yscrollcommand=scrollbar.set,
            font=FONTS['body_sm'],
            width=20,
            height=25,
        )
        apply_listbox_style(self.unassigned_listbox)
        self.unassigned_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.unassigned_listbox.bind('<<ListboxSelect>>', self.on_unassigned_select)
        scrollbar.config(command=self.unassigned_listbox.yview)

        # Method assignment buttons (4 buttons for 4 methods)
        buttons_frame = tk.Frame(left_panel, bg=COLORS['bg_panel'])
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        pools_btn = tk.Button(
            buttons_frame,
            text=self._get_button_label(self.METHOD_POOLS),
            command=lambda: self.on_assign_to_method(self.METHOD_POOLS),
        )
        apply_button_style(pools_btn, style='secondary')
        pools_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        double_btn = tk.Button(
            buttons_frame,
            text=self._get_button_label(self.METHOD_DOUBLE),
            command=lambda: self.on_assign_to_method(self.METHOD_DOUBLE),
        )
        apply_button_style(double_btn, style='secondary')
        double_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        ko_btn = tk.Button(
            buttons_frame,
            text=self._get_button_label(self.METHOD_KO),
            command=lambda: self.on_assign_to_method(self.METHOD_KO),
        )
        apply_button_style(ko_btn, style='secondary')
        ko_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        special_btn = tk.Button(
            buttons_frame,
            text=self._get_button_label(self.METHOD_SPECIAL),
            command=lambda: self.on_assign_to_method(self.METHOD_SPECIAL),
        )
        apply_button_style(special_btn, style='secondary')
        special_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # RIGHT PANEL: 4 Tables in 2x2 Grid
        right_panel = tk.Frame(self.main_frame, bg=COLORS['bg_dark'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # Create 2x2 grid
        self.tables = {}

        # Top row
        top_row = tk.Frame(right_panel, bg=COLORS['bg_dark'])
        top_row.pack(fill=tk.BOTH, expand=True, pady=5)

        self._create_method_table(top_row, self.METHOD_POOLS, self._get_display_label(self.METHOD_POOLS), side=tk.LEFT)
        self._create_method_table(top_row, self.METHOD_DOUBLE, self._get_display_label(self.METHOD_DOUBLE), side=tk.LEFT)

        # Bottom row
        bottom_row = tk.Frame(right_panel, bg=COLORS['bg_dark'])
        bottom_row.pack(fill=tk.BOTH, expand=True, pady=5)

        self._create_method_table(bottom_row, self.METHOD_KO, self._get_display_label(self.METHOD_KO), side=tk.LEFT)
        self._create_method_table(bottom_row, self.METHOD_SPECIAL, self._get_display_label(self.METHOD_SPECIAL), side=tk.LEFT)

        # Refresh display
        self._refresh_all_displays()
        
        # Mark UI as successfully initialized
        self.ui_initialized = True
        self.logger.debug("[GEN_METHOD] UI initialized successfully")

    def _create_method_table(self, parent, method_key, title, side):
        """Create a table for a generation method."""

        frame = create_dark_frame(parent)
        frame.pack(side=side, fill=tk.BOTH, expand=True, padx=5)

        # Table title
        title_label = tk.Label(
            frame,
            text=title,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['heading_md'],
        )
        apply_label_style(title_label, 'subtitle')
        title_label.pack(pady=5)

        # Listbox with scrollbar
        list_frame = tk.Frame(frame, bg=COLORS['bg_panel'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            list_frame,
            bg=COLORS['bg_input'],
            fg=COLORS['text_primary'],
            yscrollcommand=scrollbar.set,
            font=FONTS['body_sm'],
            height=8,
        )
        apply_listbox_style(listbox)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        listbox.bind('<<ListboxSelect>>', lambda e, m=method_key: self.on_table_select(m, e))
        scrollbar.config(command=listbox.yview)

        # Unassign button
        unassign_btn = tk.Button(
            frame,
            text="×",
            command=lambda m=method_key: self.on_unassign_from_table(m),
            width=3,
        )
        apply_button_style(unassign_btn, style='secondary')
        unassign_btn.pack(pady=5, padx=5)

        self.tables[method_key] = {
            'listbox': listbox,
            'unassign_btn': unassign_btn,
        }

    def on_back(self):
        """Go back to group preview screen."""
        self.logger.info("User navigated back to group preview")
        # Use new callback if available
        if self.on_back_callback and callable(self.on_back_callback):
            self.on_back_callback()
        # Fallback for backward compatibility
        elif hasattr(self.master, 'show_group_preview_window'):
            self.master.show_group_preview_window()

    def on_search(self):
        """Filter unassigned brackets by search term (supports multiple terms with AND logic)."""
        search_term = self.search_entry.get()
        
        # Use shared search utility
        filtered, matched_count, search_terms = filter_items(self.unassigned, search_term)
        self.filtered_keys = filtered
        
        if search_terms:
            self.logger.debug(f"Search terms: {search_terms}, found {matched_count} brackets")
        else:
            self.logger.debug("Search cleared - showing all unassigned brackets")
        
        self._refresh_unassigned_display()

    def on_unassigned_select(self, event):
        """Handle selection in unassigned listbox."""
        selection = self.unassigned_listbox.curselection()
        if selection:
            idx = selection[0]
            self.selected_unassigned = self.filtered_keys[idx]
            self.logger.debug(f"Selected unassigned bracket: {self.selected_unassigned}")

    def on_table_select(self, method, event):
        """Handle selection in method table."""
        listbox = self.tables[method]['listbox']
        selection = listbox.curselection()
        if selection:
            idx = selection[0]
            display_text = listbox.get(idx)
            # Reverse-lookup: find bracket key whose formatted display matches
            bracket_key = next(
                (k for k in self.brackets
                 if self._format_bracket_display(k, self.brackets[k]["tuple"]) == display_text),
                None,
            )
            if bracket_key:
                self.selected_in_tables[method] = bracket_key
            self.logger.debug(f"Selected bracket in {method} table: {bracket_key}")

    def on_assign_to_method(self, method):
        """Assign selected unassigned bracket to specified method."""
        if not self.selected_unassigned:
            self.logger.debug("Assign action failed: no bracket selected")
            messagebox.showwarning("Warning", "Please select a bracket from the unassigned list")
            return

        self.logger.debug(f"Assigning {self.selected_unassigned} to {method}")
        self._assign_bracket(self.selected_unassigned, method)
        self.selected_unassigned = None  # Clear selection after assignment
        self.unassigned_listbox.selection_clear(0, tk.END)

    def on_unassign_from_table(self, method):
        """Unassign selected bracket from a method."""
        if method not in self.selected_in_tables:
            self.logger.debug(f"Unassign action failed: no bracket selected in {method} table")
            messagebox.showwarning("Warning", "Please select a bracket from the table")
            return

        bracket_key = self.selected_in_tables[method]
        self.logger.debug(f"Unassigning {bracket_key} from {method}")
        self._unassign_bracket(bracket_key)

    def on_auto_assign(self):
        """Automatically assign all unassigned brackets based on fighter count."""
        if not self.unassigned:
            messagebox.showinfo("Info", "All brackets are already assigned!")
            return

        # Run in background thread to avoid UI freeze
        thread = threading.Thread(target=self._auto_assign_worker)
        thread.daemon = True
        thread.start()

    def _auto_assign_worker(self):
        """Background worker for auto-assignment."""
        try:
            assigned_count = 0

            for bracket_key in self.unassigned.copy():
                bracket_data = self.brackets[bracket_key]
                bracket_tuple = bracket_data["tuple"]

                # Count fighters in bracket
                fighter_count = self._count_fighters(bracket_tuple)

                # Recommend method (pass bracket_key for age group checking)
                method = self._recommend_method(fighter_count, bracket_key)

                # Assign
                self._assign_bracket(bracket_key, method)
                assigned_count += 1

            self.logger.info(f"Auto-assigned {assigned_count} brackets")
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Auto-assigned {assigned_count} brackets"))

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Auto-assign error: {e}")
            self.master.after(0, lambda msg=error_msg: messagebox.showerror("Error", msg))

    def _assign_bracket(self, bracket_key, method):
        """Assign a bracket to a method."""
        if bracket_key not in self.brackets:
            if self.DEBUG:
                self.logger.debug(f"DEBUG: Cannot assign - bracket {bracket_key} not found")
            return

        self.brackets[bracket_key]["method"] = method

        if bracket_key in self.unassigned:
            self.unassigned.remove(bracket_key)
            self.filtered_keys = [k for k in self.filtered_keys if k != bracket_key]

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Assigned {bracket_key} → {method}. Unassigned remaining: {self.unassigned}")
        self._refresh_all_displays()
        self.logger.info(f"Assigned {bracket_key} to {method}")

    def _unassign_bracket(self, bracket_key):
        """Unassign a bracket from a method."""
        if bracket_key not in self.brackets:
            if self.DEBUG:
                self.logger.debug(f"DEBUG: Cannot unassign - bracket {bracket_key} not found")
            return

        old_method = self.brackets[bracket_key]["method"]
        self.brackets[bracket_key]["method"] = None

        if bracket_key not in self.unassigned:
            self.unassigned.append(bracket_key)
            self.filtered_keys.append(bracket_key)

        if self.DEBUG:
            self.logger.debug(f"DEBUG: Unassigned {bracket_key} from {old_method}. Unassigned now: {self.unassigned}")
        self._refresh_all_displays()
        self.logger.info(f"Unassigned {bracket_key}")

    def _refresh_all_displays(self):
        """Refresh all listbox displays."""
        self.logger.debug(f"[GEN_METHOD] _refresh_all_displays called with {len(self.unassigned)} unassigned")
        self._refresh_unassigned_display()
        for method in self.tables.keys():
            self._refresh_method_display(method)
        self.logger.debug("[GEN_METHOD] _refresh_all_displays complete")

    def _refresh_unassigned_display(self):
        """Refresh unassigned brackets listbox."""
        self.logger.debug(f"[GEN_METHOD] _refresh_unassigned_display checking unassigned_listbox={self.unassigned_listbox is not None}")
        if not self.unassigned_listbox:
            self.logger.warning("[GEN_METHOD] unassigned_listbox is None!")
            return
        self.unassigned_listbox.delete(0, tk.END)
        
        self.logger.debug(f"[GEN_METHOD] Populating unassigned listbox with {len(self.filtered_keys)} items")
        for bracket_key in self.filtered_keys:
            bracket_data = self.brackets[bracket_key]
            display_text = self._format_bracket_display(bracket_key, bracket_data["tuple"])
            self.unassigned_listbox.insert(tk.END, display_text)
            self.logger.debug(f"[GEN_METHOD] Added to unassigned: {display_text}")

    def _refresh_method_display(self, method):
        """Refresh a method table display."""
        if method not in self.tables:
            return
        listbox = self.tables[method]['listbox']
        if not listbox:
            return
        listbox.delete(0, tk.END)

        for bracket_key, bracket_data in self.brackets.items():
            if bracket_data["method"] == method:
                display_text = self._format_bracket_display(bracket_key, bracket_data["tuple"])
                listbox.insert(tk.END, display_text)

    def _count_fighters(self, bracket_tuple):
        """Count fighters in a bracket tuple (list of fighter dicts)."""
        if isinstance(bracket_tuple, list):
            return len(bracket_tuple)
        return 0

    def _format_bracket_display(self, bracket_key, bracket_tuple):
        """Return the listbox display string for a bracket.

        For U9/U11 pool keys (e.g. "U11 | Pool 1") the format is:
            "U11 | Pool 1 | 4 * 6 | bis 28.5 kg"
        where  4  = number of fighters,  6  = round-robin fights (n*(n-1)/2),
        and  28.5 kg  = max weight in this pool.

        All other brackets: "<key> (<n>)"
        """
        is_u9_u11_pool = (
            isinstance(bracket_tuple, list) and
            bracket_tuple and
            ('U9 | Pool' in bracket_key or 'U11 | Pool' in bracket_key)
        )

        if is_u9_u11_pool:
            n = len(bracket_tuple)
            try:
                max_weight = max(f.get('Weight', 0) for f in bracket_tuple)
                weight_str = f"{max_weight:g}"
            except (TypeError, ValueError):
                weight_str = '?'
            return f"{bracket_key} | -{weight_str}kg ({n})"

        fighter_count = self._count_fighters(bracket_tuple)
        return f"{bracket_key} ({fighter_count})"

    def _recommend_method(self, fighter_count, bracket_key=None):
        """Recommend a generation method based on fighter count using config thresholds.
        
        Note: U9 and U11 age groups always use 'pools' method since they have configurable 
        pool sizes instead of fixed weight classes.
        """
        # Force U9 and U11 to pools method (they use configurable pool sizes)
        if bracket_key and ('U9' in bracket_key or 'U11' in bracket_key):
            if self.DEBUG:
                self.logger.debug(f"DEBUG: {bracket_key} is U9/U11 → force pools")
            return self.METHOD_POOLS
        
        # If no thresholds loaded, use fallback
        if not self.method_labels:
            if fighter_count < 3:
                method = self.METHOD_SPECIAL
            elif fighter_count <= 5:
                method = self.METHOD_POOLS
            elif fighter_count <= 10:
                method = self.METHOD_DOUBLE
            else:
                method = self.METHOD_KO
        else:
            # Find method by fighter count range from config
            method = None
            for method_key, config in self.method_labels.items():
                min_fighters = config.get('MinFighters', 0)
                max_fighters = config.get('MaxFighters', 999)
                if min_fighters <= fighter_count < max_fighters:
                    method = method_key
                    break
            
            # Fallback to KO if no method matches
            if method is None:
                method = self.METHOD_KO
        
        if self.DEBUG:
            self.logger.debug(f"DEBUG: {fighter_count} fighters → recommend {method}")
        return method

    def on_close(self):
        """Proceed with bracket generation after assignment."""
        unassigned_count = len(self.unassigned)

        if unassigned_count > 0:
            result = messagebox.askyesno(
                "Warning",
                f"You have {unassigned_count} unassigned brackets. Continue anyway?",
            )
            if not result:
                return

        # Prepare final data
        final_brackets = {k: v['method'] for k, v in self.brackets.items()}

        self.logger.info(f"Finalized bracket assignments: {final_brackets}")
        if self.DEBUG:
            methods_count = {}
            for method in final_brackets.values():
                methods_count[method] = methods_count.get(method, 0) + 1
            self.logger.debug(f"DEBUG: Final distribution - {methods_count}")

        # Call callback if available (new callback system)
        if self.on_generation_complete:
            self.on_generation_complete(final_brackets)
        # Fallback for backward compatibility with old system
        elif hasattr(self.master, 'on_generation_methods_selected'):
            self.master.on_generation_methods_selected(final_brackets)
        else:
            self.logger.warning("No callback set for generation method selection")
            messagebox.showinfo("Success", "Bracket assignments finalized!")

    def on_show(self, force_reload=False):
        """Lifecycle hook called when screen is displayed."""
        self.logger.debug(f"[LIFECYCLE] GenerationMethodScreen.on_show(force_reload={force_reload})")
        if force_reload and self.main_window:
            # Reload brackets from main_window cache
            # Convert main_window.brackets format (with 'fighters' key) to load_data format (with 'tuple' key)
            brackets_dict = {}
            for bracket_key, bracket_data in self.main_window.brackets.items():
                fighters = bracket_data.get('fighters', [])
                cached_method = self.main_window.bracket_generation_methods.get(bracket_key)
                brackets_dict[bracket_key] = {
                    'tuple': fighters,
                    'method': cached_method,
                }
            self.logger.debug("[LIFECYCLE] on_show reload: converted main_window.brackets to load_data format")
            self.load_data(brackets_dict)
            self.logger.info("[RELOAD] GenerationMethodScreen data reloaded from cache")

    def _convert_brackets_to_local_format(self, main_brackets):
        """Convert main_window.brackets to local format."""
        converted = {}
        for bracket_key, bracket_data in main_brackets.items():
            converted[bracket_key] = {
                "tuple": bracket_data,
                "method": None  # Will be assigned by user
            }
        return converted

    def _refresh_display(self):
        """Refresh the UI after data reload."""
        self.unassigned = list(self.brackets.keys())
        self.filtered_keys = self.unassigned
        self._refresh_all_displays()
        self.logger.debug(f"[RELOAD] Display refreshed - {len(self.unassigned)} unassigned brackets")

    def on_close_screen(self):
        """Cleanup when screen is hidden."""
        pass
