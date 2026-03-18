# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Direct entry point: python main.py"""

import traceback
import os
import sys

# Add edv_backend to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from utils.logging import get_logger
from backend.services.database_service import get_database_service
from frontend.views.main_window import main

logger = get_logger('main')

if __name__ == '__main__':
    # NOTE: Cache/DB ID Matching Strategy
    # - Initial participants loaded from files (XLSX/JSON) have no DB IDs
    # - Uses natural key matching (first_name + last_name + gender + birth_date + club) to find existing records
    # - Optimization opportunity: Store returned DB IDs after first save, use direct ID lookups on subsequent updates
    #   This would eliminate expensive 5-field WHERE queries (resort, duplicate detection, etc.)
    # - Current approach: Natural key as primary, ID caching as future optimization
    
    # Initialize database service (handles schema creation, connection errors)
    db_service = get_database_service()
    if db_service.is_available():
        logger.info("✓ Database initialized successfully")
    else:
        logger.warning("Database unavailable, running in offline mode")
    
    try:
        main()
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        traceback.print_exc()
