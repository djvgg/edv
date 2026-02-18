# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bracket rendering utilities for visualization on canvas."""

import tkinter as tk


def build_bracket_rounds(bracket, normalized_participants):
    """Build rounds from bracket tuples with name and club info.
    
    Args:
        bracket: List of (name1, name2) tuples from _compute_snake_bracket()
        normalized_participants: List of dicts with 'Name' and 'Verein' keys
    
    Returns:
        List of rounds, each containing match tuples: (name1, name2, club1, club2)
    """
    # Create mapping from fighter name to club
    fighter_clubs = {p['Name']: p.get('Verein', '') for p in normalized_participants}
    
    # Build first round with club info
    rounds = []
    current = [(p1, p2, fighter_clubs.get(p1, ''), fighter_clubs.get(p2, '')) 
              for p1, p2 in bracket]
    rounds.append(current)
    
    # Build subsequent rounds (winners don't have clubs)
    while len(current) > 1:
        nextRound = []
        for i in range(0, len(current), 2):
            p1 = f"Winner {i+1}"
            p2 = f"Winner {i+2}" if i+1 < len(current) else 'BYE'
            nextRound.append((p1, p2, '', ''))
        current = nextRound
        rounds.append(current)
    
    return rounds


def calculate_box_size(rounds, zoom_level):
    """Calculate dynamic box dimensions based on content.
    
    Args:
        rounds: List of match rounds
        zoom_level: Current zoom level multiplier
    
    Returns:
        Tuple of (boxWidth, boxHeight, xGap, yGap) in pixels
    """
    # Find longest text in all rounds
    max_text_len = 0
    for r, matches in enumerate(rounds):
        for match_data in matches:
            if len(match_data) == 4:
                p1, p2, club1, club2 = match_data
            else:
                p1, p2 = match_data
                club1, club2 = '', ''
            
            # Calculate display text length (name + club)
            text1_len = len(p1) + (len(club1) + 3 if club1 and club1 != 'BYE' else 0)
            text2_len = len(p2) + (len(club2) + 3 if club2 and club2 != 'BYE' else 0)
            max_text_len = max(max_text_len, text1_len, text2_len)
    
    # Scale box width based on longest text (roughly 8 pixels per character)
    base_width = max(120, int(max_text_len * 8))
    boxWidth = int(base_width * zoom_level)
    boxHeight = int(50 * zoom_level)
    xGap = int(80 * zoom_level)
    yGap = int(40 * zoom_level)
    
    return boxWidth, boxHeight, xGap, yGap


def draw_bracket_on_canvas(canvas, rounds, positions, boxWidth, boxHeight, 
                          zoom_level, colors, fonts):
    """Draw bracket visualization on canvas.
    
    Args:
        canvas: tkinter Canvas widget
        rounds: List of match rounds with (name1, name2, club1, club2) tuples
        positions: Dict mapping (round, match) to (x, y) coordinates
        boxWidth, boxHeight: Dimensions of match boxes
        zoom_level: Current zoom level
        colors: Dict of color constants
        fonts: Dict of font constants
    """
    line_width = max(1, int(2 * zoom_level))
    font_size = max(6, int(10 * zoom_level))
    scaled_font = ('Consolas', font_size)
    vs_font = ('Arial', max(6, int(10 * zoom_level)), 'bold')
    
    for r, matches in enumerate(rounds):
        for m, match_data in enumerate(matches):
            # Handle both old (2-tuple) and new (4-tuple) formats
            if len(match_data) == 4:
                p1, p2, club1, club2 = match_data
            else:
                p1, p2 = match_data
                club1, club2 = '', ''
            
            x, y = positions[(r, m)]
            
            # Draw box (white outline)
            canvas.create_rectangle(x, y, x + boxWidth, y + boxHeight,
                                   outline=colors['white'], width=line_width)
            canvas.create_line(x, y + boxHeight // 2, x + boxWidth, y + boxHeight // 2,
                             fill=colors['text_secondary'], dash=(2, 2))
            
            # Format display with club info on single line
            p1_display = f"{p1} [{club1}]" if club1 and club1 != 'BYE' else p1
            p2_display = f"{p2} [{club2}]" if club2 and club2 != 'BYE' else p2
            
            # Draw fighter names
            canvas.create_text(x + boxWidth // 2, y + boxHeight // 4,
                             text=p1_display, anchor='c',
                             fill=colors['white'], font=scaled_font)
            canvas.create_text(x + boxWidth // 2, y + 3 * boxHeight // 4,
                             text=p2_display, anchor='c',
                             fill=colors['white'], font=scaled_font)
            
            # Draw "vs" separator
            canvas.create_text(x + boxWidth // 2, y + boxHeight // 2,
                             text='vs', anchor='c',
                             font=vs_font,
                             fill=colors['accent_red'])
            
            # Draw connector to next round
            if r < len(rounds) - 1:
                next_match_idx = m // 2
                nx, ny = positions[(r + 1, next_match_idx)]
                canvas.create_line(
                    x + boxWidth, y + boxHeight // 2,
                    nx, ny + boxHeight // 2,
                    arrow=tk.LAST, width=line_width,
                    fill=colors['white']
                )
