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
                 bracket_generation_methods, match_results):
        super().__init__(parent, bg=COLORS['bg_dark'])

        # Callback – set by BracketViewerApp before showing
        self.on_back = None

        # Shared data (live references to main app dicts)
        self.brackets = brackets
        self.bracket_table_assignment = bracket_table_assignment
        self.bracket_generation_methods = bracket_generation_methods
        # {bracket_key: {(round_idx, match_idx): winner_name}}
        self.match_results = match_results

        # UI state
        self.current_bracket_key = None
        self.zoom_level = 1.0
        # {(round, match): (x1, y1, x2, y2, p1, p2)}
        self._match_boxes = {}

        self._setup_ttk_styles()
        self._build_ui()

    # ----------------------------------------------------------------- styles

    def _setup_ttk_styles(self):
        style = ttk.Style()
        for name in ('FM.Vertical.TScrollbar', 'FM.Horizontal.TScrollbar'):
            orient = 'Vertical' if 'Vertical' in name else 'Horizontal'
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
            self._view_hint.configure(
                text='Pool view (read-only) – interactive pool monitoring coming soon.')
            self._zoom_bar.pack_forget()
        else:
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

    # ----------------------------------------------------------- rendering

    def _render(self, bracket_key):
        """Dispatch to KO or pool renderer."""
        if bracket_key != self.current_bracket_key:
            return  # stale after() call

        self._canvas.delete('all')
        self._match_boxes = {}

        method = self.bracket_generation_methods.get(bracket_key)

        if method in ('pools', 'double'):
            self._render_pool(bracket_key)
        else:
            self._render_ko(bracket_key)

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
        total_w, total_h = draw_pools_on_canvas(
            self._canvas, normalized, z, COLORS, FONTS,
            int(50 * z), int(60 * z)
        )
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
            mx = max(p[0] for p in pos.values()) + BW + XG + SX
            my_max = max(p[1] for p in pos.values()) + BH + YG + SY
            self._canvas.configure(scrollregion=(0, 0, mx, my_max))

    # ------------------------------------------------------------ clicking

    def _on_canvas_click(self, event):
        if not self.current_bracket_key:
            return
        method = self.bracket_generation_methods.get(self.current_bracket_key)
        if method in ('pools', 'double'):
            return  # pool clicks not yet handled

        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)

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

    def _clear_downstream(self, round_idx, match_idx):
        results = self.match_results.get(self.current_bracket_key, {})
        r, m = round_idx + 1, match_idx // 2
        while (r, m) in results:
            del results[(r, m)]
            m = m // 2
            r += 1

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
