# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Frontend utilities for bracket rendering, participant loading, and pool rendering."""

from .bracket_renderer import (
    build_bracket_rounds,
    calculate_box_size,
    draw_bracket_on_canvas,
    compute_bracket_rounds,
    calculate_ko_positions,
    draw_ko_connectors,
    calculate_loser_positions,
    draw_loser_connectors,
)
from .participant_loader import load_participants_from_xlsx, normalize_participants
from .pool_renderer import (
    draw_pools_on_canvas,
    draw_pool_table,
    split_into_pools,
    determine_pool_structure,
    calculate_pool_box_size,
    calculate_pool_positions,
)

__all__ = [
    # Bracket Rendering
    'build_bracket_rounds',
    'calculate_box_size',
    'draw_bracket_on_canvas',
    'compute_bracket_rounds',
    'calculate_ko_positions',
    'draw_ko_connectors',
    'calculate_loser_positions',
    'draw_loser_connectors',
    # Pool Rendering
    'draw_pools_on_canvas',
    'draw_pool_table',
    'split_into_pools',
    'determine_pool_structure',
    'calculate_pool_box_size',
    'calculate_pool_positions',
    # Participant loading
    'load_participants_from_xlsx',
    'normalize_participants',
]
