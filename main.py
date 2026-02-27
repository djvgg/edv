# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Direct entry point: python main.py"""

import traceback
import os
import sys

# Add edv_backend to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from backend.services.database_service import get_database_service
from frontend.views.main_window import main

if __name__ == '__main__':
    # Initialize database service (handles schema creation, connection errors)
    db_service = get_database_service()
    if db_service.is_available():
        print("[INFO] Database initialized successfully")
    else:
        print("[WARNING] Database unavailable, running in offline mode")
    
    try:
        main()
    except Exception as e:
        print(f"[ERROR] Application crashed: {e}")
        traceback.print_exc()
