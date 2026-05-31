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
from datetime import datetime

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger, DEBUG_VERBOSE  # noqa: E402
from utils.helpers import (  # noqa: E402
    age_group_from_bracket_key,
    bracket_key_matches_age_lock,
    bracket_sort_key,
    format_bracket_label,
)
from backend.data.repositories.config_repository import ConfigRepository  # noqa: E402
from backend.services.bracket_excel_generator import BracketExcelGenerator  # noqa: E402
from backend.services.pool_excel_generator import PoolExcelGenerator  # noqa: E402
from ..utils.search_utils import filter_items  # noqa: E402
from ..utils.pool_renderer import split_into_pools  # noqa: E402
from ..styles import (  # noqa: E402
    COLORS, FONTS, SPACING,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    create_panel_frame,
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
        
        # Print tracking - prevents accidental reprints and maintains audit trail
        self.printed_brackets = {}  # {bracket_key: datetime_printed}
        
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
        label = method_key
        if method_key in self.method_labels:
            label = self.method_labels[method_key].get('ButtonLabel', method_key)
        
        # UI Translation
        translation_map = {
            'Pools': 'Pools',
            'Double': 'Doppel',
            'KO': 'KO',
            'Special': 'Spezial'
        }
        return translation_map.get(label, label)
    
    def _get_display_label(self, method_key):
        """Get display label for a method key (for table titles)."""
        label = method_key
        if method_key in self.method_labels:
            label = self.method_labels[method_key].get('DisplayLabel', method_key)
            
        # UI Translation
        translation_map = {
            'Pools (≤5 fighters)': 'Pools (≤5 Kämpfer)',
            'Double Pools (6-10)': 'Doppel-Pools (6-10)',
            'KO Brackets (11+)': 'KO-System (11+)',
            'Special Cases': 'Sonderfälle'
        }
        return translation_map.get(label, label)

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
            text="Wettkampfliste zu Methode zuweisen",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
        )
        apply_label_style(title, 'heading_xl')
        title.pack(pady=SPACING['md'])

        # --- SEARCH & CONTROL BAR ---
        control_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        control_frame.pack(fill=tk.X, padx=SPACING['md'], pady=SPACING['sm'])

        back_btn = tk.Button(
            control_frame,
            text="← Zurück",
            command=self.on_back,
        )
        apply_button_style(back_btn, style='secondary')
        back_btn.pack(side=tk.LEFT, padx=SPACING['sm'])

        search_lbl = tk.Label(control_frame, text="Suche:", bg=COLORS['bg_dark'], fg=COLORS['text_primary'])
        search_lbl.pack(side=tk.LEFT, padx=SPACING['sm'])

        self.search_entry = tk.Entry(control_frame, width=30, bg=COLORS['bg_input'], fg=COLORS['text_primary'])
        apply_entry_style(self.search_entry)
        self.search_entry.pack(side=tk.LEFT, padx=SPACING['sm'], fill=tk.X, expand=True)
        self.search_entry.bind('<KeyRelease>', lambda e: self.on_search())

        auto_assign_btn = tk.Button(
            control_frame,
            text="Auto-Zuweisung",
            command=self.on_auto_assign,
        )
        apply_button_style(auto_assign_btn, style='primary')
        auto_assign_btn.pack(side=tk.LEFT, padx=SPACING['sm'])

        close_btn = tk.Button(
            control_frame,
            text="Weiter",
            command=self.on_close,
        )
        apply_button_style(close_btn, style='success')
        close_btn.pack(side=tk.LEFT, padx=SPACING['sm'])

        # --- MAIN CONTENT FRAME ---
        self.main_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=SPACING['md'], pady=SPACING['md'])

        # LEFT PANEL: Unassigned Brackets
        left_panel = create_panel_frame(self.main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=SPACING['sm'], pady=SPACING['sm'])

        # Left title
        left_title = tk.Label(
            left_panel,
            text="Offene Listen",
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=FONTS['heading_md'],
        )
        apply_label_style(left_title, 'heading_md')
        left_title.pack(pady=SPACING['sm'])

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
            width=15,
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

        # Export buttons frame (separate row below method buttons)
        export_buttons_frame = tk.Frame(left_panel, bg=COLORS['bg_panel'])
        export_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        print_selected_btn = tk.Button(
            export_buttons_frame,
            text="Auswahl drucken",
            command=self.on_print_selected,
        )
        apply_button_style(print_selected_btn, style='secondary')
        print_selected_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        export_all_btn = tk.Button(
            export_buttons_frame,
            text="Alle exportieren",
            command=self.on_export_all,
        )
        apply_button_style(export_all_btn, style='success')
        export_all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        urkunden_btn = tk.Button(
            export_buttons_frame,
            text="Urkunden…",
            command=self.on_export_urkunden,
        )
        apply_button_style(urkunden_btn, style='success')
        urkunden_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

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

        frame = create_panel_frame(parent)
        frame.pack(side=side, fill=tk.BOTH, expand=True, padx=SPACING['sm'])

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
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Bracket aus der Liste aus")
            return

        self.logger.debug(f"Assigning {self.selected_unassigned} to {method}")
        self._assign_bracket(self.selected_unassigned, method)
        self.selected_unassigned = None  # Clear selection after assignment
        self.unassigned_listbox.selection_clear(0, tk.END)

    def on_unassign_from_table(self, method):
        """Unassign selected bracket from a method."""
        if method not in self.selected_in_tables:
            self.logger.debug(f"Unassign action failed: no bracket selected in {method} table")
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Bracket aus der Tabelle aus")
            return

        bracket_key = self.selected_in_tables[method]
        self.logger.debug(f"Unassigning {bracket_key} from {method}")
        self._unassign_bracket(bracket_key)

    def on_auto_assign(self):
        """Automatically assign all unassigned brackets based on fighter count."""
        if not self.unassigned:
            messagebox.showinfo("Info", "Alle Listen sind bereits zugewiesen!")
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
            self.master.after(0, lambda: messagebox.showinfo("Erfolg", f"{assigned_count} Listen automatisch zugewiesen"))

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Auto-assign error: {e}")
            self.master.after(0, lambda msg=error_msg: messagebox.showerror("Fehler", msg))

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
        
        # Mark downstream screens as stale (bracket structure changed - affects bracket_viewer and fight_monitoring)
        if self.main_window and hasattr(self.main_window, 'screen_manager'):
            self.main_window.screen_manager.invalidate_downstream('generation_method')
            self.logger.debug("Marked downstream screens as stale due to bracket method assignment")

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
        
        # Mark downstream screens as stale (bracket structure changed - affects bracket_viewer and fight_monitoring)
        if self.main_window and hasattr(self.main_window, 'screen_manager'):
            self.main_window.screen_manager.invalidate_downstream('generation_method')
            self.logger.debug("Marked downstream screens as stale due to bracket method unassignment")

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

        # P3 — Sort by Age → Gender → Weight (Quarantine first) before display.
        # Sorting at render time keeps `self.filtered_keys` semantically free
        # (search adds/removes, the order doesn't have to be maintained there).
        ordered_keys = sorted(self.filtered_keys, key=bracket_sort_key)

        self.logger.debug(f"[GEN_METHOD] Populating unassigned listbox with {len(ordered_keys)} items")
        for bracket_key in ordered_keys:
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

        # P3 — Age → Gender → Weight order for assigned brackets too.
        assigned_keys = sorted(
            (k for k, d in self.brackets.items() if d["method"] == method),
            key=bracket_sort_key,
        )
        for bracket_key in assigned_keys:
            bracket_data = self.brackets[bracket_key]
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
        
        Adds ✓ indicator if bracket has been printed.
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
            # U9/U11 pool keys are already "U11 | Pool 1" — no gender slot
            # to reorder, just append weight + count.
            display_text = f"{bracket_key} | -{weight_str}kg ({n})"
        else:
            fighter_count = self._count_fighters(bracket_tuple)
            # P3 — display label in sort order (Age | Gender | Weight).
            display_text = f"{format_bracket_label(bracket_key)} ({fighter_count})"

        # P6 — surface age-class lock so the user sees why a bracket can't be edited.
        locks = getattr(self.main_window, 'locked_age_classes', set()) if self.main_window else set()
        if bracket_key_matches_age_lock(bracket_key, locks):
            age = age_group_from_bracket_key(bracket_key) or ''
            display_text += f" [Gesperrt {age}]".rstrip()
        
        # Add print status indicator
        if bracket_key in self.printed_brackets:
            display_text += " ✓"
        
        return display_text

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
                "Warnung",
                f"Sie haben {unassigned_count} nicht zugewiesene Listen. Trotzdem fortfahren?",
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
            messagebox.showinfo("Erfolg", "Zuweisung abgeschlossen!")

    def on_print_selected(self):
        """Generate Excel for the currently selected bracket only."""
        selected_bracket = self.selected_unassigned or (
            self.selected_in_tables.get(self.METHOD_POOLS) or
            self.selected_in_tables.get(self.METHOD_DOUBLE) or
            self.selected_in_tables.get(self.METHOD_KO) or
            self.selected_in_tables.get(self.METHOD_SPECIAL)
        )
        
        if not selected_bracket:
            self.logger.debug("Print selected action failed: no bracket selected")
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Bracket zum Drucken aus")
            return
        
        bracket_data = self.brackets.get(selected_bracket)
        if not bracket_data:
            self.logger.error(f"Bracket not found: {selected_bracket}")
            messagebox.showerror("Fehler", f"Bracket-Daten nicht gefunden: {selected_bracket}")
            return
        
        method = bracket_data.get("method")
        if not method:
            self.logger.warning(f"Bracket has no assigned method: {selected_bracket}")
            messagebox.showwarning("Warnung", "Bitte weisen Sie eine Methode zum Drucken zu")
            return
        
        # Check if already printed
        if selected_bracket in self.printed_brackets:
            printed_time = self.printed_brackets[selected_bracket].strftime("%Y-%m-%d %H:%M:%S")
            result = messagebox.askyesno(
                "Bereits gedruckt",
                f"This bracket was printed on {printed_time}.\nPrint again?",
            )
            if not result:
                self.logger.info(f"User cancelled reprint of: {selected_bracket}")
                return
            self.logger.info(f"User approved reprint of: {selected_bracket}")
        
        # Submit to TaskRunner with proper callbacks
        if self.main_window and hasattr(self.main_window, 'task_runner'):
            self.main_window.task_runner.submit_task(
                'export_bracket',
                fn=lambda on_progress=None: self._excel_export_worker_fn([selected_bracket], on_progress),
                on_progress=self._on_export_progress,
                on_error=self._on_export_error,
                on_complete=self._on_export_complete,
            )
            self.logger.info(f"Export task submitted to TaskRunner for: {selected_bracket}")
        else:
            self.logger.warning("TaskRunner not available, falling back to direct threading")
            thread = threading.Thread(
                target=self._excel_export_worker,
                args=([selected_bracket],),
                daemon=True,
            )
            thread.start()

    def on_export_all(self):
        """Generate Excel files for all currently assigned brackets."""
        assigned_brackets = [
            k for k, v in self.brackets.items()
            if v.get("method") is not None and len(v.get("tuple", [])) > 0
        ]
        
        if not assigned_brackets:
            self.logger.info("Export all action: no assigned brackets to export")
            messagebox.showinfo("Info", "Keine zugewiesenen Brackets zum Exportieren")
            return
        
        self.logger.info(f"Exporting {len(assigned_brackets)} assigned brackets via TaskRunner")
        
        # Show progress dialog
        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.show_loading_progress(
                f"{len(assigned_brackets)} Brackets werden exportiert..."
            )
        
        # Submit to TaskRunner with proper callbacks
        if self.main_window and hasattr(self.main_window, 'task_runner'):
            self.main_window.task_runner.submit_task(
                'export_all_brackets',
                fn=lambda on_progress=None: self._excel_export_worker_fn(assigned_brackets, on_progress),
                on_progress=self._on_export_progress,
                on_error=self._on_export_error,
                on_complete=self._on_export_complete,
            )
            self.logger.info(f"Export all task submitted to TaskRunner for {len(assigned_brackets)} brackets")
        else:
            self.logger.warning("TaskRunner not available, falling back to direct threading")
            thread = threading.Thread(
                target=self._excel_export_worker,
                args=(assigned_brackets,),
                daemon=True,
            )
            thread.start()

    def on_export_urkunden(self):
        """Urkunden-Export-Dialog: fertige Klassen auswählen → XLSX-Datenquelle.

        Inkrementell während des Turniers nutzbar. Default-Auswahl = alle noch
        nicht exportierten ("● neu") Klassen. Gedruckt wird anschließend per
        Ein-Klick-Makro in der LibreOffice-Vorlage (siehe assets/urkunden/).
        """
        from backend.services.database_service import (  # noqa: PLC0415
            get_database_service,
        )
        from backend.services import urkunden_export_service as ues  # noqa: PLC0415

        try:
            db = get_database_service()
        except Exception as e:
            self.logger.error(f"Urkunden: DB nicht verfügbar: {e}", exc_info=True)
            messagebox.showerror("Urkunden", f"Datenbank nicht verfügbar:\n{e}")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Urkunden exportieren")
        dialog.configure(bg=COLORS['bg_dark'])
        dialog.geometry("540x470")
        dialog.transient(self.winfo_toplevel())

        info = tk.Label(
            dialog, justify=tk.LEFT, anchor='w',
            bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
            text=("Fertige Klassen auswählen → Exportieren.\n"
                  "●  neu seit letztem Export      ✓  schon exportiert\n"
                  "Danach in der LibreOffice-Vorlage den Druck-Knopf drücken."),
        )
        info.pack(fill=tk.X, padx=10, pady=(10, 6))

        listbox = tk.Listbox(dialog, selectmode=tk.EXTENDED)
        try:
            apply_listbox_style(listbox)
        except Exception:
            pass
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        keys = []  # parallel zur Listbox-Index-Reihenfolge

        def refresh():
            listbox.delete(0, tk.END)
            keys.clear()
            try:
                completed = sorted(db.get_completed_bracket_keys())
            except Exception as e:
                self.logger.error(f"Urkunden refresh: {e}", exc_info=True)
                messagebox.showerror(
                    "Urkunden", f"Konnte fertige Klassen nicht laden:\n{e}",
                    parent=dialog)
                return
            exported = ues.load_exported_keys()
            for key in completed:
                try:
                    n = len(db.get_bracket_placements(key))
                except Exception:
                    n = 0
                is_new = key not in exported
                marker = '●' if is_new else '✓'
                label = ues.compose_class_label(key)
                listbox.insert(tk.END, f"{marker}  {label}  ({n})")
                idx = len(keys)
                keys.append(key)
                if is_new:
                    listbox.selection_set(idx)
            if not completed:
                listbox.insert(tk.END, "(keine fertigen Klassen)")

        def do_export():
            selected = [keys[i] for i in listbox.curselection() if i < len(keys)]
            if not selected:
                messagebox.showinfo(
                    "Urkunden", "Keine Klasse ausgewählt.", parent=dialog)
                return
            try:
                result = ues.UrkundenExportService(db=db).export(selected)
                ues.mark_exported(selected)
            except Exception as e:
                self.logger.error(f"Urkunden-Export: {e}", exc_info=True)
                messagebox.showerror(
                    "Urkunden", f"Export fehlgeschlagen:\n{e}", parent=dialog)
                return
            messagebox.showinfo(
                "Urkunden",
                f"{result['rows']} Urkunden aus {result['brackets']} "
                f"Klasse(n) exportiert nach:\n{result['path']}\n\n"
                "Jetzt in der LibreOffice-Vorlage den Druck-Knopf drücken.",
                parent=dialog)
            refresh()

        btns = tk.Frame(dialog, bg=COLORS['bg_dark'])
        btns.pack(fill=tk.X, padx=10, pady=10)

        refresh_btn = tk.Button(btns, text="Aktualisieren", command=refresh)
        apply_button_style(refresh_btn, style='secondary')
        refresh_btn.pack(side=tk.LEFT, padx=2)

        close_btn = tk.Button(btns, text="Schließen", command=dialog.destroy)
        apply_button_style(close_btn, style='secondary')
        close_btn.pack(side=tk.RIGHT, padx=2)

        export_btn = tk.Button(btns, text="Exportieren", command=do_export)
        apply_button_style(export_btn, style='success')
        export_btn.pack(side=tk.RIGHT, padx=2)

        refresh()

    def _excel_export_worker_fn(self, bracket_keys, on_progress=None):
        """
        TaskRunner-compatible worker function for Excel exports.
        
        Args:
            bracket_keys: List of bracket keys to export
            on_progress: Callback function for progress updates (0-100)
        
        Returns:
            Dictionary with export results: {'success': int, 'reprint': int, 'failed': int, 'errors': []}
        """
        try:
            self._create_export_directory()
            
            success_count = 0
            reprint_count = 0
            error_count = 0
            errors = []
            total = len(bracket_keys)
            
            for idx, bracket_key in enumerate(bracket_keys):
                try:
                    if bracket_key not in self.brackets:
                        self.logger.warning(f"Bracket not found during export: {bracket_key}")
                        error_count += 1
                        errors.append(f"{bracket_key}: Bracket data not found")
                        continue
                    
                    bracket_data = self.brackets[bracket_key]
                    fighters = bracket_data.get("tuple", [])
                    method = bracket_data.get("method")
                    
                    # Skip empty brackets
                    if not fighters or len(fighters) == 0:
                        self.logger.debug(f"Skipping empty bracket: {bracket_key}")
                        continue
                    
                    if not method:
                        self.logger.warning(f"Bracket has no method assigned: {bracket_key}")
                        error_count += 1
                        errors.append(f"{bracket_key}: No method assigned")
                        continue
                    
                    # Check if reprint
                    is_reprint = bracket_key in self.printed_brackets
                    
                    # Export based on method
                    success = self._export_bracket_to_excel(bracket_key, method, fighters)
                    
                    if success:
                        self._mark_bracket_printed(bracket_key)
                        if is_reprint:
                            reprint_count += 1
                            self.logger.info(f"[REPRINT] {bracket_key} ({method})")
                        else:
                            success_count += 1
                            self.logger.info(f"[EXPORT] {bracket_key} ({method})")
                    else:
                        error_count += 1
                        errors.append(f"{bracket_key}: Export failed")
                        self.logger.error(f"Failed to export {bracket_key}")
                
                except Exception as e:
                    error_count += 1
                    error_msg = str(e)
                    errors.append(f"{bracket_key}: {error_msg}")
                    self.logger.error(f"Error exporting {bracket_key}: {e}", exc_info=True)
                
                # Update progress
                if on_progress:
                    progress_pct = int((idx + 1) / total * 100)
                    on_progress(progress_pct)
            
            result = {
                'success': success_count,
                'reprint': reprint_count,
                'failed': error_count,
                'errors': errors,
            }
            self.logger.info(f"Export worker completed: {result}")
            return result
        
        except Exception as e:
            self.logger.error(f"Excel export worker failed: {e}", exc_info=True)
            raise

    def _on_export_progress(self, progress_value):
        """Called when export progress is updated (0-100)."""
        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.update_progress(progress_value)
            self.logger.debug(f"Export progress: {progress_value}%")

    def _on_export_error(self, error):
        """Called when export task encounters an error."""
        error_msg = str(error)
        self.logger.error(f"Export task error: {error_msg}")
        
        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.hide_loading_progress()
            self.main_window.ui_feedback.show_error("Export Error", error_msg)

    def _on_export_complete(self, result):
        """Called when export task completes successfully."""
        success_count = result.get('success', 0)
        reprint_count = result.get('reprint', 0)
        error_count = result.get('failed', 0)
        errors = result.get('errors', [])
        
        # Hide progress dialog
        if self.main_window and hasattr(self.main_window, 'ui_feedback'):
            self.main_window.ui_feedback.hide_loading_progress()
        
        # Build summary message
        summary_lines = []
        if success_count > 0:
            summary_lines.append(f"✓ Exported {success_count} bracket(s)")
        if reprint_count > 0:
            summary_lines.append(f"↻ Reprinted {reprint_count} bracket(s)")
        if error_count > 0:
            summary_lines.append(f"✗ Failed {error_count} bracket(s)")
        
        summary_text = "\n".join(summary_lines)
        if error_count > 0:
            summary_text += "\n\nErrors:\n" + "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                summary_text += f"\n... and {len(errors) - 5} more"
        
        summary_text += "\n\nDateien gespeichert in:\n/temp/exports/"
        
        self.logger.info(f"Export completed: {summary_text.replace(chr(10), ' | ')}")
        messagebox.showinfo("Export abgeschlossen", summary_text)

    def _excel_export_worker(self, bracket_keys):
        """
        Background worker fallback for Excel export operations (for threading without TaskRunner).
        
        This is only called if TaskRunner is not available. Normally, export goes through 
        TaskRunner which supports progress reporting and proper error handling.
        """
        try:
            result = self._excel_export_worker_fn(bracket_keys, on_progress=None)
            # Show completion message in main thread
            self.master.after(0, lambda r=result: self._on_export_complete(r))
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Excel export worker failed: {e}", exc_info=True)
            # Show error in main thread
            self.master.after(0, lambda msg=error_msg: messagebox.showerror("Export Error", msg))

    def _export_bracket_to_excel(self, bracket_key, method, fighters):
        """Generate Excel file for a single bracket."""
        try:
            filename = self._sanitize_filename(bracket_key, method)
            output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'temp', 'exports', filename)
            output_path = os.path.abspath(output_path)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            self.logger.debug(f"Exporting to: {output_path}")
            
            if method == self.METHOD_POOLS:
                # Single pool
                pools_data = [{
                    'pool_name': bracket_key,
                    'fighters': fighters,
                }]
                generator = PoolExcelGenerator()
                success = generator.generate_pools_excel(
                    output_path=output_path,
                    pools_data=pools_data,
                    title=bracket_key,
                    include_finale=False,
                )
            elif method == self.METHOD_DOUBLE:
                # Double pools - use split_into_pools utility for proper distribution
                pools = split_into_pools(fighters, num_pools=2)
                pools_data = [
                    {
                        'pool_name': f"{bracket_key} - Pool {i+1}",
                        'fighters': pool,
                    }
                    for i, pool in enumerate(pools)
                ]
                generator = PoolExcelGenerator()
                success = generator.generate_pools_excel(
                    output_path=output_path,
                    pools_data=pools_data,
                    title=bracket_key,
                    include_finale=True,  # Generate finale bracket from pool winners
                )
            else:
                # KO or Special - export as bracket with double elimination (includes loser round)
                generator = BracketExcelGenerator()
                success = generator.generate_bracket_excel(
                    output_path=output_path,
                    fighters=fighters,
                    bracket_type='double',  # Double elimination with loser bracket
                    title=bracket_key,
                )
            
            if success:
                self.logger.info(f"Successfully exported: {bracket_key} → {output_path}")
            else:
                self.logger.error(f"Generator returned False for: {bracket_key}")
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error exporting bracket {bracket_key}: {e}", exc_info=True)
            return False

    def _mark_bracket_printed(self, bracket_key):
        """Mark a bracket as printed and update display."""
        self.printed_brackets[bracket_key] = datetime.now()
        self.logger.info(f"Marked as printed: {bracket_key}")
        
        # Update displays to show print indicator
        self._refresh_all_displays()

    def _sanitize_filename(self, bracket_key, method):
        """Convert bracket key to a safe filename."""
        # Replace unsafe characters with underscores
        safe_key = bracket_key.replace('|', '').replace('/', '_').replace('\\', '_').strip()
        safe_key = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in safe_key)
        # Remove multiple spaces
        safe_key = '_'.join(safe_key.split())
        
        method_name = method.upper() if method else 'UNKNOWN'
        filename = f"{safe_key}_{method_name}.xls"
        
        return filename

    def _create_export_directory(self):
        """Ensure /temp/exports/ directory exists."""
        export_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'temp', 'exports')
        export_dir = os.path.abspath(export_dir)
        os.makedirs(export_dir, exist_ok=True)
        self.logger.debug(f"Export directory ready: {export_dir}")

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
