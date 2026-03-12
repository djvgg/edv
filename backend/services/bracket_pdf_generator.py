# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket PDF Generator - Generates printable PDFs from bracket data.

Translates existing bracket rendering logic (from bracket_renderer.py and pool_renderer.py)
to PDF format using ReportLab, ensuring visual consistency between on-screen and printed output.
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple

from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from frontend.utils.bracket_renderer import (  # noqa: E402
    build_bracket_rounds,
    calculate_box_size,
)
from frontend.utils.pool_renderer import (  # noqa: E402
    draw_pool_table,
    split_into_pools,
    _generate_fight_schedule,
)
from frontend.styles import COLORS as FRONTEND_COLORS, FONTS as FRONTEND_FONTS  # noqa: E402

logger = get_logger('bracket_pdf_generator')

# Color palette matching the frontend - convert to ReportLab colors
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
    'dark_grey': colors.HexColor('#4A4A4A'),  # Dark grey for arrows
}


class BracketPDFGenerator:
    """Generate printable PDF from bracket data."""

    def __init__(self, db=None):
        """
        Initialize PDF generator.
        
        Args:
            db: SQLAlchemy database session (for future bracket data retrieval)
        """
        self.db = db
        self.logger = logger
        self.zoom_level = 1.0  # Fixed zoom for PDF (matches 100% view)

    def generate_bracket_pdf(self, bracket_id: int, output_path: str) -> str:
        """
        Generate KO bracket PDF.
        
        Args:
            bracket_id: ID of bracket to print
            output_path: Where to save PDF file
        
        Returns:
            Path to generated PDF file
        
        Raises:
            ValueError: If bracket not found or data invalid
            IOError: If PDF generation fails
        """
        self.logger.info(f"Generating KO bracket PDF: bracket_id={bracket_id}")
        
        # TODO: Retrieve bracket data from database
        # bracket_data = self._fetch_bracket_data(bracket_id, 'ko')
        
        # For now, create a realistic sample PDF
        return self._create_sample_ko_pdf_realistic(output_path)

    def generate_pool_pdf(self, bracket_id: int, output_path: str) -> str:
        """
        Generate pool bracket PDF.
        
        Args:
            bracket_id: ID of bracket to print
            output_path: Where to save PDF file
        
        Returns:
            Path to generated PDF file
        
        Raises:
            ValueError: If bracket not found or data invalid
            IOError: If PDF generation fails
        """
        self.logger.info(f"Generating pool bracket PDF: bracket_id={bracket_id}")
        
        # TODO: Retrieve bracket data from database
        # bracket_data = self._fetch_bracket_data(bracket_id, 'pool')
        
        # For now, create a realistic sample PDF
        return self._create_sample_pool_pdf_realistic(output_path)

    # ===== PDF Drawing Methods (translating canvas operations to ReportLab) =====

    def draw_bracket_pdf_ko(self, output_path: str, bracket: List[Tuple],
                           normalized_participants: List[Dict[str, Any]]) -> str:
        """
        Generate KO bracket PDF using exact viewer rendering logic.
        
        This method replicates the bracketing rendering from table_and_bracket_viewer.py
        to ensure visual consistency between screen and print.
        
        Args:
            output_path: Where to save PDF
            bracket: List of (name1, name2) tuples from _compute_snake_bracket()
            normalized_participants: List of dicts with 'Name' and 'Verein' keys
        
        Returns:
            Path to generated PDF
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Build rounds with club information (exactly as viewer does)
            rounds_with_clubs = build_bracket_rounds(bracket, normalized_participants)
            self.logger.debug(f"Built bracket with {len(rounds_with_clubs)} rounds")
            
            # Calculate box dimensions (exactly as viewer does)
            box_width, box_height, x_gap, y_gap = calculate_box_size(
                rounds_with_clubs, self.zoom_level
            )
            self.logger.debug(f"Box dimensions: {box_width}x{box_height}, gaps: {x_gap}x{y_gap}")
            
            # Calculate positions (exactly as viewer does)
            positions = {}
            y_offsets = {}
            first_total = len(rounds_with_clubs[0])
            start_x = int(60 * self.zoom_level)
            start_y = int(60 * self.zoom_level)
            
            # Round 0: vertical stack
            for m in range(first_total):
                x = start_x
                y = start_y + m * (box_height + y_gap)
                positions[(0, m)] = (x, y)
                y_offsets[(0, m)] = y + box_height // 2
            
            # Later rounds: center between previous matches
            for r in range(1, len(rounds_with_clubs)):
                matches = rounds_with_clubs[r]
                x = start_x + r * (box_width + x_gap)
                for m in range(len(matches)):
                    prev1 = (r - 1, m * 2)
                    prev2 = (r - 1, m * 2 + 1)
                    y1 = y_offsets.get(prev1, start_y)
                    y2 = y_offsets.get(prev2, y1)
                    y = (y1 + y2) // 2 - box_height // 2
                    positions[(r, m)] = (x, y)
                    y_offsets[(r, m)] = y + box_height // 2
            
            self.logger.debug(f"Calculated {len(positions)} match positions")
            
            # Create PDF canvas
            max_x = max(p[0] for p in positions.values()) + box_width + start_x if positions else 1000
            max_y = max(p[1] for p in positions.values()) + box_height + start_y if positions else 500
            
            from reportlab.lib.pagesizes import landscape
            from reportlab.lib.units import inch as pdf_inch
            
            # Use landscape A4 or larger if needed
            page_width = max(11.7 * pdf_inch, max_x + 2 * pdf_inch)
            page_height = max(8.3 * pdf_inch, max_y + 2 * pdf_inch)
            
            c = pdf_canvas.Canvas(output_path, pagesize=(page_width, page_height))
            
            # Draw bracket
            self._draw_bracket_on_pdf(c, rounds_with_clubs, positions, box_width,
                                     box_height, self.zoom_level)
            
            # Add header
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(COLORS['text_primary'])
            c.drawString(50, page_height - 50, "Tournament Bracket - KO Format")
            
            # Add footer
            c.setFont("Helvetica", 8)
            c.setFillColor(COLORS['text_secondary'])
            c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            c.save()
            self.logger.info(f"KO bracket PDF created: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error generating KO PDF: {e}")
            raise

    def _draw_bracket_on_pdf(self, c: pdf_canvas.Canvas,
                            rounds: List[List[Tuple]],
                            positions: Dict[Tuple[int, int], Tuple[int, int]],
                            box_width: int, box_height: int, zoom_level: float) -> None:
        """
        Draw bracket visualization on PDF canvas.
        
        Translates draw_bracket_on_canvas() logic from bracket_renderer.py to ReportLab.
        
        Args:
            c: ReportLab canvas
            rounds: List of match rounds with (name1, name2, club1, club2) tuples
            positions: Dict mapping (round, match) to (x, y) coordinates
            box_width, box_height: Dimensions of match boxes
            zoom_level: Current zoom level
        """
        self.logger.debug(f"Drawing bracket with {len(rounds)} rounds and {len(positions)} positions")
        
        line_width = max(1, int(2 * zoom_level))
        font_size = max(6, int(10 * zoom_level))
        
        # First pass: draw all boxes and text
        for r, matches in enumerate(rounds):
            self.logger.debug(f"Drawing round {r} with {len(matches)} matches")
            
            for m, match_data in enumerate(matches):
                # Handle both old (2-tuple) and new (4-tuple) formats
                if len(match_data) == 4:
                    p1, p2, club1, club2 = match_data
                else:
                    p1, p2 = match_data
                    club1, club2 = '', ''
                
                if (r, m) not in positions:
                    continue
                
                x, y = positions[(r, m)]
                
                # Format display with club info
                p1_display = f"{p1} [{club1}]" if club1 and club1 != 'Freilos' else p1
                p2_display = f"{p2} [{club2}]" if club2 and club2 != 'Freilos' else p2
                
                self.logger.debug(f"Round {r}, Match {m}: {p1_display} vs {p2_display} @ ({x}, {y})")
                
                # Draw match box
                c.setLineWidth(line_width)
                c.setStrokeColor(COLORS['white'])
                c.setFillColor(COLORS['bg_dark'])
                c.rect(x, y, box_width, box_height, stroke=1, fill=1)
                
                # Draw separator line (dashed)
                c.setLineWidth(line_width * 0.5)
                c.setDash(int(2 * zoom_level), int(2 * zoom_level))
                c.setStrokeColor(COLORS['text_secondary'])
                c.line(x, y + box_height // 2, x + box_width, y + box_height // 2)
                c.setDash()  # Reset to solid
                c.setLineWidth(line_width)
                c.setStrokeColor(COLORS['white'])
                
                # Draw fighter names
                c.setFont("Courier", font_size)
                c.setFillColor(COLORS['white'])
                c.drawCentredString(x + box_width // 2, y + 3 * box_height // 4, p1_display)
                c.drawCentredString(x + box_width // 2, y + box_height // 4, p2_display)
                
                # Draw "vs" separator
                c.setFont("Helvetica-Bold", max(6, int(10 * zoom_level)))
                c.setFillColor(COLORS['accent_red'])
                c.drawCentredString(x + box_width // 2, y + box_height // 2, "vs")
        
        # Second pass: draw connectors with arrows on top
        c.setLineWidth(line_width)
        c.setStrokeColor(COLORS['white'])
        
        for r in range(len(rounds) - 1):
            for m in range(len(rounds[r])):
                if (r, m) not in positions:
                    continue
                
                x1, y1 = positions[(r, m)]
                next_match_idx = m // 2
                
                if (r + 1, next_match_idx) not in positions:
                    continue
                
                x2, y2 = positions[(r + 1, next_match_idx)]
                
                # Draw connector line from middle of current box to middle of next box
                start_x = x1 + box_width
                start_y = y1 + box_height // 2
                end_x = x2
                end_y = y2 + box_height // 2
                
                self._draw_arrow_connector(c, start_x, start_y, end_x, end_y,
                                         line_width * 1.5, COLORS['dark_grey'], zoom_level)

    # ===== Sample PDFs for testing =====

    def _draw_arrow_connector(self, c: pdf_canvas.Canvas, x1: float, y1: float,
                             x2: float, y2: float, line_width: float,
                             color, zoom_level: float) -> None:
        """
        Draw a simple connector line (no arrow head).
        
        Args:
            c: ReportLab canvas
            x1, y1: Start point
            x2, y2: End point
            line_width: Width of the line
            color: Color of the line
            zoom_level: Current zoom level
        """
        # Draw simple line
        c.setLineWidth(line_width)
        c.setStrokeColor(color)
        c.line(x1, y1, x2, y2)

    def _create_sample_ko_pdf_realistic(self, output_path: str) -> str:
        """Create a realistic KO bracket PDF with multiple rounds."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Sample bracket data
            bracket = [
                ('Alice Schmidt', 'Bob Müller'),
                ('Carol Weber', 'Diana König'),
            ]
            
            normalized_participants = [
                {'Name': 'Alice Schmidt', 'Verein': 'TSC Berlin'},
                {'Name': 'Bob Müller', 'Verein': 'Kendo Köln'},
                {'Name': 'Carol Weber', 'Verein': 'JKA Munich'},
                {'Name': 'Diana König', 'Verein': 'Shotokan Stuttgart'},
            ]
            
            return self.draw_bracket_pdf_ko(output_path, bracket, normalized_participants)
        
        except Exception as e:
            self.logger.error(f"Error creating sample KO PDF: {e}")
            raise

    def _create_sample_pool_pdf_realistic(self, output_path: str) -> str:
        """Create a realistic pool bracket PDF."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            c = pdf_canvas.Canvas(output_path, pagesize=landscape(A4))
            width, height = landscape(A4)
            
            # Sample pool data
            fighters = [
                {'Name': 'Alice Schmidt', 'Verein': 'TSC Berlin'},
                {'Name': 'Bob Müller', 'Verein': 'Kendo Köln'},
                {'Name': 'Carol Weber', 'Verein': 'JKA Munich'},
                {'Name': 'Diana König', 'Verein': 'Shotokan Stuttgart'},
            ]
            
            # Draw simple pool table
            self._draw_pool_results_table(c, fighters, start_x=50, start_y=height-100,
                                         pool_label="Pool 1", zoom_level=1.0)
            
            # Footer
            c.setFont("Helvetica", 8)
            c.setFillColor(COLORS['text_secondary'])
            c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            c.save()
            self.logger.info(f"Pool bracket PDF created: {output_path}")
            return output_path
        
        except Exception as e:
            self.logger.error(f"Error creating sample pool PDF: {e}")
            raise

    def _draw_pool_results_table(self, c: pdf_canvas.Canvas,
                                 pool_fighters: List[Dict[str, str]],
                                 start_x: float = 50, start_y: float = 400,
                                 pool_label: str = "Pool 1",
                                 zoom_level: float = 1.0) -> None:
        """
        Draw pool results table on PDF.
        
        Args:
            c: ReportLab canvas
            pool_fighters: List of fighter dicts with 'Name' and 'Verein' keys
            start_x, start_y: Starting position
            pool_label: Label for the pool
            zoom_level: Zoom level for sizing
        """
        try:
            self.logger.debug(f"Drawing pool table with {len(pool_fighters)} fighters")
            
            # Calculate dimensions
            pool_size = len(pool_fighters)
            fight_schedule = _generate_fight_schedule(pool_size)
            num_fights = len(fight_schedule)
            
            line_width = max(1, int(2 * zoom_level))
            font_size = max(8, int(10 * zoom_level))
            header_font_size = max(10, int(12 * zoom_level))
            
            # Column widths
            num_col_width = 40
            name_col_width = 200
            result_col_width = 60
            
            header_height = 25
            row_height = 20
            
            # Draw pool label
            c.setFont("Helvetica-Bold", header_font_size)
            c.setFillColor(COLORS['text_primary'])
            c.drawCentredString(start_x + (num_col_width + name_col_width + result_col_width * num_fights) // 2,
                               start_y + 10, pool_label)
            
            # Draw headers
            c.setLineWidth(line_width)
            c.setStrokeColor(COLORS['accent_blue'])
            c.setFillColor(COLORS['bg_panel'])
            
            # Header row
            col_x = start_x
            headers = ['#'] + [f.get('Name', '').split()[0][:3] for f in pool_fighters]
            
            for header_idx, header in enumerate(headers):
                if header_idx == 0:
                    col_width = num_col_width
                elif header_idx == 1:
                    col_width = name_col_width
                else:
                    col_width = result_col_width
                
                # Draw header cell
                c.rect(col_x, start_y - header_height, col_width, header_height,
                       stroke=1, fill=1)
                
                c.setFont("Helvetica-Bold", font_size)
                c.setFillColor(COLORS['accent_red'])
                c.drawCentredString(col_x + col_width // 2, start_y - header_height // 2, header)
                
                col_x += col_width
            
            # Draw fighter rows
            for row_idx, fighter in enumerate(pool_fighters):
                row_y = start_y - header_height - (row_idx + 1) * row_height
                col_x = start_x
                
                # Rank/number cell
                c.setLineWidth(line_width)
                c.setStrokeColor(COLORS['border_light'])
                c.setFillColor(COLORS['bg_dark'])
                c.rect(col_x, row_y - row_height, num_col_width, row_height, stroke=1, fill=1)
                c.setFont("Helvetica", font_size)
                c.setFillColor(COLORS['text_primary'])
                c.drawCentredString(col_x + num_col_width // 2, row_y - row_height // 2,
                                   str(row_idx + 1))
                col_x += num_col_width
                
                # Name cell
                c.rect(col_x, row_y - row_height, name_col_width, row_height, stroke=1, fill=1)
                c.setFillColor(COLORS['text_primary'])
                fighter_name = fighter.get('Name', '')
                c.drawString(col_x + 5, row_y - row_height // 2, fighter_name[:25])
                col_x += name_col_width
                
                # Result cells (one per opponent)
                for fight_idx in range(pool_size - 1):
                    c.rect(col_x, row_y - row_height, result_col_width, row_height, stroke=1, fill=1)
                    if fight_idx < pool_size - 1:
                        c.setFillColor(COLORS['text_secondary'])
                        c.drawCentredString(col_x + result_col_width // 2, row_y - row_height // 2, "-")
                    col_x += result_col_width
            
            self.logger.debug(f"Drew pool table with {len(pool_fighters)} fighters and {num_fights} fights")
        
        except Exception as e:
            self.logger.error(f"Error drawing pool table: {e}")

    def draw_double_pool_ko_pdf(self, output_path: str, pool1_fighters: List[Dict[str, str]],
                               pool2_fighters: List[Dict[str, str]], bracket_key: str = "Tournament Bracket") -> str:
        """
        Generate double pool with KO knockout bracket PDF.
        
        Format:
        - Header with bracket key at top
        - Pool 1 and Pool 2 drawn below header
        - Semi-final KO matches between pool winners
        - Final match
        
        Args:
            output_path: Where to save PDF
            pool1_fighters: List of fighters in pool 1
            pool2_fighters: List of fighters in pool 2
            bracket_key: Header text for bracket identification
        
        Returns:
            Path to generated PDF
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            c = pdf_canvas.Canvas(output_path, pagesize=landscape(A4))
            width, height = landscape(A4)
            
            # Draw header at top
            c.setFont("Helvetica-Bold", 18)
            c.setFillColor(COLORS['text_primary'])
            header_y = height - 40
            c.drawCentredString(width // 2, header_y, bracket_key)
            
            # Draw divider line under header
            c.setLineWidth(2)
            c.setStrokeColor(COLORS['border_light'])
            c.line(50, header_y - 10, width - 50, header_y - 10)
            
            # Draw both pools (moved to top, below header)
            pools_start_y = header_y - 80
            self._draw_pool_results_table(c, pool1_fighters, 
                                         start_x=50, start_y=pools_start_y,
                                         pool_label="Pool 1", zoom_level=1.0)
            
            self._draw_pool_results_table(c, pool2_fighters, 
                                         start_x=450, start_y=pools_start_y,
                                         pool_label="Pool 2", zoom_level=1.0)
            
            # Draw semi-final KO bracket section (below pools)
            ko_start_y = pools_start_y - 250
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(COLORS['text_primary'])
            c.drawString(50, ko_start_y + 50, "KO Round - Semi-Finals & Final")
            
            # Semi-final boxes (simplified - 4 positions: winners of pools)
            box_width, box_height = 180, 60
            semi1_x, semi1_y = 80, ko_start_y - 20
            semi2_x, semi2_y = 80, ko_start_y - 120
            final_x, final_y = 350, ko_start_y - 70
            
            # Draw semi-final 1
            c.setLineWidth(2)
            c.setStrokeColor(COLORS['white'])
            c.setFillColor(COLORS['bg_dark'])
            c.rect(semi1_x, semi1_y - box_height, box_width, box_height, stroke=1, fill=1)
            c.setFont("Helvetica", 9)
            c.setFillColor(COLORS['text_primary'])
            c.drawCentredString(semi1_x + box_width//2, semi1_y - box_height//4, 
                               f"Winner Pool 1")
            c.drawCentredString(semi1_x + box_width//2, semi1_y - 3*box_height//4,
                               f"Winner Pool 2")
            
            # Draw semi-final 2
            c.rect(semi2_x, semi2_y - box_height, box_width, box_height, stroke=1, fill=1)
            c.drawCentredString(semi2_x + box_width//2, semi2_y - box_height//4,
                               f"Winner Pool 2")
            c.drawCentredString(semi2_x + box_width//2, semi2_y - 3*box_height//4,
                               f"Winner Pool 1")
            
            # Draw final
            c.rect(final_x, final_y - box_height, box_width, box_height, stroke=1, fill=1)
            c.drawCentredString(final_x + box_width//2, final_y - box_height//4,
                               "Semi 1 Winner")
            c.drawCentredString(final_x + box_width//2, final_y - 3*box_height//4,
                               "Semi 2 Winner")
            
            # Draw arrows from semis to final (pointing to middle of boxes)
            self._draw_arrow_connector(c, 
                                     semi1_x + box_width, semi1_y - box_height//2,
                                     final_x, final_y - box_height//2,
                                     2, COLORS['dark_grey'], 1.0)
            
            self._draw_arrow_connector(c,
                                     semi2_x + box_width, semi2_y - box_height//2,
                                     final_x, final_y - box_height//2,
                                     2, COLORS['dark_grey'], 1.0)
            
            # Footer
            c.setFont("Helvetica", 8)
            c.setFillColor(COLORS['text_secondary'])
            c.drawString(50, 30, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            c.save()
            self.logger.info(f"Double pool KO PDF created: {output_path}")
            return output_path
        
        except Exception as e:
            self.logger.error(f"Error creating double pool KO PDF: {e}")
            raise

