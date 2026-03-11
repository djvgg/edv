# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Pytest root configuration.

Adds the edv_backend directory to sys.path once so all test modules can do
    from utils.helpers import normalize_gender
    from backend.services.tournament_service import TournamentService
without per-file sys.path manipulation.
"""

import os
import sys

_root = os.path.dirname(__file__)
if _root not in sys.path:
    sys.path.insert(0, _root)
