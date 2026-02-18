# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket Service - Thin wrapper layer for bracket functionality.

This module provides wrapper functions for bracket generation and configuration.
All actual bracket logic is in bracket_utils; this module just delegates to it.
"""

import os
import sys

# Add parent directory to path for libraries access
_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from libraries.logging import get_logger  # noqa: E402
from ..data.repositories.config_repository import ConfigRepository  # noqa: E402

# Import bracket_utils from the utils package at edv_backend level
# We're in backend/services/, so go up 2 levels to edv_backend/
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.bracket_utils import (  # noqa: E402
    export_all_brackets as _export_all_brackets,
    get_age_group as _get_age_group,
    get_weight_class as _get_weight_class,
    get_pool_size as _get_pool_size,
    make_bracket as _make_bracket,
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

