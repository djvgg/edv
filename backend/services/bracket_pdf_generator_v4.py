# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket PDF Generator v4 - "Canvas to PDF"

Renders bracket on tkinter canvas using viewer's exact algorithm (bracket_renderer),
then extracts canvas items and draws them on ReportLab PDF.

Benefits:
- ✅ Uses exact viewer algorithm (bracket_renderer functions)
- ✅ Direct ReportLab PDF (no Docker/PostScript)
- ✅ Supports pagination for massive tournaments
- ✅ Smallest files (like v2)
- ✅ Future-proof (auto-updates with viewer changes)
- ✅ No code duplication
"""

import os
import sys
import tkinter as tk
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import inch
from reportlab.lib import colors

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger
from frontend.styles import COLORS as FRONTEND_COLORS
from frontend.utils.bracket_renderer import (
    compute_bracket_rounds,
    calculate_box_size,
    draw_bracket_on_canvas,
    calculate_ko_positions,
    draw_ko_connectors,
    calculate_loser_positions,
    draw_loser_connectors,
)

logger = get_logger('bracket_pdf_generator_v4')

# Print-friendly color palette (light mode)
PRINT_COLORS = {
    'bg_match': '#ffffff',
    'bg_panel': '#ffffff',
    'text_primary': '#000000',
    'text_secondary': '#333333',
    'border_ko': '#000000',
    'border_light': '#cccccc',
    'accent_orange': '#ff9900',
    'accent_red': '#ff0000',
    'accent_blue': '#0000ff',
    'white': '#000000',  # Use BLACK for outlines on white canvas
    'black': '#000000',
}

# Color conversion cache
COLOR_CACHE = {
    '#ffffff': colors.HexColor('#ffffff'),
    '#000000': colors.HexColor('#000000'),
    '#333333': colors.HexColor('#333333'),
    '#cccccc': colors.HexColor('#cccccc'),
    '#ff9900': colors.HexColor('#ff9900'),
    '#ff0000': colors.HexColor('#ff0000'),
    '#0000ff': colors.HexColor('#0000ff'),
}


def get_color(hex_color):
    """Convert hex color string to ReportLab color with caching."""
    if hex_color not in COLOR_CACHE:
        try:
            COLOR_CACHE[hex_color] = colors.HexColor(hex_color)
        except:
            COLOR_CACHE[hex_color] = colors.black
    return COLOR_CACHE[hex_color]


def get_reportlab_font(font_name):
    """Map font names to ReportLab supported fonts."""
    # ReportLab only supports these standard PDF fonts
    if not font_name:
        return 'Helvetica'
    
    font_lower = font_name.lower()
    
    # Map common fonts to ReportLab fonts
    if 'courier' in font_lower or 'consolas' in font_lower or 'mono' in font_lower:
        return 'Courier'
    elif 'times' in font_lower:
        return 'Times-Roman'
    elif 'symbol' in font_lower:
        return 'Symbol'
    else:
        # Default to Helvetica for Arial, Verdana, and other sans-serif
        return 'Helvetica'


def render_double_elimination_to_canvas(root, bracket_pairs, participants_list=None):
    """
    Render double elimination bracket on tkinter canvas using viewer's algorithm.
    
    Args:
        root: tkinter Tk root
        bracket_pairs: List of (name1, name2) tuples
        participants_list: Optional participant list
    
    Returns:
        Configured tkinter Canvas
    """
    canvas = tk.Canvas(root, bg='white')
    
    # Build winners bracket
    wb_rounds = compute_bracket_rounds(bracket_pairs)
    if not wb_rounds:
        return canvas
    
    # Convert to tuples for sizing
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
    wb_positions, wb_y_midpoints = wb_positions_result
    
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
    draw_ko_connectors(canvas, wb_positions, wb_rounds, zoom_level=1.0, colors=PRINT_COLORS)
    
    # Compute loser bracket
    def get_loser(match):
        w = match.get('winner')
        if w is None:
            return 'TBD'
        if match.get('p1') == 'Freilos' or match.get('p2') == 'Freilos':
            return 'Freilos'
        return match.get('p2') if w == match.get('p1') else match.get('p1')
    
    loser_rounds = []
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
                reduction = []
                for i in range(0, len(lb_winners), 2):
                    p1 = lb_winners[i]
                    p2 = lb_winners[i + 1] if i + 1 < len(lb_winners) else 'Freilos'
                    reduction.append({'p1': p1, 'p2': p2, 'winner': None})
                loser_rounds.append(reduction)
            else:
                injection = []
                for j in range(len(wb_losers)):
                    lw = lb_winners[j] if j < len(lb_winners) else 'TBD'
                    wl = wb_losers[j]
                    injection.append({'p1': lw, 'p2': wl, 'winner': None})
                loser_rounds.append(injection)
                wb_idx += 1
        else:
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
        lb_positions, lb_y_midpoints = lb_result
        
        draw_loser_connectors(canvas, lb_positions, loser_rounds, zoom_level=1.0,
                             colors=PRINT_COLORS)
        
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
    
    # Configure canvas
    max_x = max(pos[0] for pos in wb_positions.values()) + box_w + 50
    if loser_rounds and lb_positions:
        max_y = max(max(pos[1] for pos in lb_positions.values()) + box_h + 50,
                   max(pos[1] for pos in wb_positions.values()) + box_h + 50)
    else:
        max_y = max(pos[1] for pos in wb_positions.values()) + box_h + 50
    
    canvas.config(width=max_x, height=max_y, scrollregion=(0, 0, max_x, max_y))
    
    item_count = len(canvas.find_all())
    bbox = canvas.bbox("all")
    print(f"Canvas rendered: {max_x}x{max_y}, {item_count} items, bbox: {bbox}")
    
    return canvas


def canvas_items_to_pdf(c, canvas, canvas_bbox, page_x_offset=0, page_y_offset=0,
                       page_width=8.5*inch, page_height=11*inch):
    """
    Extract canvas items and draw them on PDF canvas.
    
    Args:
        c: ReportLab canvas
        canvas: tkinter canvas with rendered bracket
        canvas_bbox: Tuple of (x1, y1, x2, y2) bounding box
        page_x_offset: X offset on PDF page
        page_y_offset: Y offset on PDF page
        page_width: Available width on page
        page_height: Available height on page
    
    Returns:
        Tuple (max_x_used, max_y_used) for pagination
    """
    if not canvas_bbox:
        return 0, 0
    
    x1, y1, x2, y2 = canvas_bbox
    canvas_w = x2 - x1
    canvas_h = y2 - y1
    
    # Scale factor if needed (for now 1:1)
    scale_x = 1.0
    scale_y = 1.0
    
    # First pass: collect all rectangles (boxes) with their canvas coords
    box_coords = []  # List of (y1_c, y2_c, x_c, pdf_y_top) for text positioning
    
    for item_id in canvas.find_all():
        if canvas.type(item_id) == 'rectangle':
            coords = canvas.coords(item_id)
            if len(coords) >= 4:
                x_c, y1_c, x2_c, y2_c = coords[:4]
                # Calculate PDF top position for this box
                y_pdf_bottom = page_y_offset - (y2_c - y1) * scale_y
                h = (y2_c - y1_c) * scale_y
                y_pdf_top = y_pdf_bottom + h
                box_coords.append((y1_c, y2_c, x_c, y_pdf_top, y_pdf_bottom, h))
    
    # Get all canvas items
    all_items = canvas.find_all()
    print(f"Drawing {len(all_items)} canvas items to PDF")
    
    text_count = 0
    line_count = 0
    rect_count = 0
    
    for item_id in all_items:
        item_type = canvas.type(item_id)
        
        try:
            if item_type == 'rectangle':
                rect_count += 1
                coords = canvas.coords(item_id)
                fill = canvas.itemcget(item_id, 'fill')
                outline = canvas.itemcget(item_id, 'outline')
                width = canvas.itemcget(item_id, 'width')
                
                if len(coords) >= 4:
                    x_canvas, y_canvas, x2_canvas, y2_canvas = coords[:4]
                    
                    # Convert canvas coords to PDF coords
                    # Canvas: Y increases downward (top=0)
                    # PDF: Y increases upward (bottom=0)
                    # For PDF rect: (x, y, width, height) where (x,y) is BOTTOM-LEFT
                    x_pdf = page_x_offset + (x_canvas - x1) * scale_x
                    y_pdf = page_y_offset - (y2_canvas - y1) * scale_y
                    w = (x2_canvas - x_canvas) * scale_x
                    h = (y2_canvas - y_canvas) * scale_y
                    
                    # Draw rectangle
                    fill_color = get_color(fill) if fill and fill != '' else colors.white
                    outline_color = get_color(outline) if outline and outline != '' else colors.black
                    line_width = float(width) if width else 1
                    
                    c.setLineWidth(line_width)
                    c.setStrokeColor(outline_color)
                    c.setFillColor(fill_color)
                    c.rect(x_pdf, y_pdf, w, h, stroke=1, fill=1)
            
            elif item_type == 'line':
                coords = canvas.coords(item_id)
                fill = canvas.itemcget(item_id, 'fill')
                width = canvas.itemcget(item_id, 'width')
                dash = canvas.itemcget(item_id, 'dash')
                
                # Skip light grey connectors - they don't serve a purpose in brackets
                if fill == '#cccccc':  # border_light color
                    continue
                
                if len(coords) >= 4:
                    x1_c, y1_c, x2_c, y2_c = coords[:4]
                    
                    # Convert to PDF coords (flip Y axis)
                    x1_p = page_x_offset + (x1_c - x1) * scale_x
                    y1_p = page_y_offset - (y1_c - y1) * scale_y
                    x2_p = page_x_offset + (x2_c - x1) * scale_x
                    y2_p = page_y_offset - (y2_c - y1) * scale_y
                    
                    # Draw line - respect meaningful colors
                    line_color = get_color(fill) if fill and fill != '' else colors.black
                    line_width = float(width) if width else 1
                    
                    c.setLineWidth(line_width)
                    c.setStrokeColor(line_color)
                    c.line(x1_p, y1_p, x2_p, y2_p)
                    line_count += 1
            
            elif item_type == 'text':
                coords = canvas.coords(item_id)
                text = canvas.itemcget(item_id, 'text')
                fill = canvas.itemcget(item_id, 'fill')
                font = canvas.itemcget(item_id, 'font')
                anchor = canvas.itemcget(item_id, 'anchor')
                
                print(f"  Text item: '{text}', coords={coords}, fill={fill}")
                
                if len(coords) >= 2 and text:
                    x_c, y_c = coords[:2]
                    
                    # Strip whitespace from text
                    text = text.strip()
                    if not text:  # Skip if empty after stripping
                        continue
                    
                    # Find which box this text belongs to (by Y coordinate)
                    box_info = None
                    for y1_c, y2_c, box_x_c, pdf_y_top, pdf_y_bottom, box_h in box_coords:
                        if y1_c <= y_c <= y2_c:
                            box_info = (y1_c, y2_c, box_x_c, pdf_y_top, pdf_y_bottom, box_h)
                            break
                    
                    # Convert to PDF coords
                    x_p = page_x_offset + (x_c - x1) * scale_x
                    
                    if box_info:
                        # Position text relative to box top
                        y1_c, y2_c, box_x_c, pdf_y_top, pdf_y_bottom, box_h = box_info
                        # Calculate offset from box top in canvas
                        offset_from_box_top = y_c - y1_c
                        # Apply same offset from box top in PDF
                        y_p = pdf_y_top - offset_from_box_top * scale_y
                    else:
                        # Fallback: absolute positioning
                        y_p = page_y_offset - (y_c - y1) * scale_y
                    
                    # Draw text - ALWAYS use black for PDF (print output)
                    text_color = colors.black
                    c.setFillColor(text_color)
                    
                    # Parse font (e.g., "Consolas 8")
                    font_size = 8
                    font_name = 'Helvetica'
                    if font:
                        parts = font.split()
                        if len(parts) >= 2:
                            raw_font = parts[0]
                            try:
                                font_size = int(parts[1])
                            except:
                                pass
                            # Map system fonts to ReportLab available fonts
                            font_map = {
                                'Consolas': 'Courier',
                                'Arial': 'Helvetica',
                                'Times': 'Times-Roman',
                            }
                            font_name = font_map.get(raw_font, raw_font)
                    
                    try:
                        c.setFont(font_name, font_size)
                    except:
                        # Fallback to Helvetica if font not found
                        c.setFont('Helvetica', font_size)
                    
                    # Anchor handling - for centered text, don't add extra offset
                    if anchor == 'c':
                        c.drawCentredString(x_p, y_p, text)
                    else:
                        c.drawString(x_p, y_p, text)
                    text_count += 1
        
        except Exception as e:
            import traceback
            print(f"  ERROR drawing {item_type} item {item_id}: {type(e).__name__}: {e}")
            logger.debug(f"Error drawing {item_type} item: {traceback.format_exc()}")
            continue
    
    print(f"  Rectangles: {rect_count}, Lines: {line_count}, Text: {text_count}")
    
    return canvas_w, canvas_h


def draw_double_elimination_pdf(output_path: str, bracket_pairs: List[Tuple[str, str]],
                               fighters: Optional[List[Dict]] = None,
                               bracket_key: str = "Double Elimination Bracket") -> str:
    """
    Generate double elimination PDF by rendering on canvas then extracting to PDF.
    
    Args:
        output_path: Path to save PDF
        bracket_pairs: List of (name1, name2) tuples
        fighters: Optional list of fighter dicts
        bracket_key: Title for the bracket
    
    Returns:
        Path to generated PDF
    """
    try:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        # Render on canvas using viewer's algorithm
        root = tk.Tk()
        root.withdraw()
        canvas = render_double_elimination_to_canvas(root, bracket_pairs, fighters)
        
        bbox = canvas.bbox("all")
        if not bbox:
            logger.error("Canvas rendering failed")
            root.destroy()
            return None
        
        # Create PDF
        c = pdf_canvas.Canvas(output_path, pagesize=landscape(A4))
        width, height = landscape(A4)
        
        # Draw header
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.black)
        c.drawCentredString(width // 2, height - 30, bracket_key)
        
        # No divider needed for clean bracket display
        
        # Extract and draw canvas items to PDF
        available_height = height - 100
        available_width = width - 100
        
        canvas_items_to_pdf(c, canvas, bbox,
                           page_x_offset=50,
                           page_y_offset=height - 60,
                           page_width=available_width,
                           page_height=available_height)
        
        # Footer
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        c.drawString(50, 20, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        c.save()
        logger.info(f"✓ Double elimination PDF created: {output_path}")
        
        root.destroy()
        return output_path
    
    except Exception as e:
        logger.error(f"Error creating double elimination PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


class BracketPDFGeneratorV4:
    """Bracket PDF generator using canvas→PDF approach."""
    
    def __init__(self):
        self.logger = logger
    
    def draw_bracket_pdf(self, output_path: str, bracket_pairs: List[Tuple[str, str]],
                        participants_list: Optional[List[Dict]] = None,
                        bracket_type: str = 'single') -> bool:
        """
        Draw bracket PDF from canvas rendering.
        
        Args:
            output_path: Path to save PDF
            bracket_pairs: List of (name1, name2) tuples
            participants_list: Optional participant list
            bracket_type: 'single' or 'double'
        
        Returns:
            True if successful
        """
        if bracket_type == 'double':
            result = draw_double_elimination_pdf(output_path, bracket_pairs,
                                                participants_list, "Double Elimination")
            return result is not None
        else:
            logger.error("Single elimination not yet implemented in v4")
            return False
    
    def draw_double_elimination_pdf(self, output_path: str, bracket_data: Dict,
                                   bracket_key: str = "Tournament Bracket") -> str:
        """
        Generate double elimination PDF (compatible with v2 interface).
        """
        bracket = bracket_data.get('bracket', [])
        fighters = bracket_data.get('fighters', [])
        
        return draw_double_elimination_pdf(output_path, bracket, fighters,
                                          bracket_key) or output_path


if __name__ == '__main__':
    # Test
    from utils.bracket_utils import _compute_snake_bracket
    
    fighters = [
        {'Name': f'Fighter {chr(65+i)}', 'Verein': f'Club {i%3+1}'}
        for i in range(8)
    ]
    
    bracket_pairs = _compute_snake_bracket(fighters)
    
    gen = BracketPDFGeneratorV4()
    success = gen.draw_bracket_pdf('temp/v4_test.pdf', bracket_pairs, fighters, 'double')
    print(f"v4 test: {'✓' if success else '✗'}")
