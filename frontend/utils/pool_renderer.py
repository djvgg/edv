# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pool rendering utilities for round-robin group visualization on canvas."""


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
    if pool_size < 3:
        return []

    # Hardcoded optimal schedules for small pools (verified patterns)
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
    # This is a fallback - may need refinement
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

    return all_matches[:pool_size]  # Limit to pool_size columns


def split_into_pools(participants, num_pools=1):
    """Split participants into pools.

    Args:
        participants: List of participant dicts with 'Name' and 'Verein' keys
        num_pools: Number of pools (1 or 2)

    Returns:
        List of pools, each containing participant dicts
    """
    if num_pools == 1:
        return [participants]

    # For double pools, split evenly
    mid = len(participants) // 2
    return [participants[:mid], participants[mid:]]


def determine_pool_structure(num_participants):
    """Determine how many pools are needed based on participant count.

    Args:
        num_participants: Number of participants in group

    Returns:
        Number of pools (1 for 3-5 people, 2 for 6-10 people)
    """
    if 3 <= num_participants <= 5:
        return 1
    elif 6 <= num_participants <= 10:
        return 2
    else:
        # Default to single pool for other sizes
        return 1


def calculate_pool_box_size(pool_participants, zoom_level):
    """Calculate dynamic box dimensions for pool display.

    Args:
        pool_participants: List of participants in the pool
        zoom_level: Current zoom level multiplier

    Returns:
        Tuple of (boxWidth, boxHeight, cellSize, padding) in pixels
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
    boxWidth = int(base_width * zoom_level)
    boxHeight = int(40 * zoom_level)
    cellSize = int(60 * zoom_level)  # Size of match cells
    padding = int(20 * zoom_level)

    return boxWidth, boxHeight, cellSize, padding


def calculate_pool_positions(pools, boxWidth, boxHeight, cellSize, padding, start_x=50, start_y=50):
    """Calculate positions for all pools and their components.

    Args:
        pools: List of pools (each pool is a list of participants)
        boxWidth, boxHeight: Dimensions of fighter name boxes
        cellSize: Size of match result cells
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

        # Calculate grid dimensions (numWidth + nameWidth + kampfnummerWidth + match columns)
        numWidth = cellSize  # Start-nr column width
        nameWidth = boxWidth  # Name/Verein column width
        kampfnummerWidth = int(cellSize * 1.5)  # Kampfnummer column (Punkte + Ubw.)
        grid_width = numWidth + nameWidth + kampfnummerWidth + (num_fights * cellSize) + padding
        grid_height = (pool_size * boxHeight) + padding * 2

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


