# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Entry point for running as module: python -m edv_backend"""

from .backend.services.database_service import get_database_service
from .frontend.views.main_window import main

if __name__ == '__main__':
    # Initialize database service (handles schema creation, connection errors)
    db_service = get_database_service()
    if db_service.is_available():
        print("[INFO] Database initialized successfully")
    else:
        print("[WARNING] Database unavailable, running in offline mode")
    
    main()
