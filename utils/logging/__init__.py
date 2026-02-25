# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
#
# SPDX-License-Identifier: CC0-1.0

"""Small logging package wrapper.

Expose `get_logger` for convenient imports:

	from libraries.logging import get_logger

"""
from .logger import get_logger

__all__ = ['get_logger']
