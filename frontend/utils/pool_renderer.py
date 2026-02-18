# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pool rendering utilities for round-robin group visualization on canvas."""


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

    # Scale dimensions
    base_width = max(100, int(max_text_len * 8))
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

        # Calculate grid dimensions
        grid_width = boxWidth + (pool_size * cellSize) + padding
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
                    cellSize, padding, zoom_level, colors, fonts, pool_label="Pool 1"):
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
    """
    line_width = max(1, int(2 * zoom_level))
    font_size = max(6, int(10 * zoom_level))
    scaled_font = ('Consolas', font_size)
    header_font = ('Arial', max(8, int(12 * zoom_level)), 'bold')
    cell_font = ('Consolas', max(6, int(8 * zoom_level)))

    pool_size = len(pool_participants)

    # Draw pool label/title
    title_y = start_y - padding
    canvas.create_text(
        start_x + boxWidth // 2,
        title_y,
        text=pool_label,
        anchor='c',
        fill=colors['accent_blue'],
        font=header_font
    )

    # Draw column headers (fighter names across top)
    for col in range(pool_size):
        x = start_x + boxWidth + (col * cellSize)
        y = start_y

        # Draw header cell
        canvas.create_rectangle(
            x, y, x + cellSize, y + boxHeight,
            outline=colors['white'],
            fill=colors['bg_panel'],
            width=line_width
        )

        # Draw fighter number
        canvas.create_text(
            x + cellSize // 2,
            y + boxHeight // 2,
            text=str(col + 1),
            anchor='c',
            fill=colors['accent_blue'],
            font=cell_font
        )

    # Draw rows (each fighter)
    for row in range(pool_size):
        y = start_y + ((row + 1) * boxHeight)

        # Draw row header (fighter number + name)
        fighter = pool_participants[row]
        name = fighter.get('Name', 'Unknown')
        club = fighter.get('Verein', '')
        fighter_num = row + 1
        display_text = f"{fighter_num}. {name} [{club}]" if club else f"{fighter_num}. {name}"

        canvas.create_rectangle(
            start_x, y, start_x + boxWidth, y + boxHeight,
            outline=colors['white'],
            fill=colors['bg_panel'],
            width=line_width
        )

        canvas.create_text(
            start_x + padding // 2,
            y + boxHeight // 2,
            text=display_text,
            anchor='w',
            fill=colors['white'],
            font=scaled_font
        )

        # Draw match cells for this fighter
        for col in range(pool_size):
            x = start_x + boxWidth + (col * cellSize)

            # Skip diagonal (fighter vs themselves)
            if row == col:
                canvas.create_rectangle(
                    x, y, x + cellSize, y + boxHeight,
                    outline=colors['text_muted'],
                    fill=colors['bg_darker'],
                    width=line_width,
                    stipple='gray50'
                )
                canvas.create_text(
                    x + cellSize // 2,
                    y + boxHeight // 2,
                    text='—',
                    anchor='c',
                    fill=colors['text_muted'],
                    font=cell_font
                )
            else:
                # Draw match cell with "vs" indicator
                canvas.create_rectangle(
                    x, y, x + cellSize, y + boxHeight,
                    outline=colors['white'],
                    fill=colors['bg_input'],
                    width=line_width
                )

                # Show "vs" for all non-diagonal cells
                canvas.create_text(
                    x + cellSize // 2,
                    y + boxHeight // 2,
                    text='vs',
                    anchor='c',
                    fill=colors['text_secondary'],
                    font=cell_font
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

    # Draw each pool
    current_y = start_y
    max_width = 0

    for pool_idx, pool in enumerate(pools):
        pool_label = f"Pool {chr(65 + pool_idx)}" if num_pools > 1 else "Pool"

        draw_pool_table(
            canvas, pool, start_x, current_y,
            boxWidth, boxHeight, cellSize, padding,
            zoom_level, colors, fonts, pool_label
        )

        # Calculate dimensions
        pool_size = len(pool)
        grid_width = boxWidth + (pool_size * cellSize) + padding * 2
        grid_height = ((pool_size + 1) * boxHeight) + padding * 3

        max_width = max(max_width, grid_width)
        current_y += grid_height + padding * 2

    total_width = start_x + max_width + 50
    total_height = current_y + 50

    return total_width, total_height
