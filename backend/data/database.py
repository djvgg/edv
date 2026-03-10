# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Database initialization and configuration.

**IMPORTANT DESIGN NOTE:**
This system is used only 2 days per year (tournament period). The database is
completely cleared after the tournament ends. Because of this ephemeral nature:

- Fresh database is created each year from ORM models (Base.metadata.create_all)
- Alembic migrations are TECHNICALLY UNNECESSARY but kept for:
  * Future flexibility if system evolves to year-round operation
  * Schema version history/documentation
  * Best-practice consistency

If Alembic becomes maintenance burden, can be safely removed since we only ever
have fresh database installations (no data preservation across versions).

For now: keep it simple, use ORM models as source of truth, Alembic as optional.
"""

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
    """Create all tables from ORM models.
    
    Since database is cleared annually (ephemeral system), we always start fresh
    from ORM model definitions. No data preservation needed during schema changes.
    
    **Alembic Note:** Alembic migrations are available but optional for this use case.
    They're kept for documentation and future-proofing if system becomes year-round.
    
    For one-time setup or debugging:
        Base.metadata.drop_all(engine)  # Optional: clear old schema
        Base.metadata.create_all(engine)  # Create fresh from models
    """
    logger.info("[DATABASE] Initializing database schema...")
    import backend.data.models  # noqa: F401 — models must be imported before create_all

    Base.metadata.create_all(engine)
    logger.info("[DATABASE] Base tables created/verified")
    
    # NOTE: Alembic migrations would normally handle schema evolution of existing data.
    # Since this system clears its database annually (ephemeral), all upgrades start fresh.
    # Alembic is kept for documentation and future flexibility if system design changes.
    
    logger.info("[DATABASE] ✓ Database initialized successfully")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
