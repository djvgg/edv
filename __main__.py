# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Entry point for running as module: python -m edv_backend"""

import os
import sys

# Add edv_backend directory to path so utils imports work
_edv_backend_path = os.path.dirname(__file__)
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from .backend.services.database_service import get_database_service  # noqa: E402
from .frontend.views.main_window import main  # noqa: E402

logger = get_logger('main')

if __name__ == '__main__':
    # Initialize database service (handles schema creation, connection errors)
    db_service = get_database_service()
    if db_service.is_available():
        logger.info("✓ Database initialized successfully")
    else:
        logger.warning("Database unavailable, running in offline mode")
    
    main()
