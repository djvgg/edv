# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Generation Method Screen - Assign brackets to generation methods (Pools, Double Pools, KO, Special)

This screen allows users to choose which generation method each bracket will use.
Displays unassigned brackets on the left and 4 method tables on the right in a 2x2 grid.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import threading

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

logger = get_logger('generation_method_screen')


class GenerationMethodScreen(tk.Frame):
    """
    Screen for assigning brackets to generation methods.
    
    Displays unassigned brackets and 4 tables for different generation strategies:
    - Pools (≤5 fighters)
    - Double Pools (6-10 fighters)
    - KO Brackets (11+ fighters)
    - Special Cases (edge cases)
    """

    # Method constants
    METHOD_POOLS = 'pools'
    METHOD_DOUBLE = 'double'
    METHOD_KO = 'ko'
    METHOD_SPECIAL = 'special'

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger

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

    def load_data(self, brackets_dict=None):
        """
        Load bracket data and initialize UI.
        
        Args:
            brackets_dict: Dict of {bracket_key: bracket_tuple} or 
                          {bracket_key: {"tuple": bracket_tuple, "method": method_name, ...}}
        """
        if brackets_dict:
            self.brackets = {}
            self.unassigned = []

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

                if method is None:
                    self.unassigned.append(key)

            self.filtered_keys = self.unassigned.copy()
            self.logger.info(f"Loaded {len(self.brackets)} brackets, {len(self.unassigned)} unassigned")

        # Build or refresh UI
        if self.main_frame:
            self.main_frame.destroy()

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""

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
            text="Close & Proceed",
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

        # Assign button
        assign_btn = tk.Button(
            left_panel,
            text="Assign Selected →",
            command=self.on_assign_selected,
        )
        apply_button_style(assign_btn, style='secondary')
        assign_btn.pack(pady=5, fill=tk.X, padx=5)

        # RIGHT PANEL: 4 Tables in 2x2 Grid
        right_panel = tk.Frame(self.main_frame, bg=COLORS['bg_dark'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # Create 2x2 grid
        self.tables = {}

        # Top row
        top_row = tk.Frame(right_panel, bg=COLORS['bg_dark'])
        top_row.pack(fill=tk.BOTH, expand=True, pady=5)

        self._create_method_table(top_row, self.METHOD_POOLS, 'Pools (≤5 fighters)', side=tk.LEFT)
        self._create_method_table(top_row, self.METHOD_DOUBLE, 'Double Pools (6-10)', side=tk.LEFT)

        # Bottom row
        bottom_row = tk.Frame(right_panel, bg=COLORS['bg_dark'])
        bottom_row.pack(fill=tk.BOTH, expand=True, pady=5)

        self._create_method_table(bottom_row, self.METHOD_KO, 'KO Brackets (11+)', side=tk.LEFT)
        self._create_method_table(bottom_row, self.METHOD_SPECIAL, 'Special Cases', side=tk.LEFT)

        # Refresh display
        self._refresh_all_displays()

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
            text="← Unassign",
            command=lambda m=method_key: self.on_unassign_from_table(m),
        )
        apply_button_style(unassign_btn, style='secondary')
        unassign_btn.pack(pady=5, fill=tk.X, padx=5)

        self.tables[method_key] = {
            'listbox': listbox,
            'unassign_btn': unassign_btn,
        }

    def on_search(self):
        """Filter unassigned brackets by search term."""
        search_term = self.search_entry.get().lower()

        if search_term:
            self.filtered_keys = [k for k in self.unassigned if search_term in k.lower()]
        else:
            self.filtered_keys = self.unassigned.copy()

        self._refresh_unassigned_display()

    def on_unassigned_select(self, event):
        """Handle selection in unassigned listbox."""
        selection = self.unassigned_listbox.curselection()
        if selection:
            idx = selection[0]
            self.selected_unassigned = self.filtered_keys[idx]

    def on_table_select(self, method, event):
        """Handle selection in method table."""
        listbox = self.tables[method]['listbox']
        selection = listbox.curselection()
        if selection:
            idx = selection[0]
            # Get the bracket key from the listbox
            bracket_key = listbox.get(idx).split(' (')[0]  # Extract key before " (N)"
            self.selected_in_tables[method] = bracket_key

    def on_assign_selected(self):
        """Assign selected unassigned bracket to a method (user needs to choose)."""
        if not self.selected_unassigned:
            messagebox.showwarning("Warning", "Please select a bracket from the unassigned list")
            return

        # Ask user which method
        method = self._ask_method()
        if not method:
            return

        self._assign_bracket(self.selected_unassigned, method)

    def on_unassign_from_table(self, method):
        """Unassign selected bracket from a method."""
        if method not in self.selected_in_tables:
            messagebox.showwarning("Warning", "Please select a bracket from the table")
            return

        bracket_key = self.selected_in_tables[method]
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

                # Recommend method
                method = self._recommend_method(fighter_count)

                # Assign
                self._assign_bracket(bracket_key, method)
                assigned_count += 1

            self.logger.info(f"Auto-assigned {assigned_count} brackets")
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Auto-assigned {assigned_count} brackets"))

        except Exception as e:
            self.logger.error(f"Auto-assign error: {e}")
            self.master.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _assign_bracket(self, bracket_key, method):
        """Assign a bracket to a method."""
        if bracket_key not in self.brackets:
            return

        self.brackets[bracket_key]["method"] = method

        if bracket_key in self.unassigned:
            self.unassigned.remove(bracket_key)
            self.filtered_keys = [k for k in self.filtered_keys if k != bracket_key]

        self._refresh_all_displays()
        self.logger.info(f"Assigned {bracket_key} to {method}")

    def _unassign_bracket(self, bracket_key):
        """Unassign a bracket from a method."""
        if bracket_key not in self.brackets:
            return

        self.brackets[bracket_key]["method"] = None

        if bracket_key not in self.unassigned:
            self.unassigned.append(bracket_key)
            self.filtered_keys.append(bracket_key)

        self._refresh_all_displays()
        self.logger.info(f"Unassigned {bracket_key}")

    def _refresh_all_displays(self):
        """Refresh all listbox displays."""
        self._refresh_unassigned_display()
        for method in self.tables.keys():
            self._refresh_method_display(method)

    def _refresh_unassigned_display(self):
        """Refresh unassigned brackets listbox."""
        if not self.unassigned_listbox:
            return
        self.unassigned_listbox.delete(0, tk.END)

        for bracket_key in self.filtered_keys:
            bracket_data = self.brackets[bracket_key]
            fighter_count = self._count_fighters(bracket_data["tuple"])
            display_text = f"{bracket_key} ({fighter_count})"
            self.unassigned_listbox.insert(tk.END, display_text)

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
                fighter_count = self._count_fighters(bracket_data["tuple"])
                display_text = f"{bracket_key} ({fighter_count})"
                listbox.insert(tk.END, display_text)

    def _count_fighters(self, bracket_tuple):
        """Count fighters in a bracket tuple."""
        if isinstance(bracket_tuple, list):
            # List of (name1, name2) tuples
            return len(bracket_tuple) * 2
        elif isinstance(bracket_tuple, (tuple, list)) and len(bracket_tuple) > 0:
            # Check if it's a list of tuples
            if isinstance(bracket_tuple[0], (tuple, list)):
                return len(bracket_tuple) * 2
            # Otherwise count items
            return len(bracket_tuple)
        return 0

    def _recommend_method(self, fighter_count):
        """Recommend a generation method based on fighter count."""
        if fighter_count < 3:
            return self.METHOD_SPECIAL
        elif fighter_count <= 5:
            return self.METHOD_POOLS
        elif fighter_count <= 10:
            return self.METHOD_DOUBLE
        else:
            return self.METHOD_KO

    def _ask_method(self):
        """Ask user which method to assign to."""
        # Simple dialog - could be improved with a popup dialog
        methods = {
            self.METHOD_POOLS: 'Pools (≤5 fighters)',
            self.METHOD_DOUBLE: 'Double Pools (6-10)',
            self.METHOD_KO: 'KO Brackets (11+)',
            self.METHOD_SPECIAL: 'Special Cases',
        }

        # Create a simple popup for method selection
        popup = tk.Toplevel(self)
        popup.title("Select Generation Method")
        popup.geometry("300x200")
        popup.configure(bg=COLORS['bg_dark'])

        label = tk.Label(popup, text="Choose generation method:", bg=COLORS['bg_dark'], fg=COLORS['text_primary'])
        label.pack(pady=10)

        selected_method = {'value': None}

        for method_key, method_name in methods.items():
            btn = tk.Button(
                popup,
                text=method_name,
                command=lambda m=method_key: self._on_method_selected(popup, selected_method, m),
            )
            apply_button_style(btn, style='secondary')
            btn.pack(pady=5, fill=tk.X, padx=10)

        popup.transient(self)
        popup.grab_set()
        self.wait_window(popup)

        return selected_method['value']

    def _on_method_selected(self, popup, selected_method, method):
        """Handle method selection."""
        selected_method['value'] = method
        popup.destroy()

    def on_close(self):
        """Close screen and proceed to generation."""
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

        # Call callback if available
        if hasattr(self.master, 'on_generation_methods_selected'):
            self.master.on_generation_methods_selected(final_brackets)
        else:
            self.logger.warning("No callback set for generation method selection")
            messagebox.showinfo("Success", "Bracket assignments finalized!")

    def on_close_screen(self):
        """Cleanup when screen is hidden."""
        pass
