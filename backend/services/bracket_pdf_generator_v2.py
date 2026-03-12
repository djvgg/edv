# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket PDF Generator v2 - Generates printable PDFs for all bracket types.

Supports:
1. Double Elimination (main bracket + loser's bracket)
2. Pool System (1-2 pools with round-robin + KO finals)
3. Single Pool (1 pool round-robin only)
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple

from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import inch
from reportlab.lib import colors

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger
from frontend.styles import COLORS as FRONTEND_COLORS, FONTS as FRONTEND_FONTS
from frontend.utils.pool_renderer import _generate_fight_schedule  # Import fight schedule

logger = get_logger('bracket_pdf_generator_v2')

# Color palette - ReportLab format
COLORS = {
    'white': colors.HexColor(FRONTEND_COLORS['white']),
    'black': colors.HexColor(FRONTEND_COLORS['black']),
    'bg_dark': colors.HexColor(FRONTEND_COLORS['bg_dark']),
    'bg_panel': colors.HexColor(FRONTEND_COLORS['bg_panel']),
    'text_primary': colors.HexColor(FRONTEND_COLORS['text_primary']),
    'text_secondary': colors.HexColor(FRONTEND_COLORS['text_secondary']),
    'border_light': colors.HexColor(FRONTEND_COLORS['border_light']),
    'accent_red': colors.HexColor(FRONTEND_COLORS['accent_red']),
    'accent_blue': colors.HexColor(FRONTEND_COLORS['accent_blue']),
    'accent_orange': colors.HexColor(FRONTEND_COLORS['accent_orange']),
    'dark_grey': colors.HexColor('#4A4A4A'),
}


class BracketPDFGeneratorV2:
    """Generate printable PDFs for all bracket types."""

    def __init__(self, db=None):
        """Initialize PDF generator."""
        self.db = db
        self.logger = logger
        self.zoom_level = 1.0

    def draw_double_elimination_pdf(self, output_path: str, fighters_or_data: Dict[str, Any], 
                                   bracket_key: str = "Tournament Bracket") -> str:
        """
        Generate double elimination bracket PDF.
        
        Can accept either:
        1. List of fighter dicts: [{'Name': str, 'Verein': str}, ...]
           In this case, applies snake seeding automatically
        2. Dict with bracket_data: {'bracket': [...], 'match_results': {...}, 'fighters': [...]}
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Check if input is a list of fighters (apply snake seeding) or bracket data
            if isinstance(fighters_or_data, list):
                # Apply snake seeding
                from utils.bracket_utils import _compute_snake_bracket
                fighters = fighters_or_data
                bracket_pairs = _compute_snake_bracket(fighters)
                bracket_data = {
                    'bracket': bracket_pairs,
                    'match_results': {},
                    'fighters': fighters
                }
            else:
                # Use provided bracket data
                bracket_data = fighters_or_data
            
            c = pdf_canvas.Canvas(output_path, pagesize=landscape(A4))
            width, height = landscape(A4)
            
            # Draw header
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(COLORS['black'])
            header_y = height - 40
            c.drawCentredString(width // 2, header_y, bracket_key)
            
            # Draw divider
            c.setLineWidth(2)
            c.setStrokeColor(COLORS['border_light'])
            c.line(50, header_y - 10, width - 50, header_y - 10)
            
            # Build and draw bracket
            self._draw_double_elimination_structure(c, bracket_data, width, height, header_y)
            
            # Footer (on current page)
            c.setFont("Helvetica", 8)
            c.setFillColor(COLORS['text_secondary'])
            c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            c.save()
            self.logger.info(f"Double elimination PDF created: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error creating double elimination PDF: {e}")
            raise

    def _draw_double_elimination_structure(self, c, bracket_data: Dict, width: float, 
                                          height: float, header_y: float):
        """Draw complete double elimination bracket structure with pagination.
        
        Automatically creates new pages if brackets don't fit vertically.
        """
        from frontend.utils.bracket_renderer import compute_bracket_rounds
        
        bracket_pairs = bracket_data.get('bracket', [])
        match_results = bracket_data.get('match_results', {})
        fighters_list = bracket_data.get('fighters', [])
        
        if not bracket_pairs:
            self.logger.warning("No bracket pairs in bracket data")
            return
        
        # Build main bracket rounds
        main_rounds = compute_bracket_rounds(bracket_pairs, match_results)
        if not main_rounds:
            self.logger.warning("Could not build main rounds")
            return
        
        # Layout parameters
        start_x = 50
        bw_box_w, bw_box_h = 140, 50
        bw_spacing = 180
        
        # Calculate space needed for winners bracket
        max_fights_in_round = max(len(r) for r in main_rounds)
        winners_bracket_height = max_fights_in_round * (bw_box_h + 20) + 80  # +80 for label and margin
        
        # Build loser bracket structure first to know its size
        loser_bracket = self._build_loser_bracket(main_rounds)
        max_loser_fights = max((len(r) for r in loser_bracket), default=0)
        loser_bracket_height = max_loser_fights * (bw_box_h + 20) + 80
        
        # Check if both fit on one page
        total_needed = winners_bracket_height + loser_bracket_height + 100  # +100 for gaps
        bottom_margin = 50
        available_height = height - header_y - bottom_margin
        
        # ============== PAGE 1: WINNERS BRACKET ==============
        current_y = header_y - 50
        
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(COLORS['accent_blue'])
        c.drawString(start_x, current_y + 20, "WINNERS BRACKET")
        
        winners_y = current_y
        
        # Store Y midpoints for proper connector calculation (same as bracket_renderer)
        # y_midpoint = center vertical position of match box
        y_midpoints = {}  # (round_idx, fight_idx) -> y_midpoint
        
        # Draw winners bracket with proper alignment
        for r_idx, round_fights in enumerate(main_rounds):
            round_x = start_x + (r_idx * bw_spacing)
            num_fights = len(round_fights)
            
            if r_idx == 0:
                # Round 0: vertical stack
                for f_idx, fight in enumerate(round_fights):
                    fight_y = winners_y - (f_idx * (bw_box_h + 20))
                    y_midpoints[(r_idx, f_idx)] = fight_y + bw_box_h / 2  # Center of box
                    
                    self._draw_match_box_from_dict(c, fight, round_x, fight_y, 
                                                 bw_box_w, bw_box_h)
            else:
                # Later rounds: center between previous winners
                for m in range(num_fights):
                    # Average the Y midpoints of the two incoming fights
                    ya = y_midpoints.get((r_idx - 1, m * 2), winners_y + bw_box_h / 2)
                    yb = y_midpoints.get((r_idx - 1, m * 2 + 1), ya)
                    y_mid = (ya + yb) / 2
                    fight_y = y_mid - bw_box_h / 2  # Convert midpoint to top-left corner
                    y_midpoints[(r_idx, m)] = y_mid
                    
                    # Get fight data
                    if m < len(round_fights):
                        fight = round_fights[m]
                        self._draw_match_box_from_dict(c, fight, round_x, fight_y, 
                                                     bw_box_w, bw_box_h)
            
            # Draw connectors from this round to next
            if r_idx + 1 < len(main_rounds):
                for f_idx in range(len(round_fights)):
                    if (r_idx, f_idx) not in y_midpoints:
                        continue
                    
                    from_y = y_midpoints[(r_idx, f_idx)]
                    target_m = f_idx // 2
                    
                    if (r_idx + 1, target_m) not in y_midpoints:
                        continue
                    
                    to_y = y_midpoints[(r_idx + 1, target_m)]
                    next_x = start_x + ((r_idx + 1) * bw_spacing)
                    
                    # 3-part connector like bracket_renderer: horizontal → vertical → horizontal
                    # Target Y depends on whether this is first or second fight of pair
                    if f_idx % 2 == 0:
                        # First of pair: target upper quarter of next box
                        target_y = to_y - bw_box_h / 4
                    else:
                        # Second of pair: target lower quarter of next box
                        target_y = to_y + bw_box_h / 4
                    
                    mid_x = round_x + bw_box_w + bw_spacing / 2
                    
                    # Horizontal from current box
                    self._draw_connector(c, 
                        round_x + bw_box_w, from_y,
                        mid_x, from_y)
                    
                    # Vertical to target Y
                    self._draw_connector(c,
                        mid_x, from_y,
                        mid_x, target_y)
                    
                    # Horizontal to next box
                    self._draw_connector(c,
                        mid_x, target_y,
                        next_x, target_y)
        
        # ============== LOSER BRACKET ==============
        # Determine if loser bracket fits on current page
        loser_start_y = winners_y - winners_bracket_height - 50  # -50 for gap
        
        if loser_start_y - loser_bracket_height < bottom_margin:
            # Doesn't fit - create new page
            c.showPage()
            
            # Redraw header on new page
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(COLORS['black'])
            new_header_y = height - 40
            c.drawCentredString(width // 2, new_header_y, "LOSER BRACKET (Continued)")
            c.setLineWidth(2)
            c.setStrokeColor(COLORS['border_light'])
            c.line(50, new_header_y - 10, width - 50, new_header_y - 10)
            
            loser_start_y = new_header_y - 50
        
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(COLORS['accent_red'])
        c.drawString(start_x, loser_start_y + 20, "LOSER BRACKET")
        
        loser_y = loser_start_y
        
        if loser_bracket:
            # Use same positioning algorithm as viewer: calculate_loser_positions()
            # Store Y midpoints for proper connector calculation
            loser_y_midpoints = {}
            
            # First pass: calculate positions for all loser bracket fights
            # This mirrors the viewer's calculate_loser_positions logic
            for r_idx, round_fights in enumerate(loser_bracket):
                round_x = start_x + (r_idx * bw_spacing)
                num_fights = len(round_fights)
                
                if num_fights == 0:
                    continue
                
                if r_idx == 0:
                    # LB R0: vertical stack (like winners bracket R0)
                    for f_idx, fight in enumerate(round_fights):
                        fight_y = loser_y - (f_idx * (bw_box_h + 20))
                        loser_y_midpoints[(r_idx, f_idx)] = fight_y + bw_box_h / 2
                else:
                    # Later rounds: reduction vs injection
                    # Reduction: fewer fights than previous (center between two sources)
                    # Injection: same/more fights (align with source)
                    prev_count = len(loser_bracket[r_idx - 1])
                    curr_count = num_fights
                    is_reduction = curr_count < prev_count
                    
                    for m in range(curr_count):
                        if is_reduction:
                            # Reduction: center between two source fights
                            ya = loser_y_midpoints.get((r_idx - 1, m * 2), loser_y + bw_box_h / 2)
                            yb = loser_y_midpoints.get((r_idx - 1, m * 2 + 1), ya)
                            y_mid = (ya + yb) / 2
                        else:
                            # Injection: align with source fight m
                            y_mid = loser_y_midpoints.get((r_idx - 1, m), loser_y + bw_box_h / 2)
                        
                        fight_y = y_mid - bw_box_h / 2
                        loser_y_midpoints[(r_idx, m)] = y_mid
            
            # Second pass: draw all loser bracket fights
            for r_idx, round_fights in enumerate(loser_bracket):
                round_x = start_x + (r_idx * bw_spacing)
                
                for f_idx, fight in enumerate(round_fights):
                    if (r_idx, f_idx) not in loser_y_midpoints:
                        continue
                    
                    y_mid = loser_y_midpoints[(r_idx, f_idx)]
                    fight_y = y_mid - bw_box_h / 2
                    
                    self._draw_match_box_from_dict(c, fight, round_x, fight_y,
                                                 bw_box_w, bw_box_h)
            
            # Third pass: draw connectors (same 3-part logic as winners bracket)
            # This mirrors draw_loser_connectors from the viewer
            for r_idx, round_fights in enumerate(loser_bracket):
                if r_idx + 1 >= len(loser_bracket):
                    continue
                
                num_fights = len(round_fights)
                if num_fights == 0:
                    continue
                
                round_x = start_x + (r_idx * bw_spacing)
                next_x = start_x + ((r_idx + 1) * bw_spacing)
                
                prev_count = num_fights
                next_count = len(loser_bracket[r_idx + 1])
                is_reduction = next_count < prev_count
                
                for f_idx in range(num_fights):
                    if (r_idx, f_idx) not in loser_y_midpoints:
                        continue
                    
                    from_y = loser_y_midpoints[(r_idx, f_idx)]
                    target_m = f_idx // 2 if is_reduction else f_idx
                    
                    if (r_idx + 1, target_m) not in loser_y_midpoints:
                        continue
                    
                    to_y = loser_y_midpoints[(r_idx + 1, target_m)]
                    
                    # 3-part connector (matching draw_loser_connectors logic)
                    if is_reduction:
                        # In reduction: first of pair targets upper quarter, second targets lower
                        target_y = to_y - bw_box_h / 4 if f_idx % 2 == 0 else to_y + bw_box_h / 4
                    else:
                        # In injection: LB winner targets top half (p1) of next match
                        target_y = to_y + bw_box_h / 4
                    
                    mid_x = round_x + bw_box_w + bw_spacing / 2
                    
                    # Horizontal from current box
                    self._draw_connector(c,
                        round_x + bw_box_w, from_y,
                        mid_x, from_y,
                        color_key='accent_orange')
                    
                    # Vertical to target Y
                    self._draw_connector(c,
                        mid_x, from_y,
                        mid_x, target_y,
                        color_key='accent_orange')
                    
                    # Horizontal to next box
                    self._draw_connector(c,
                        mid_x, target_y,
                        next_x, target_y,
                        color_key='accent_orange')

    def _build_loser_bracket(self, main_rounds: List[List[Dict]]) -> List[List[Dict]]:
        """Build loser bracket structure using exact logic from viewer (_fight_monitoring_ko.py).
        
        This uses the proven algorithm from the tkinter viewer that's already working correctly.
        Structure:
          LB R0  – consecutive WB-R0 losers fight each other in pairs
          LB R1  – LB-R0 winners vs WB-R1 losers (1-to-1 injection)
          LB R2  – reduction if needed (LB winners > next WB-loser count), else injection
          ...until one match remains → 3rd-place fight

        WB Final loser is NOT fed into LB (they are already 2nd place).
        """
        if len(main_rounds) < 2:
            return []
        
        def get_loser(match):
            """Extract loser from a match dict with winner field."""
            w = match.get('winner')
            if w is None:
                return 'TBD'
            if match.get('p1') == 'Freilos' or match.get('p2') == 'Freilos':
                return 'Freilos'
            return match.get('p2') if w == match.get('p1') else match.get('p1')
        
        def make_match(p1, p2):
            """Create a match dict."""
            # Auto-bye logic: if one side is Freilos, award to the other
            winner = None
            if p1 == 'Freilos' and p2 not in ('Freilos', 'TBD'):
                winner = p2
            elif p2 == 'Freilos' and p1 not in ('Freilos', 'TBD'):
                winner = p1
            return {'p1': p1, 'p2': p2, 'winner': winner}
        
        loser_rounds = []
        
        # LB R0: pair consecutive losers from WB R0
        wb_r0_losers = [get_loser(m) for m in main_rounds[0]]
        lb_r0 = []
        for i in range(0, len(wb_r0_losers), 2):
            p1 = wb_r0_losers[i]
            p2 = wb_r0_losers[i + 1] if i + 1 < len(wb_r0_losers) else 'Freilos'
            lb_r0.append(make_match(p1, p2))
        loser_rounds.append(lb_r0)
        
        wb_idx = 1  # next WB round to pull losers from (skip WB Final)
        
        while True:
            prev = loser_rounds[-1]
            if len(prev) <= 1:
                break
            
            lb_winners = [(m.get('winner') if m.get('winner') is not None else 'TBD')
                         for m in prev]
            
            # Inject losers from next WB round (stop before WB Final)
            if wb_idx < len(main_rounds) - 1:
                wb_losers = [get_loser(m) for m in main_rounds[wb_idx]]
                
                if len(lb_winners) > len(wb_losers):
                    # Reduction round: LB winners fight each other first
                    reduction = []
                    for i in range(0, len(lb_winners), 2):
                        p1 = lb_winners[i]
                        p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                        reduction.append(make_match(p1, p2))
                    loser_rounds.append(reduction)
                    # Loop again to re-read from reduction round
                else:
                    # Injection round: each LB winner faces a WB loser
                    injection = []
                    for j in range(len(wb_losers)):
                        lw = lb_winners[j] if j < len(lb_winners) else 'TBD'
                        wl = wb_losers[j]
                        injection.append(make_match(lw, wl))
                    loser_rounds.append(injection)
                    wb_idx += 1
            else:
                # No more WB rounds to inject — remaining LB winners fight for 3rd place
                if len(lb_winners) > 1:
                    final = []
                    for i in range(0, len(lb_winners), 2):
                        p1 = lb_winners[i]
                        p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                        final.append(make_match(p1, p2))
                    loser_rounds.append(final)
                break
        
        return loser_rounds


    def _draw_match_box_from_dict(self, c, fight: Dict, x: float, y: float, 
                                  width: float, height: float, 
                                  style: str = 'default', label: str = ""):
        """Draw a single match box from fight dict with p1, p2, winner keys.
        
        Match dict format: {'p1': str, 'p2': str, 'winner': str or None}
        """
        # Choose colors based on style
        if style == 'accent_orange':
            bg_color = COLORS['bg_panel']
            border_color = COLORS['accent_orange']
        else:
            bg_color = COLORS['bg_panel']
            border_color = COLORS['border_light']
        
        # Draw box
        c.setLineWidth(2)
        c.setStrokeColor(border_color)
        c.setFillColor(bg_color)
        c.rect(x, y - height, width, height, stroke=1, fill=1)
        
        # Get names
        p1 = fight.get('p1', '---')[:16]
        p2 = fight.get('p2', '---')[:16]
        winner = fight.get('winner')
        
        # Draw text
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(COLORS['text_primary'])
        
        if label:
            c.drawCentredString(x + width/2, y - height/2, label)
        else:
            # Show winner with highlight
            if winner == p1:
                c.setFillColor(COLORS['accent_blue'])
                c.drawString(x + 5, y - height/3, "● " + p1)
                c.setFillColor(COLORS['text_secondary'])
                c.drawString(x + 5, y - 2*height/3, "  " + p2)
            elif winner == p2:
                c.setFillColor(COLORS['text_secondary'])
                c.drawString(x + 5, y - height/3, "  " + p1)
                c.setFillColor(COLORS['accent_blue'])
                c.drawString(x + 5, y - 2*height/3, "● " + p2)
            else:
                # Not yet decided
                c.setFillColor(COLORS['text_primary'])
                c.drawString(x + 5, y - height/3, p1)
                c.drawString(x + 5, y - 2*height/3, p2)
    
    def _draw_bracket_rounds(self, c, rounds: List[List[Dict]], participants: Dict,
                            start_x: float, start_y: float, round_spacing: float,
                            box_width: float, box_height: float, title: str = ""):
        """Draw a series of rounds (main or loser bracket)."""
        if title:
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(COLORS['text_primary'])
            c.drawString(start_x, start_y + 25, title)
        
        for round_idx, fights in enumerate(rounds):
            round_x = start_x + (round_idx * round_spacing)
            num_fights = len(fights)
            
            # Calculate vertical spacing for this round
            total_height = num_fights * (box_height + 20)
            round_start_y = start_y - (total_height / 2)
            
            # Draw each fight in the round
            for fight_idx, fight in enumerate(fights):
                fight_y = round_start_y - (fight_idx * (box_height + 20))
                self._draw_match_box_from_dict(c, fight, round_x, fight_y,
                                             box_width, box_height)
                
                # Draw connectors to next round if available
                if round_idx + 1 < len(rounds):
                    self._draw_round_connector(c, round_idx, fight_idx, len(rounds[round_idx + 1]),
                                             round_x, fight_y, round_spacing, box_width, box_height)

    def _draw_round_connector(self, c, from_round: int, from_fight: int, to_fight_count: int,
                            round_x: float, fight_y: float, round_spacing: float,
                            box_width: float, box_height: float):
        """Draw connector line from current fight to next round."""
        c.setLineWidth(1)
        c.setStrokeColor(COLORS['dark_grey'])
        
        next_round_x = round_x + round_spacing
        
        # Calculate target Y for next round
        # Winner of even-indexed fight goes to half position in next round
        target_f_idx = from_fight // 2
        target_y = fight_y - ((target_f_idx - from_fight) * (box_height + 20) / 2)
        
        # Draw line from right of current box to left of next box
        c.line(round_x + box_width, fight_y - box_height // 2,
               next_round_x, target_y - box_height // 2)
    
    def _draw_connector(self, c, x1: float, y1: float, x2: float, y2: float, 
                       style: str = 'solid', color_key: str = 'dark_grey'):
        """Draw a connector line between boxes."""
        c.setLineWidth(1.5)
        c.setStrokeColor(COLORS[color_key])
        
        if style == 'dashed':
            c.line(x1, y1, x2, y2, dash=(3, 3))
        else:
            c.line(x1, y1, x2, y2)

    def draw_pools_pdf(self, output_path: str, pools_data: List[Dict[str, Any]],
                       ko_bracket_data: Optional[Dict[str, Any]] = None,
                       bracket_key: str = "Tournament Bracket") -> str:
        """
        Generate pool system bracket PDF with auto-pagination.
        
        Each pool gets its own page if needed. Pools fit on pages automatically,
        with new pages created when space runs out.
        
        Expected format:
        pools_data = [
            {
                'pool_name': 'Pool A',
                'fighters': [
                    {'rank': 1, 'name': 'John', 'club': 'Club', 'points': 10, 'diff': 5, 'place': 1},
                    ...
                ],
                'fights': {} (can be empty, scores not shown)
            },
            ...
        ]
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            from reportlab.pdfgen.canvas import Canvas
            from reportlab.lib.pagesizes import landscape, A4
            
            c = Canvas(output_path, pagesize=landscape(A4))
            width, height = landscape(A4)
            
            # Draw main header on first page
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(COLORS['black'])
            header_y = height - 40
            c.drawCentredString(width // 2, header_y, bracket_key)
            
            # Draw divider
            c.setLineWidth(2)
            c.setStrokeColor(COLORS['border_light'])
            c.line(50, header_y - 10, width - 50, header_y - 10)
            
            # Track current position
            current_y = header_y - 30
            current_page_num = 1
            
            # Draw all pools with auto-pagination
            for pool_idx, pool_data in enumerate(pools_data):
                # Estimate height needed for this pool
                num_fighters = len(pool_data.get('fighters', []))
                estimated_height = 100 + (num_fighters * 25) + 50  # title + fighters + time row
                
                # Check if pool fits on current page
                if current_y - estimated_height < 50:  # 50px bottom margin
                    # Start new page
                    c.showPage()
                    current_page_num += 1
                    current_y = height - 50  # Top with margin
                
                # Draw pool table and pass canvas for page handling
                current_y = self._draw_pool_table(c, pool_data, 50, current_y, width - 100, height)
            
            # Draw KO bracket if present
            if ko_bracket_data:
                # Check if KO fits on current page
                if current_y - 200 < 50:  # KO needs ~200px
                    c.showPage()
                    current_page_num += 1
                    current_y = height - 50
                
                self._draw_ko_bracket(c, ko_bracket_data, 50, current_y, width - 100)
            
            # Footer
            c.setFont("Helvetica", 8)
            c.setFillColor(COLORS['text_secondary'])
            c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            c.save()
            self.logger.info(f"Pools PDF created: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error creating pools PDF: {e}")
            raise

    def _draw_pool_table(self, c, pool_data: Dict[str, Any], start_x: float, start_y: float,
                        available_width: float, page_height: float) -> float:
        """
        Draw a pool round-robin table with actual fight scores, wrapping fights across multiple sections.
        
        Format: Nr | Fighter | Fight results | Points | Diff | Place
                Plus fight time row below
        
        Each fight cell has 2 subdivisions: [score_fighter | score_opponent]
        Uses _generate_fight_schedule() to determine fight pairings.
        
        If fights exceed page width, they wrap into multiple horizontal sections.
        If fit sections exceed page height, automatically creates new pages.
        
        Returns: final current_y position after drawing all sections
        """
        fighters = pool_data.get('fighters', [])
        if not fighters:
            return start_y
        
        pool_name = pool_data.get('pool_name', 'Pool')
        fights_data = pool_data.get('fights', [])  # Dict mapping (fighter_idx1, fighter_idx2) -> {scores}
        num_fighters = len(fighters)
        
        # Generate fight schedule to determine pairings
        fight_schedule = _generate_fight_schedule(num_fighters)
        num_fights = len(fight_schedule)
        
        # Dimensions
        cell_height = 20
        header_height = 25
        nr_col_width = 35
        name_col_width = 130
        fight_col_width = 40  # Each fight = 40px (2 subdivisions × 20px each)
        points_col_width = 50
        diff_col_width = 40
        place_col_width = 40
        
        # Calculate how many fights fit per row
        fixed_cols_width = nr_col_width + name_col_width + points_col_width + diff_col_width + place_col_width
        available_for_fights = available_width - fixed_cols_width - 20  # 20px padding
        fights_per_row = max(1, int(available_for_fights / fight_col_width))
        
        # Split fights into rows
        fight_rows = []
        for i in range(0, num_fights, fights_per_row):
            fight_rows.append(list(range(i, min(i + fights_per_row, num_fights))))
        
        # Calculate widths for each row
        current_fights_width = fight_col_width * fights_per_row
        row_width = nr_col_width + name_col_width + current_fights_width + points_col_width + diff_col_width + place_col_width
        
        # Draw pool title
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(COLORS['black'])  # Black text on white paper
        c.drawString(start_x, start_y, pool_name)
        
        current_y = start_y - 30  # Start position for first section
        total_height = 30  # Track total height used
        
        # Draw each fight row section
        for fight_row_idx, fight_indices in enumerate(fight_rows):
            title_y = current_y
            
            # Estimate height needed for this section
            section_height = 10  # Label
            section_height += 25  # Header row
            section_height += len(fighters) * 20  # Fighter rows
            section_height += 20  # Fight time row
            section_height += 15  # Spacing after section
            
            # Check if section fits on current page (50px bottom margin)
            if current_y - section_height < 50 and fight_row_idx > 0:
                # Start a new page
                c.showPage()
                # Redraw pool title on new page
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(COLORS['black'])
                new_page_title_y = page_height - 40
                c.drawString(start_x, new_page_title_y, pool_name + " (continued)")
                title_y = new_page_title_y - 30
                current_y = title_y
            
            # Section label for multi-row fights
            if len(fight_rows) > 1:
                c.setFont("Helvetica", 8)
                c.setFillColor(COLORS['text_secondary'])
                fights_in_section = f"Fights {fight_indices[0]+1}-{fight_indices[-1]+1}"
                c.drawString(start_x, title_y, fights_in_section)
                title_y -= 10
                current_y -= 10
            
            # Draw header row for this section
            c.setFont("Helvetica-Bold", 9)
            c.setLineWidth(1)
            c.setStrokeColor(COLORS['border_light'])
            c.setFillColor(COLORS['bg_dark'])
            
            # Header: Nr | Fighter | Fights in this row | Points | Diff | Place
            headers = ['Nr', 'Fighter'] + [str(i+1) for i in fight_indices] + ['Points', 'Diff', 'Place']
            section_fights_width = fight_col_width * len(fight_indices)
            col_widths = [nr_col_width, name_col_width] + [fight_col_width] * len(fight_indices) + [points_col_width, diff_col_width, place_col_width]
            
            col_x = start_x
            for header, col_width in zip(headers, col_widths):
                # Draw header cell
                c.setFillColor(COLORS['bg_dark'])
                c.setStrokeColor(COLORS['border_light'])
                c.rect(col_x, title_y - header_height, col_width, header_height, stroke=1, fill=1)
                
                # Header text - white on dark background
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(COLORS['white'])
                text_x = col_x + col_width // 2
                c.drawCentredString(text_x, title_y - header_height // 2, header)
                
                col_x += col_width
            
            # Draw fighter rows for this section
            current_y = title_y - header_height
            for row_idx, fighter in enumerate(fighters):
                row_y = current_y
                col_x = start_x
                
                # Nr cell
                c.setFillColor(COLORS['bg_panel'])
                c.rect(col_x, row_y - cell_height, nr_col_width, cell_height, stroke=1, fill=1)
                c.setFillColor(COLORS['text_primary'])
                c.setFont("Helvetica", 9)
                c.drawCentredString(col_x + nr_col_width // 2, row_y - cell_height // 2, 
                                  str(fighter.get('rank', row_idx + 1)))
                col_x += nr_col_width
                
                # Fighter name cell
                c.setFillColor(COLORS['bg_panel'])
                c.rect(col_x, row_y - cell_height, name_col_width, cell_height, stroke=1, fill=1)
                c.setFillColor(COLORS['text_primary'])
                fighter_name = fighter.get('name', '')
                c.drawString(col_x + 5, row_y - cell_height // 2, fighter_name[:25])
                col_x += name_col_width
                
                # Fight cells for fights in this section only
                for section_fight_idx, global_fight_idx in enumerate(fight_indices):
                    fight_cell_x = col_x
                    
                    # Draw outer fight cell box
                    c.setFillColor(COLORS['bg_panel'])
                    c.rect(fight_cell_x, row_y - cell_height, fight_col_width, cell_height, stroke=1, fill=1)
                    
                    # Determine if fighter participates in this fight
                    fighter_participates = False
                    
                    if global_fight_idx < len(fight_schedule):
                        fight_matchups = fight_schedule[global_fight_idx]
                        if fight_matchups:
                            for match in fight_matchups:
                                if len(match) == 2:
                                    f1_idx, f2_idx = match
                                    if f1_idx == row_idx or f2_idx == row_idx:
                                        fighter_participates = True
                                        break
                    
                    c.setFillColor(COLORS['text_secondary'])
                    c.setFont("Helvetica", 8)
                    
                    if fighter_participates:
                        # Draw subdivision (vertical divider) only when fighter participates
                        subdivision_width = fight_col_width // 2
                        c.setStrokeColor(COLORS['border_light'])
                        c.setLineWidth(1)
                        c.line(fight_cell_x + subdivision_width, row_y - cell_height,
                               fight_cell_x + subdivision_width, row_y)
                        
                        # Left and right subdivisions (empty)
                        c.drawCentredString(fight_cell_x + subdivision_width // 2, 
                                          row_y - cell_height // 2, "-")
                        c.drawCentredString(fight_cell_x + subdivision_width + subdivision_width // 2,
                                          row_y - cell_height // 2, "-")
                    else:
                        # No participation - show single dash
                        c.drawCentredString(fight_cell_x + fight_col_width // 2, 
                                          row_y - cell_height // 2, "-")
                    
                    col_x += fight_col_width
                
                # Points, Diff, Place cells (only on first fight row section, repeated on others)
                if fight_row_idx == 0:
                    # Points
                    c.setFillColor(COLORS['bg_panel'])
                    c.rect(col_x, row_y - cell_height, points_col_width, cell_height, stroke=1, fill=1)
                    c.setFillColor(COLORS['text_primary'])
                    c.setFont("Helvetica", 9)
                    points = fighter.get('points', '-')
                    c.drawCentredString(col_x + points_col_width // 2, row_y - cell_height // 2, str(points))
                    col_x += points_col_width
                    
                    # Diff
                    c.setFillColor(COLORS['bg_panel'])
                    c.rect(col_x, row_y - cell_height, diff_col_width, cell_height, stroke=1, fill=1)
                    c.setFillColor(COLORS['text_primary'])
                    diff = fighter.get('diff', '-')
                    c.drawCentredString(col_x + diff_col_width // 2, row_y - cell_height // 2, str(diff))
                    col_x += diff_col_width
                    
                    # Place
                    c.setFillColor(COLORS['bg_panel'])
                    c.rect(col_x, row_y - cell_height, place_col_width, cell_height, stroke=1, fill=1)
                    c.setFillColor(COLORS['text_primary'])
                    place = fighter.get('place', '-')
                    c.drawCentredString(col_x + place_col_width // 2, row_y - cell_height // 2, str(place))
                else:
                    # Empty cells for summary columns in non-first rows
                    for col_width in [points_col_width, diff_col_width, place_col_width]:
                        c.setFillColor(COLORS['bg_panel'])
                        c.rect(col_x, row_y - cell_height, col_width, cell_height, stroke=1, fill=1)
                        col_x += col_width
                
                current_y -= cell_height
            
            # Draw fight time row for this section
            fight_time_y = current_y
            col_x = start_x
            
            # Nr cell (empty)
            c.setFillColor(COLORS['bg_panel'])
            c.setStrokeColor(COLORS['border_light'])
            c.setLineWidth(1)
            c.rect(col_x, fight_time_y - cell_height, nr_col_width, cell_height, stroke=1, fill=1)
            col_x += nr_col_width
            
            # Name cell with "Fight time" label (only on first row)
            c.setFillColor(COLORS['bg_panel'])
            c.rect(col_x, fight_time_y - cell_height, name_col_width, cell_height, stroke=1, fill=1)
            if fight_row_idx == 0:
                c.setFillColor(COLORS['text_primary'])
                c.setFont("Helvetica-Bold", 8)
                c.drawString(col_x + 5, fight_time_y - cell_height // 2, "Fight time:")
            col_x += name_col_width
            
            # Fight time cells
            for _ in fight_indices:
                c.setFillColor(COLORS['bg_panel'])
                c.rect(col_x, fight_time_y - cell_height, fight_col_width, cell_height, stroke=1, fill=1)
                c.setFillColor(COLORS['text_secondary'])
                c.setFont("Helvetica", 8)
                c.drawCentredString(col_x + fight_col_width // 2, fight_time_y - cell_height // 2, "-")
                col_x += fight_col_width
            
            # Summary cells (empty in time row)
            for col_width in [points_col_width, diff_col_width, place_col_width]:
                c.setFillColor(COLORS['bg_panel'])
                c.rect(col_x, fight_time_y - cell_height, col_width, cell_height, stroke=1, fill=1)
                col_x += col_width
            
            current_y -= cell_height + 15  # Add spacing between sections
        
        # Return final position on current page (or new page if we created one)
        return current_y - 20  # 20px bottom margin

    def _draw_ko_bracket(self, c, ko_data: Dict[str, Any], start_x: float, start_y: float,
                        available_width: float):
        """Draw KO bracket for 4 pool winners (Semis + Final)."""
        # Extract winners (pool winners)
        winners = ko_data.get('winners', [])
        if len(winners) < 2:
            return
        
        # Box dimensions
        box_width, box_height = 150, 50
        line_spacing = 80
        
        # Draw KO bracket title
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(COLORS['black'])
        c.drawString(start_x, start_y + 20, "KO Round (Finals)")
        
        # Semi-final 1 (Pool A 1st vs Pool B 1st)
        semi1_x = start_x
        semi1_y = start_y
        
        c.setLineWidth(2)
        c.setStrokeColor(COLORS['white'])
        c.setFillColor(COLORS['bg_dark'])
        c.rect(semi1_x, semi1_y - box_height, box_width, box_height, stroke=1, fill=1)
        
        c.setFont("Helvetica", 9)
        c.setFillColor(COLORS['text_primary'])
        winner1 = winners[0] if len(winners) > 0 else "---"
        c.drawCentredString(semi1_x + box_width // 2, semi1_y - box_height // 3, 
                          "Semi-final 1")
        c.setFont("Helvetica", 8)
        c.drawCentredString(semi1_x + box_width // 2, semi1_y - 2 * box_height // 3, 
                          str(winner1)[:20])
        
        # Semi-final 2 (Pool A 2nd vs Pool B 2nd)
        semi2_x = start_x
        semi2_y = start_y - line_spacing
        
        c.setLineWidth(2)
        c.setStrokeColor(COLORS['white'])
        c.setFillColor(COLORS['bg_dark'])
        c.rect(semi2_x, semi2_y - box_height, box_width, box_height, stroke=1, fill=1)
        
        c.setFont("Helvetica", 9)
        c.setFillColor(COLORS['text_primary'])
        winner2 = winners[1] if len(winners) > 1 else "---"
        c.drawCentredString(semi2_x + box_width // 2, semi2_y - box_height // 3,
                          "Semi-final 2")
        c.setFont("Helvetica", 8)
        c.drawCentredString(semi2_x + box_width // 2, semi2_y - 2 * box_height // 3,
                          str(winner2)[:20])
        
        # Final
        final_x = start_x + 250
        final_y = start_y - line_spacing // 2
        
        c.setLineWidth(2)
        c.setStrokeColor(COLORS['accent_blue'])
        c.setFillColor(COLORS['bg_dark'])
        c.rect(final_x, final_y - box_height, box_width, box_height, stroke=1, fill=1)
        
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(COLORS['accent_blue'])
        c.drawCentredString(final_x + box_width // 2, final_y - box_height // 2, "FINAL")
        
        # Draw connectors (lines from semis to final)
        c.setLineWidth(1.5)
        c.setStrokeColor(COLORS['dark_grey'])
        
        # Semi 1 to final
        c.line(semi1_x + box_width, semi1_y - box_height // 2,
               final_x, final_y - box_height // 2)
        
        # Semi 2 to final
        c.line(semi2_x + box_width, semi2_y - box_height // 2,
               final_x, final_y - box_height // 2)

    def draw_single_pool_pdf(self, output_path: str, pool_data: Dict[str, Any],
                           bracket_key: str = "Tournament Bracket") -> str:
        """
        Generate single pool bracket PDF (round-robin only).
        
        Expected format same as pools_data[0]
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            c = pdf_canvas.Canvas(output_path, pagesize=landscape(A4))
            width, height = landscape(A4)
            
            # Draw header
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(COLORS['black'])
            header_y = height - 40
            c.drawCentredString(width // 2, header_y, bracket_key)
            
            # Draw divider
            c.setLineWidth(2)
            c.setStrokeColor(COLORS['border_light'])
            c.line(50, header_y - 10, width - 50, header_y - 10)
            
            # Draw single pool table
            self._draw_pool_table(c, pool_data, 50, header_y - 80, width - 100)
            
            # Footer
            c.setFont("Helvetica", 8)
            c.setFillColor(COLORS['text_secondary'])
            c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            c.save()
            self.logger.info(f"Single pool PDF created: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error creating single pool PDF: {e}")
            raise


# Keep old class for backwards compatibility
class BracketPDFGenerator(BracketPDFGeneratorV2):
    """Backwards compatible interface."""
    pass