def draw_pool_table(canvas, pool_participants, start_x, start_y, boxWidth, boxHeight,
                    cellSize, padding, zoom_level, colors, fonts, pool_label="Pool 1",
                    fight_numbers=None):
    """Draw a single pool table on canvas.

    Args:
        canvas: tkinter Canvas widget
        pool_participants: List of participants in this pool
        start_x, start_y: Starting coordinates for the pool
        boxWidth, boxHeight: Dimensions of fighter name boxes
        cellSize: Size of match result cells
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

    pool_size = len(pool_participants)

    # Generate fight schedule and calculate number of fights
    fight_schedule = _generate_fight_schedule(pool_size)
    num_fights = len(fight_schedule)

    # Use provided fight numbers or default to sequential (1, 2, 3, ...)
    if fight_numbers is None:
        fight_numbers = list(range(1, num_fights + 1))

    # Define column widths
    numWidth = cellSize  # Width of the number column
    nameWidth = boxWidth  # Width of the name column
    kampfnummerWidth = int(cellSize * 1.5)  # Width of Kampfnummer column (Punkte + Ubw.)
    punkteWidth = kampfnummerWidth // 2  # Half for Punkte
    ubwWidth = kampfnummerWidth - punkteWidth  # Other half for Ubw.

    # Draw pool label/title
    title_y = start_y - padding
    canvas.create_text(
        start_x + (numWidth + nameWidth + kampfnummerWidth) // 2,
        title_y,
        text=pool_label,
        anchor='c',
        fill=colors['white'],
        font=header_font
    )

    # Draw "Start-nr" header cell (top-left)
    canvas.create_rectangle(
        start_x, start_y, start_x + numWidth, start_y + boxHeight,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )
    canvas.create_text(
        start_x + numWidth // 2,
        start_y + boxHeight // 2,
        text="Start\nnr",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Draw "Kämpfername/Verein" header cell (second column header)
    canvas.create_rectangle(
        start_x + numWidth, start_y, start_x + numWidth + nameWidth, start_y + boxHeight,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )
    canvas.create_text(
        start_x + numWidth + nameWidth // 2,
        start_y + boxHeight // 2,
        text="Kämpfername\nVerein",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Draw "Kampfnummer" header cell (third column header)
    kampf_x = start_x + numWidth + nameWidth
    canvas.create_rectangle(
        kampf_x, start_y, kampf_x + kampfnummerWidth, start_y + boxHeight,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )

    # Draw "Kampfnummer" header text
    canvas.create_text(
        kampf_x + kampfnummerWidth // 2,
        start_y + boxHeight // 2,
        text="Kampfnummer",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Draw column headers (fight numbers across top)
    for col in range(num_fights):
        x = start_x + numWidth + nameWidth + kampfnummerWidth + (col * cellSize)
        y = start_y

        # Draw header cell
        canvas.create_rectangle(
            x, y, x + cellSize, y + boxHeight,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )

        # Draw fight number (use provided fight_numbers list)
        canvas.create_text(
            x + cellSize // 2,
            y + boxHeight // 2,
            text=str(fight_numbers[col]),
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

    # Draw rows (each fighter)
    for row in range(pool_size):
        y = start_y + ((row + 1) * boxHeight)

        fighter = pool_participants[row]
        name = fighter.get('Name', 'Unknown')
        club = fighter.get('Verein', '')
        fighter_num = row + 1

        # Draw number cell (first column)
        canvas.create_rectangle(
            start_x, y, start_x + numWidth, y + boxHeight,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )
        canvas.create_text(
            start_x + numWidth // 2,
            y + boxHeight // 2,
            text=str(fighter_num),
            anchor='c',
            fill=colors['white'],
            font=scaled_font
        )

        # Draw name cell (second column)
        display_text = f"{name} [{club}]" if club else name
        canvas.create_rectangle(
            start_x + numWidth, y, start_x + numWidth + nameWidth, y + boxHeight,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )
        canvas.create_text(
            start_x + numWidth + padding // 2,
            y + boxHeight // 2,
            text=display_text,
            anchor='w',
            fill=colors['white'],
            font=scaled_font
        )

        # Draw Kampfnummer cell (third column) with Punkte and Ubw. sub-columns
        kampf_x = start_x + numWidth + nameWidth
        canvas.create_rectangle(
            kampf_x, y, kampf_x + kampfnummerWidth, y + boxHeight,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )

        # Draw "Punkte" text in left sub-column
        canvas.create_text(
            kampf_x + punkteWidth // 2,
            y + boxHeight // 2,
            text="Punkte",
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

        # Draw "Ubw." text in right sub-column
        canvas.create_text(
            kampf_x + punkteWidth + ubwWidth // 2,
            y + boxHeight // 2,
            text="Ubw.",
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

        # Draw vertical separator line between Punkte and Ubw. for this row
        canvas.create_line(
            kampf_x + punkteWidth, y,
            kampf_x + punkteWidth, y + boxHeight,
            fill=colors['accent_green'],
            width=line_width
        )

        # Draw fight cells for this fighter
        # Columns represent FIGHT numbers (blue numbers), not fighter numbers
        for fight_num in range(num_fights):
            x = start_x + numWidth + nameWidth + kampfnummerWidth + (fight_num * cellSize)

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
                    x, y, x + cellSize, y + boxHeight,
                    outline=colors['accent_green'],
                    fill=colors['white'],
                    width=line_width
                )

                # Draw vertical divider in the middle of the cell
                canvas.create_line(
                    x + cellSize // 2, y,
                    x + cellSize // 2, y + boxHeight,
                    fill=colors['black'],
                    width=line_width
                )
            else:
                # Draw empty/blank cell (fighter doesn't participate in this fight)
                canvas.create_rectangle(
                    x, y, x + cellSize, y + boxHeight,
                    outline=colors['accent_green'],
                    fill=colors['bg_panel'],
                    width=line_width
                )

    # Draw legend at bottom
    legend_y = start_y + ((pool_size + 1) * boxHeight) + padding
    legend_text = f"{pool_size} fighters • Round-robin format"
    canvas.create_text(
        start_x,
        legend_y,
        text=legend_text,
        anchor='w',
        fill=colors['text_secondary'],
        font=cell_font
    )


def draw_pools_on_canvas(canvas, participants, zoom_level, colors, fonts, start_x=50, start_y=80):
    """Draw pool visualization on canvas based on number of participants.

    Args:
        canvas: tkinter Canvas widget
        participants: List of participant dicts with 'Name' and 'Verein' keys
        zoom_level: Current zoom level multiplier
        colors: Dict of color constants
        fonts: Dict of font constants
        start_x, start_y: Starting coordinates

    Returns:
        Tuple of (total_width, total_height) for canvas sizing
    """
    num_participants = len(participants)
    num_pools = determine_pool_structure(num_participants)

    # Split into pools
    pools = split_into_pools(participants, num_pools)

    # Calculate box sizes
    boxWidth, boxHeight, cellSize, padding = calculate_pool_box_size(participants, zoom_level)

    # Draw title
    header_font = ('Arial', max(10, int(14 * zoom_level)), 'bold')
    title = f"Pool System - {num_participants} Participants"
    if num_pools == 2:
        title += " (Double Pool)"

    canvas.create_text(
        start_x,
        start_y - 40,
        text=title,
        anchor='w',
        fill=colors['white'],
        font=header_font
    )

    # Generate fight numbers for double pools (alternating 2-by-2)
    all_fight_numbers = {}
    if num_pools == 2:
        # Calculate number of fights for each pool
        pool_fight_counts = []
        for pool in pools:
            pool_size = len(pool)
            fight_schedule = _generate_fight_schedule(pool_size)
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

        # Store in dictionary
        all_fight_numbers[0] = pool_assigned[0]
        all_fight_numbers[1] = pool_assigned[1]

    # Draw each pool
    current_y = start_y
    max_width = 0

    for pool_idx, pool in enumerate(pools):
        pool_label = f"Pool {chr(65 + pool_idx)}" if num_pools > 1 else "Pool"

        # Get fight numbers for this pool
        fight_numbers = all_fight_numbers.get(pool_idx, None)

        draw_pool_table(
            canvas, pool, start_x, current_y,
            boxWidth, boxHeight, cellSize, padding,
            zoom_level, colors, fonts, pool_label,
            fight_numbers
        )

        # Calculate dimensions (numWidth + nameWidth + kampfnummerWidth + match columns)
        pool_size = len(pool)
        fight_schedule = _generate_fight_schedule(pool_size)
        num_fights = len(fight_schedule)
        numWidth = cellSize  # Start-nr column
        nameWidth = boxWidth  # Name/Verein column
        kampfnummerWidth = int(cellSize * 1.5)  # Kampfnummer column (Punkte + Ubw.)
        grid_width = numWidth + nameWidth + kampfnummerWidth + (num_fights * cellSize) + padding * 2
        grid_height = ((pool_size + 1) * boxHeight) + padding * 3

        max_width = max(max_width, grid_width)
        current_y += grid_height + padding * 2

    total_width = start_x + max_width + 50
    total_height = current_y + 50

    return total_width, total_height
