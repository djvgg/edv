# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import messagebox, ttk

from ..styles import (
    COLORS, FONTS,
    apply_button_style,
    apply_table_panel_style,
    create_dark_frame,
)
import os, sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger


class _AssignmentMixin:
    """Mixin for table assignment and bracket panel management."""

    def assign_to_table(self, table_num):
        """Assign selected bracket to a table."""
        if not self.bracket_listbox.curselection():
            messagebox.showinfo('No Selection', 'Please select a bracket first.')
            return

        display_text = self.bracket_listbox.get(self.bracket_listbox.curselection()[0])
        bracket_key = self.bracket_listbox_map.get(display_text, display_text)

        if not self.main_window:
            return

        # Assign the bracket
        self.main_window.bracket_table_assignment[bracket_key] = table_num
        bracket_data = self.main_window.brackets[bracket_key]
        self.main_window.db_service.assign_and_create_fights(
            bracket_key,
            table_num=table_num,
            fight_pairs=bracket_data.get('bracket', []),
            bracket_type=self.main_window.bracket_generation_methods.get(bracket_key, 'ko'),
            fighters=bracket_data.get('fighters', []),
            pool_size=bracket_data.get('pool_size'),
        )

        self.update_bracket_list()
        self.update_table_panels()
        self.logger.info(f"Assigned '{bracket_key}' to Matte {table_num}")

    def unassign_bracket(self, bracket_key=None):
        """Unassign bracket from its table."""
        if not bracket_key:
            selection = self.bracket_listbox.curselection()
            if not selection:
                messagebox.showinfo('No Selection', 'Please select a bracket first.')
                return
            bracket_key = self.bracket_listbox.get(selection[0])

        if not self.main_window:
            return

        if not self.main_window.bracket_table_assignment.get(bracket_key):
            messagebox.showinfo('Not Assigned', 'This bracket is not assigned to any table.')
            return

        old_table = self.main_window.bracket_table_assignment[bracket_key]
        self.main_window.bracket_table_assignment[bracket_key] = None
        self.main_window.db_service.unassign_bracket_from_table(bracket_key)
        self.update_bracket_list()
        self.update_table_panels()
        self.logger.info(f"Unassigned '{bracket_key}' from Matte {old_table}")

    def auto_assign_tables(self):
        """Automatically distribute unassigned brackets across tables."""
        if not self.main_window:
            return

        unassigned = [k for k in self.main_window.brackets.keys()
                     if not self.main_window.bracket_table_assignment.get(k)]

        if not unassigned:
            messagebox.showinfo('Auto-assign', 'No unassigned brackets to assign.')
            return

        # Count current assignments per table
        assigned_count = {t: len([k for k, v in self.main_window.bracket_table_assignment.items() if v == t])
                         for t in range(1, 5)}

        table = 1
        for bracket_key in unassigned:
            # Find next table with space
            for _ in range(4):
                if assigned_count[table] < 2:
                    self.main_window.bracket_table_assignment[bracket_key] = table
                    assigned_count[table] += 1
                    table = table % 4 + 1
                    break
                table = table % 4 + 1

        # Assign and create fights for newly assigned brackets
        for bracket_key in unassigned:
            table_num = self.main_window.bracket_table_assignment.get(bracket_key)
            if table_num:
                bracket_data = self.main_window.brackets[bracket_key]
                self.main_window.db_service.assign_and_create_fights(
                    bracket_key,
                    table_num=table_num,
                    fight_pairs=bracket_data.get('bracket', []),
                    bracket_type=self.main_window.bracket_generation_methods.get(bracket_key, 'ko'),
                    fighters=bracket_data.get('fighters', []),
                    pool_size=bracket_data.get('pool_size'),
                )

        self.update_bracket_list()
        self.update_table_panels()

    def update_table_panels(self):
        """Update the visual display of table assignments with scrollable content."""
        if not self.main_window:
            return

        # Clear all panels
        for panel in self.table_panels.values():
            for widget in panel.winfo_children():
                widget.destroy()

        # Track totals for each table
        table_totals = {}

        # For each panel, create scrollable content
        for table_num, panel in self.table_panels.items():
            # Create canvas for scrollable content
            canvas = tk.Canvas(panel, bg=COLORS['bg_panel'], highlightthickness=0, borderwidth=0)
            scrollbar = ttk.Scrollbar(panel, orient=tk.VERTICAL, command=canvas.yview, style='Vertical.TScrollbar')

            # Frame inside canvas to hold content
            content_frame = create_dark_frame(canvas)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas_window = canvas.create_window((0, 0), window=content_frame, anchor='nw')

            # Bind canvas resize
            def _on_canvas_configure(event, c=canvas, cf=content_frame, cw=canvas_window):
                c.itemconfig(cw, width=event.width)

            canvas.bind('<Configure>', _on_canvas_configure)

            # Bind mousewheel
            def _on_panel_wheel(event, c=canvas):
                if event.num == 5 or event.delta < 0:
                    c.yview_scroll(1, "units")
                elif event.num == 4 or event.delta > 0:
                    c.yview_scroll(-1, "units")

            canvas.bind('<MouseWheel>', _on_panel_wheel)
            canvas.bind('<Button-4>', _on_panel_wheel)
            canvas.bind('<Button-5>', _on_panel_wheel)

            # Pack scrollbar and canvas
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Add assigned brackets to this table
            for bracket_key, assigned_table in self.main_window.bracket_table_assignment.items():
                if assigned_table == table_num and len(self.main_window.brackets[bracket_key].get('fighters', [])) > 0:
                    # Create row frame
                    row_frame = create_dark_frame(content_frame)
                    row_frame.pack(fill=tk.X, pady=2, padx=4)

                    fighter_count = len(self.main_window.brackets[bracket_key].get('fighters', []))
                    fight_count = self._calculate_number_of_fights(bracket_key)

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

            # Add totals footer
            fighter_total = table_totals.get(table_num, {}).get('fighters', 0)
            fight_total = table_totals.get(table_num, {}).get('fights', 0)

            separator = tk.Frame(content_frame, height=1, bg=COLORS['border'])
            separator.pack(fill=tk.X, pady=4, padx=4)

            total_frame = create_dark_frame(content_frame)
            total_frame.pack(fill=tk.X, pady=2, padx=4)

            total_text = f"Table Total: {fighter_total} players • {fight_total} matches"
            total_label = tk.Label(total_frame, text=total_text,
                                  justify='left', anchor='w',
                                  bg=COLORS['bg_panel'], fg=COLORS['accent_orange'],
                                  font=FONTS['heading_sm'])
            total_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            content_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))

    def _calculate_number_of_fights(self, bracket_key):
        """Calculate the number of fights for a bracket."""
        if not self.main_window:
            return 0

        bracket_data = self.main_window.brackets.get(bracket_key, {})

        if bracket_data.get('is_quarantine', False):
            return 0

        fighters = bracket_data.get('fighters', [])
        num_fighters = len(fighters)

        if num_fighters == 0:
            return 0

        assigned_method = self.main_window.bracket_generation_methods.get(bracket_key)
        method = assigned_method or 'ko'

        if method in ('pools', 'double'):
            num_fights = num_fighters * (num_fighters - 1) // 2
        else:
            num_fights = num_fighters - 1

        return num_fights
