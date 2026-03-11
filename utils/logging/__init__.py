# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
#
# SPDX-License-Identifier: CC0-1.0

"""Small logging package wrapper.

Expose `get_logger` and `DEBUG_VERBOSE` for convenient imports:

    from utils.logging import get_logger, DEBUG_VERBOSE

Set the environment variable LOG_DEBUG=1 (or 'true'/'yes') to enable
verbose debug output to console across the entire application.
"""
import os
from .logger import get_logger

# Single source of truth for debug verbosity.
# Set LOG_DEBUG=1 in the environment to enable console debug output.
DEBUG_VERBOSE: bool = os.getenv('LOG_DEBUG', '').lower() in ('1', 'true', 'yes')

__all__ = ['get_logger', 'DEBUG_VERBOSE']
