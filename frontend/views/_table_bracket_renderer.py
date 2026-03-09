# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from ..styles import COLORS, FONTS
from ..utils import (
    calculate_box_size,
    draw_pools_on_canvas,
    build_bracket_rounds,
    draw_bracket_on_canvas,
    compute_bracket_rounds,
    calculate_loser_positions,
    draw_loser_connectors,
)
import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from backend.services.bracket_service import make_bracket


class _RendererMixin:
    """Mixin for bracket and pool visualization rendering."""

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
            import traceback
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
            import traceback
            traceback.print_exc()
            self.bracket_canvas.create_text(400, 300,
                text=f"Error rendering pool:\n{str(e)}",
                font=FONTS['body_md'], fill='red')
