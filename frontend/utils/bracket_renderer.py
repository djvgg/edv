# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bracket rendering utilities for visualization on canvas."""

import sys
import os
import tkinter as tk

# Setup path for imports
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

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


def compute_bracket_rounds(bracket_pairs, match_results=None):
    """
    Build all bracket rounds from first-round pairs, propagating winners forward.
    Freilos (bye) auto-advances immediately.
    
    Args:
        bracket_pairs: List of (name1, name2) tuples for round 0
        match_results: Dict mapping (round, match_idx) to winner_name
    
    Returns:
        List of rounds, each containing [{p1, p2, winner}, ...]
    """
    if not bracket_pairs:
        return []
    
    if match_results is None:
        match_results = {}
    
    logger.debug(f"compute_bracket_rounds: {len(bracket_pairs)} R0 pairs, {len(match_results)} existing results")
    
    rounds = []
    
    # Round 0: build from pairs
    r0 = []
    for i, (p1, p2) in enumerate(bracket_pairs):
        winner = match_results.get((0, i))
        if winner is None:
            # Auto-bye logic
            if p1 == 'Freilos' and p2 != 'Freilos':
                winner = p2
                match_results[(0, i)] = winner
                logger.debug(f"  R0 pos{i}: BYE — '{p2}' auto-advances")
            elif p2 == 'Freilos' and p1 != 'Freilos':
                winner = p1
                match_results[(0, i)] = winner
                logger.debug(f"  R0 pos{i}: BYE — '{p1}' auto-advances")
        else:
            logger.debug(f"  R0 pos{i}: '{p1}' vs '{p2}' → winner='{winner}'")
        
        r0.append({'p1': p1, 'p2': p2, 'winner': winner})
    
    rounds.append(r0)
    
    # Later rounds: propagate winners
    while len(rounds[-1]) > 1:
        prev = rounds[-1]
        r_idx = len(rounds)
        next_r = []
        
        for i in range(0, len(prev), 2):
            m1 = prev[i]
            m2 = prev[i + 1] if i + 1 < len(prev) else None
            
            # Extract slot winner (or placeholder if not decided)
            def _slot(match):
                if match is None:
                    return 'Freilos'
                if match['winner']:
                    return match['winner']
                if match['p1'] == 'Freilos' and match['p2'] == 'Freilos':
                    return 'Freilos'
                return 'TBD'
            
            p1, p2 = _slot(m1), _slot(m2)
            m_idx = len(next_r)
            winner = match_results.get((r_idx, m_idx))
            
            # Auto-bye for later rounds
            if winner is None:
                if p1 == 'Freilos' and p2 not in ('Freilos', 'TBD'):
                    winner = p2
                    match_results[(r_idx, m_idx)] = winner
                elif p2 == 'Freilos' and p1 not in ('Freilos', 'TBD'):
                    winner = p1
                    match_results[(r_idx, m_idx)] = winner
            
            next_r.append({'p1': p1, 'p2': p2, 'winner': winner})
        
        rounds.append(next_r)
    
    logger.debug(f"Built {len(rounds)} rounds from pairs")
    return rounds


