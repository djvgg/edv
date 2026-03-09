# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket Service - Thin wrapper layer for bracket functionality.

This module provides wrapper functions for bracket generation and configuration.
All actual bracket logic is in bracket_utils; this module just delegates to it.
"""

import os
import sys

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from ..data.repositories.config_repository import ConfigRepository  # noqa: E402

from utils.bracket_utils import (  # noqa: E402
    export_all_brackets as _export_all_brackets,
    get_age_group as _get_age_group,
    get_weight_class as _get_weight_class,
    get_pool_size as _get_pool_size,
    make_bracket as _make_bracket,
    validate_age_from_birthyear as _validate_age_from_birthyear,
)

# module logger
logger = get_logger('bracket_service')

# Global config instance (can be replaced or reloaded as needed)
_current_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_current_dir, '..', '..', 'config', 'bracket_config.xlsx')
bracket_config = None


def set_bracket_config(path):
    """Set the configuration path for bracket operations."""
    global bracket_config
    bracket_config = ConfigRepository(path)


def ensure_config_loaded():
    """Ensure configuration is loaded."""
    global bracket_config
    if bracket_config is None:
        bracket_config = ConfigRepository(CONFIG_PATH)


def get_age_group(age, event_year=None):
    """
    Returns the age group (e.g., U13, U15, etc.) for a given age and event year.
    
    Args:
        age: Age of the participant
        event_year: Event year (uses config default if None)
    
    Returns:
        Age group string (e.g., 'U9', 'U11', 'U13', etc.) or None if invalid
    """
    ensure_config_loaded()
    return _get_age_group(age, event_year)


def get_age_group_from_birthyear(birthyear, event_year=None):
    """
    Returns the age group for a given birthyear (single source of truth for age calculation).
    
    Handles calculation: age = current_year - birthyear
    Then determines age group with fallback for out-of-bounds ages.
    
    Args:
        birthyear: Birth year as integer (e.g., 2018)
        event_year: Event year (uses config default if None)
    
    Returns:
        Tuple: (age_group_str, calculated_age) or (None, None) if calculation fails
        Examples:
            (2018, None) → ('U13', 8)
            (2001, None) → ('18+', 25)
            (2026, None) → ('18+', 0)  # Fallback for out-of-bounds
            (2000, None) → ('18+', 26)
    """
    import datetime
    try:
        current_year = event_year or datetime.datetime.now().year
        calculated_age = current_year - int(birthyear)
        age_group = get_age_group(calculated_age, event_year)
        return age_group, calculated_age
    except (ValueError, TypeError):
        return None, None


def validate_age_from_birthyear(birthyear, min_age=6, max_age=120, event_year=None):
    """
    Validates age from birthyear with bounds checking.
    
    SINGLE SOURCE OF TRUTH for age validation across the app.
    Consolidates all age checking and bounds validation logic.
    
    Args:
        birthyear: Birth year as integer (e.g., 2018)
        min_age: Minimum valid age (default 6)
        max_age: Maximum valid age (default 120)
        event_year: Event year for calculation (uses config default if None)
    
    Returns:
        Tuple: (age_group, calculated_age, is_valid, rejection_reason)
        Examples:
            (2018, None, ...) → ('U13', 8, True, None)
            (2001, None, ...) → ('18+', 25, True, None)
            (2026, None, ...) → ('18+', 0, True, None)
            (1900, None, ...) → (None, 126, False, 'too old (126 years)')
            (None, None, ...) → (None, None, False, 'no age/birthyear')
    """
    ensure_config_loaded()
    return _validate_age_from_birthyear(birthyear, min_age, max_age, event_year)


def get_weight_class(weight, gender, age_group=None):
    """
    Returns the weight class for a given weight, gender, and age group.
    
    Args:
        weight: Weight in kg
        gender: Participant's gender
        age_group: Age group (e.g., 'U13', 'U15'); if None, uses lookup
    
    Returns:
        Weight class string (e.g., '-45kg', '+80kg') or 'no-class' for U9/U11
    """
    ensure_config_loaded()
    return _get_weight_class(weight, gender, age_group)


def get_pool_size(age_group):
    """
    Get the pool size configuration for U9 and U11 age groups.
    
    Args:
        age_group: The age group (e.g., 'U9', 'U11')
    
    Returns:
        The pool size as integer, or None if not configured
    """
    ensure_config_loaded()
    return _get_pool_size(age_group)


def export_all_brackets(participants, event_year=None):
    """
    Groups participants by (gender, age group, weight class) and generates brackets.
    
    Args:
        participants: List of participant dictionaries
        event_year: Event year (uses config default if None)
    
    Returns:
        Dictionary: {bracket_key: {'fighters': [...], 'bracket': [...], 'pool_size': ...}}
    """
    ensure_config_loaded()
    return _export_all_brackets(participants, event_year)


def make_bracket(participants):
    """
    Creates a tournament bracket from a list of participants.
    
    Args:
        participants: List of participant dictionaries
    
    Returns:
        Generated bracket structure
    """
    return _make_bracket(participants)

