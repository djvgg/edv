# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bracket rendering utilities for visualization on canvas."""

import sys
import os
import tkinter as tk

# Setup path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger

logger = get_logger('bracket_renderer')


def build_bracket_rounds(bracket, normalized_participants):
    """Build rounds from bracket tuples with name and club info.
    
    Args:
        bracket: List of (name1, name2) tuples from _compute_snake_bracket()
        normalized_participants: List of dicts with 'Name' and 'Verein' keys
    
    Returns:
        List of rounds, each containing match tuples: (name1, name2, club1, club2)
    """
    logger.debug(f"build_bracket_rounds: {len(bracket)} bracket pairs, {len(normalized_participants)} participants")
    
    # Create mapping from fighter name to club
    fighter_clubs = {p['Name']: p.get('Verein', '') for p in normalized_participants}
    logger.debug(f"Fighter clubs mapping: {fighter_clubs}")
    
    # Build first round with club info
    rounds = []
    current = [(p1, p2, fighter_clubs.get(p1, ''), fighter_clubs.get(p2, '')) 
              for p1, p2 in bracket]
    
    logger.debug(f"First round matches with clubs: {current}")
    rounds.append(current)
    
    # Build subsequent rounds (winners don't have clubs)
    while len(current) > 1:
        next_round = []
        for i in range(0, len(current), 2):
            p1 = f"Winner {i+1}"
            p2 = f"Winner {i+2}" if i+1 < len(current) else 'Freilos'
            next_round.append((p1, p2, '', ''))
        current = next_round
        rounds.append(current)
    
    logger.debug(f"Built {len(rounds)} rounds with club info")
    return rounds

def calculate_box_size(rounds, zoom_level):
    """Calculate dynamic box dimensions based on content.
    
    Args:
        rounds: List of match rounds
        zoom_level: Current zoom level multiplier
    
    Returns:
        Tuple of (box_width, box_height, x_gap, y_gap) in pixels
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
            text1_len = len(p1) + (len(club1) + 3 if club1 and club1 != 'Freilos' else 0)
            text2_len = len(p2) + (len(club2) + 3 if club2 and club2 != 'Freilos' else 0)
            max_text_len = max(max_text_len, text1_len, text2_len)
    
    # Scale box width based on longest text (roughly 8 pixels per character)
    base_width = max(120, int(max_text_len * 8))
    box_width = int(base_width * zoom_level)
    box_height = int(50 * zoom_level)
    x_gap = int(80 * zoom_level)
    y_gap = int(40 * zoom_level)
    
    return box_width, box_height, x_gap, y_gap


def draw_bracket_on_canvas(canvas, rounds, positions, box_width, box_height, 
                          zoom_level, colors, fonts):
    """Draw bracket visualization on canvas.
    
    Args:
        canvas: tkinter Canvas widget
        rounds: List of match rounds with (name1, name2, club1, club2) tuples
        positions: Dict mapping (round, match) to (x, y) coordinates
        box_width, box_height: Dimensions of match boxes
        zoom_level: Current zoom level
        colors: Dict of color constants
        fonts: Dict of font constants
    """
    logger.debug(f"draw_bracket_on_canvas: {len(rounds)} rounds, {len(positions)} positions")
    
    line_width = max(1, int(2 * zoom_level))
    font_size = max(6, int(10 * zoom_level))
    scaled_font = ('Consolas', font_size)
    vs_font = ('Arial', max(6, int(10 * zoom_level)), 'bold')
    
    for r, matches in enumerate(rounds):
        logger.debug(f"Drawing round {r} with {len(matches)} matches")
        for m, match_data in enumerate(matches):
            # Handle both old (2-tuple) and new (4-tuple) formats
            if len(match_data) == 4:
                p1, p2, club1, club2 = match_data
            else:
                p1, p2 = match_data
                club1, club2 = '', ''
            
            x, y = positions[(r, m)]
            
            # Format display with club info on single line
            p1_display = f"{p1} [{club1}]" if club1 and club1 != 'Freilos' else p1
            p2_display = f"{p2} [{club2}]" if club2 and club2 != 'Freilos' else p2
            
            logger.debug(f"Round {r}, Match {m}: {p1_display} vs {p2_display} @ ({x}, {y})")
            
            # Draw box (white outline)
            canvas.create_rectangle(x, y, x + box_width, y + box_height,
                                   outline=colors['white'], width=line_width)
            canvas.create_line(x, y + box_height // 2, x + box_width, y + box_height // 2,
                             fill=colors['text_secondary'], dash=(2, 2))
            
            # Draw fighter names
            canvas.create_text(x + box_width // 2, y + box_height // 4,
                             text=p1_display, anchor='c',
                             fill=colors['white'], font=scaled_font)
            canvas.create_text(x + box_width // 2, y + 3 * box_height // 4,
                             text=p2_display, anchor='c',
                             fill=colors['white'], font=scaled_font)
            
            # Draw "vs" separator
            canvas.create_text(x + box_width // 2, y + box_height // 2,
                             text='vs', anchor='c',
                             font=vs_font,
                             fill=colors['accent_red'])
            
            # Draw connector to next round
            if r < len(rounds) - 1:
                next_match_idx = m // 2
                nx, ny = positions[(r + 1, next_match_idx)]
                canvas.create_line(
                    x + box_width, y + box_height // 2,
                    nx, ny + box_height // 2,
                    arrow=tk.LAST, width=line_width,
                    fill=colors['white']
                )