def calculate_ko_positions(rounds, zoom_level, start_x=50, start_y=50):
    """
    Calculate (round, match) -> (x, y) positions for all KO bracket rounds.
    
    Args:
        rounds: List of rounds (each round is list of matches)
        zoom_level: Current zoom level multiplier
        start_x, start_y: Top-left corner for bracket layout
    
    Returns:
        Tuple of (positions_dict, y_midpoints_dict) for position and connector calculations
    """
    positions = {}
    y_midpoints = {}
    
    BW = int(200 * zoom_level)   # box width
    BH = int(64 * zoom_level)    # box height
    XG = int(70 * zoom_level)    # x gap between rounds
    YG = int(28 * zoom_level)    # y gap between matches
    
    # Round 0: vertical stack
    for m in range(len(rounds[0])):
        x = start_x
        y = start_y + m * (BH + YG)
        positions[(0, m)] = (x, y)
        y_midpoints[(0, m)] = y + BH // 2
    
    # Later rounds: center between previous winners
    for r in range(1, len(rounds)):
        x = start_x + r * (BW + XG)
        for m in range(len(rounds[r])):
            # Center between two sources from previous round
            ya = y_midpoints.get((r - 1, m * 2), start_y + BH // 2)
            yb = y_midpoints.get((r - 1, m * 2 + 1), ya)
            y = (ya + yb) // 2 - BH // 2
            positions[(r, m)] = (x, y)
            y_midpoints[(r, m)] = y + BH // 2
    
    logger.debug(f"Calculated positions for {len(rounds)} rounds")
    return positions, y_midpoints


def draw_ko_connectors(canvas, positions, rounds, zoom_level, colors):
    """
    Draw connecting lines between KO bracket rounds.
    
    Args:
        canvas: tkinter Canvas widget
        positions: Dict from calculate_ko_positions
        rounds: List of match rounds
        zoom_level: Current zoom level
        colors: Dict of color constants
    """
    BW = int(200 * zoom_level)
    BH = int(64 * zoom_level)
    XG = int(70 * zoom_level)
    LW = max(1, int(2 * zoom_level))
    
    for r in range(len(rounds) - 1):
        for m in range(len(rounds[r])):
            if (r, m) not in positions:
                continue
            
            x, y = positions[(r, m)]
            xr = x + BW
            yc = y + BH // 2
            nm = m // 2
            
            if (r + 1, nm) not in positions:
                continue
            
            nx, ny = positions[(r + 1, nm)]
            xmid = xr + XG // 2
            ty = ny + BH // 4 if m % 2 == 0 else ny + 3 * BH // 4
            
            canvas.create_line(xr, yc, xmid, yc,
                             fill=colors['border_light'], width=LW)
            canvas.create_line(xmid, yc, xmid, ty,
                             fill=colors['border_light'], width=LW)
            canvas.create_line(xmid, ty, nx, ty,
                             fill=colors['border_light'], width=LW)


def calculate_loser_positions(loser_rounds, zoom_level, y_offset, start_x=50):
    """
    Calculate (round, match) -> (x, y) positions for all loser bracket rounds.
    
    Handles both reduction rounds (fewer matches than previous) and injection rounds 
    (same or more matches with new losers from winners bracket).
    
    Args:
        loser_rounds: List of loser bracket rounds (each round is list of matches)
        zoom_level: Current zoom level multiplier
        y_offset: Vertical offset where loser bracket starts
        start_x: Horizontal starting position
    
    Returns:
        Tuple of (positions_dict, y_midpoints_dict) for position and connector calculations
    """
    positions = {}
    y_midpoints = {}
    
    BW = int(200 * zoom_level)   # box width
    BH = int(64 * zoom_level)    # box height
    XG = int(70 * zoom_level)    # x gap between rounds
    YG = int(28 * zoom_level)    # y gap between matches
    
    # LB R0: vertical stack
    for m in range(len(loser_rounds[0])):
        x = start_x
        y = y_offset + m * (BH + YG)
        positions[(0, m)] = (x, y)
        y_midpoints[(0, m)] = y + BH // 2
    
    # Later rounds: handle reductions and injections
    for r in range(1, len(loser_rounds)):
        x = start_x + r * (BW + XG)
        prev_count = len(loser_rounds[r - 1])
        curr_count = len(loser_rounds[r])
        
        for m in range(curr_count):
            if curr_count < prev_count:
                # Reduction: centre between the two source matches
                ya = y_midpoints.get((r - 1, m * 2), y_offset + BH // 2)
                yb = y_midpoints.get((r - 1, m * 2 + 1), ya)
                y = (ya + yb) // 2 - BH // 2
            else:
                # Injection (or equal-count): same row as source match m
                ya = y_midpoints.get((r - 1, m), y_offset + BH // 2)
                y = ya - BH // 2
            
            positions[(r, m)] = (x, y)
            y_midpoints[(r, m)] = y + BH // 2
    
    logger.debug(f"Calculated loser bracket positions for {len(loser_rounds)} rounds")
    return positions, y_midpoints


def draw_loser_connectors(canvas, positions, loser_rounds, zoom_level, colors):
    """
    Draw connecting lines between loser bracket rounds (dashed orange lines).
    
    Handles both reduction rounds (many-to-one) and injection rounds (one-to-one).
    
    Args:
        canvas: tkinter Canvas widget
        positions: Dict from calculate_loser_positions
        loser_rounds: List of loser bracket match rounds
        zoom_level: Current zoom level
        colors: Dict of color constants
    """
    BW = int(200 * zoom_level)
    BH = int(64 * zoom_level)
    XG = int(70 * zoom_level)
    LW = max(1, int(2 * zoom_level))
    
    nr = len(loser_rounds)
    for r in range(nr - 1):
        prev_count = len(loser_rounds[r])
        next_count = len(loser_rounds[r + 1])
        is_reduction = next_count < prev_count
        
        for m in range(prev_count):
            if (r, m) not in positions:
                continue
            
            x, y = positions[(r, m)]
            xr = x + BW
            yc = y + BH // 2
            nm = m // 2 if is_reduction else m
            
            if (r + 1, nm) not in positions:
                continue
            
            nx, ny = positions[(r + 1, nm)]
            xmid = xr + XG // 2
            
            if is_reduction:
                ty = ny + BH // 4 if m % 2 == 0 else ny + 3 * BH // 4
            else:
                ty = ny + BH // 4  # LB winner → top half (p1) of injection match
            
            canvas.create_line(
                xr, yc, xmid, yc,
                fill=colors['accent_orange'], width=LW, dash=(4, 3))
            canvas.create_line(
                xmid, yc, xmid, ty,
                fill=colors['accent_orange'], width=LW, dash=(4, 3))
            canvas.create_line(
                xmid, ty, nx, ty,
                fill=colors['accent_orange'], width=LW, dash=(4, 3))
