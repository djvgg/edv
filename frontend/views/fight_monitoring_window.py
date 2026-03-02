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
from ..utils import draw_pools_on_canvas


class FightMonitoringScreen(tk.Frame):
    """
    In-app Fight Monitoring screen.

    The main window creates this frame, packs it full-screen, and sets:
        screen.on_back = self.show_bracket_viewer
    """

    def __init__(self, parent, brackets, bracket_table_assignment,
                 bracket_generation_methods, match_results,
                 loser_match_results=None, pool_cell_values=None,
                 ko_bracket_data=None, ko_match_results=None):
        super().__init__(parent, bg=COLORS['bg_dark'])

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
                        text='Click a bracket to monitor its fights.')
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
        for t, panel in self._matte_panels.items():
            for w in panel.winfo_children():
                w.destroy()

            assigned = [k for k, v in self.bracket_table_assignment.items()
                        if v == t]
            if not assigned:
                lbl = tk.Label(panel, text='(no brackets assigned)',
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

        self._back_btn.configure(text='← Back to Bracket Manager')
        self._breadcrumb.set('Fight Monitoring')
        self.current_bracket_key = None
        self._refresh_matten_panels()

    def show_fight_view(self, bracket_key):
        """Show the interactive KO or pool view for a bracket."""
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

    # ------------------------------------------------------ bracket logic

    def _compute_rounds(self, bracket_pairs, match_results):
        """
        Compute all rounds from first-round pairs, propagating winners forward.
        Freilos (vs BYE) auto-advances immediately.

        Returns:
            List of rounds; each = [{'p1', 'p2', 'winner'}, ...]
        """
        if not bracket_pairs:
            return []

        rounds = []

        # Round 0
        r0 = []
        for i, (p1, p2) in enumerate(bracket_pairs):
            winner = match_results.get((0, i))
            if winner is None:
                if p1 == 'Freilos' and p2 != 'Freilos':
                    winner = p2
                elif p2 == 'Freilos' and p1 != 'Freilos':
                    winner = p1
            r0.append({'p1': p1, 'p2': p2, 'winner': winner})
        rounds.append(r0)

        # Later rounds
        while len(rounds[-1]) > 1:
            prev = rounds[-1]
            r_idx = len(rounds)
            next_r = []

            for i in range(0, len(prev), 2):
                m1 = prev[i]
                m2 = prev[i + 1] if i + 1 < len(prev) else None

                def _slot(match):
                    if match is None:
                        return 'Freilos'
                    if match['winner']:
                        return match['winner']
                    if match['p1'] == 'Freilos' and match['p2'] == 'Freilos':
                        return 'Freilos'
                    return 'TBD'

                p1, p2 = _slot(m1), _slot(m2)
                m_idx = len(next_r)
                winner = match_results.get((r_idx, m_idx))
                if winner is None:
                    if p1 == 'Freilos' and p2 not in ('Freilos', 'TBD'):
                        winner = p2
                    elif p2 == 'Freilos' and p1 not in ('Freilos', 'TBD'):
                        winner = p1

                next_r.append({'p1': p1, 'p2': p2, 'winner': winner})

            rounds.append(next_r)

        return rounds

    def _compute_loser_rounds(self, wb_rounds, lb_results):
        """
        Compute losers (consolation) bracket rounds from the winners bracket.

        Structure:
          LB R1  – consecutive WB-R1 losers fight each other in pairs
          LB R2  – LB-R1 winners vs WB-R2 losers (1-to-1)
          LB R3  – reduction if needed (LB winners > next WB-loser count), else
                   LB Rk winners vs WB-Rk losers
          ...until one match remains → 3rd-place fight

        WB Final loser is NOT fed into the LB (they are already 2nd place).
        """
        if len(wb_rounds) < 2:
            return []

        def get_loser(match):
            w = match['winner']
            if w is None:
                return 'TBD'
            if match['p1'] == 'Freilos' or match['p2'] == 'Freilos':
                return 'Freilos'
            return match['p2'] if w == match['p1'] else match['p1']

        def make_match(p1, p2, lb_r, lb_m):
            stored = lb_results.get((lb_r, lb_m))
            if stored is None:
                if p1 == 'Freilos' and p2 not in ('Freilos', 'TBD'):
                    stored = p2
                elif p2 == 'Freilos' and p1 not in ('Freilos', 'TBD'):
                    stored = p1
            return {'p1': p1, 'p2': p2, 'winner': stored}

        loser_rounds = []
        lb_r = 0

        # LB R1: pair consecutive losers from WB R1
        wb_r1_losers = [get_loser(m) for m in wb_rounds[0]]
        lb_r1 = []
        for i in range(0, len(wb_r1_losers), 2):
            p1 = wb_r1_losers[i]
            p2 = wb_r1_losers[i + 1] if i + 1 < len(wb_r1_losers) else 'Freilos'
            lb_r1.append(make_match(p1, p2, lb_r, i // 2))
        loser_rounds.append(lb_r1)
        lb_r += 1

        wb_idx = 1  # next WB round to pull losers from (we skip the WB Final)

        while True:
            prev = loser_rounds[-1]
            if len(prev) <= 1:
                break

            lb_winners = [(m['winner'] if m['winner'] is not None else 'TBD')
                          for m in prev]

            # Inject losers from next WB round (stop before the WB Final)
            if wb_idx < len(wb_rounds) - 1:
                wb_losers = [get_loser(m) for m in wb_rounds[wb_idx]]

                if len(lb_winners) > len(wb_losers):
                    # Reduction round: LB winners fight each other first
                    reduction = []
                    for i in range(0, len(lb_winners), 2):
                        p1 = lb_winners[i]
                        p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                        reduction.append(make_match(p1, p2, lb_r, i // 2))
                    loser_rounds.append(reduction)
                    lb_r += 1
                    # Loop again — re-read prev from the reduction round
                else:
                    # Injection round: each LB winner faces a WB loser
                    injection = []
                    for j in range(len(wb_losers)):
                        lw = lb_winners[j] if j < len(lb_winners) else 'TBD'
                        wl = wb_losers[j]
                        injection.append(make_match(lw, wl, lb_r, j))
                    loser_rounds.append(injection)
                    lb_r += 1
                    wb_idx += 1
            else:
                # No more WB rounds to inject — remaining LB winners fight for 3rd
                if len(lb_winners) > 1:
                    final = []
                    for i in range(0, len(lb_winners), 2):
                        p1 = lb_winners[i]
                        p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                        final.append(make_match(p1, p2, lb_r, i // 2))
                    loser_rounds.append(final)
                break

        return loser_rounds

    # ----------------------------------------------------------- rendering

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

    def _render_loser_bracket(self, loser_rounds, y_offset,
                              z, BW, BH, XG, YG, SX, FS, LW):
        """Draw the losers (consolation) bracket below the winners bracket.

        Returns the max y coordinate used (for scroll-region calculation).
        """
        font = ('Consolas', FS)
        label_font = ('Arial', max(8, int(11 * z)), 'bold')

        # ── Compute positions ───────────────────────────────────────────
        lb_pos = {}
        lb_ymid = {}

        # LB R0: stack vertically
        for m in range(len(loser_rounds[0])):
            x = SX
            y = y_offset + m * (BH + YG)
            lb_pos[(0, m)] = (x, y)
            lb_ymid[(0, m)] = y + BH // 2

        for r in range(1, len(loser_rounds)):
            x = SX + r * (BW + XG)
            prev_count = len(loser_rounds[r - 1])
            curr_count = len(loser_rounds[r])

            for m in range(curr_count):
                if curr_count < prev_count:
                    # Reduction: centre between the two source matches
                    ya = lb_ymid.get((r - 1, m * 2), y_offset + BH // 2)
                    yb = lb_ymid.get((r - 1, m * 2 + 1), ya)
                    y = (ya + yb) // 2 - BH // 2
                else:
                    # Injection (or equal-count): same row as source match m
                    ya = lb_ymid.get((r - 1, m), y_offset + BH // 2)
                    y = ya - BH // 2

                lb_pos[(r, m)] = (x, y)
                lb_ymid[(r, m)] = y + BH // 2

        # ── Round labels ─────────────────────────────────────────────────
        nr = len(loser_rounds)
        for r in range(nr):
            lx = SX + r * (BW + XG) + BW // 2
            label = '3rd Place' if r == nr - 1 else f'Loser R{r + 1}'
            self._canvas.create_text(
                lx, y_offset - int(20 * z),
                text=label, anchor='c',
                fill=COLORS['accent_orange'], font=label_font)

        # ── Connectors ───────────────────────────────────────────────────
        for r in range(nr - 1):
            prev_count = len(loser_rounds[r])
            next_count = len(loser_rounds[r + 1])
            is_reduction = next_count < prev_count

            for m in range(prev_count):
                if (r, m) not in lb_pos:
                    continue
                x, y = lb_pos[(r, m)]
                xr = x + BW
                yc = y + BH // 2
                nm = m // 2 if is_reduction else m

                if (r + 1, nm) not in lb_pos:
                    continue
                nx, ny = lb_pos[(r + 1, nm)]
                xmid = xr + XG // 2

                if is_reduction:
                    ty = ny + BH // 4 if m % 2 == 0 else ny + 3 * BH // 4
                else:
                    ty = ny + BH // 4  # LB winner → top half (p1) of injection match

                self._canvas.create_line(
                    xr, yc, xmid, yc,
                    fill=COLORS['accent_orange'], width=LW, dash=(4, 3))
                self._canvas.create_line(
                    xmid, yc, xmid, ty,
                    fill=COLORS['accent_orange'], width=LW, dash=(4, 3))
                self._canvas.create_line(
                    xmid, ty, nx, ty,
                    fill=COLORS['accent_orange'], width=LW, dash=(4, 3))

        # ── Match boxes ──────────────────────────────────────────────────
        for r, matches in enumerate(loser_rounds):
            is_last = (r == nr - 1)
            for m, match in enumerate(matches):
                p1, p2, winner = match['p1'], match['p2'], match['winner']
                x, y = lb_pos[(r, m)]
                x2, y2 = x + BW, y + BH
                my = y + BH // 2

                if is_last:
                    # Both fighters share 3rd place — no fight, both shown green
                    p1w = p1 not in ('Freilos', 'TBD')
                    p2w = p2 not in ('Freilos', 'TBD')
                    decided = True
                else:
                    self._loser_match_boxes[(r, m)] = (x, y, x2, y2, p1, p2)
                    p1w = (winner is not None and winner == p1
                           and p1 not in ('Freilos', 'TBD'))
                    p2w = (winner is not None and winner == p2
                           and p2 not in ('Freilos', 'TBD'))
                    decided = winner is not None

                # Box (orange border to distinguish from WB)
                self._canvas.create_rectangle(
                    x, y, x2, y2,
                    fill=COLORS['bg_panel'],
                    outline=COLORS['accent_orange'], width=LW)

                if p1w:
                    self._canvas.create_rectangle(
                        x + LW, y + LW, x2 - LW, my, fill='#1a3d1a', outline='')
                elif decided and not p1w and p1 not in ('Freilos', 'TBD'):
                    self._canvas.create_rectangle(
                        x + LW, y + LW, x2 - LW, my, fill='#3d1a1a', outline='')

                if p2w:
                    self._canvas.create_rectangle(
                        x + LW, my, x2 - LW, y2 - LW, fill='#1a3d1a', outline='')
                elif decided and not p2w and p2 not in ('Freilos', 'TBD'):
                    self._canvas.create_rectangle(
                        x + LW, my, x2 - LW, y2 - LW, fill='#3d1a1a', outline='')

                self._canvas.create_line(
                    x, my, x2, my,
                    fill=COLORS['border'], width=1, dash=(4, 3))

                def _col(name, won):
                    if name == 'Freilos':
                        return COLORS['text_disabled']
                    if name == 'TBD':
                        return COLORS['text_muted']
                    if won:
                        return COLORS['accent_green']
                    if decided and not won:
                        return COLORS['accent_red']
                    return COLORS['text_primary']

                self._canvas.create_text(
                    x + 8, y + BH // 4,
                    text=(p1[:24] if len(p1) > 24 else p1),
                    anchor='w', fill=_col(p1, p1w), font=font)
                self._canvas.create_text(
                    x + 8, y + 3 * BH // 4,
                    text=(p2[:24] if len(p2) > 24 else p2),
                    anchor='w', fill=_col(p2, p2w), font=font)

                ck_font = ('Arial', FS + 1, 'bold')
                if p1w:
                    self._canvas.create_text(
                        x2 - 10, y + BH // 4, text='✓',
                        anchor='c', fill=COLORS['accent_green'], font=ck_font)
                if p2w:
                    self._canvas.create_text(
                        x2 - 10, y + 3 * BH // 4, text='✓',
                        anchor='c', fill=COLORS['accent_green'], font=ck_font)

                sm_font = ('Arial', max(6, FS - 1))
                both_real = (p1 not in ('Freilos', 'TBD')
                             and p2 not in ('Freilos', 'TBD'))
                if both_real and not decided:
                    self._canvas.create_text(
                        x2 - 6, my, text='← pick',
                        anchor='e', fill=COLORS['text_muted'], font=sm_font)

        if lb_pos:
            return max(p[1] for p in lb_pos.values()) + BH + YG
        return y_offset

    # ---- pool (read-only) ------------------------------------------------

    def _render_pool(self, bracket_key):
        bracket_data = self.brackets.get(bracket_key, {})
        participants = bracket_data.get('fighters', [])
        if not participants:
            self._canvas.create_text(300, 200, text='No participants found.',
                                     fill=COLORS['text_muted'],
                                     font=FONTS['heading_md'])
            return

        normalized = [
            {'Name': p.get('Name', p.get('name', '')),
             'Verein': p.get('Verein', p.get('verein', p.get('club', '')))}
            for p in participants if isinstance(p, dict)
        ]

        z = self.zoom_level
        cell_values = self.pool_cell_values.get(bracket_key, {})
        ko_data = self.ko_bracket_data.get(bracket_key)
        ko_results = self.ko_match_results.get(bracket_key, {})
        pool_size = bracket_data.get('pool_size')
        method = self.bracket_generation_methods.get(bracket_key)
        total_w, total_h, cell_positions, ko_boxes = draw_pools_on_canvas(
            self._canvas, normalized, z, COLORS, FONTS,
            int(50 * z), int(60 * z),
            cell_values=cell_values, ko_data=ko_data, ko_match_results=ko_results,
            pool_size=pool_size, generation_method=method
        )
        self._pool_cells = cell_positions
        self._ko_match_boxes = ko_boxes
        self._canvas.configure(scrollregion=(0, 0, total_w, total_h))

    # ---- KO bracket (interactive) ----------------------------------------

    def _render_ko(self, bracket_key):
        pairs = self.brackets.get(bracket_key, {}).get('bracket', [])
        if not pairs:
            self._canvas.create_text(300, 200,
                                     text='No bracket data available.',
                                     fill=COLORS['text_muted'],
                                     font=FONTS['heading_md'])
            return

        results = self.match_results.get(bracket_key, {})
        rounds = self._compute_rounds(pairs, results)
        if not rounds:
            return

        z = self.zoom_level
        BW = int(200 * z)   # box width
        BH = int(64 * z)    # box height
        XG = int(70 * z)    # x gap between rounds
        YG = int(28 * z)    # y gap between matches
        SX = int(50 * z)    # start x
        SY = int(50 * z)    # start y
        FS = max(7, int(10 * z))
        LW = max(1, int(2 * z))
        font = ('Consolas', FS)
        label_font = ('Arial', max(8, int(11 * z)), 'bold')

        # Positions
        pos = {}
        ymid = {}
        for m in range(len(rounds[0])):
            x, y = SX, SY + m * (BH + YG)
            pos[(0, m)] = (x, y)
            ymid[(0, m)] = y + BH // 2

        for r in range(1, len(rounds)):
            x = SX + r * (BW + XG)
            for m in range(len(rounds[r])):
                ya = ymid.get((r - 1, m * 2), SY + BH // 2)
                yb = ymid.get((r - 1, m * 2 + 1), ya)
                y = (ya + yb) // 2 - BH // 2
                pos[(r, m)] = (x, y)
                ymid[(r, m)] = y + BH // 2

        # Round labels
        nr = len(rounds)
        for r in range(nr):
            lx = SX + r * (BW + XG) + BW // 2
            if r == 0:
                label = 'Round 1'
            elif r == nr - 1:
                label = 'Final'
            elif r == nr - 2 and nr > 2:
                label = 'Semi-Final'
            else:
                label = f'Round {r + 1}'
            self._canvas.create_text(lx, SY // 2, text=label, anchor='c',
                                     fill=COLORS['text_secondary'],
                                     font=label_font)

        # Connectors (drawn behind boxes)
        for r in range(nr - 1):
            for m in range(len(rounds[r])):
                if (r, m) not in pos:
                    continue
                x, y = pos[(r, m)]
                xr = x + BW
                yc = y + BH // 2
                nm = m // 2
                if (r + 1, nm) not in pos:
                    continue
                nx, ny = pos[(r + 1, nm)]
                xmid = xr + XG // 2
                ty = ny + BH // 4 if m % 2 == 0 else ny + 3 * BH // 4

                self._canvas.create_line(xr, yc, xmid, yc,
                                         fill=COLORS['border_light'], width=LW)
                self._canvas.create_line(xmid, yc, xmid, ty,
                                         fill=COLORS['border_light'], width=LW)
                self._canvas.create_line(xmid, ty, nx, ty,
                                         fill=COLORS['border_light'], width=LW)

        # Match boxes
        for r, matches in enumerate(rounds):
            for m, match in enumerate(matches):
                p1, p2, winner = match['p1'], match['p2'], match['winner']
                x, y = pos[(r, m)]
                x2, y2 = x + BW, y + BH
                my = y + BH // 2

                self._match_boxes[(r, m)] = (x, y, x2, y2, p1, p2)

                p1w = winner is not None and winner == p1 and p1 not in ('Freilos', 'TBD')
                p2w = winner is not None and winner == p2 and p2 not in ('Freilos', 'TBD')
                decided = winner is not None

                # Box background
                self._canvas.create_rectangle(x, y, x2, y2,
                                              fill=COLORS['bg_panel'],
                                              outline=COLORS['border_light'],
                                              width=LW)

                # Winner/loser halves
                if p1w:
                    self._canvas.create_rectangle(
                        x + LW, y + LW, x2 - LW, my, fill='#1a3d1a', outline='')
                elif decided and not p1w and p1 not in ('Freilos', 'TBD'):
                    self._canvas.create_rectangle(
                        x + LW, y + LW, x2 - LW, my, fill='#3d1a1a', outline='')

                if p2w:
                    self._canvas.create_rectangle(
                        x + LW, my, x2 - LW, y2 - LW, fill='#1a3d1a', outline='')
                elif decided and not p2w and p2 not in ('Freilos', 'TBD'):
                    self._canvas.create_rectangle(
                        x + LW, my, x2 - LW, y2 - LW, fill='#3d1a1a', outline='')

                # Separator
                self._canvas.create_line(x, my, x2, my,
                                         fill=COLORS['border'], width=1,
                                         dash=(4, 3))

                # Name colours
                def _col(name, won):
                    if name == 'Freilos':
                        return COLORS['text_disabled']
                    if name == 'TBD':
                        return COLORS['text_muted']
                    if won:
                        return COLORS['accent_green']
                    if decided and not won:
                        return COLORS['accent_red']
                    return COLORS['text_primary']

                self._canvas.create_text(x + 8, y + BH // 4,
                                         text=(p1[:24] if len(p1) > 24 else p1),
                                         anchor='w', fill=_col(p1, p1w), font=font)
                self._canvas.create_text(x + 8, y + 3 * BH // 4,
                                         text=(p2[:24] if len(p2) > 24 else p2),
                                         anchor='w', fill=_col(p2, p2w), font=font)

                # Checkmarks
                ck_font = ('Arial', FS + 1, 'bold')
                if p1w:
                    self._canvas.create_text(x2 - 10, y + BH // 4, text='✓',
                                             anchor='c', fill=COLORS['accent_green'],
                                             font=ck_font)
                if p2w:
                    self._canvas.create_text(x2 - 10, y + 3 * BH // 4, text='✓',
                                             anchor='c', fill=COLORS['accent_green'],
                                             font=ck_font)

                # "← pick" hint for undecided real matches
                sm_font = ('Arial', max(6, FS - 1))
                both_real = p1 not in ('Freilos', 'TBD') and p2 not in ('Freilos', 'TBD')
                if both_real and winner is None:
                    self._canvas.create_text(x2 - 6, my, text='← pick',
                                             anchor='e', fill=COLORS['text_muted'],
                                             font=sm_font)

        if pos:
            wb_max_x = max(p[0] for p in pos.values()) + BW + XG + SX
            wb_max_y = max(p[1] for p in pos.values()) + BH + YG + SY
        else:
            wb_max_x = SX + BW + SX
            wb_max_y = SY + BH + SY

        # ── Losers Bracket ───────────────────────────────────────────────
        lb_results = self.loser_match_results.get(bracket_key, {})
        loser_rounds = self._compute_loser_rounds(rounds, lb_results)

        total_height = wb_max_y
        total_width = wb_max_x

        if loser_rounds:
            SECTION_GAP = int(60 * z)
            lb_y_start = wb_max_y + SECTION_GAP

            # Section divider
            div_y = wb_max_y + SECTION_GAP // 2
            self._canvas.create_line(
                SX, div_y, wb_max_x - SX, div_y,
                fill=COLORS['accent_orange'], width=1, dash=(6, 4))
            self._canvas.create_text(
                SX, div_y - int(10 * z),
                text='Losers Bracket',
                anchor='w', fill=COLORS['accent_orange'],
                font=('Arial', max(8, int(11 * z)), 'bold'))

            lb_max_y = self._render_loser_bracket(
                loser_rounds, lb_y_start,
                z, BW, BH, XG, YG, SX, FS, LW)

            lb_max_x = SX + len(loser_rounds) * (BW + XG) + SX
            total_height = lb_max_y + SY
            total_width = max(wb_max_x, lb_max_x)

        self._canvas.configure(scrollregion=(0, 0, total_width, total_height))

    # ------------------------------------------------------------ clicking

    def _on_canvas_click(self, event):
        # Commit any open cell entry before processing the click
        if self._active_cell_entry is not None:
            self._active_cell_entry._commit()

        if not self.current_bracket_key:
            return
        method = self.bracket_generation_methods.get(self.current_bracket_key)
        if method in ('pools', 'double'):
            cx = self._canvas.canvasx(event.x)
            cy = self._canvas.canvasy(event.y)

            # KO bracket boxes (clickable like regular KO)
            for (r, m), (x1, y1, x2, y2, p1, p2) in self._ko_match_boxes.items():
                if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                    continue
                if not p1 or not p2 or 'TBD' in (p1, p2):
                    return
                clicked = p1 if cy <= (y1 + y2) / 2 else p2
                results = self.ko_match_results.setdefault(self.current_bracket_key, {})
                current = results.get((r, m))
                if current == clicked:
                    del results[(r, m)]
                    # clear downstream final if a semi changed
                    if r == 0:
                        results.pop((1, 0), None)
                else:
                    if current is not None and r == 0:
                        results.pop((1, 0), None)
                    results[(r, m)] = clicked
                self._render(self.current_bracket_key)
                return

            # Pool score cells
            for cell_key, (x1, y1, x2, y2) in self._pool_cells.items():
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    self._start_cell_edit(cell_key, x1, y1, x2, y2)
                    return
            return

        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)

        # Check losers bracket boxes first (they sit below WB, no overlap)
        for (r, m), (x1, y1, x2, y2, p1, p2) in self._loser_match_boxes.items():
            if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                continue
            if p1 in ('Freilos', 'TBD') or p2 in ('Freilos', 'TBD'):
                return

            clicked = p1 if cy <= (y1 + y2) / 2 else p2
            lb_results = self.loser_match_results.setdefault(
                self.current_bracket_key, {})
            current = lb_results.get((r, m))

            if current == clicked:
                del lb_results[(r, m)]
                self._clear_loser_downstream(r)
            else:
                if current is not None:
                    self._clear_loser_downstream(r)
                lb_results[(r, m)] = clicked

            self._render(self.current_bracket_key)
            return

        for (r, m), (x1, y1, x2, y2, p1, p2) in self._match_boxes.items():
            if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                continue
            if p1 in ('Freilos', 'TBD') or p2 in ('Freilos', 'TBD'):
                return

            clicked = p1 if cy <= (y1 + y2) / 2 else p2
            results = self.match_results.setdefault(self.current_bracket_key, {})
            current = results.get((r, m))

            if current == clicked:
                del results[(r, m)]
                self._clear_downstream(r, m)
            else:
                if current is not None:
                    self._clear_downstream(r, m)
                results[(r, m)] = clicked

            self._render(self.current_bracket_key)
            break

    def _finish_pool(self):
        """Read Platz 1 & 2 from each pool and populate the KO bracket slots."""
        from frontend.utils import split_into_pools, determine_pool_structure

        bkey = self.current_bracket_key
        if not bkey:
            return

        bracket_data = self.brackets.get(bkey, {})
        participants = bracket_data.get('fighters', [])
        normalized = [
            {'Name': p.get('Name', p.get('name', '')),
             'Verein': p.get('Verein', p.get('verein', p.get('club', '')))}
            for p in participants if isinstance(p, dict)
        ]

        num_pools = determine_pool_structure(len(normalized))
        pools = split_into_pools(normalized, num_pools=num_pools)
        cv = self.pool_cell_values.get(bkey, {})

        ko = {}
        for pool_idx, pool in enumerate(pools):
            for row, fighter in enumerate(pool):
                platz = cv.get((pool_idx, row, 'platz'), '').strip()
                if platz == '1':
                    ko[f'p{pool_idx}_1st'] = fighter['Name']
                elif platz == '2':
                    ko[f'p{pool_idx}_2nd'] = fighter['Name']

        self.ko_bracket_data[bkey] = ko
        self._render(bkey)

    def _start_cell_edit(self, cell_key, x1, y1, x2, y2):
        """Overlay an Entry widget on a pool score cell for inline editing."""
        # Commit any existing entry first
        if self._active_cell_entry is not None:
            self._active_cell_entry.destroy()
            self._active_cell_entry = None

        bkey = self.current_bracket_key
        current_val = self.pool_cell_values.get(bkey, {}).get(cell_key, '')

        # Detect cell type and set input constraints
        is_score_cell = len(cell_key) == 4 and cell_key[-1] in ('L', 'R')
        is_kampfzeit  = cell_key[1] == 'kampfzeit'

        if is_score_cell:
            max_chars, allow_spaces = 2, False
        elif is_kampfzeit:
            max_chars, allow_spaces = 5, False
        else:  # summary: punkte, ubw, platz
            max_chars, allow_spaces = 2, False

        var = tk.StringVar(value=current_val)
        entry_kwargs = dict(
            bg='white', fg='black',
            font=('Consolas', max(7, int(9 * self.zoom_level))),
            justify='center', relief='flat', bd=0,
            highlightthickness=0,
        )
        vcmd = (self.register(
            lambda text, m=max_chars, s=allow_spaces:
                len(text) <= m and (s or ' ' not in text)
        ), '%P')
        entry_kwargs['validate'] = 'key'
        entry_kwargs['validatecommand'] = vcmd

        entry = tk.Entry(self._canvas, textvariable=var, **entry_kwargs)
        self._canvas.create_window(
            (x1 + x2) / 2, (y1 + y2) / 2,
            window=entry,
            width=int(x2 - x1) - 4,
            height=int(y2 - y1) - 4,
            anchor='c',
        )
        entry.focus_set()
        entry.select_range(0, tk.END)
        self._active_cell_entry = entry

        def commit(event=None):  # also stored as entry._commit for external calls
            if self._active_cell_entry is not entry:
                return  # already superseded
            self._active_cell_entry = None
            val = var.get().strip()
            vals = self.pool_cell_values.setdefault(bkey, {})
            if val:
                vals[cell_key] = val
            elif cell_key in vals:
                del vals[cell_key]
            if is_score_cell:
                self._mirror_score(cell_key, val, vals)
            entry.destroy()
            self._render(bkey)

        entry._commit = commit
        entry.bind('<Return>', commit)
        entry.bind('<Tab>', commit)
        entry.bind('<FocusOut>', commit)
        entry.bind('<Escape>', lambda e: (
            setattr(self, '_active_cell_entry', None),
            entry.destroy(),
        ))

    def _mirror_score(self, cell_key, val, vals):
        """Mirror a score entry to the opponent's corresponding cell.

        For fight cell (pool_idx, row, fight_num, side):
          - entering on 'L' (my score) → writes same value to opponent's 'R'
          - entering on 'R' (opponent score) → writes same value to opponent's 'L'
        """
        from frontend.utils.pool_renderer import _generate_fight_schedule
        from frontend.utils import split_into_pools, determine_pool_structure

        pool_idx, row, fight_num, side = cell_key

        bracket_data = self.brackets.get(self.current_bracket_key, {})
        participants = bracket_data.get('fighters', [])
        normalized = [
            {'Name': p.get('Name', p.get('name', '')),
             'Verein': p.get('Verein', p.get('verein', p.get('club', '')))}
            for p in participants if isinstance(p, dict)
        ]

        num_pools = determine_pool_structure(len(normalized))
        pools = split_into_pools(normalized, num_pools=num_pools)
        if pool_idx >= len(pools):
            return

        fight_schedule = _generate_fight_schedule(len(pools[pool_idx]))
        if fight_num >= len(fight_schedule):
            return

        # Find the other fighter's row in this fight
        other_row = None
        for match in fight_schedule[fight_num]:
            if row in match:
                other_row = match[0] if match[1] == row else match[1]
                break
        if other_row is None:
            return

        # my L → opponent R, my R → opponent L
        mirror_side = 'R' if side == 'L' else 'L'
        mirror_key = (pool_idx, other_row, fight_num, mirror_side)
        if val:
            vals[mirror_key] = val
        elif mirror_key in vals:
            del vals[mirror_key]

    def _clear_downstream(self, round_idx, match_idx):
        results = self.match_results.get(self.current_bracket_key, {})
        r, m = round_idx + 1, match_idx // 2
        while (r, m) in results:
            del results[(r, m)]
            m = m // 2
            r += 1

    def _clear_loser_downstream(self, lb_round_idx):
        """Clear all losers-bracket results in rounds after lb_round_idx."""
        results = self.loser_match_results.get(self.current_bracket_key, {})
        for k in [k for k in results if k[0] > lb_round_idx]:
            del results[k]

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
