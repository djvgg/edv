# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Table and Bracket Viewer - Complete bracket management screen with search, assignment, and visualization."""

import os
import sys

import tkinter as tk
from tkinter import messagebox, ttk

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402

from ..styles import (  # noqa: E402
    COLORS,
    FONTS,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    apply_table_panel_style,
    create_dark_frame,
)

from ..utils.search_utils import filter_items  # noqa: E402

from ._table_bracket_assignment import _AssignmentMixin
from ._table_bracket_renderer import _RendererMixin


class TableAndBracketViewer(_AssignmentMixin, _RendererMixin, tk.Frame):
    """Complete bracket management interface: search, assignment, tables, and visualization."""

    def __init__(self, parent, main_window=None):
        """Initialize the complete bracket management screen.

        Args:
            parent: Parent widget (typically right_frame in main_window)
            main_window: Reference to BracketViewerApp for accessing data and callbacks
        """
        super().__init__(parent, bg=COLORS['bg_dark'])

        self.logger = get_logger('table_and_bracket_viewer')
        self.main_window = main_window

        # State managed by this viewer
        self.zoom_level = 1.0
        self.current_bracket_key = None
        self.bracket_listbox_map = {}
        self.table_panels = {}

        # Build complete UI with left panel + right panel
        self._build_ui()
        self.logger.debug("TableAndBracketViewer initialized")

    def _build_ui(self):
        """Build the complete UI layout with search, listbox, assignment buttons, tables, and bracket view."""
        # Create PanedWindow for resizable split
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                              bg=COLORS['bg_dark'],
                              sashwidth=4,
                              sashrelief=tk.FLAT,
                              showhandle=False)
        paned.pack(fill=tk.BOTH, expand=True)

        # ===== LEFT PANEL: Search & Bracket Selection =====
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

        # Bracket listbox
        self.bracket_listbox = tk.Listbox(left_frame, width=26, height=16)
        apply_listbox_style(self.bracket_listbox)
        self.bracket_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.bracket_listbox.bind('<<ListboxSelect>>', self.on_bracket_select)
        self.bracket_listbox.bind('<Double-Button-1>', self.on_bracket_double_click)

        # Assignment buttons
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

        # ===== RIGHT PANEL: Tables OR Bracket View =====
        right_frame = create_dark_frame(paned)
        paned.add(right_frame, minsize=400)

        # Tables display (shown initially)
        self.tables_frame = create_dark_frame(right_frame)

        # Add navigation row at the top
        tables_nav_frame = create_dark_frame(self.tables_frame)
        tables_nav_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=18, pady=10)

        back_to_gen_btn = tk.Button(tables_nav_frame, text='← Back to Generation Setup',
                                    command=self._on_back_to_generation)
        apply_button_style(back_to_gen_btn, 'secondary')
        back_to_gen_btn.pack(side=tk.LEFT, padx=5)

        monitor_btn = tk.Button(tables_nav_frame, text='Fight Monitoring',
                                command=self._on_monitoring_clicked)
        apply_button_style(monitor_btn, 'primary')
        monitor_btn.pack(side=tk.RIGHT, padx=5)

        # Create table panels
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

        # Bracket visualization frame (hidden initially)
        self.bracket_view_frame = create_dark_frame(right_frame)

        # Top bar with title and zoom controls
        top_bar = create_dark_frame(self.bracket_view_frame)
        top_bar.pack(fill=tk.X, pady=(0, 5), padx=5)

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
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas for bracket visualization
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

        # Show tables view by default
        self.show_tables()
        self.update_bracket_list()
        self.update_table_panels()

    # ===== Navigation =====

    def _on_back_to_generation(self):
        """Handle back button to generation setup."""
        if self.main_window and hasattr(self.main_window, 'show_generation_method_screen'):
            self.main_window.show_generation_method_screen()

    def _on_monitoring_clicked(self):
        """Handle fight monitoring button click."""
        if self.main_window and hasattr(self.main_window, 'show_fight_monitoring_screen'):
            self.main_window.show_fight_monitoring_screen()

    def show_tables(self):
        """Show table assignment view."""
        self.bracket_view_frame.pack_forget()
        self.tables_frame.pack(fill=tk.BOTH, expand=True)

    def show_bracket_view(self, bracket_key):
        """Show bracket visualization for selected bracket."""
        self.tables_frame.pack_forget()
        self.bracket_view_frame.pack(fill=tk.BOTH, expand=True)
        self.current_bracket_key = bracket_key
        self.render_bracket(bracket_key)

    # ===== Zoom Controls =====

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling on canvas."""
        if event.num == 5 or event.delta < 0:
            self.bracket_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.bracket_canvas.yview_scroll(-1, "units")

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

    # ===== Bracket List Management =====

    def update_bracket_list(self, *args):
        """Update the bracket list based on search filter."""
        if not hasattr(self, 'search_var') or not self.main_window:
            return

        search_term = self.search_var.get()
        self.bracket_listbox.delete(0, tk.END)
        self.bracket_listbox_map = {}

        # Get unassigned bracket keys
        if not hasattr(self.main_window, 'bracket_table_assignment'):
            return

        unassigned_keys = [k for k in sorted(self.main_window.brackets.keys())
                           if not self.main_window.bracket_table_assignment.get(k)
                           and len(self.main_window.brackets[k].get('fighters', [])) > 0]

        # Move QUARANTINE_* brackets to front
        quarantine_keys = [k for k in unassigned_keys if k.startswith('QUARANTINE_')]
        normal_keys = [k for k in unassigned_keys if not k.startswith('QUARANTINE_')]
        unassigned_keys = quarantine_keys + normal_keys

        # Use shared search utility
        filtered_keys, matched_count, search_terms = filter_items(unassigned_keys, search_term)

        if search_terms:
            self.logger.debug(f"Bracket search: {search_terms}, found {matched_count} brackets")

        total_unassigned = 0

        # Display filtered brackets
        for bracket_key in filtered_keys:
            bracket_data = self.main_window.brackets.get(bracket_key, {})
            fighter_count = len(bracket_data.get('fighters', []))
            fight_count = self._calculate_number_of_fights(bracket_key)

            display_text = f"{bracket_key} • {fighter_count} / {fight_count}"

            self.bracket_listbox.insert(tk.END, display_text)
            self.bracket_listbox_map[display_text] = bracket_key
            total_unassigned += fighter_count

        # Update counter
        if hasattr(self, 'unassigned_count_var'):
            self.unassigned_count_var.set(f"({total_unassigned})")

    def on_bracket_select(self, event):
        """Called when user clicks a bracket in the list."""
        pass

    def on_bracket_double_click(self, event):
        """Handle double-click on bracket - show visualization."""
        selection = self.bracket_listbox.curselection()
        if selection:
            display_text = self.bracket_listbox.get(selection[0])
            bracket_key = self.bracket_listbox_map.get(display_text, display_text)
            self.show_bracket_view(bracket_key)
