# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Table and Bracket Viewer - Complete bracket management screen with search, assignment, and visualization."""

import os
import sys

import tkinter as tk
from tkinter import messagebox, ttk

# Setup sys.path for backend imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

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
from ._table_bracket_renderer import _RendererMixin  # noqa: E402


class TableAndBracketViewer(_RendererMixin, tk.Frame):
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
        self.ui_initialized = False  # Track if UI has been built
        
        # Build complete UI with left panel + right panel
        self._build_ui()
        self.logger.debug("TableAndBracketViewer initialized")
    
    def _build_ui(self):
        """Build the complete UI layout with search, listbox, assignment buttons, tables, and bracket view."""
        if self.ui_initialized:
            self.logger.debug("UI already initialized, skipping rebuild")
            return
        
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
        self.ui_initialized = True
        self._poll_job = None  # holds the after() handle
        self.logger.debug("UI initialized successfully")

    # ===== Navigation =====

    def _on_back_to_generation(self):
        """Handle back button to generation setup."""
        if self.main_window:
            self.main_window.screen_manager.navigate_to('generation_method')
    
    def _on_monitoring_clicked(self):
        """Handle fight monitoring button click."""
        if self.main_window:
            self.main_window.screen_manager.navigate_to('fight_monitoring')

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

        if not hasattr(self.main_window, 'bracket_table_assignment'):
            return

        completed_keys = self.main_window.db_service.get_completed_bracket_keys()

        unassigned_keys = [k for k in sorted(self.main_window.brackets.keys())
                           if not self.main_window.bracket_table_assignment.get(k)
                           and len(self.main_window.brackets[k].get('fighters', [])) > 0
                           and k not in completed_keys]

        # Move QUARANTINE_* brackets to front
        quarantine_keys = [k for k in unassigned_keys if k.startswith('QUARANTINE_')]
        normal_keys = [k for k in unassigned_keys if not k.startswith('QUARANTINE_')]
        unassigned_keys = quarantine_keys + normal_keys

        filtered_keys, matched_count, search_terms = filter_items(unassigned_keys, search_term)
        if search_terms:
            self.logger.debug(f"Bracket search: {search_terms}, found {matched_count} brackets")

        total_unassigned = 0
        for bracket_key in filtered_keys:
            bracket_data = self.main_window.brackets.get(bracket_key, {})
            fighter_count = len(bracket_data.get('fighters', []))
            fight_count = self._calculate_number_of_fights(bracket_key)
            display_text = f"{bracket_key} • {fighter_count} / {fight_count}"
            self.bracket_listbox.insert(tk.END, display_text)
            self.bracket_listbox_map[display_text] = bracket_key
            total_unassigned += fighter_count

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
        
        # Mark downstream screens as stale (FightMonitoring needs to refresh with new assignments)
        if hasattr(self.main_window, 'screen_manager'):
            self.main_window.screen_manager.invalidate_downstream('bracket_viewer')

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
        
        # Mark downstream screens as stale (FightMonitoring needs to refresh with new assignments)
        if hasattr(self.main_window, 'screen_manager'):
            self.main_window.screen_manager.invalidate_downstream('bracket_viewer')

    def auto_assign_tables(self):
        """Automatically distribute unassigned brackets across tables."""
        if not self.main_window:
            return

        completed_keys = self.main_window.db_service.get_completed_bracket_keys()
        unassigned = [k for k in self.main_window.brackets.keys()
                      if not self.main_window.bracket_table_assignment.get(k)
                      and len(self.main_window.brackets[k].get('fighters', [])) > 0
                      and k not in completed_keys]

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
        
        # Mark downstream screens as stale (FightMonitoring needs to refresh with new assignments)
        if hasattr(self.main_window, 'screen_manager'):
            self.main_window.screen_manager.invalidate_downstream('bracket_viewer')

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
        completed_keys = self.main_window.db_service.get_completed_bracket_keys()

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
            
            # Add assigned brackets to this table (skip completed ones)
            for bracket_key, assigned_table in self.main_window.bracket_table_assignment.items():
                if assigned_table == table_num and len(self.main_window.brackets[bracket_key].get('fighters', [])) > 0 and bracket_key not in completed_keys:
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

    def on_show(self, force_reload=False):
        """Lifecycle hook called when screen is displayed."""
        self.logger.debug(f"[LIFECYCLE] TableAndBracketViewer.on_show(force_reload={force_reload})")
        if force_reload and self.main_window:
            self.update_bracket_list()
            self.logger.info("[RELOAD] TableAndBracketViewer data reloaded from cache")
        self._start_poll()

    def on_close_screen(self):
        """Cleanup when screen is hidden."""
        self._stop_poll()

    _POLL_INTERVAL_MS = 15_000  # 15 seconds

    def _start_poll(self):
        """Begin periodic refresh of bracket list and mat panels."""
        self._stop_poll()  # cancel any existing job first
        self._schedule_poll()

    def _stop_poll(self):
        """Cancel the pending poll job if one exists."""
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None

    def _schedule_poll(self):
        self._poll_job = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    def _poll_tick(self):
        """Called every _POLL_INTERVAL_MS; refreshes panels then reschedules."""
        self._poll_job = None
        if self.main_window:
            self.update_bracket_list()
            self.update_table_panels()
            self.logger.debug("[POLL] Bracket panels refreshed")
        self._schedule_poll()
