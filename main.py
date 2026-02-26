# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Main entry point for the Tournament Bracket Manager application.

Refactored structure:
- frontend/views/main_window.py: GUI code
- backend/services/bracket_service.py: Business logic
- backend/data/repositories/config_repository.py: Configuration management
"""

import backend.data.database as _db
from backend.data.database import init_db
from frontend.views.main_window import main

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print(f"[WARNING] DB unavailable, running without database: {e}")
        _db.DB_AVAILABLE = False
    main()
