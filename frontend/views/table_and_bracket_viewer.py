# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Table and Bracket Viewer - Complete bracket management screen with search, assignment, and visualization."""

import os
import sys
import traceback

import tkinter as tk
from tkinter import messagebox, ttk

# Setup sys.path for backend imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger  # noqa: E402
from backend.services.bracket_service import make_bracket  # noqa: E402

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

# Import frontend utilities
from ..utils import (  # noqa: E402
    calculate_box_size,
    draw_pools_on_canvas,
    build_bracket_rounds,
    draw_bracket_on_canvas,
    compute_bracket_rounds,
    calculate_loser_positions,
    draw_loser_connectors,
)

from ..utils.search_utils import filter_items  # noqa: E402


class TableAndBracketViewer(tk.Frame):
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

    # ===== Table Assignment =====

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

    # ===== Bracket Rendering =====

    def render_bracket(self, bracket_key):
        """Render bracket or pool visualization on canvas."""
        if not self.main_window:
            return

        try:
            self.bracket_canvas.delete('all')

            bracket_data = self.main_window.brackets.get(bracket_key)
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

            # Get user's generation method assignment
            assigned_method = self.main_window.bracket_generation_methods.get(bracket_key)
            method = assigned_method or 'ko'
            self.logger.debug(f"Bracket {bracket_key} method: {method} (assigned: {assigned_method})")

            # Get pool_size from bracket data
            pool_size = self.main_window.brackets.get(bracket_key, {}).get('pool_size')
            
            # Fallback logic
            should_use_bracket_fallback = (
                method in ('pools', 'double') and
                pool_size is None and
                num_participants > 10 and
                method != 'double'
            )
            
            if should_use_bracket_fallback:
                self.logger.debug(f"Falling back to bracket system: {num_participants} participants with no pool_size configured")
                method = 'ko'
            
            # Render based on method
            if method in ('pools', 'double'):
                title = f"Pool Visualization ({bracket_key})"
                self.viz_title_var.set(title)
                self._render_pool(bracket_key, participants, pool_size, generation_method=method)
                return

            self.logger.debug(f"Rendering as KO bracket (method: {assigned_method})")
            self.viz_title_var.set('Bracket Visualization (KO)')

            # Normalize participants and generate bracket rounds
            normalized_participants = []
            for p in participants:
                if isinstance(p, dict):
                    if not normalized_participants:
                        self.logger.debug(f"Participant keys: {list(p.keys())}")
                    
                    normalized_participants.append({
                        'Name': p.get('Name', p.get('name', '')),
                        'Verein': p.get('Club', p.get('Verein', p.get('verein', p.get('club', ''))))
                    })

            if not normalized_participants:
                self.logger.debug("No normalized participants")
                self.bracket_canvas.create_text(400, 300,
                    text="Error: Could not process participants",
                    font=FONTS['heading_md'], fill='red')
                return

            self.logger.debug(f"Normalized {len(normalized_participants)} participants")

            # Generate bracket visualization
            bracket = make_bracket(normalized_participants)
            self.logger.debug(f"Generated bracket with {len(bracket)} first round matches")

            # Keep stored bracket in sync
            self.main_window.brackets[bracket_key]['bracket'] = bracket

            # Build rounds with club information
            rounds_with_clubs = build_bracket_rounds(bracket, normalized_participants)
            self.logger.debug(f"Generated bracket structure with {len(rounds_with_clubs)} rounds and club info")

            # Calculate box dimensions
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

            # Draw bracket
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

            # Draw simplified empty loser bracket
            loser_max_y = self._draw_loser_bracket_on_canvas(
                bracket, bracket_key, positions, box_width, box_height,
                start_x, start_y, self.zoom_level
            )

            # Update scroll region
            max_x = max(pos[0] for pos in positions.values()) + box_width + start_x
            max_y = loser_max_y + start_y
            self.bracket_canvas.configure(scrollregion=(0, 0, max_x, max_y))

            self.logger.debug(f"Successfully rendered bracket with {len(rounds_with_clubs)} rounds at {int(self.zoom_level*100)}% zoom")

        except Exception as e:
            self.logger.error(f"Exception rendering bracket: {e}")
            traceback.print_exc()
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering bracket:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

    def _draw_loser_bracket_on_canvas(self, bracket, bracket_key, wb_positions, 
                                     box_width, box_height, start_x, start_y, zoom_level):
        """Draw a simplified empty loser bracket below the winners bracket on the canvas."""
        try:
            wb_rounds = compute_bracket_rounds(bracket, {})
            if not wb_rounds:
                return max(pos[1] for pos in wb_positions.values()) + box_height
            
            loser_rounds = self._compute_loser_rounds_for_preview(wb_rounds)
            if not loser_rounds:
                return max(pos[1] for pos in wb_positions.values()) + box_height
            
            max_wb_y = max(pos[1] for pos in wb_positions.values()) + box_height
            y_offset = max_wb_y + int(40 * zoom_level)
            
            lb_pos, _ = calculate_loser_positions(loser_rounds, zoom_level, y_offset, start_x)
            draw_loser_connectors(self.bracket_canvas, lb_pos, loser_rounds, zoom_level, COLORS)
            
            LW = max(1, int(2 * zoom_level))
            BW = int(200 * zoom_level)
            BH = int(64 * zoom_level)
            
            for r, matches in enumerate(loser_rounds):
                for m in range(len(matches)):
                    if (r, m) not in lb_pos:
                        continue
                    
                    x, y = lb_pos[(r, m)]
                    x2, y2 = x + BW, y + BH
                    my = y + BH // 2
                    
                    self.bracket_canvas.create_rectangle(
                        x, y, x2, y2,
                        fill=COLORS['bg_panel'],
                        outline=COLORS['accent_orange'], width=LW)
                    
                    self.bracket_canvas.create_line(
                        x, my, x2, my,
                        fill=COLORS['border'], width=1, dash=(4, 3))
            
            nr = len(loser_rounds)
            XG = int(70 * zoom_level)
            label_font = ('Arial', max(8, int(11 * zoom_level)), 'bold')
            
            for r in range(nr):
                lx = start_x + r * (BW + XG) + BW // 2
                label = '3rd Place' if r == nr - 1 else f'Loser R{r + 1}'
                self.bracket_canvas.create_text(
                    lx, y_offset - int(20 * zoom_level),
                    text=label, anchor='c',
                    fill=COLORS['accent_orange'], font=label_font)
            
            if lb_pos:
                max_lb_y = max(pos[1] for pos in lb_pos.values()) + BH
                self.logger.debug(f"Drew loser bracket for '{bracket_key}' with max_y={max_lb_y}")
                return max_lb_y
            else:
                return max_wb_y
        except Exception as e:
            self.logger.debug(f"Error drawing loser bracket for '{bracket_key}': {e}")
            return max(pos[1] for pos in wb_positions.values()) + box_height

    def _compute_loser_rounds_for_preview(self, wb_rounds):
        """Compute loser bracket structure from winners bracket rounds."""
        if len(wb_rounds) < 2:
            return []

        def get_loser(match):
            """Extract the loser from a winner/loser match tuple."""
            if match['winner'] and match['winner'] in ('Freilos', 'TBD'):
                return 'TBD'
            if match['winner'] and match['winner'] == match['p1']:
                return match['p2'] if match['p2'] not in ('Freilos', 'TBD') else 'Freilos'
            if match['winner'] and match['winner'] == match['p2']:
                return match['p1'] if match['p1'] not in ('Freilos', 'TBD') else 'Freilos'
            return 'TBD'
        
        loser_rounds = []
        
        wb_r0_losers = [get_loser(m) for m in wb_rounds[0]]
        lb_r0_matches = []
        for i in range(0, len(wb_r0_losers), 2):
            p1 = wb_r0_losers[i]
            p2 = wb_r0_losers[i + 1] if i + 1 < len(wb_r0_losers) else 'Freilos'
            lb_r0_matches.append({'p1': p1, 'p2': p2, 'winner': None})
        loser_rounds.append(lb_r0_matches)
        
        for r in range(1, len(wb_rounds)):
            wb_r_losers = [get_loser(m) for m in wb_rounds[r]]
            lb_r1_winners = [m['winner'] if m['winner'] else 'TBD' for m in loser_rounds[r - 1]]
            
            if r == len(wb_rounds) - 1:
                p1 = lb_r1_winners[0] if lb_r1_winners else 'TBD'
                p2 = wb_r_losers[0] if wb_r_losers else 'TBD'
                loser_rounds.append([{'p1': p1, 'p2': p2, 'winner': None}])
            else:
                lb_matches = []
                prev_count = len(loser_rounds[r - 1])
                curr_wb_losers = len(wb_r_losers)
                
                if curr_wb_losers >= prev_count:
                    for i in range(prev_count):
                        p1 = lb_r1_winners[i] if i < len(lb_r1_winners) else 'TBD'
                        p2 = wb_r_losers[i] if i < len(wb_r_losers) else 'Freilos'
                        lb_matches.append({'p1': p1, 'p2': p2, 'winner': None})
                else:
                    for i in range(0, len(lb_r1_winners), 2):
                        p1 = lb_r1_winners[i] if i < len(lb_r1_winners) else 'TBD'
                        p2 = lb_r1_winners[i + 1] if i + 1 < len(lb_r1_winners) else 'Freilos'
                        lb_matches.append({'p1': p1, 'p2': p2, 'winner': None})
                
                loser_rounds.append(lb_matches)
        
        return loser_rounds

    def _render_pool(self, bracket_key, participants, pool_size=None, generation_method=None):
        """Render pool/round-robin visualization on canvas."""
        if not self.main_window:
            return

        try:
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

            self.bracket_canvas.configure(scrollregion=(0, 0, total_width, total_height))

            num_participants = len(normalized_participants)
            assigned_method = self.main_window.bracket_generation_methods.get(bracket_key, 'unknown')
            num_matches = (num_participants * (num_participants - 1)) // 2
            
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
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering pool:\n{str(e)}",
                font=FONTS['body_md'], fill='red')

    # ===== Utilities =====

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
