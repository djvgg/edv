# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pool bracket mixin for FightMonitoringScreen."""

import tkinter as tk
from ..styles import COLORS, FONTS
from ..utils import draw_pools_on_canvas
import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger  # noqa: E402
logger = get_logger('fight_monitoring')


class _PoolMixin:
    """Mixin providing pool rendering, cell editing, and pool click handling."""

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

    def _handle_pool_click(self, cx, cy, bkey):
        """Handle a click when the current bracket uses the pool/double method.

        Checks KO phase match boxes first, then falls through to score cell edits.
        """
        # KO bracket boxes (pool KO phase — clickable like regular KO)
        for (r, m), (x1, y1, x2, y2, p1, p2) in self._ko_match_boxes.items():
            if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                continue
            if not p1 or not p2:
                return
            if p1 == 'TBD' and p2 == 'TBD':
                return

            if p1 == 'TBD':
                clicked = p2
            elif p2 == 'TBD':
                clicked = p1
            else:
                clicked = p1 if cy <= (y1 + y2) / 2 else p2

            results = self.ko_match_results.setdefault(bkey, {})
            current = results.get((r, m))
            if current == clicked:
                del results[(r, m)]
                if r == 0:
                    # Undoing a semi invalidates the final
                    if self.db_service:
                        self.db_service.delete_fight_position(bkey, 'wb', 1, 0)
                    results.pop((1, 0), None)
                if self.db_service:
                    self.db_service.reset_fight_result(bkey, 'wb', r, m)
            else:
                if current is not None and r == 0:
                    # Changing a semi: the final gets new participants
                    if self.db_service:
                        self.db_service.delete_fight_position(bkey, 'wb', 1, 0)
                    results.pop((1, 0), None)
                results[(r, m)] = clicked
                logger.info(f"Fight result set: bracket='{bkey}', wb r{r} m{m}: {p1} vs {p2} -> Winner: {clicked}")
                if self.db_service:
                    logger.debug(f"Recording fight result to DB for '{bkey}'")
                    self.db_service.record_fight_result(bkey, 'wb', r, m, clicked, p1_name=p1, p2_name=p2)
            self._render(bkey)
            return

        # Pool score cells
        for cell_key, (x1, y1, x2, y2) in self._pool_cells.items():
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                self._start_cell_edit(cell_key, x1, y1, x2, y2)
                return

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
            font=(FONTS['body_md'][0], max(7, int(9 * self.zoom_level))),
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
                self._persist_pool_score(bkey, cell_key, vals)
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

    def _persist_pool_score(self, bkey, cell_key, vals):
        """
        After a score cell is committed, write the fight result to DB.
        cell_key = (pool_idx, row, fight_num, 'L'|'R')
        Resolves both fighters from the fight schedule, then calls db_service.
        """
        if not self.db_service:
            return
        from frontend.utils.pool_renderer import _generate_fight_schedule
        from frontend.utils import split_into_pools, determine_pool_structure

        pool_idx, row, fight_num, side = cell_key

        bracket_data = self.brackets.get(bkey, {})
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

        pool = pools[pool_idx]
        schedule = _generate_fight_schedule(len(pool))
        if fight_num >= len(schedule):
            return

        # Find the two fighter indices for this fight
        idx_a = idx_b = None
        for match in schedule[fight_num]:
            if row in match:
                idx_a = match[0]
                idx_b = match[1]
                break
        if idx_a is None or idx_b is None or idx_a >= len(pool) or idx_b >= len(pool):
            return

        name_a = pool[idx_a]['Name']
        name_b = pool[idx_b]['Name']

        # Collect both sides of the score for this fight
        score_a = vals.get((pool_idx, idx_a, fight_num, 'L'), '')
        score_b = vals.get((pool_idx, idx_b, fight_num, 'L'), '')

        self.db_service.record_pool_score(
            bkey, name_a, name_b, score_a, score_b
        )
