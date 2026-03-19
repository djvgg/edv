# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""KO bracket mixin for FightMonitoringScreen."""

from ..styles import COLORS, FONTS
from ..utils import (
    compute_bracket_rounds,
    calculate_ko_positions,
    draw_ko_connectors,
    calculate_loser_positions,
    draw_loser_connectors,
)
import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger  # noqa: E402
logger = get_logger('fight_monitoring')


class _KOMixin:
    """Mixin providing all KO bracket logic, rendering, and click handling."""

    def _compute_rounds(self, bracket_pairs, match_results):
        """
        Compute all rounds from first-round pairs, propagating winners forward.
        (Delegates to imported utility function)

        Returns:
            List of rounds; each = [{'p1', 'p2', 'winner'}, ...]
        """
        logger.debug(f"_compute_rounds: {len(bracket_pairs)} R0 pairs, {len(match_results)} existing results")
        return compute_bracket_rounds(bracket_pairs, match_results)

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
                    lb_results[(lb_r, lb_m)] = stored  # Persist auto-bye winner
                elif p2 == 'Freilos' and p1 not in ('Freilos', 'TBD'):
                    stored = p1
                    lb_results[(lb_r, lb_m)] = stored  # Persist auto-bye winner
            return {'p1': p1, 'p2': p2, 'winner': stored}

        loser_rounds = []
        lb_r = 0  # Use 0-indexed rounds for consistency with rendering

        # LB R0: pair consecutive losers from WB R0
        wb_r0_losers = [get_loser(m) for m in wb_rounds[0]]
        lb_r0 = []
        for i in range(0, len(wb_r0_losers), 2):
            p1 = wb_r0_losers[i]
            p2 = wb_r0_losers[i + 1] if i + 1 < len(wb_r0_losers) else 'Freilos'
            lb_r0.append(make_match(p1, p2, lb_r, i // 2))
        loser_rounds.append(lb_r0)
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

    def _sync_bye_results(self, bracket_key, rounds, results, bracket_type):
        """Sync Freilos auto-advance winners into results dict and DB.

        For every match where one side is a bye (Freilos) and no result is
        recorded yet, the real fighter is automatically advanced and persisted
        to the DB once (tracked via _bye_db_synced to avoid duplicate writes).
        Mutates results in-place.
        """
        for r, matches in enumerate(rounds):
            for m, match in enumerate(matches):
                if (r, m) not in results and match['winner'] is not None:
                    results[(r, m)] = match['winner']
                    bye_key = (bracket_key, bracket_type, r, m)
                    if (self.db_service and bye_key not in self._bye_db_synced
                            and (match['p1'] == 'Freilos' or match['p2'] == 'Freilos')):
                        p1, p2 = match['p1'], match['p2']
                        if p1 != 'Freilos' and p2 == 'Freilos':
                            p1_name, p2_name = p1, 'Freilos'
                        else:
                            p1_name, p2_name = p2, 'Freilos'
                        self.db_service.record_fight_result(
                            bracket_key, bracket_type, r, m, match['winner'],
                            p1_name=p1_name, p2_name=p2_name)
                        self._bye_db_synced.add(bye_key)

    def _sync_lb_final_byes(self, bracket_key, loser_rounds, lb_results):
        """Auto-advance fighters in the final LB round if their opponent is a bye.

        Only triggered when the last round has ≤2 matches, meaning no more
        opponents can arrive from the WB. Mutates lb_results in-place.
        """
        if not loser_rounds or len(loser_rounds[-1]) > 2:
            return
        last_round_idx = len(loser_rounds) - 1
        for m, match in enumerate(loser_rounds[last_round_idx]):
            key = (last_round_idx, m)
            if (key not in lb_results
                    and match['winner'] is not None
                    and (match['p1'] in ('Freilos', 'TBD') or match['p2'] in ('Freilos', 'TBD'))):
                lb_results[key] = match['winner']
                bye_key = (bracket_key, 'lb', last_round_idx, m)
                if self.db_service and bye_key not in self._bye_db_synced:
                    p1, p2 = match['p1'], match['p2']
                    p1_name = p1 if p1 not in ('Freilos', 'TBD') else 'Freilos'
                    p2_name = p2 if p2 not in ('Freilos', 'TBD') else 'Freilos'
                    self.db_service.record_fight_result(
                        bracket_key, 'lb', last_round_idx, m,
                        match['winner'], p1_name=p1_name, p2_name=p2_name)
                    self._bye_db_synced.add(bye_key)

    def _render_ko(self, bracket_key):
        pairs = self.brackets.get(bracket_key, {}).get('bracket', [])
        logger.debug(f"Rendering KO bracket '{bracket_key}' with {len(pairs)} pairs from self.brackets")
        if not pairs:
            logger.warning(f"No bracket data in self.brackets for '{bracket_key}'")
            self._canvas.create_text(300, 200, text='No bracket data available.',
                                     fill=COLORS['text_muted'], font=FONTS['heading_md'])
            return

        results = self.match_results.get(bracket_key, {})
        logger.debug(f"Rendering KO rounds: {len(results)} fight results already recorded")
        rounds = self._compute_rounds(pairs, results)
        if not rounds:
            return

        self._sync_bye_results(bracket_key, rounds, results, 'wb')
        self.match_results[bracket_key] = results

        # Layout constants (all scaled by zoom)
        z = self.zoom_level
        BW = int(200 * z)
        BH = int(64 * z)
        XG = int(70 * z)
        YG = int(28 * z)
        SX = int(50 * z)
        SY = int(50 * z)
        FS = max(7, int(10 * z))
        LW = max(1, int(2 * z))
        font = ('Consolas', FS)
        label_font = ('Arial', max(8, int(11 * z)), 'bold')

        pos, ymid = calculate_ko_positions(rounds, z, SX, SY)

        # WB round labels
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
                                     fill=COLORS['text_secondary'], font=label_font)

        draw_ko_connectors(self._canvas, pos, rounds, z, COLORS)
        self._draw_wb_matches(rounds, pos, BW, BH, LW, FS, font)

        if pos:
            wb_max_x = max(p[0] for p in pos.values()) + BW + XG + SX
            wb_max_y = max(p[1] for p in pos.values()) + BH + YG + SY
        else:
            wb_max_x = SX + BW + SX
            wb_max_y = SY + BH + SY

        # Loser bracket
        lb_results = self.loser_match_results.get(bracket_key, {})
        loser_rounds = self._compute_loser_rounds(rounds, lb_results)

        self._sync_bye_results(bracket_key, loser_rounds, lb_results, 'lb')
        self._sync_lb_final_byes(bracket_key, loser_rounds, lb_results)
        self.loser_match_results[bracket_key] = lb_results

        total_height = wb_max_y
        total_width = wb_max_x

        if loser_rounds:
            SECTION_GAP = int(60 * z)
            lb_y_start = wb_max_y + SECTION_GAP
            div_y = wb_max_y + SECTION_GAP // 2
            self._canvas.create_line(SX, div_y, wb_max_x - SX, div_y,
                                     fill=COLORS['accent_orange'], width=1, dash=(6, 4))
            self._canvas.create_text(SX, div_y - int(10 * z), text='Losers Bracket',
                                     anchor='w', fill=COLORS['accent_orange'],
                                     font=(FONTS['body_md'][0], max(8, int(11 * z)), 'bold'))
            lb_max_y = self._render_loser_bracket(loser_rounds, lb_y_start,
                                                   z, BW, BH, XG, YG, SX, FS, LW)
            lb_max_x = SX + len(loser_rounds) * (BW + XG) + SX
            total_height = lb_max_y + SY
            total_width = max(wb_max_x, lb_max_x)

        self._canvas.configure(scrollregion=(0, 0, total_width, total_height))

    def _render_loser_bracket(self, loser_rounds, y_offset,
                              z, BW, BH, XG, YG, SX, FS, LW):
        """Draw the losers (consolation) bracket below the winners bracket.

        Returns the max y coordinate used (for scroll-region calculation).
        """
        font = ('Consolas', FS)
        label_font = ('Arial', max(8, int(11 * z)), 'bold')

        # ── Compute positions using imported utility ───────────────────────
        lb_pos, lb_ymid = calculate_loser_positions(loser_rounds, z, y_offset, SX)

        # ── Round labels ─────────────────────────────────────────────────
        nr = len(loser_rounds)
        for r in range(nr):
            lx = SX + r * (BW + XG) + BW // 2
            label = '3rd Place' if r == nr - 1 else f'Loser R{r + 1}'
            self._canvas.create_text(
                lx, y_offset - int(20 * z),
                text=label, anchor='c',
                fill=COLORS['accent_orange'], font=label_font)

        # ── Draw connectors using imported utility ──────────────────────────
        draw_loser_connectors(self._canvas, lb_pos, loser_rounds, z, COLORS)

        ck_font = ('Arial', FS + 1, 'bold')
        sm_font = ('Arial', max(6, FS - 1))

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

                self._canvas.create_text(
                    x + 8, y + BH // 4,
                    text=(p1[:24] if len(p1) > 24 else p1),
                    anchor='w', fill=self._name_color(p1, p1w, decided), font=font)
                self._canvas.create_text(
                    x + 8, y + 3 * BH // 4,
                    text=(p2[:24] if len(p2) > 24 else p2),
                    anchor='w', fill=self._name_color(p2, p2w, decided), font=font)

                if p1w:
                    self._canvas.create_text(
                        x2 - 10, y + BH // 4, text='✓',
                        anchor='c', fill=COLORS['accent_green'], font=ck_font)
                if p2w:
                    self._canvas.create_text(
                        x2 - 10, y + 3 * BH // 4, text='✓',
                        anchor='c', fill=COLORS['accent_green'], font=ck_font)

                both_real = (p1 not in ('Freilos', 'TBD')
                             and p2 not in ('Freilos', 'TBD'))
                if both_real and not decided:
                    self._canvas.create_text(
                        x2 - 6, my, text='← pick',
                        anchor='e', fill=COLORS['text_muted'], font=sm_font)

        if lb_pos:
            return max(p[1] for p in lb_pos.values()) + BH + YG
        return y_offset

    def _draw_wb_matches(self, rounds, pos, BW, BH, LW, FS, font):
        """Draw all WB match boxes onto the canvas and populate self._match_boxes."""
        ck_font = ('Arial', FS + 1, 'bold')
        sm_font = ('Arial', max(6, FS - 1))

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
                                              outline=COLORS['border_light'], width=LW)

                # Winner/loser half highlights
                if p1w:
                    self._canvas.create_rectangle(x + LW, y + LW, x2 - LW, my,
                                                  fill='#1a3d1a', outline='')
                elif decided and not p1w and p1 not in ('Freilos', 'TBD'):
                    self._canvas.create_rectangle(x + LW, y + LW, x2 - LW, my,
                                                  fill='#3d1a1a', outline='')
                if p2w:
                    self._canvas.create_rectangle(x + LW, my, x2 - LW, y2 - LW,
                                                  fill='#1a3d1a', outline='')
                elif decided and not p2w and p2 not in ('Freilos', 'TBD'):
                    self._canvas.create_rectangle(x + LW, my, x2 - LW, y2 - LW,
                                                  fill='#3d1a1a', outline='')

                # Separator line
                self._canvas.create_line(x, my, x2, my,
                                         fill=COLORS['border'], width=1, dash=(4, 3))

                # Player names
                self._canvas.create_text(x + 8, y + BH // 4,
                                         text=(p1[:24] if len(p1) > 24 else p1),
                                         anchor='w', fill=self._name_color(p1, p1w, decided),
                                         font=font)
                self._canvas.create_text(x + 8, y + 3 * BH // 4,
                                         text=(p2[:24] if len(p2) > 24 else p2),
                                         anchor='w', fill=self._name_color(p2, p2w, decided),
                                         font=font)

                # Checkmarks for winner
                if p1w:
                    self._canvas.create_text(x2 - 10, y + BH // 4, text='✓',
                                             anchor='c', fill=COLORS['accent_green'], font=ck_font)
                if p2w:
                    self._canvas.create_text(x2 - 10, y + 3 * BH // 4, text='✓',
                                             anchor='c', fill=COLORS['accent_green'], font=ck_font)

                # "← pick" hint for undecided real matches
                if p1 not in ('Freilos', 'TBD') and p2 not in ('Freilos', 'TBD') and winner is None:
                    self._canvas.create_text(x2 - 6, my, text='← pick',
                                             anchor='e', fill=COLORS['text_muted'], font=sm_font)

    @staticmethod
    def _name_color(name, won, decided):
        """Return the display colour for a fighter name based on match state."""
        if name == 'Freilos':
            return COLORS['text_disabled']
        if name == 'TBD':
            return COLORS['text_muted']
        if won:
            return COLORS['accent_green']
        if decided and not won:
            return COLORS['accent_red']
        return COLORS['text_primary']

    def _handle_wb_click(self, cx, cy, bkey):
        """Handle a click in the winner bracket area."""
        for (r, m), (x1, y1, x2, y2, p1, p2) in self._match_boxes.items():
            if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                continue
            # Only block if BOTH are bye/unknown (can't click pure-bye match)
            if p1 in ('Freilos', 'TBD') and p2 in ('Freilos', 'TBD'):
                logger.debug(f"WB click ignored: both slots are '{p1}'/'{p2}' at R{r} pos{m}")
                return

            if p1 in ('Freilos', 'TBD'):
                clicked = p2
            elif p2 in ('Freilos', 'TBD'):
                clicked = p1
            else:
                clicked = p1 if cy <= (y1 + y2) / 2 else p2

            results = self.match_results.setdefault(bkey, {})
            current = results.get((r, m))
            logger.info(
                f"[WB CLICK] '{bkey}' R{r} pos{m}: '{p1}' vs '{p2}' | "
                f"clicked='{clicked}', current_winner='{current}'"
            )

            if current == clicked:
                logger.info(f"[WB CLICK] De-selecting winner '{clicked}' at R{r} pos{m}")
                del results[(r, m)]
                # Delete downstream WB fight rows before clearing memory
                if self.db_service:
                    dr, dm = r + 1, m // 2
                    while (dr, dm) in results:
                        logger.info(f"[WB CLICK] Deleting downstream fight wb R{dr} pos{dm}")
                        self.db_service.delete_fight_position(bkey, 'wb', dr, dm)
                        dm = dm // 2
                        dr += 1
                self._clear_downstream(r, m)
                if self.db_service:
                    self.db_service.reset_fight_result(bkey, 'wb', r, m)
            else:
                if current is not None:
                    logger.info(f"[WB CLICK] Changing winner from '{current}' to '{clicked}' at R{r} pos{m}")
                    if self.db_service:
                        dr, dm = r + 1, m // 2
                        while (dr, dm) in results:
                            logger.info(f"[WB CLICK] Deleting downstream fight wb R{dr} pos{dm}")
                            self.db_service.delete_fight_position(bkey, 'wb', dr, dm)
                            dm = dm // 2
                            dr += 1
                    self._clear_downstream(r, m)
                else:
                    logger.info(f"[WB CLICK] Setting winner '{clicked}' at R{r} pos{m}")
                results[(r, m)] = clicked
                if self.db_service:
                    self.db_service.record_fight_result(bkey, 'wb', r, m, clicked, p1_name=p1, p2_name=p2)
                    # Check if this was the final — if so, compute placements
                    self._maybe_compute_placements(bkey)

            self._render(bkey)
            break

    def _handle_lb_click(self, cx, cy, bkey) -> bool:
        """Handle a click in the loser bracket area.

        Returns True if a loser bracket box was hit (consumed), False if the
        click missed all LB boxes and should fall through to the WB handler.
        """
        for (r, m), (x1, y1, x2, y2, p1, p2) in self._loser_match_boxes.items():
            if not (x1 <= cx <= x2 and y1 <= cy <= y2):
                continue
            if p1 in ('Freilos', 'TBD') and p2 in ('Freilos', 'TBD'):
                logger.debug(f"LB click ignored: both slots are '{p1}'/'{p2}' at R{r} pos{m}")
                return True

            if p1 in ('Freilos', 'TBD'):
                clicked = p2
            elif p2 in ('Freilos', 'TBD'):
                clicked = p1
            else:
                clicked = p1 if cy <= (y1 + y2) / 2 else p2

            lb_results = self.loser_match_results.setdefault(bkey, {})
            current = lb_results.get((r, m))
            logger.info(
                f"[LB CLICK] '{bkey}' R{r} pos{m}: '{p1}' vs '{p2}' | "
                f"clicked='{clicked}', current_winner='{current}'"
            )

            if current == clicked:
                logger.info(f"[LB CLICK] De-selecting winner '{clicked}' at R{r} pos{m}")
                del lb_results[(r, m)]
                if self.db_service:
                    for (dr, dm) in list(lb_results):
                        if dr > r:
                            logger.info(f"[LB CLICK] Deleting downstream fight lb R{dr} pos{dm}")
                            self.db_service.delete_fight_position(bkey, 'lb', dr, dm)
                self._clear_loser_downstream(r)
                if self.db_service:
                    self.db_service.reset_fight_result(bkey, 'lb', r, m)
            else:
                if current is not None:
                    logger.info(f"[LB CLICK] Changing winner from '{current}' to '{clicked}' at R{r} pos{m}")
                    if self.db_service:
                        for (dr, dm) in list(lb_results):
                            if dr > r:
                                logger.info(f"[LB CLICK] Deleting downstream fight lb R{dr} pos{dm}")
                                self.db_service.delete_fight_position(bkey, 'lb', dr, dm)
                    self._clear_loser_downstream(r)
                else:
                    logger.info(f"[LB CLICK] Setting winner '{clicked}' at R{r} pos{m}")
                lb_results[(r, m)] = clicked
                if self.db_service:
                    self.db_service.record_fight_result(bkey, 'lb', r, m, clicked, p1_name=p1, p2_name=p2)
                    # Re-compute placements (3rd places come from LB)
                    self._maybe_compute_placements(bkey)

            self._render(bkey)
            return True

        return False

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

    def _maybe_compute_placements(self, bkey):
        """Compute and store placements if the bracket is fully decided."""
        if not self.db_service:
            return
        pairs = self.brackets.get(bkey, {}).get('bracket', [])
        if not pairs:
            return
        results = self.match_results.get(bkey, {})
        rounds = self._compute_rounds(pairs, results)
        if not rounds:
            return
        # Check: does the final round have a winner?
        final_round = rounds[-1]
        if final_round and final_round[0].get('winner'):
            logger.info(f"[PLACEMENTS] Final decided for '{bkey}' — computing placements")
            placements = self.db_service.compute_placements(bkey)
            if placements:
                logger.info(
                    f"[PLACEMENTS] '{bkey}': 1st=gp{placements.get('first')}, "
                    f"2nd=gp{placements.get('second')}, "
                    f"3rd=gp{placements.get('third_1')} & gp{placements.get('third_2')}"
                )
