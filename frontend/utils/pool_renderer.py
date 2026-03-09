# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pool rendering utilities for round-robin group visualization on canvas."""

import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger  # noqa: E402
logger = get_logger('pool_renderer')


def _generate_fight_schedule(pool_size):
    """Generate round-robin fight schedule with optimal spacing.

    Args:
        pool_size: Number of fighters in the pool

    Returns:
        List where each index is a fight/column, containing list of matches for that column
        Each match is a tuple of (fighter1_index, fighter2_index)
        Example for 3 fighters: [[( 0,2)], [(1,2)], [(0,1)]]
        Example for 4 fighters: [[(0,3)], [(1,2)], [(0,2), (1,3)], [(0,1), (2,3)]]
    """
    if pool_size < 2:
        return []

    # Hardcoded optimal schedules for small pools (verified patterns)
    if pool_size == 2:
        # Single fight between the two fighters
        return [[(0, 1)]]

    if pool_size == 3:
        # Fight 1: 1v3, Fight 2: 2v3, Fight 3: 1v2
        return [[(0, 2)], [(1, 2)], [(0, 1)]]
    elif pool_size == 4:
        # Total 6 matches (4*3/2 = 6): 1v2, 1v3, 1v4, 2v3, 2v4, 3v4
        return [
            [(0, 3)],  # Fight 1: 1v4
            [(1, 2)],  # Fight 2: 2v3
            [(0, 2)],  # Fight 3: 1v3
            [(1, 3)],  # Fight 4: 2v4
            [(0, 1)],  # Fight 5: 1v2
            [(2, 3)],  # Fight 6: 3v4
        ]
    elif pool_size == 5:
        # Total 10 matches (5*4/2 = 10): all combinations
        return [
            [(0, 4)],  # Fight 1: 1v5
            [(1, 3)],  # Fight 2: 2v4
            [(0, 2)],  # Fight 3: 1v3
            [(1, 4)],  # Fight 4: 2v5
            [(2, 3)],  # Fight 5: 3v4
            [(0, 3)],  # Fight 6: 1v4
            [(1, 2)],  # Fight 7: 2v3
            [(3, 4)],  # Fight 8: 4v5
            [(0, 1)],  # Fight 9: 1v2
            [(2, 4)],  # Fight 10: 3v5
        ]

    # For larger pools, use circle method and flatten to one match per column
    # This generates all matches for the pool
    n = pool_size if pool_size % 2 == 0 else pool_size + 1
    players = list(range(n))
    all_matches = []

    for round_num in range(n - 1):
        for i in range(n // 2):
            p1 = players[i]
            p2 = players[n - 1 - i]
            if p1 < pool_size and p2 < pool_size:
                all_matches.append([(p1, p2)])

        players = [players[0]] + [players[-1]] + players[1:-1]

    return all_matches  # Return all generated matches for complete round-robin


def split_into_pools(participants, pool_size=None, num_pools=None):
    """Split participants into pools.

    Args:
        participants: List of participant dicts with 'Name' and 'Verein' keys
        pool_size: Size of each pool (e.g., 4 means max 4 participants per pool)
                  If provided, calculates num_pools automatically
        num_pools: Number of pools (1 or 2). Used only if pool_size is None

    Returns:
        List of pools, each containing participant dicts
    """
    # If pool_size is provided, calculate num_pools from it
    if pool_size is not None and pool_size > 0:
        num_pools = (len(participants) + pool_size - 1) // pool_size  # Ceiling division
        num_pools = max(1, num_pools)  # At least 1 pool
    elif num_pools is None:
        num_pools = 1
    
    if num_pools == 1:
        return [participants]

    # For multiple pools, split evenly
    pools = []
    for i in range(num_pools):
        start_idx = (i * len(participants)) // num_pools
        end_idx = ((i + 1) * len(participants)) // num_pools
        pools.append(participants[start_idx:end_idx])
    
    return pools


def determine_pool_structure(num_participants, pool_size=None):
    """Determine how many pools are needed based on participant count and pool_size.

    Args:
        num_participants: Number of participants in group
        pool_size: Configured pool size (max participants per pool).
                  If provided, uses this to calculate number of pools.
                  If None, uses default heuristic.

    Returns:
        Number of pools needed
    """
    if pool_size is not None and pool_size > 0:
        # Calculate num_pools based on configured pool_size
        num_pools = (num_participants + pool_size - 1) // pool_size  # Ceiling division
        return max(1, num_pools)
    
    # Default heuristic if no pool_size configured
    if 3 <= num_participants <= 5:
        return 1
    elif 6 <= num_participants <= 10:
        return 2
    else:
        return 1


def calculate_pool_box_size(pool_participants, zoom_level):
    """Calculate dynamic box dimensions for pool display.

    Args:
        pool_participants: List of participants in the pool
        zoom_level: Current zoom level multiplier

    Returns:
        Tuple of (box_width, box_height, cell_size, padding) in pixels
    """
    # Find longest name + club combination
    max_text_len = 0
    for p in pool_participants:
        name = p.get('Name', '')
        club = p.get('Verein', '')
        text_len = len(name) + (len(club) + 3 if club else 0)
        max_text_len = max(max_text_len, text_len)

    # Scale dimensions - increased multiplier for wider name column
    base_width = max(150, int(max_text_len * 10))
    box_width = int(base_width * zoom_level)
    box_height = int(40 * zoom_level)
    cell_size = int(80 * zoom_level)  # Size of match cells (wide enough for "03:00")
    padding = int(20 * zoom_level)

    return box_width, box_height, cell_size, padding


def calculate_pool_positions(pools, box_width, box_height, cell_size, padding, start_x=50, start_y=50):
    """Calculate positions for all pools and their components.

    Args:
        pools: List of pools (each pool is a list of participants)
        box_width, box_height: Dimensions of fighter name boxes
        cell_size: Size of match result cells
        padding: Padding between elements
        start_x, start_y: Starting coordinates

    Returns:
        Dict with position data for each pool
    """
    positions = {}
    current_y = start_y

    for pool_idx, pool in enumerate(pools):
        pool_size = len(pool)

        # Calculate number of fights using formula n(n-1)/2
        fight_schedule = _generate_fight_schedule(pool_size)
        num_fights = len(fight_schedule)

        # Calculate grid dimensions (num_width + name_width + kampfnummer_width + match columns)
        num_width = cell_size  # Start-nr column width
        name_width = box_width  # Name/Verein column width
        kampfnummer_width = int(cell_size * 1.5)  # Kampfnummer column (Punkte + Ubw.)
        grid_width = num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (3 * cell_size) + padding
        grid_height = (pool_size * box_height) + box_height + padding * 2  # +1 row for Kampfzeit

        positions[pool_idx] = {
            'start_x': start_x,
            'start_y': current_y,
            'pool_participants': pool,
            'pool_size': pool_size,
            'grid_width': grid_width,
            'grid_height': grid_height,
        }

        # Move to next pool position (below current pool)
        current_y += grid_height + padding * 3

    return positions


def draw_pool_table(canvas, pool_participants, start_x, start_y, box_width, box_height,
                    cell_size, padding, zoom_level, colors, fonts, pool_label="Pool 1",
                    fight_numbers=None, cell_values=None):
    """Draw a single pool table on canvas.

    Args:
        canvas: tkinter Canvas widget
        pool_participants: List of participants in this pool
        start_x, start_y: Starting coordinates for the pool
        box_width, box_height: Dimensions of fighter name boxes
        cell_size: Size of match result cells
        padding: Padding between elements
        zoom_level: Current zoom level
        colors: Dict of color constants
        fonts: Dict of font constants
        pool_label: Label for this pool (e.g., "Pool 1", "Pool A")
        fight_numbers: List of fight numbers to display (for double pool alternating numbering)
    """
    line_width = max(1, int(2 * zoom_level))
    font_size = max(6, int(10 * zoom_level))
    scaled_font = ('Consolas', font_size)
    header_font = ('Arial', max(8, int(12 * zoom_level)), 'bold')
    cell_font = ('Consolas', max(6, int(8 * zoom_level)))

    # Color assignments for easy customization
    border_color = colors['accent_blue']         # Soft periwinkle borders
    header_bg_color = colors['bg_panel']         # Header background color
    field_color = colors['text_secondary']       # Very light grey for editable fields
    text_color = colors['text_secondary']        # Light gray for text labels
    divider_color = colors['accent_blue']        # Soft periwinkle divider lines
    value_color = colors['text_primary']         # Text for cell values (white)

    pool_size = len(pool_participants)

    # Generate fight schedule and calculate number of fights
    fight_schedule = _generate_fight_schedule(pool_size)
    num_fights = len(fight_schedule)

    # Use provided fight numbers or default to sequential (1, 2, 3, ...)
    if fight_numbers is None:
        fight_numbers = list(range(1, num_fights + 1))

    # Define column widths
    num_width = cell_size  # Width of the number column
    name_width = box_width  # Width of the name column
    kampfnummer_width = int(cell_size * 1.5)  # Width of Kampfnummer column (Punkte + Ubw.)
    punkte_width = kampfnummer_width // 2  # Half for Punkte
    ubw_width = kampfnummer_width - punkte_width  # Other half for Ubw.

    # Draw pool label/title
    title_y = start_y - padding
    canvas.create_text(
        start_x + (num_width + name_width + kampfnummer_width) // 2,
        title_y,
        text=pool_label,
        anchor='c',
        fill=text_color,
        font=header_font
    )

    # Draw "Start-nr" header cell (top-left)
    canvas.create_rectangle(
        start_x, start_y, start_x + num_width, start_y + box_height,
        outline=border_color,
        fill=header_bg_color,
        width=line_width
    )
    canvas.create_text(
        start_x + num_width // 2,
        start_y + box_height // 2,
        text="Start\nnr",
        anchor='c',
        fill=text_color,
        font=cell_font
    )

    # Draw "Kämpfername/Verein" header cell (second column header)
    canvas.create_rectangle(
        start_x + num_width, start_y, start_x + num_width + name_width, start_y + box_height,
        outline=border_color,
        fill=header_bg_color,
        width=line_width
    )
    canvas.create_text(
        start_x + num_width + name_width // 2,
        start_y + box_height // 2,
        text="Kämpfername\nVerein",
        anchor='c',
        fill=text_color,
        font=cell_font
    )

    # Draw "Kampfnummer" header cell (third column header)
    kampf_x = start_x + num_width + name_width
    canvas.create_rectangle(
        kampf_x, start_y, kampf_x + kampfnummer_width, start_y + box_height,
        outline=border_color,
        fill=header_bg_color,
        width=line_width
    )

    # Draw "Kampfnummer" header text
    canvas.create_text(
        kampf_x + kampfnummer_width // 2,
        start_y + box_height // 2,
        text="Kampfnummer",
        anchor='c',
        fill=text_color,
        font=cell_font
    )

    # Draw column headers (fight numbers across top)
    for col in range(num_fights):
        x = start_x + num_width + name_width + kampfnummer_width + (col * cell_size)
        y = start_y

        # Draw header cell
        canvas.create_rectangle(
            x, y, x + cell_size, y + box_height,
            outline=border_color,
            fill=header_bg_color,
            width=line_width
        )

        # Draw fight number (use provided fight_numbers list)
        canvas.create_text(
            x + cell_size // 2,
            y + box_height // 2,
            text=str(fight_numbers[col]),
            anchor='c',
            fill=text_color,
            font=cell_font
        )

    # Draw summary column headers (Punkte, Ubw., Platz) after fight columns
    summary_labels = ["Punkte", "Ubw.", "Platz"]
    for i, label in enumerate(summary_labels):
        x = start_x + num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (i * cell_size)
        canvas.create_rectangle(
            x, start_y, x + cell_size, start_y + box_height,
            outline=border_color,
            fill=header_bg_color,
            width=line_width
        )
        canvas.create_text(
            x + cell_size // 2,
            start_y + box_height // 2,
            text=label,
            anchor='c',
            fill=text_color,
            font=cell_font
        )

    # Draw rows (each fighter)
    cell_positions = {}  # {(row, fight_num): (x1, y1, x2, y2)}
    for row in range(pool_size):
        y = start_y + ((row + 1) * box_height)

        fighter = pool_participants[row]
        name = fighter.get('Name', 'Unknown')
        club = fighter.get('Verein', '')
        fighter_num = row + 1

        # Draw number cell (first column)
        canvas.create_rectangle(
            start_x, y, start_x + num_width, y + box_height,
            outline=border_color,
            fill=header_bg_color,
            width=line_width
        )
        canvas.create_text(
            start_x + num_width // 2,
            y + box_height // 2,
            text=str(fighter_num),
            anchor='c',
            fill=text_color,
            font=scaled_font
        )

        # Draw name cell (second column)
        display_text = f"{name} [{club}]" if club else name
        canvas.create_rectangle(
            start_x + num_width, y, start_x + num_width + name_width, y + box_height,
            outline=border_color,
            fill=header_bg_color,
            width=line_width
        )
        canvas.create_text(
            start_x + num_width + padding // 2,
            y + box_height // 2,
            text=display_text,
            anchor='w',
            fill=text_color,
            font=scaled_font
        )

        # Draw Kampfnummer cell (third column) with Punkte and Ubw. sub-columns
        kampf_x = start_x + num_width + name_width
        canvas.create_rectangle(
            kampf_x, y, kampf_x + kampfnummer_width, y + box_height,
            outline=border_color,
            fill=header_bg_color,
            width=line_width
        )

        # Draw "Punkte" text in left sub-column
        canvas.create_text(
            kampf_x + punkte_width // 2,
            y + box_height // 2,
            text="Punkte",
            anchor='c',
            fill=text_color,
            font=cell_font
        )

        # Draw "Ubw." text in right sub-column
        canvas.create_text(
            kampf_x + punkte_width + ubw_width // 2,
            y + box_height // 2,
            text="Ubw.",
            anchor='c',
            fill=text_color,
            font=cell_font
        )

        # Draw vertical separator line between Punkte and Ubw. for this row
        canvas.create_line(
            kampf_x + punkte_width, y,
            kampf_x + punkte_width, y + box_height,
            fill=divider_color,
            width=line_width
        )

        # Draw fight cells for this fighter
        # Columns represent FIGHT numbers (blue numbers), not fighter numbers
        for fight_num in range(num_fights):
            x = start_x + num_width + name_width + kampfnummer_width + (fight_num * cell_size)

            # Determine if this fighter participates in this fight
            should_have_divider = False

            # Check if this fighter (row) participates in this fight (fight_num/column)
            if fight_num < len(fight_schedule):
                for match in fight_schedule[fight_num]:
                    if row in match:
                        should_have_divider = True
                        break

            if should_have_divider:
                # Draw bright cell with vertical divider (fighter participates in this fight)
                canvas.create_rectangle(
                    x, y, x + cell_size, y + box_height,
                    outline=border_color,
                    fill=field_color,
                    width=line_width
                )

                # Draw vertical divider in the middle of the cell
                canvas.create_line(
                    x + cell_size // 2, y,
                    x + cell_size // 2, y + box_height,
                    fill=divider_color,
                    width=line_width
                )
                # Each white cell is two independent sub-cells (left | right)
                mid_x = x + cell_size // 2
                val_l = (cell_values or {}).get((row, fight_num, 'L'), '')
                val_r = (cell_values or {}).get((row, fight_num, 'R'), '')
                if val_l:
                    canvas.create_text(
                        x + cell_size // 4, y + box_height // 2,
                        text=val_l, anchor='c',
                        fill=value_color, font=scaled_font
                    )
                if val_r:
                    canvas.create_text(
                        mid_x + cell_size // 4, y + box_height // 2,
                        text=val_r, anchor='c',
                        fill=value_color, font=scaled_font
                    )
                cell_positions[(row, fight_num, 'L')] = (x,     y, mid_x,          y + box_height)
                cell_positions[(row, fight_num, 'R')] = (mid_x, y, x + cell_size,  y + box_height)
            else:
                # Draw empty/blank cell (fighter doesn't participate in this fight)
                canvas.create_rectangle(
                    x, y, x + cell_size, y + box_height,
                    outline=border_color,
                    fill=header_bg_color,
                    width=line_width
                )

        # Draw summary cells (Punkte, Ubw., Platz) — editable (slate grey fill)
        summary_keys = ['punkte', 'ubw', 'platz']
        for i, skey in enumerate(summary_keys):
            x = start_x + num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (i * cell_size)
            canvas.create_rectangle(
                x, y, x + cell_size, y + box_height,
                outline=border_color,
                fill=field_color,
                width=line_width
            )
            sval = (cell_values or {}).get((row, skey), '')
            if sval:
                canvas.create_text(
                    x + cell_size // 2, y + box_height // 2,
                    text=sval, anchor='c',
                    fill=value_color, font=scaled_font
                )
            cell_positions[(row, skey)] = (x, y, x + cell_size, y + box_height)

    # Draw Kampfzeit bottom row
    bottom_y = start_y + ((pool_size + 1) * box_height)

    # Kampfzeit cell spanning Punkte + Ubw. columns
    kampf_x = start_x + num_width + name_width
    canvas.create_rectangle(
        kampf_x, bottom_y,
        kampf_x + kampfnummer_width, bottom_y + box_height,
        outline=border_color,
        fill=header_bg_color,
        width=line_width
    )
    canvas.create_text(
        kampf_x + kampfnummer_width // 2,
        bottom_y + box_height // 2,
        text="Kampfzeit",
        anchor='c',
        fill=text_color,
        font=cell_font
    )

    # Kampfzeit cells under each fight column — editable (slate grey fill)
    for fight_num in range(num_fights):
        x = start_x + num_width + name_width + kampfnummer_width + (fight_num * cell_size)
        canvas.create_rectangle(
            x, bottom_y, x + cell_size, bottom_y + box_height,
            outline=border_color,
            fill=field_color,
            width=line_width
        )
        kval = (cell_values or {}).get(('kampfzeit', fight_num), '')
        if kval:
            canvas.create_text(
                x + cell_size // 2, bottom_y + box_height // 2,
                text=kval, anchor='c',
                fill=value_color, font=scaled_font
            )
        cell_positions[('kampfzeit', fight_num)] = (x, bottom_y, x + cell_size, bottom_y + box_height)

    # Draw legend at bottom
    legend_y = start_y + ((pool_size + 2) * box_height) + padding
    legend_text = f"{pool_size} fighters • Round-robin format"
    canvas.create_text(
        start_x,
        legend_y,
        text=legend_text,
        anchor='w',
        fill=text_color,
        font=cell_font
    )

    return cell_positions


def _draw_ko_match_box(canvas, x, y, bw, bh, p1, p2, lw, font, colors, winner=None):
    """Draw a single KO match box with winner/loser colouring."""
    divider_color = colors['accent_blue']        # Soft periwinkle divider lines
    
    my = y + bh // 2
    def real(n):
        return n and n not in ('', 'TBD')
    p1w = winner is not None and winner == p1 and real(p1)
    p2w = winner is not None and winner == p2 and real(p2)

    canvas.create_rectangle(x, y, x + bw, y + bh,
                             fill=colors['bg_panel'],
                             outline=colors['border_light'], width=lw)

    # Winner/loser half backgrounds
    if p1w:
        canvas.create_rectangle(x+lw, y+lw, x+bw-lw, my, fill='#1a3d1a', outline='')
    elif winner is not None and real(p1):
        canvas.create_rectangle(x+lw, y+lw, x+bw-lw, my, fill='#3d1a1a', outline='')
    if p2w:
        canvas.create_rectangle(x+lw, my, x+bw-lw, y+bh-lw, fill='#1a3d1a', outline='')
    elif winner is not None and real(p2):
        canvas.create_rectangle(x+lw, my, x+bw-lw, y+bh-lw, fill='#3d1a1a', outline='')

    canvas.create_line(x, my, x + bw, my,
                       fill=divider_color, width=1, dash=(4, 3))

    pad = max(6, lw * 4)

    def _col(name, won):
        if not real(name):
            return colors['text_muted']
        if won:
            return colors['accent_green']
        if winner is not None:
            return colors['accent_red']
        return colors['text_secondary']

    canvas.create_text(x + pad, y + bh // 4, text=p1, anchor='w',
                       fill=_col(p1, p1w), font=font)
    canvas.create_text(x + pad, y + 3 * bh // 4, text=p2, anchor='w',
                       fill=_col(p2, p2w), font=font)

    # Checkmarks
    if p1w:
        canvas.create_text(x + bw - 8, y + bh // 4, text='✓', anchor='c',
                           fill=colors['accent_green'], font=font)
    if p2w:
        canvas.create_text(x + bw - 8, y + 3 * bh // 4, text='✓', anchor='c',
                           fill=colors['accent_green'], font=font)

    # Pick hint for undecided real matches
    if winner is None and real(p1) and real(p2):
        small = (font[0], max(6, font[1] - 1))
        canvas.create_text(x + bw - 6, my, text='← pick', anchor='e',
                           fill=colors['text_muted'], font=small)


def draw_double_pool_ko_bracket(canvas, start_x, start_y, zoom_level, colors, fonts, ko_data=None, ko_match_results=None):
    """Draw the 4-player KO bracket for a double pool:
      Semi 1: 1st Pool A  vs  2nd Pool B
      Semi 2: 1st Pool B  vs  2nd Pool A
      Final:  winner Semi 1 vs winner Semi 2

    Returns (width, height) of the drawn area.
    """
    text_color = colors['text_secondary']        # Light gray for text labels
    divider_color = colors['accent_blue']        # Soft periwinkle divider lines
    
    bw = int(160 * zoom_level)   # match box width
    bh = int(56 * zoom_level)    # match box height
    gx = int(60 * zoom_level)    # horizontal gap (semis → final)
    gy = int(50 * zoom_level)    # vertical gap between the two semi boxes
    lw = max(1, int(2 * zoom_level))

    body_font  = ('Consolas', max(6, int(9 * zoom_level)))
    label_font = ('Arial',    max(7, int(10 * zoom_level)), 'bold')
    small_font = ('Arial',    max(6, int(8 * zoom_level)))

    # ── Semi positions ───────────────────────────────────────────────────
    s1x, s1y = start_x, start_y
    s2x, s2y = start_x, start_y + bh + gy

    # ── Final position: vertically centred between the two semi boxes ────
    mid_y = (s1y + bh // 2 + s2y + bh // 2) // 2
    fy = mid_y - bh // 2
    fx = start_x + bw + gx

    # ── Title (above semi-final label with clear gap) ────────────────────
    canvas.create_text(start_x + bw // 2,
                       s1y - int(42 * zoom_level),
                       text='KO Round', anchor='c',
                       fill=text_color, font=label_font)

    # ── Round labels ─────────────────────────────────────────────────────
    canvas.create_text(start_x + bw // 2, s1y - int(18 * zoom_level),
                       text='Semi-final', anchor='c',
                       fill=text_color, font=small_font)
    canvas.create_text(fx + bw // 2, fy - int(18 * zoom_level),
                       text='Final', anchor='c',
                       fill=text_color, font=small_font)

    # ── Derive players and winners ───────────────────────────────────────
    ko      = ko_data or {}
    results = ko_match_results or {}

    s1p1 = ko.get('p0_1st', '')
    s1p2 = ko.get('p1_2nd', '')
    s2p1 = ko.get('p1_1st', '')
    s2p2 = ko.get('p0_2nd', '')

    s1_winner = results.get((0, 0))
    s2_winner = results.get((0, 1))

    # Final slots filled by semi winners (TBD while undecided but slots have names)
    fp1 = s1_winner or ('TBD' if (s1p1 or s1p2) else '')
    fp2 = s2_winner or ('TBD' if (s2p1 or s2p2) else '')
    f_winner = results.get((1, 0))

    # ── Match boxes ──────────────────────────────────────────────────────
    _draw_ko_match_box(canvas, s1x, s1y, bw, bh,
                       s1p1, s1p2, lw, body_font, colors, winner=s1_winner)
    _draw_ko_match_box(canvas, s2x, s2y, bw, bh,
                       s2p1, s2p2, lw, body_font, colors, winner=s2_winner)
    _draw_ko_match_box(canvas, fx, fy, bw, bh,
                       fp1, fp2, lw, body_font, colors, winner=f_winner)

    # ── Box positions for click detection ────────────────────────────────
    ko_match_boxes = {
        (0, 0): (s1x, s1y, s1x + bw, s1y + bh, s1p1, s1p2),
        (0, 1): (s2x, s2y, s2x + bw, s2y + bh, s2p1, s2p2),
        (1, 0): (fx,  fy,  fx  + bw, fy  + bh, fp1,  fp2),
    }

    # ── Connectors ───────────────────────────────────────────────────────
    xmid = start_x + bw + gx // 2   # vertical spine x

    # Semi 1 → final (connects to top quarter of final box)
    s1_cy = s1y + bh // 2
    t1y   = fy + bh // 4
    canvas.create_line(s1x + bw, s1_cy, xmid, s1_cy,
                       fill=divider_color, width=lw)
    canvas.create_line(xmid, s1_cy, xmid, t1y,
                       fill=divider_color, width=lw)
    canvas.create_line(xmid, t1y, fx, t1y,
                       fill=divider_color, width=lw)

    # Semi 2 → final (connects to bottom quarter of final box)
    s2_cy = s2y + bh // 2
    t2y   = fy + 3 * bh // 4
    canvas.create_line(s2x + bw, s2_cy, xmid, s2_cy,
                       fill=divider_color, width=lw)
    canvas.create_line(xmid, s2_cy, xmid, t2y,
                       fill=divider_color, width=lw)
    canvas.create_line(xmid, t2y, fx, t2y,
                       fill=divider_color, width=lw)

    total_w = fx + bw - start_x + int(20 * zoom_level)
    total_h = s2y + bh  - start_y + int(20 * zoom_level)
    return total_w, total_h, ko_match_boxes


def _generate_fight_numbers_for_double_pool(pools):
    """Generate alternating fight numbers for a double pool (2-by-2 interleaving).

    Args:
        pools: List of two pools (each pool is a list of participants)

    Returns:
        Dict {pool_idx: [fight_number, ...]} with alternating numbers assigned 2-at-a-time.
    """
    # Calculate number of fights for each pool
    pool_fight_counts = []
    for pool in pools:
        fight_schedule = _generate_fight_schedule(len(pool))
        pool_fight_counts.append(len(fight_schedule))

    # Generate sequential fight numbers alternating between pools
    current_fight_num = 1
    pool_assigned = [[], []]  # Track assigned numbers for each pool

    while len(pool_assigned[0]) < pool_fight_counts[0] or len(pool_assigned[1]) < pool_fight_counts[1]:
        # Assign 2 fights to Pool A (if it needs them)
        for _ in range(2):
            if len(pool_assigned[0]) < pool_fight_counts[0]:
                pool_assigned[0].append(current_fight_num)
                current_fight_num += 1
            else:
                break

        # Assign 2 fights to Pool B (if it needs them)
        for _ in range(2):
            if len(pool_assigned[1]) < pool_fight_counts[1]:
                pool_assigned[1].append(current_fight_num)
                current_fight_num += 1
            else:
                break

    return {0: pool_assigned[0], 1: pool_assigned[1]}


def draw_pools_on_canvas(canvas, participants, zoom_level, colors, fonts, start_x=50, start_y=80, cell_values=None, ko_data=None, ko_match_results=None, pool_size=None, generation_method=None):
    """Draw pool visualization on canvas based on number of participants.

    Args:
        canvas: tkinter Canvas widget
        participants: List of participant dicts with 'Name' and 'Verein' keys
        zoom_level: Current zoom level multiplier
        colors: Dict of color constants
        fonts: Dict of font constants
        start_x, start_y: Starting coordinates
        cell_values: Optional cell selection values
        ko_data: Optional knockout bracket data
        ko_match_results: Optional knockout match results
        pool_size: Configured pool size (max participants per pool).
                  If provided, uses this to calculate number of pools.
                  If None, uses default heuristic.
        generation_method: 'pools', 'double', or None.
                          If 'double', forces 2 pools regardless of participant count.

    Returns:
        Tuple of (total_width, total_height) for canvas sizing
    """
    text_color = colors['text_secondary']        # Light gray for text labels

    num_participants = len(participants)

    # If generation_method is 'double', always use 2 pools (respects explicit user choice)
    if generation_method == 'double':
        num_pools = 2
        logger.info(f"Pool rendering: {num_participants} participants with generation_method='double' → 2 pools (forced)")
    else:
        num_pools = determine_pool_structure(num_participants, pool_size)

    if pool_size:
        logger.info(f"Pool rendering: {num_participants} participants with pool_size={pool_size} → {num_pools} pools")
    else:
        logger.debug(f"Pool rendering: {num_participants} participants (no config pool_size) → {num_pools} pools")

    # Split into pools
    pools = split_into_pools(participants, pool_size=pool_size, num_pools=num_pools)

    # Calculate box sizes
    box_width, box_height, cell_size, padding = calculate_pool_box_size(participants, zoom_level)

    # Draw title
    header_font = ('Arial', max(10, int(14 * zoom_level)), 'bold')
    title = f"Pool System - {num_participants} Participants"
    if num_pools == 2:
        title += " (Double Pool)"

    canvas.create_text(
        start_x,
        start_y,
        text=title,
        anchor='w',
        fill=text_color,
        font=header_font
    )

    # Generate fight numbers for double pools (alternating 2-by-2)
    all_fight_numbers = _generate_fight_numbers_for_double_pool(pools) if num_pools == 2 else {}

    # Draw each pool — start below the title
    current_y = start_y + int(45 * zoom_level)
    max_width = 0
    all_cell_positions = {}  # {(pool_idx, row, fight_num): (x1, y1, x2, y2)}

    for pool_idx, pool in enumerate(pools):
        pool_label = f"Pool {chr(65 + pool_idx)}" if num_pools > 1 else "Pool"

        # Get fight numbers for this pool
        fight_numbers = all_fight_numbers.get(pool_idx, None)

        # Extract cell values for this pool (strip the leading pool_idx from each key)
        pool_cv = {k[1:]: v for k, v in (cell_values or {}).items() if k[0] == pool_idx}

        cell_pos = draw_pool_table(
            canvas, pool, start_x, current_y,
            box_width, box_height, cell_size, padding,
            zoom_level, colors, fonts, pool_label,
            fight_numbers, cell_values=pool_cv
        )
        for sub_key, bbox in cell_pos.items():
            all_cell_positions[(pool_idx,) + sub_key] = bbox

        # Calculate dimensions (num_width + name_width + kampfnummer_width + match columns)
        this_pool_size = len(pool)
        fight_schedule = _generate_fight_schedule(this_pool_size)
        num_fights = len(fight_schedule)
        num_width = cell_size  # Start-nr column
        name_width = box_width  # Name/Verein column
        kampfnummer_width = int(cell_size * 1.5)  # Kampfnummer column (Punkte + Ubw.)
        grid_width = num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (3 * cell_size) + padding * 2
        grid_height = ((this_pool_size + 2) * box_height) + padding * 3  # +1 for header, +1 for Kampfzeit row

        max_width = max(max_width, grid_width)
        current_y += grid_height + padding * 2

    total_width = start_x + max_width + 50
    total_height = current_y + 50

    # For double pool: draw KO bracket to the right of both pool tables
    ko_match_boxes = {}
    if num_pools == 2:
        ko_x = start_x + max_width + int(padding * 3)
        ko_y = start_y + int(40 * zoom_level)
        ko_w, ko_h, ko_match_boxes = draw_double_pool_ko_bracket(
            canvas, ko_x, ko_y, zoom_level, colors, fonts,
            ko_data=ko_data, ko_match_results=ko_match_results)
        total_width  = max(total_width,  ko_x + ko_w + 50)
        total_height = max(total_height, ko_y + ko_h + 50)

    return total_width, total_height, all_cell_positions, ko_match_boxes
