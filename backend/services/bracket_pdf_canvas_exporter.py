# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Export bracket canvas to PDF by rendering on tkinter canvas then capturing.

Uses Ghostscript to convert PostScript to PDF for proper formatting.
"""

import sys
import os
import tkinter as tk
from io import BytesIO
from pathlib import Path
import tempfile

# Setup path for imports
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger
from utils.bracket_utils import _compute_snake_bracket
from frontend.utils.bracket_renderer import (
    compute_bracket_rounds, calculate_box_size, draw_bracket_on_canvas,
    calculate_ko_positions, draw_ko_connectors,
    calculate_loser_positions, draw_loser_connectors
)

logger = get_logger('bracket_canvas_exporter')

try:
    import ghostscript
    HAS_GHOSTSCRIPT = True
except ImportError:
    HAS_GHOSTSCRIPT = False
    logger.warning("ghostscript package not available - PostScript to PDF conversion disabled")


def render_bracket_to_canvas(root, bracket_pairs, participants_list, tournament_type='single'):
    """
    Render bracket on a tkinter Canvas and return the canvas.
    
    Args:
        root: tkinter Tk root window
        bracket_pairs: List of (name1, name2) tuples for R0
        participants_list: List of dicts with 'Name' and 'Verein' keys
        tournament_type: 'single' or 'double'
    
    Returns:
        Configured tkinter Canvas with bracket rendered
    """
    # Create canvas
    canvas = tk.Canvas(root, bg='white')
    
    # Build brackets
    rounds = compute_bracket_rounds(bracket_pairs)
    
    # Calculate box dimensions
    box_w, box_h, x_gap, y_gap = calculate_box_size(rounds, zoom_level=1.0)
    
    # Calculate positions for winners bracket
    positions = calculate_ko_positions(rounds, zoom_level=1.0)
    
    # Configure canvas size
    max_x = max(pos[0] for pos in positions.values()) + box_w + 50
    max_y = max(pos[1] for pos in positions.values()) + box_h + 50
    
    # Build normalized participants for colors
    fighter_clubs = {p['Name']: p.get('Verein', '') for p in participants_list}
    
    colors = {
        'bg_match': '#f0f0f0',
        'border_ko': '#333333',
        'text_winner': '#000000',
        'accent_orange': '#ff9900',
        'accent_red': '#cc0000',
    }
    
    fonts = {
        'name': ('Arial', 10),
        'club': ('Arial', 8),
    }
    
    # Draw winners bracket
    draw_bracket_on_canvas(canvas, rounds, positions, box_w, box_h, 
                          zoom_level=1.0, colors=colors, fonts=fonts)
    
    # Draw connectors
    draw_ko_connectors(canvas, positions, rounds, zoom_level=1.0, colors=colors)
    
    # If double elimination, add loser bracket
    if tournament_type == 'double':
        # Compute loser rounds
        loser_rounds = _compute_loser_rounds(rounds)
        
        if loser_rounds:
            max_wb_y = max(pos[1] for pos in positions.values()) + box_h
            y_offset = max_wb_y + 80
            
            lb_positions, _ = calculate_loser_positions(loser_rounds, zoom_level=1.0, 
                                                         y_offset=y_offset, start_x=50)
            
            draw_loser_connectors(canvas, lb_positions, loser_rounds, 
                                 zoom_level=1.0, colors=colors)
            
            # Draw loser bracket boxes
            for r, matches in enumerate(loser_rounds):
                for m in range(len(matches)):
                    if (r, m) not in lb_positions:
                        continue
                    
                    x, y = lb_positions[(r, m)]
                    x2, y2 = x + box_w, y + box_h
                    
                    canvas.create_rectangle(x, y, x2, y2,
                        fill=colors['bg_match'], outline=colors['accent_orange'],
                        width=2)
            
            # Update canvas size if needed
            max_y = max(max_y, max(pos[1] for pos in lb_positions.values()) + box_h + 50)
    
    canvas.config(width=max_x, height=max_y, scrollregion=(0, 0, max_x, max_y))
    
    logger.info(f"Rendered bracket on canvas: {max_x}x{max_y}")
    return canvas


def _compute_loser_rounds(wb_rounds):
    """Compute loser bracket rounds from winners bracket rounds."""
    if len(wb_rounds) < 2:
        return []
    
    def get_loser(match):
        if match['winner'] and match['winner'] in ('Freilos', 'TBD'):
            return 'TBD'
        if match['winner'] == match['p1']:
            return match['p2'] if match['p2'] not in ('Freilos', 'TBD') else 'Freilos'
        if match['winner'] == match['p2']:
            return match['p1'] if match['p1'] not in ('Freilos', 'TBD') else 'Freilos'
        return 'TBD'
    
    loser_rounds = []
    
    # LB R0: pair consecutive losers from WB R0
    wb_r0_losers = [get_loser(m) for m in wb_rounds[0]]
    lb_r0_matches = []
    for i in range(0, len(wb_r0_losers), 2):
        p1 = wb_r0_losers[i]
        p2 = wb_r0_losers[i + 1] if i + 1 < len(wb_r0_losers) else 'Freilos'
        lb_r0_matches.append({'p1': p1, 'p2': p2, 'winner': None})
    loser_rounds.append(lb_r0_matches)
    
    # Later rounds: inject losers from each WB round
    for r in range(1, len(wb_rounds)):
        wb_r_losers = [get_loser(m) for m in wb_rounds[r]]
        lb_prev_winners = [m['winner'] if m['winner'] else 'TBD' for m in loser_rounds[r - 1]]
        
        if r == len(wb_rounds) - 1:
            # Final: LB winner vs WB loser (3rd place)
            p1 = lb_prev_winners[0] if lb_prev_winners else 'TBD'
            p2 = wb_r_losers[0] if wb_r_losers else 'TBD'
            loser_rounds.append([{'p1': p1, 'p2': p2, 'winner': None}])
        else:
            # Injection or reduction
            lb_matches = []
            prev_count = len(loser_rounds[r - 1])
            curr_wb_losers = len(wb_r_losers)
            
            if curr_wb_losers >= prev_count:
                # Injection: 1-to-1 pairing
                for i in range(prev_count):
                    p1 = lb_prev_winners[i] if i < len(lb_prev_winners) else 'TBD'
                    p2 = wb_r_losers[i] if i < len(wb_r_losers) else 'Freilos'
                    lb_matches.append({'p1': p1, 'p2': p2, 'winner': None})
            else:
                # Reduction: pair LB winners
                for i in range(0, len(lb_prev_winners), 2):
                    p1 = lb_prev_winners[i] if i < len(lb_prev_winners) else 'TBD'
                    p2 = lb_prev_winners[i + 1] if i + 1 < len(lb_prev_winners) else 'Freilos'
                    lb_matches.append({'p1': p1, 'p2': p2, 'winner': None})
            
            loser_rounds.append(lb_matches)
    
    return loser_rounds


def postscript_to_pdf(ps_path, pdf_path):
    """Convert PostScript to PDF using Ghostscript.
    
    Args:
        ps_path: Path to PostScript file
        pdf_path: Output PDF path
    
    Returns:
        True if successful, False otherwise
    """
    if not HAS_GHOSTSCRIPT:
        logger.error("ghostscript package required for PostScript to PDF conversion")
        return False
    
    try:
        args = [
            "ps2pdf",
            "-dNOPAUSE",
            "-dBATCH",
            "-dSAFER",
            "-sPAPERSIZE=a4",
            ps_path,
            pdf_path
        ]
        
        ghostscript.Ghostscript(*args)
        logger.info(f"Converted PostScript to PDF: {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"Error converting PostScript to PDF: {e}")
        return False


def canvas_to_postscript(canvas, output_path):
    """Export tkinter canvas to PostScript format.
    
    Args:
        canvas: tkinter Canvas widget
        output_path: Path to save PostScript
    
    Returns:
        True if successful, False otherwise
    """
    try:
        ps_string = canvas.postscript(colormode='color')
        with open(output_path, 'w') as f:
            f.write(ps_string)
        logger.info(f"Saved PostScript to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to PostScript: {e}")
        return False


def export_bracket_to_pdf(output_path, bracket_pairs, participants_list, 
                         tournament_type='single', title='Bracket'):
    """
    Export bracket to PDF by rendering on canvas then converting via Ghostscript.
    
    Args:
        output_path: Path to save PDF
        bracket_pairs: List of (name1, name2) tuples
        participants_list: List of dicts with 'Name' and 'Verein'
        tournament_type: 'single' or 'double'
        title: PDF title
    
    Returns:
        True if successful, False otherwise
    """
    if not HAS_GHOSTSCRIPT:
        logger.error("ghostscript required for PDF export")
        return False
    
    try:
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()  # Hide window
        
        # Render bracket on canvas
        canvas = render_bracket_to_canvas(root, bracket_pairs, participants_list, 
                                         tournament_type)
        
        # Get canvas bounds
        bbox = canvas.bbox("all")
        if not bbox:
            logger.error("Canvas rendering failed")
            root.destroy()
            return False
        
        # Create temporary PostScript file
        with tempfile.TemporaryDirectory() as tmpdir:
            ps_path = os.path.join(tmpdir, 'bracket_temp.ps')
            
            # Export canvas to PostScript
            if not canvas_to_postscript(canvas, ps_path):
                root.destroy()
                return False
            
            # Convert PostScript to PDF using Ghostscript
            if not postscript_to_pdf(ps_path, output_path):
                root.destroy()
                return False
            
            logger.info(f"Success: Exported bracket to {output_path}")
        
        root.destroy()
        return True
        
    except Exception as e:
        logger.error(f"Error exporting bracket to PDF: {e}")
        return False


if __name__ == '__main__':
    # Test
    fighters = [
        {'Name': 'Emma Koch', 'Verein': 'Club Alpha'},
        {'Name': 'Clara Becker', 'Verein': 'Club Beta'},
        {'Name': 'Julia Bauer', 'Verein': 'Club Alpha'},
        {'Name': 'Lena Müller', 'Verein': 'Club Gamma'},
    ]
    
    # Create snake seeded bracket
    bracket_pairs = _compute_snake_bracket(fighters)
    
    export_bracket_to_pdf('temp/test_canvas_export.pdf', bracket_pairs, fighters, 
                         tournament_type='double', title='Test Bracket')
