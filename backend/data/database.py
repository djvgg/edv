# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .db_config import DB_CONFIG

# Add edv_backend directory to path for utils access
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402

logger = get_logger('database')

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def init_db():
    """Create all tables and apply incremental migrations. Called once at startup."""
    logger.info("[DATABASE] Initializing database schema...")
    import backend.data.models  # noqa: F401 — models must be imported before create_all

    Base.metadata.create_all(engine)
    logger.info("[DATABASE] Base tables created/verified")

    from .migrations import apply_migrations
    apply_migrations(engine, logger)

    logger.info("[DATABASE] ✓ Database initialized successfully")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
