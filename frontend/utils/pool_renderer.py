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
    cell_size = int(60 * zoom_level)  # Size of match cells
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
                    fight_numbers=None):
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
        fill=colors['white'],
        font=header_font
    )

    # Draw "Start-nr" header cell (top-left)
    canvas.create_rectangle(
        start_x, start_y, start_x + num_width, start_y + box_height,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )
    canvas.create_text(
        start_x + num_width // 2,
        start_y + box_height // 2,
        text="Start\nnr",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Draw "Kämpfername/Verein" header cell (second column header)
    canvas.create_rectangle(
        start_x + num_width, start_y, start_x + num_width + name_width, start_y + box_height,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )
    canvas.create_text(
        start_x + num_width + name_width // 2,
        start_y + box_height // 2,
        text="Kämpfername\nVerein",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Draw "Kampfnummer" header cell (third column header)
    kampf_x = start_x + num_width + name_width
    canvas.create_rectangle(
        kampf_x, start_y, kampf_x + kampfnummer_width, start_y + box_height,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )

    # Draw "Kampfnummer" header text
    canvas.create_text(
        kampf_x + kampfnummer_width // 2,
        start_y + box_height // 2,
        text="Kampfnummer",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Draw column headers (fight numbers across top)
    for col in range(num_fights):
        x = start_x + num_width + name_width + kampfnummer_width + (col * cell_size)
        y = start_y

        # Draw header cell
        canvas.create_rectangle(
            x, y, x + cell_size, y + box_height,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )

        # Draw fight number (use provided fight_numbers list)
        canvas.create_text(
            x + cell_size // 2,
            y + box_height // 2,
            text=str(fight_numbers[col]),
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

    # Draw summary column headers (Punkte, Ubw., Platz) after fight columns
    summary_labels = ["Punkte", "Ubw.", "Platz"]
    for i, label in enumerate(summary_labels):
        x = start_x + num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (i * cell_size)
        canvas.create_rectangle(
            x, start_y, x + cell_size, start_y + box_height,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )
        canvas.create_text(
            x + cell_size // 2,
            start_y + box_height // 2,
            text=label,
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

    # Draw rows (each fighter)
    for row in range(pool_size):
        y = start_y + ((row + 1) * box_height)

        fighter = pool_participants[row]
        name = fighter.get('Name', 'Unknown')
        club = fighter.get('Verein', '')
        fighter_num = row + 1

        # Draw number cell (first column)
        canvas.create_rectangle(
            start_x, y, start_x + num_width, y + box_height,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )
        canvas.create_text(
            start_x + num_width // 2,
            y + box_height // 2,
            text=str(fighter_num),
            anchor='c',
            fill=colors['white'],
            font=scaled_font
        )

        # Draw name cell (second column)
        display_text = f"{name} [{club}]" if club else name
        canvas.create_rectangle(
            start_x + num_width, y, start_x + num_width + name_width, y + box_height,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )
        canvas.create_text(
            start_x + num_width + padding // 2,
            y + box_height // 2,
            text=display_text,
            anchor='w',
            fill=colors['white'],
            font=scaled_font
        )

        # Draw Kampfnummer cell (third column) with Punkte and Ubw. sub-columns
        kampf_x = start_x + num_width + name_width
        canvas.create_rectangle(
            kampf_x, y, kampf_x + kampfnummer_width, y + box_height,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )

        # Draw "Punkte" text in left sub-column
        canvas.create_text(
            kampf_x + punkte_width // 2,
            y + box_height // 2,
            text="Punkte",
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

        # Draw "Ubw." text in right sub-column
        canvas.create_text(
            kampf_x + punkte_width + ubw_width // 2,
            y + box_height // 2,
            text="Ubw.",
            anchor='c',
            fill=colors['white'],
            font=cell_font
        )

        # Draw vertical separator line between Punkte and Ubw. for this row
        canvas.create_line(
            kampf_x + punkte_width, y,
            kampf_x + punkte_width, y + box_height,
            fill=colors['accent_green'],
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
                    outline=colors['accent_green'],
                    fill=colors['white'],
                    width=line_width
                )

                # Draw vertical divider in the middle of the cell
                canvas.create_line(
                    x + cell_size // 2, y,
                    x + cell_size // 2, y + box_height,
                    fill=colors['black'],
                    width=line_width
                )
            else:
                # Draw empty/blank cell (fighter doesn't participate in this fight)
                canvas.create_rectangle(
                    x, y, x + cell_size, y + box_height,
                    outline=colors['accent_green'],
                    fill=colors['bg_panel'],
                    width=line_width
                )

        # Draw blank summary cells (Punkte, Ubw., Platz) for this row — stop before Kampfzeit
        for i in range(3):
            x = start_x + num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (i * cell_size)
            canvas.create_rectangle(
                x, y, x + cell_size, y + box_height,
                outline=colors['accent_green'],
                fill=colors['bg_panel'],
                width=line_width
            )

    # Draw Kampfzeit bottom row
    bottom_y = start_y + ((pool_size + 1) * box_height)

    # Kampfzeit cell spanning Punkte + Ubw. columns
    kampf_x = start_x + num_width + name_width
    canvas.create_rectangle(
        kampf_x, bottom_y,
        kampf_x + kampfnummer_width, bottom_y + box_height,
        outline=colors['accent_green'],
        fill=colors['bg_panel'],
        width=line_width
    )
    canvas.create_text(
        kampf_x + kampfnummer_width // 2,
        bottom_y + box_height // 2,
        text="Kampfzeit",
        anchor='c',
        fill=colors['white'],
        font=cell_font
    )

    # Blank cells under each fight column
    for fight_num in range(num_fights):
        x = start_x + num_width + name_width + kampfnummer_width + (fight_num * cell_size)
        canvas.create_rectangle(
            x, bottom_y, x + cell_size, bottom_y + box_height,
            outline=colors['accent_green'],
            fill=colors['bg_panel'],
            width=line_width
        )

    # Draw legend at bottom
    legend_y = start_y + ((pool_size + 2) * box_height) + padding
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
    box_width, box_height, cell_size, padding = calculate_pool_box_size(participants, zoom_level)

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
            box_width, box_height, cell_size, padding,
            zoom_level, colors, fonts, pool_label,
            fight_numbers
        )

        # Calculate dimensions (num_width + name_width + kampfnummer_width + match columns)
        pool_size = len(pool)
        fight_schedule = _generate_fight_schedule(pool_size)
        num_fights = len(fight_schedule)
        num_width = cell_size  # Start-nr column
        name_width = box_width  # Name/Verein column
        kampfnummer_width = int(cell_size * 1.5)  # Kampfnummer column (Punkte + Ubw.)
        grid_width = num_width + name_width + kampfnummer_width + (num_fights * cell_size) + (3 * cell_size) + padding * 2
        grid_height = ((pool_size + 2) * box_height) + padding * 3  # +1 for header, +1 for Kampfzeit row

        max_width = max(max_width, grid_width)
        current_y += grid_height + padding * 2

    total_width = start_x + max_width + 50
    total_height = current_y + 50

    return total_width, total_height
