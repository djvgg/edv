# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Unified Bracket PDF Generator v3

Uses the exact same canvas rendering as the tkinter viewer, but:
- Renders on invisible canvas
- Uses print-friendly colors (light mode)
- Exports via Ghostscript PostScript→PDF

Advantage: Any visualization changes in bracket_renderer automatically 
apply to both UI and prints - no code duplication!
"""

import os
import sys
import tkinter as tk
import tempfile
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger
from utils.bracket_utils import _compute_snake_bracket
from frontend.utils.bracket_renderer import (
    compute_bracket_rounds,
    calculate_box_size,
    draw_bracket_on_canvas,
    calculate_ko_positions,
    draw_ko_connectors,
    calculate_loser_positions,
    draw_loser_connectors,
)

logger = get_logger('bracket_pdf_generator_v3')

try:
    import ghostscript
    HAS_GHOSTSCRIPT = True
except (ImportError, RuntimeError):
    HAS_GHOSTSCRIPT = False
    logger.debug("ghostscript Python package not available - will try subprocess")


# Print-friendly color palette (light mode)
PRINT_COLORS = {
    'bg_match': '#ffffff',           # White background
    'bg_panel': '#ffffff',           # White
    'text_primary': '#000000',       # Black text
    'text_secondary': '#333333',     # Dark grey
    'border_ko': '#000000',          # Black borders
    'border_light': '#cccccc',       # Light grey
    'accent_orange': '#ff9900',      # Orange for LB
    'accent_red': '#ff0000',         # Red for emphasis
    'accent_blue': '#0000ff',        # Blue
    'white': '#000000',              # Use BLACK for outlines on white canvas
    'black': '#000000',              # Black
}


def postscript_to_pdf(ps_path, pdf_path):
    """Convert PostScript to PDF using Ghostscript via Docker.
    
    Uses minidocks/ghostscript Docker container for reliable conversion.
    Falls back to command-line tools if Docker not available.
    
    Args:
        ps_path: Path to PostScript file
        pdf_path: Output PDF path
    
    Returns:
        True if successful, False otherwise
    """
    # Get absolute paths
    ps_abs = os.path.abspath(ps_path)
    pdf_abs = os.path.abspath(pdf_path)
    workspace = os.path.dirname(ps_abs)
    ps_filename = os.path.basename(ps_abs)
    pdf_filename = os.path.basename(pdf_abs)
    
    # Try Docker first (minidocks/ghostscript)
    try:
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{workspace}:/tmp",
            "minidocks/ghostscript",
            "sh", "-c",
            f"gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=/tmp/{pdf_filename} /tmp/{ps_filename}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(pdf_abs):
            logger.info(f"✓ Converted PostScript to PDF (via Docker Ghostscript): {pdf_path}")
            return True
        else:
            logger.debug(f"Docker Ghostscript failed: {result.stderr}")
    except FileNotFoundError:
        logger.debug("Docker not found")
    except subprocess.TimeoutExpired:
        logger.debug("Docker command timeout")
    except Exception as e:
        logger.debug(f"Docker conversion failed: {e}")
    
    # Try command line tools if Docker fails
    try:
        cmd = [
            'gswin64c',
            '-dNOPAUSE',
            '-dBATCH',
            '-sDEVICE=pdfwrite',
            f'-sOutputFile={pdf_abs}',
            ps_abs
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(pdf_abs):
            logger.info(f"✓ Converted PostScript to PDF (via gswin64c): {pdf_path}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    
    logger.error(f"PostScript to PDF conversion failed. Install Docker or Ghostscript.")
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
        # Check if canvas has any items
        all_items = canvas.find_all()
        print(f"Canvas has {len(all_items)} items")
        
        if not all_items:
            print("WARNING: Canvas is empty - no items to render!")
            logger.warning("Canvas is empty - no items to render!")
        
        # Get canvas bounds for correct PostScript export
        bbox = canvas.bbox("all")
        print(f"Canvas bbox: {bbox}")
        
        if not bbox:
            print("ERROR: Canvas has no items with bbox")
            logger.error("Canvas has no items")
            return False
        
        # Add padding around items (20px on each side)
        x1, y1, x2, y2 = bbox
        padding = 20
        x1 -= padding
        y1 -= padding
        x2 += padding
        y2 += padding
        
        # Export to PostScript with explicit bounds
        # postscript(x1, y1, x2, y2) uses canvas coordinates
        try:
            ps_string = canvas.postscript(colormode='color', x=x1, y=y1, width=x2-x1, height=y2-y1)
        except TypeError:
            # Fallback if parameters aren't available
            print("postscript() doesn't support x/y/width/height, trying basic call...")
            ps_string = canvas.postscript(colormode='color')
        
        # Check PostScript content
        ps_size = len(ps_string)
        print(f"PostScript generated: {ps_size} bytes")
        
        if ps_size < 100:
            print(f"WARNING: PostScript very small ({ps_size} bytes) - may be empty!")
            logger.warning(f"PostScript very small ({ps_size} bytes) - may be empty!")
        
        with open(output_path, 'w') as f:
            f.write(ps_string)
        print(f"Saved PostScript to {output_path} ({ps_size} bytes)")
        return True
    except Exception as e:
        print(f"ERROR: Error exporting to PostScript: {e}")
        logger.error(f"Error exporting to PostScript: {e}")
        import traceback
        traceback.print_exc()
        return False


def render_single_knockout_to_canvas(root, bracket_pairs, participants_list=None):
    """
    Render single/double elimination KO bracket on canvas using viewer's algorithm.
    
    Args:
        root: tkinter Tk root
        bracket_pairs: List of (name1, name2) tuples
        participants_list: Optional list of participant dicts for club info
    
    Returns:
        Configured tkinter Canvas with bracket rendered
    """
    canvas = tk.Canvas(root, bg='white')
    
    # Build bracket rounds using viewer's algorithm
    rounds = compute_bracket_rounds(bracket_pairs)
    
    if not rounds:
        logger.warning("No rounds computed from bracket pairs")
        return canvas
    
    # Convert match dicts to tuples for calculate_box_size (which expects tuples)
    rounds_for_sizing = []
    for round_matches in rounds:
        round_tuples = []
        for match in round_matches:
            if isinstance(match, dict):
                round_tuples.append((match.get('p1', 'TBD'), match.get('p2', 'TBD')))
            else:
                round_tuples.append(match)
        rounds_for_sizing.append(round_tuples)
    
    # Calculate dimensions
    box_w, box_h, x_gap, y_gap = calculate_box_size(rounds_for_sizing, zoom_level=1.0)
    
    # Calculate positions using viewer's algorithm
    positions = calculate_ko_positions(rounds_for_sizing, zoom_level=1.0)
    
    if not positions:
        logger.warning("No positions calculated")
        return canvas
    
    # Unpack the tuple (positions_dict, y_midpoints_dict)
    positions_dict, y_midpoints = positions
    
    # Configure canvas size
    max_x = max(pos[0] for pos in positions_dict.values()) + box_w + 50
    max_y = max(pos[1] for pos in positions_dict.values()) + box_h + 50
    
    # Draw bracket using viewer's exact rendering function
    draw_bracket_on_canvas(canvas, rounds, positions_dict, box_w, box_h,
                          zoom_level=1.0, colors=PRINT_COLORS, fonts={})
    
    # Draw connectors using viewer's algorithm
    draw_ko_connectors(canvas, positions_dict, rounds, zoom_level=1.0, colors=PRINT_COLORS)
    
    canvas.config(width=max_x, height=max_y, scrollregion=(0, 0, max_x, max_y))
    item_count = len(canvas.find_all())
    print(f"Rendered KO bracket: {max_x}x{max_y}, {item_count} canvas items")
    logger.info(f"Rendered KO bracket on canvas: {max_x}x{max_y}")
    
    return canvas


def render_double_elimination_to_canvas(root, bracket_pairs, participants_list=None):
    """
    Render double elimination bracket (winners + losers) on canvas.
    
    Args:
        root: tkinter Tk root
        bracket_pairs: List of (name1, name2) tuples for winners bracket
        participants_list: Optional participant list
    
    Returns:
        Configured tkinter Canvas
    """
    canvas = tk.Canvas(root, bg='white')
    
    # Build winners bracket
    wb_rounds = compute_bracket_rounds(bracket_pairs)
    if not wb_rounds:
        return canvas
    
    # Convert to tuples for all calculations (viewer functions work with tuples or need conversion)
    wb_rounds_for_sizing = []
    for round_matches in wb_rounds:
        round_tuples = []
        for match in round_matches:
            if isinstance(match, dict):
                round_tuples.append((match.get('p1', 'TBD'), match.get('p2', 'TBD')))
            else:
                round_tuples.append(match)
        wb_rounds_for_sizing.append(round_tuples)
    
    # Calculate dimensions
    box_w, box_h, x_gap, y_gap = calculate_box_size(wb_rounds_for_sizing, zoom_level=1.0)
    
    # Draw winners bracket
    wb_positions_result = calculate_ko_positions(wb_rounds_for_sizing, zoom_level=1.0)
    wb_positions, wb_y_midpoints = wb_positions_result  # Unpack tuple
    
    # Convert wb_rounds to tuple format for draw_bracket_on_canvas
    wb_rounds_for_drawing = []
    for round_matches in wb_rounds:
        round_tuples = []
        for match in round_matches:
            if isinstance(match, dict):
                round_tuples.append((match.get('p1', 'TBD'), match.get('p2', 'TBD')))
            else:
                round_tuples.append(match)
        wb_rounds_for_drawing.append(round_tuples)
    
    draw_bracket_on_canvas(canvas, wb_rounds_for_drawing, wb_positions, box_w, box_h,
                          zoom_level=1.0, colors=PRINT_COLORS, fonts={})
    draw_ko_connectors(canvas, wb_positions, wb_rounds, zoom_level=1.0, 
                      colors=PRINT_COLORS)
    
    # Compute loser bracket using viewer's algorithm
    def get_loser(match):
        w = match.get('winner')
        if w is None:
            return 'TBD'
        if match.get('p1') == 'Freilos' or match.get('p2') == 'Freilos':
            return 'Freilos'
        return match.get('p2') if w == match.get('p1') else match.get('p1')
    
    loser_rounds = []
    
    # LB R0: pair consecutive losers from WB R0
    wb_r0_losers = [get_loser(m) for m in wb_rounds[0]]
    lb_r0 = []
    for i in range(0, len(wb_r0_losers), 2):
        p1 = wb_r0_losers[i]
        p2 = wb_r0_losers[i + 1] if i + 1 < len(wb_r0_losers) else 'Freilos'
        lb_r0.append({'p1': p1, 'p2': p2, 'winner': None})
    loser_rounds.append(lb_r0)
    
    wb_idx = 1
    while True:
        prev = loser_rounds[-1]
        if len(prev) <= 1:
            break
        
        lb_winners = [(m.get('winner') if m.get('winner') is not None else 'TBD')
                     for m in prev]
        
        if wb_idx < len(wb_rounds) - 1:
            wb_losers = [get_loser(m) for m in wb_rounds[wb_idx]]
            
            if len(lb_winners) > len(wb_losers):
                # Reduction round
                reduction = []
                for i in range(0, len(lb_winners), 2):
                    p1 = lb_winners[i]
                    p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                    reduction.append({'p1': p1, 'p2': p2, 'winner': None})
                loser_rounds.append(reduction)
            else:
                # Injection round
                injection = []
                for j in range(len(wb_losers)):
                    lw = lb_winners[j] if j < len(lb_winners) else 'TBD'
                    wl = wb_losers[j]
                    injection.append({'p1': lw, 'p2': wl, 'winner': None})
                loser_rounds.append(injection)
                wb_idx += 1
        else:
            # Final 3rd place match
            if len(lb_winners) > 1:
                final = []
                for i in range(0, len(lb_winners), 2):
                    p1 = lb_winners[i]
                    p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                    final.append({'p1': p1, 'p2': p2, 'winner': None})
                loser_rounds.append(final)
            break
    
    # Draw loser bracket
    if loser_rounds:
        max_wb_y = max(pos[1] for pos in wb_positions.values()) + box_h
        y_offset = max_wb_y + 80
        
        lb_result = calculate_loser_positions(loser_rounds, zoom_level=1.0,
                                             y_offset=y_offset, start_x=50)
        lb_positions, lb_y_midpoints = lb_result  # Unpack tuple
        
        draw_loser_connectors(canvas, lb_positions, loser_rounds, zoom_level=1.0,
                             colors=PRINT_COLORS)
        
        # Draw loser bracket boxes using same style as viewer
        for r, matches in enumerate(loser_rounds):
            for m in range(len(matches)):
                if (r, m) not in lb_positions:
                    continue
                
                x, y = lb_positions[(r, m)]
                x2, y2 = x + box_w, y + box_h
                
                canvas.create_rectangle(x, y, x2, y2,
                    fill=PRINT_COLORS['bg_match'],
                    outline=PRINT_COLORS['accent_orange'],
                    width=2)
    
    # Update canvas size
    max_x = max(pos[0] for pos in wb_positions.values()) + box_w + 50
    if loser_rounds and lb_positions:
        max_y = max(max(pos[1] for pos in lb_positions.values()) + box_h + 50,
                   max(pos[1] for pos in wb_positions.values()) + box_h + 50)
    else:
        max_y = max(pos[1] for pos in wb_positions.values()) + box_h + 50
    
    # Update canvas size
    max_x = max(pos[0] for pos in wb_positions.values()) + box_w + 50
    if loser_rounds and lb_positions:
        max_y = max(max(pos[1] for pos in lb_positions.values()) + box_h + 50,
                   max(pos[1] for pos in wb_positions.values()) + box_h + 50)
    else:
        max_y = max(pos[1] for pos in wb_positions.values()) + box_h + 50
    
    canvas.config(width=max_x, height=max_y, scrollregion=(0, 0, max_x, max_y))
    
    # Debug: check actual canvas bounds
    bbox = canvas.bbox("all")
    item_count = len(canvas.find_all())
    print(f"Rendered double elimination: {max_x}x{max_y}, {item_count} canvas items")
    print(f"  Canvas bbox: {bbox}")
    print(f"  WB rounds: {len(wb_rounds)}, LB rounds: {len(loser_rounds)}")
    
    if not bbox or bbox == (0, 0, 0, 0):
        print(f"WARNING: Canvas bbox is empty or zero!")
    
    logger.info(f"Rendered double elimination on canvas: {max_x}x{max_y}")
    
    return canvas


def export_bracket_to_pdf(output_path: str, bracket_pairs: List[Tuple[str, str]],
                         participants_list: Optional[List[Dict]] = None,
                         bracket_type: str = 'single') -> bool:
    """
    Export bracket to PDF by rendering on hidden canvas then converting via Ghostscript.
    
    Uses the exact same rendering algorithm as the tkinter viewer for consistency.
    
    Args:
        output_path: Path to save PDF
        bracket_pairs: List of (name1, name2) tuples
        participants_list: Optional list of participant dicts
        bracket_type: 'single', 'double'
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()
        
        # Render appropriate bracket type on canvas
        if bracket_type == 'double':
            canvas = render_double_elimination_to_canvas(root, bracket_pairs, 
                                                        participants_list)
        else:
            canvas = render_single_knockout_to_canvas(root, bracket_pairs, 
                                                      participants_list)
        
        # Get canvas bounds
        bbox = canvas.bbox("all")
        if not bbox:
            logger.error("Canvas rendering failed")
            root.destroy()
            return False
        
        # Export canvas to PostScript first
        ps_path = output_path.replace('.pdf', '.ps')
        if not canvas_to_postscript(canvas, ps_path):
            root.destroy()
            return False
        
        logger.info(f"✓ Saved PostScript to {ps_path}")
        
        # Try to convert PostScript to PDF using Ghostscript
        if postscript_to_pdf(ps_path, output_path):
            logger.info(f"✓ Exported {bracket_type} bracket to {output_path}")
            # Clean up PostScript if PDF succeeded
            try:
                os.remove(ps_path)
            except:
                pass
            root.destroy()
            return True
        else:
            logger.info(f"Note: PDF conversion requires Ghostscript. PostScript saved to {ps_path}")
            logger.info(f"  To convert: ps2pdf {ps_path} {output_path}")
            root.destroy()
            return True  # Success if PostScript saved, even if PDF conversion failed
        
    except Exception as e:
        logger.error(f"Error exporting bracket to PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


class BracketPDFGeneratorV3:
    """Unified PDF generator using canvas renderer (viewer's algorithm)."""
    
    def __init__(self):
        """Initialize generator."""
        self.logger = logger
    
    def draw_bracket_pdf(self, output_path: str, bracket_pairs: List[Tuple[str, str]],
                        participants_list: Optional[List[Dict]] = None,
                        bracket_type: str = 'single') -> bool:
        """
        Draw bracket PDF using viewer's canvas rendering.
        
        Args:
            output_path: Path to save PDF
            bracket_pairs: List of (name1, name2) tuples
            participants_list: Optional participant list
            bracket_type: 'single' or 'double'
        
        Returns:
            True if successful
        """
        return export_bracket_to_pdf(output_path, bracket_pairs, participants_list,
                                    bracket_type)


if __name__ == '__main__':
    # Test
    from utils.bracket_utils import _compute_snake_bracket
    
    fighters = [
        {'Name': 'Emma Koch', 'Verein': 'Club Alpha'},
        {'Name': 'Clara Becker', 'Verein': 'Club Beta'},
        {'Name': 'Julia Bauer', 'Verein': 'Club Alpha'},
        {'Name': 'Lena Müller', 'Verein': 'Club Gamma'},
        {'Name': 'Mia Meyer', 'Verein': 'Club Delta'},
        {'Name': 'Lina Müller', 'Verein': 'Club Beta'},
        {'Name': 'Lena Schmidt', 'Verein': 'Club Epsilon'},
        {'Name': 'Amelie Schäfer', 'Verein': 'Club Zeta'},
    ]
    
    bracket_pairs = _compute_snake_bracket(fighters)
    
    gen = BracketPDFGeneratorV3()
    
    # Test double elimination
    success = gen.draw_bracket_pdf('temp/test_v3_double.pdf', bracket_pairs, 
                                  fighters, bracket_type='double')
    print(f"Double elimination: {'✓' if success else '✗'}")
    
    # Test single elimination
    success = gen.draw_bracket_pdf('temp/test_v3_single.pdf', bracket_pairs,
                                  fighters, bracket_type='single')
    print(f"Single elimination: {'✓' if success else '✗'}")
