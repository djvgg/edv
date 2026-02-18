# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Frontend utilities for bracket rendering, participant loading, and caching."""

from .bracket_renderer import build_bracket_rounds, calculate_box_size, draw_bracket_on_canvas
from .participant_loader import load_participants_from_xlsx, normalize_participants
from .bracket_cache import save_bracket_to_cache, load_bracket_from_cache, clear_bracket_cache

__all__ = [
    # Rendering
    'build_bracket_rounds',
    'calculate_box_size',
    'draw_bracket_on_canvas',
    # Participant loading
    'load_participants_from_xlsx',
    'normalize_participants',
    # Caching
    'save_bracket_to_cache',
    'load_bracket_from_cache',
    'clear_bracket_cache',
]

"""Frontend utilities for bracket rendering, file loading, and caching."""
