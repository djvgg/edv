# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Fight Monitoring screen – in-app screen (tk.Frame) for live match tracking.

Navigation flow (all inside the main window, no separate Toplevel):
    Bracket Viewer  ──►  Matten overview  ──►  KO / Pool fight view
                    ◄──  ← Back           ◄──  ← Matten
"""

import tkinter as tk
from tkinter import ttk

from ..styles import (
    COLORS,
    FONTS,
    apply_button_style,
    apply_label_style,
    apply_table_panel_style,
    create_dark_frame,
)

import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger  # noqa: E402
logger = get_logger('fight_monitoring')

from ._fight_monitoring_ko import _KOMixin  # noqa: E402
from ._fight_monitoring_pool import _PoolMixin  # noqa: E402


class FightMonitoringScreen(_KOMixin, _PoolMixin, tk.Frame):
    """
    In-app Fight Monitoring screen.

    The main window creates this frame, packs it full-screen, and sets:
        screen.on_back = self.show_bracket_viewer
    """

    def __init__(self, parent, brackets, bracket_table_assignment,
                 bracket_generation_methods, match_results,
                 loser_match_results=None, pool_cell_values=None,
                 ko_bracket_data=None, ko_match_results=None,
                 db_service=None, main_window=None):
        super().__init__(parent, bg=COLORS['bg_dark'])
        self.db_service = db_service
        self.main_window = main_window
        logger.info(f"FightMonitoringScreen initialized with {len(brackets)} brackets, {len(bracket_table_assignment)} table assignments")

        # Callback – set by BracketViewerApp before showing
        self.on_back = None

        # Shared data (live references to main app dicts)
        self.brackets = brackets
        self.bracket_table_assignment = bracket_table_assignment
        self.bracket_generation_methods = bracket_generation_methods
        # {bracket_key: {(round_idx, match_idx): winner_name}}
        self.match_results = match_results
        # {bracket_key: {(lb_round, lb_match): winner_name}}
        self.loser_match_results = loser_match_results if loser_match_results is not None else {}
        # {bracket_key: {(pool_idx, row, fight_num): "score"}}
        self.pool_cell_values = pool_cell_values if pool_cell_values is not None else {}
        # {bracket_key: {'p0_1st': name, 'p0_2nd': name, 'p1_1st': name, 'p1_2nd': name}}
        self.ko_bracket_data = ko_bracket_data if ko_bracket_data is not None else {}
        # {bracket_key: {(round, match): winner_name}}  — for the pool KO bracket
        self.ko_match_results = ko_match_results if ko_match_results is not None else {}

        # UI state
        self.current_bracket_key = None
        self.zoom_level = 1.0
        # {(round, match): (x1, y1, x2, y2, p1, p2)}
        self._match_boxes = {}
        # clickable cells from last pool render: {(pool_idx, row, fight_num): (x1,y1,x2,y2)}
        self._pool_cells = {}
        self._active_cell_entry = None
        # KO box positions from last pool render: {(round, match): (x1,y1,x2,y2,p1,p2)}
        self._ko_match_boxes = {}
        # losers bracket box positions: {(lb_round, lb_match): (x1,y1,x2,y2,p1,p2)}
        self._loser_match_boxes = {}
        # Tracks byes already synced to DB — prevents redundant DB calls on re-render
        # {(bracket_key, phase, round, pos)}
        self._bye_db_synced = set()
        
        # Track UI initialization
        self.ui_initialized = False

        self._setup_ttk_styles()
        self._build_ui()

    # ----------------------------------------------------------------- styles

    def _setup_ttk_styles(self):
        style = ttk.Style()
        for name in ('FM.Vertical.TScrollbar', 'FM.Horizontal.TScrollbar'):
            style.configure(name,
                            background=COLORS['bg_panel'],
                            troughcolor=COLORS['bg_dark'],
                            bordercolor=COLORS['bg_dark'],
                            arrowcolor=COLORS['text_secondary'])

    # ------------------------------------------------------------- build UI

    def _build_ui(self):
        """Build the UI. Only initialize once."""
        if self.ui_initialized:
            logger.debug("UI already initialized, skipping rebuild")
            return
        self.ui_initialized = True
        # ── Navigation bar ───────────────────────────────────────────────────
        nav = create_dark_frame(self)
        nav.pack(fill=tk.X, padx=10, pady=(8, 0))

        # Context-sensitive back button (label/command change per view)
        self._back_btn = tk.Button(nav, text='← Back',
                                   command=self._go_back)
        apply_button_style(self._back_btn, 'secondary')
        self._back_btn.pack(side=tk.LEFT, padx=(0, 10))

        self._breadcrumb = tk.StringVar(value='Fight Monitoring')
        bc = tk.Label(nav, textvariable=self._breadcrumb)
        apply_label_style(bc, 'heading_md')
        bc.pack(side=tk.LEFT)

        # Manueller Refresh-Button (Welle 3-ish: holt externe DB-Updates)
        self._refresh_btn = tk.Button(nav, text='↻ Aktualisieren',
                                      command=self._manual_refresh)
        apply_button_style(self._refresh_btn, 'secondary')
        self._refresh_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Zoom controls (hidden when in matten overview)
        self._zoom_bar = create_dark_frame(nav)
        self._zoom_bar.pack(side=tk.RIGHT)

        self._zoom_label = tk.Label(self._zoom_bar, text='100%')
        apply_label_style(self._zoom_label, 'info')
        self._zoom_label.pack(side=tk.LEFT, padx=(0, 4))

        for sym, cmd in [('−', self._zoom_out), ('+', self._zoom_in)]:
            b = tk.Button(self._zoom_bar, text=sym, width=2, command=cmd)
            apply_button_style(b, 'secondary')
            b.configure(font=FONTS['heading_md'], pady=2)
            b.pack(side=tk.LEFT, padx=1)

        rb = tk.Button(self._zoom_bar, text='100%', command=self._zoom_reset)
        apply_button_style(rb, 'secondary')
        rb.configure(pady=2)
        rb.pack(side=tk.LEFT, padx=(1, 0))

        # ── Content area (swapped between the two sub-views) ─────────────────
        self._content = create_dark_frame(self)
        self._content.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self._build_matten_view()
        self._build_fight_view()

    # ------------------------------------------------------- matten overview

    def _build_matten_view(self):
        self._matten_frame = create_dark_frame(self._content)

        hint = tk.Label(self._matten_frame,
                        text='Klicke auf ein Bracket, um dessen Kämpfe zu überwachen.')
        apply_label_style(hint, 'info')
        hint.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        self._matte_panels = {}
        for i, (row, col) in enumerate([(1, 0), (1, 1), (2, 0), (2, 1)]):
            t = i + 1
            panel = tk.LabelFrame(self._matten_frame, text=f'Matte {t}',
                                  labelanchor='n')
            apply_table_panel_style(panel)
            panel.grid(row=row, column=col, padx=14, pady=12, sticky='nsew')
            self._matte_panels[t] = panel

        for r in range(3):
            self._matten_frame.grid_rowconfigure(r, weight=0 if r == 0 else 1)
        self._matten_frame.grid_columnconfigure(0, weight=1)
        self._matten_frame.grid_columnconfigure(1, weight=1)

    def _refresh_matten_panels(self):
        logger.info("[MATTEN REFRESH] Refreshing mat panels")
        for t, panel in self._matte_panels.items():
            for w in panel.winfo_children():
                w.destroy()

            assigned = [k for k, v in self.bracket_table_assignment.items()
                        if v == t]
            logger.info(f"  Mat {t}: {len(assigned)} brackets assigned: {assigned}")
            if not assigned:
                lbl = tk.Label(panel, text='(Keine Brackets zugewiesen)',
                               bg=COLORS['bg_panel'], fg=COLORS['text_muted'],
                               font=FONTS['body_xs'])
                lbl.pack(pady=14)
                continue

            for key in assigned:
                status_txt, status_col = self._bracket_status(key)
                row = tk.Frame(panel, bg=COLORS['bg_panel'])
                row.pack(fill=tk.X, pady=3, padx=8)

                short = key if len(key) <= 32 else key[:29] + '…'
                btn = tk.Button(row, text=short, anchor='w',
                                command=lambda k=key: self.show_fight_view(k))
                apply_button_style(btn, 'primary')
                btn.configure(font=FONTS['body_sm'], padx=8, pady=4)
                btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

                tk.Label(row, text=status_txt,
                         bg=COLORS['bg_panel'], fg=status_col,
                         font=FONTS['body_xs']).pack(side=tk.RIGHT, padx=(6, 0))

    def _bracket_status(self, key):
        method = self.bracket_generation_methods.get(key)
        if method in ('pools', 'double'):
            return 'Pool', COLORS['text_muted']

        pairs = self.brackets.get(key, {}).get('bracket', [])
        if not pairs:
            return '', COLORS['text_muted']

        rounds = self._compute_rounds(pairs, self.match_results.get(key, {}))
        real = [d for rnd in rounds for d in rnd
                if not (d['p1'] == 'Freilos' and d['p2'] == 'Freilos')]
        done = sum(1 for d in real if d['winner'] is not None)
        total = len(real)

        if total == 0:
            return '', COLORS['text_muted']
        if done == total:
            return '✓ Done', COLORS['accent_green']
        if done > 0:
            return f'{done}/{total}', COLORS['accent_orange']
        return 'Not started', COLORS['text_secondary']

    # ---------------------------------------------------------- fight view UI

    def _build_fight_view(self):
        self._fight_frame = create_dark_frame(self._content)

        # Hint label (shown above canvas in pool view, hidden in KO view)
        self._view_hint = tk.Label(self._fight_frame, text='')
        apply_label_style(self._view_hint, 'info')
        self._view_hint.pack(fill=tk.X, pady=(0, 4))

        canvas_wrap = create_dark_frame(self._fight_frame)
        canvas_wrap.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(canvas_wrap, bg=COLORS['bg_darker'],
                                 highlightthickness=0, borderwidth=0)

        xsc = ttk.Scrollbar(canvas_wrap, orient=tk.HORIZONTAL,
                            style='FM.Horizontal.TScrollbar',
                            command=self._canvas.xview)
        ysc = ttk.Scrollbar(canvas_wrap, orient=tk.VERTICAL,
                            style='FM.Vertical.TScrollbar',
                            command=self._canvas.yview)

        self._canvas.configure(xscrollcommand=xsc.set, yscrollcommand=ysc.set)
        self._canvas.bind('<Button-1>', self._on_canvas_click)
        self._canvas.bind('<MouseWheel>', self._on_mousewheel)
        self._canvas.bind('<Button-4>', self._on_mousewheel)
        self._canvas.bind('<Button-5>', self._on_mousewheel)

        ysc.pack(side=tk.RIGHT, fill=tk.Y)
        xsc.pack(side=tk.BOTTOM, fill=tk.X)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # "Finish Pool" action bar — shown only for double-pool brackets
        self._pool_action_bar = create_dark_frame(self._fight_frame)
        self._finish_pool_btn = tk.Button(
            self._pool_action_bar, text='✓ Finish Pool  →  Fill KO Bracket',
            command=self._finish_pool)
        apply_button_style(self._finish_pool_btn, 'primary')
        self._finish_pool_btn.pack(side=tk.RIGHT, padx=8, pady=6)

    # ----------------------------------------------------------------- views

    def show_matten_view(self):
        """Show the 4-Matte overview (entry point for this screen)."""
        self._fight_frame.pack_forget()
        self._zoom_bar.pack_forget()
        self._matten_frame.pack(fill=tk.BOTH, expand=True)

        self._back_btn.configure(text='← Zurück zur Listenansicht')
        self._breadcrumb.set('Fight Monitoring')
        self.current_bracket_key = None
        self._refresh_matten_panels()

    def show_fight_view(self, bracket_key):
        """Show the interactive KO or pool view for a bracket."""
        logger.info(f"Showing fight view for bracket '{bracket_key}'")
        self.current_bracket_key = bracket_key
        self._matten_frame.pack_forget()
        self._fight_frame.pack(fill=tk.BOTH, expand=True)

        t = self.bracket_table_assignment.get(bracket_key, '?')
        self._breadcrumb.set(f'Matte {t}  ›  {bracket_key}')
        self._back_btn.configure(text='← Matten')

        method = self.bracket_generation_methods.get(bracket_key)
        is_pool = method in ('pools', 'double')

        if is_pool:
            self._view_hint.configure(text='Click a score cell to edit it.')
            self._zoom_bar.pack(side=tk.RIGHT, in_=self.winfo_children()[0])
            if method == 'double':
                self._pool_action_bar.pack(fill=tk.X)
            else:
                self._pool_action_bar.pack_forget()
        else:
            self._pool_action_bar.pack_forget()
            self._view_hint.configure(
                text='Click top half of a match box → Fighter 1 wins  │  '
                     'Bottom half → Fighter 2 wins  │  Click winner again → undo')
            self._zoom_bar.pack(side=tk.RIGHT,
                                in_=self.winfo_children()[0])  # nav bar

        # Schedule render after layout settles (fixes invisible-on-first-open bug)
        self.after(30, lambda k=bracket_key: self._render(k))

    def _go_back(self):
        """Context-sensitive back: matten overview → bracket viewer."""
        if self.current_bracket_key is not None:
            # We're in a fight view → go back to matten overview
            self.show_matten_view()
        else:
            # We're in matten overview → leave the screen entirely
            if self.on_back:
                self.on_back()

    # ------------------------------------------------------ render dispatcher

    def _render(self, bracket_key):
        """Dispatch to KO or pool renderer."""
        if bracket_key != self.current_bracket_key:
            return  # stale after() call

        if self._active_cell_entry is not None:
            self._active_cell_entry.destroy()
            self._active_cell_entry = None

        self._canvas.delete('all')
        self._match_boxes = {}
        self._pool_cells = {}
        self._ko_match_boxes = {}
        self._loser_match_boxes = {}

        method = self.bracket_generation_methods.get(bracket_key)

        if method in ('pools', 'double'):
            self._render_pool(bracket_key)
        else:
            self._render_ko(bracket_key)

    # ------------------------------------------------------------ clicking

    def _on_canvas_click(self, event):
        # Commit any open cell entry before processing the click
        if self._active_cell_entry is not None:
            self._active_cell_entry._commit()

        if not self.current_bracket_key:
            logger.debug("Click handler: no current bracket key")
            return

        bkey = self.current_bracket_key
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        logger.debug(f"Canvas click on bracket '{bkey}' at ({event.x}, {event.y})")

        method = self.bracket_generation_methods.get(bkey)
        if method in ('pools', 'double'):
            self._handle_pool_click(cx, cy, bkey)
        else:
            if not self._handle_lb_click(cx, cy, bkey):
                self._handle_wb_click(cx, cy, bkey)

    # ----------------------------------------------------------------- zoom

    def _zoom_in(self):
        self.zoom_level = min(self.zoom_level * 1.2, 3.0)
        self._zoom_label.config(text=f'{int(self.zoom_level * 100)}%')
        if self.current_bracket_key:
            self._render(self.current_bracket_key)

    def _zoom_out(self):
        self.zoom_level = max(self.zoom_level / 1.2, 0.3)
        self._zoom_label.config(text=f'{int(self.zoom_level * 100)}%')
        if self.current_bracket_key:
            self._render(self.current_bracket_key)

    def _zoom_reset(self):
        self.zoom_level = 1.0
        self._zoom_label.config(text='100%')
        if self.current_bracket_key:
            self._render(self.current_bracket_key)

    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self._canvas.yview_scroll(1, 'units')
        elif event.num == 4 or event.delta > 0:
            self._canvas.yview_scroll(-1, 'units')

    def on_show(self, force_reload=False):
        """Lifecycle hook called when screen is displayed."""
        logger.debug(f"[LIFECYCLE] FightMonitoringScreen.on_show(force_reload={force_reload})")
        if self.main_window:
            # Always update brackets from main_window cache (they may have been modified from previous screens)
            self.brackets = self.main_window.brackets
            self.bracket_generation_methods = self.main_window.bracket_generation_methods
            self.bracket_table_assignment = self.main_window.bracket_table_assignment
            self.match_results = self.main_window.match_results
            self.loser_match_results = self.main_window.loser_match_results if hasattr(self.main_window, 'loser_match_results') else {}
            self.pool_cell_values = self.main_window.pool_cell_values if hasattr(self.main_window, 'pool_cell_values') else {}
            logger.debug(f"[ON_SHOW] FightMonitoringScreen synced {len(self.brackets)} brackets from cache")
            
            # Always reset to matten view when screen is shown (ensures mat assignments display in sync)
            self.show_matten_view()
            logger.info("[ON_SHOW] FightMonitoringScreen reset to matten overview")

            # Welle-3-ish: einmaliger Sync aus DB + periodisches Polling starten
            try:
                n = self._reload_results_for_all_brackets()
                logger.info(f"[ON_SHOW] Initial-Sync aus DB: {n} Brackets")
                if self.current_bracket_key:
                    self._render(self.current_bracket_key)
                else:
                    self._refresh_matten_panels()
            except Exception:
                logger.error("Initial-Sync fehlgeschlagen", exc_info=True)
            self._start_polling()

    def on_close_screen(self):
        """Cleanup when screen is hidden."""
        # Polling stoppen wenn Screen verlassen
        self._polling_active = False

    # ----------------------------------------------------- External-DB-Refresh

    def _reload_results_for_all_brackets(self):
        """Holt fuer alle bekannten Brackets die Scores/winner_ids aus DB
        und ueberschreibt die in-memory Caches auf main_window. Fuer Live-
        Sync mit JudgeFrontend (das direkt in DB schreibt).
        """
        if not self.main_window or not self.main_window.db_service:
            return 0
        db = self.main_window.db_service
        # Bracket DB-IDs holen (bracket_key -> bracket_id)
        bracket_ids = db.get_bracket_id_map() if hasattr(db, 'get_bracket_id_map') else None
        reloaded = 0
        for bkey, bdata in (self.brackets or {}).items():
            bid = None
            if bracket_ids:
                bid = bracket_ids.get(bkey)
            if bid is None:
                # Fallback: ueber Groups-API
                try:
                    bid = db.get_bracket_id_by_key(bkey)
                except Exception:
                    bid = None
            if bid is None:
                continue
            btype = self.bracket_generation_methods.get(bkey, 'ko')
            ok = db.reload_results_into_caches(
                bracket_key=bkey,
                bracket_id=bid,
                bracket_type=btype,
                bracket_data=bdata,
                match_results=self.match_results,
                pool_cell_values=self.pool_cell_values,
                ko_match_results=self.ko_match_results,
                loser_match_results=self.loser_match_results,
            )
            if ok:
                reloaded += 1
        return reloaded

    def _manual_refresh(self):
        """User klickt 'Aktualisieren'. Lade alle Caches aus DB, re-render."""
        n = self._reload_results_for_all_brackets()
        logger.info(f"[MANUAL REFRESH] {n} Brackets aus DB neu geladen")
        # Re-render der aktuellen Sicht
        if self.current_bracket_key:
            self._render(self.current_bracket_key)
        else:
            self._refresh_matten_panels()

    def _start_polling(self):
        """Periodischer Refresh alle 3s waehrend dieser Screen sichtbar ist."""
        self._polling_active = True
        self._schedule_next_poll()

    def _schedule_next_poll(self):
        if not getattr(self, '_polling_active', False):
            return
        self.after(3000, self._poll_tick)

    def _poll_tick(self):
        if not getattr(self, '_polling_active', False):
            return
        # Nicht refreshen wenn User gerade in einer Zelle tippt
        if getattr(self, '_active_cell_entry', None) is not None:
            self._schedule_next_poll()
            return
        try:
            self._reload_results_for_all_brackets()
            if self.current_bracket_key:
                self._render(self.current_bracket_key)
            else:
                self._refresh_matten_panels()
        except Exception:
            logger.error("Polling-Refresh fehlgeschlagen", exc_info=True)
        self._schedule_next_poll()

