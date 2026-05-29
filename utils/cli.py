# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Console-script entry-point for ``edv-backend``.

Lives inside the installable ``utils`` package so the entry-point
``[project.scripts] edv-backend = "utils.cli:main"`` resolves no matter
which cwd the script is invoked from. The previous wiring
(``edv-backend = "main:main"``) broke because ``main.py`` is a top-level
file (not a package): setuptools' editable installer maps top-level
names to *directories* in its finder (e.g. ``{'main': '.../main'}``),
not to ``.py`` files — so ``from main import main`` then raised
``ModuleNotFoundError: No module named 'main'``.

The actual application code is unchanged; this module owns the boot
sequence (logger, DB service, error handler) and the legacy ``main.py``
delegates here so ``python main.py`` keeps working.
"""

import os
import sys
import traceback


def main() -> int:
    """Boot edv-backend: init logger + DB service, then launch the Tk GUI."""
    # Belt-and-braces: make sure the repo root is on sys.path so
    # `utils.logging` / `backend.*` / `frontend.*` resolve even in the rare
    # strict-editable install layout where __file__ lives under build/.
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

    from utils.logging import get_logger
    from backend.services.database_service import get_database_service
    from frontend.views.main_window import main as launch_gui

    logger = get_logger('main')

    # NOTE: Cache/DB ID Matching Strategy
    # - Initial participants loaded from files (XLSX/JSON) have no DB IDs
    # - Uses natural key matching (first_name + last_name + gender +
    #   birth_date + club) to find existing records
    # - Optimization opportunity: Store returned DB IDs after first save,
    #   use direct ID lookups on subsequent updates — would eliminate
    #   expensive 5-field WHERE queries (resort, duplicate detection, etc.)
    # - Current approach: Natural key as primary, ID caching as future
    #   optimization

    # Initialize database service (handles schema creation, connection errors)
    db_service = get_database_service()
    if db_service.is_available():
        logger.info("✓ Database initialized successfully")
    else:
        logger.warning("Database unavailable, running in offline mode")

    try:
        launch_gui()
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        traceback.print_exc()
        return 1
    return 0
