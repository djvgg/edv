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

DB_AVAILABLE = True  # set to False at startup if DB is unreachable


def init_db():
    """Create all tables if they do not exist. Called once at app startup.
    Also applies incremental schema migrations for columns added after initial deploy."""
    logger.info("[DATABASE] Initializing database schema...")
    import backend.data.models  # noqa: F401 — must be imported before create_all
    from sqlalchemy import inspect, text
    
    Base.metadata.create_all(engine)
    logger.info("[DATABASE] Base tables created/verified")

    # Incremental schema migrations
    inspector = inspect(engine)
    migration_count = 0
    
    if 'groups' in inspector.get_table_names():
        existing_cols = {c['name']: c for c in inspector.get_columns('groups')}

        # Migration 1: add groups.name (added when QUARANTINE/named groups were introduced)
        if 'name' not in existing_cols:
            logger.info("[DATABASE] Migration 1/4: Adding groups.name column...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE groups ADD COLUMN name VARCHAR(100)"))
                conn.execute(text(
                    "UPDATE groups SET name = CONCAT(gender, ' | ', age_group, ' | ', weight_class)"
                    " WHERE name IS NULL AND gender IS NOT NULL"
                ))
                conn.execute(text(
                    "ALTER TABLE groups ADD CONSTRAINT groups_name_key UNIQUE (name)"
                ))
            logger.info("[DATABASE] Migration 1/4: ✓ Added groups.name column")
            migration_count += 1

        # Migration 2: allow NULL gender/age_group/weight_class for U9, U11, QUARANTINE
        migration_2_needed = False
        for col in ('gender', 'age_group', 'weight_class'):
            col_info = existing_cols.get(col, {})
            if col_info.get('nullable') is False:
                migration_2_needed = True
                break
        
        if migration_2_needed:
            logger.info("[DATABASE] Migration 2/4: Allowing NULL for gender/age_group/weight_class...")
            for col in ('gender', 'age_group', 'weight_class'):
                col_info = existing_cols.get(col, {})
                if col_info.get('nullable') is False:
                    with engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE groups ALTER COLUMN {col} DROP NOT NULL"))
            logger.info("[DATABASE] Migration 2/4: ✓ Nullable constraints updated")
            migration_count += 1

    if 'fights' in inspector.get_table_names():
        fight_cols = {c['name'] for c in inspector.get_columns('fights')}
        
        # Migration 3: bracket position metadata columns
        logger.info("[DATABASE] Migration 3/4: Checking bracket metadata columns...")
        new_fight_cols = {
            'bracket_phase': "VARCHAR(10) NOT NULL DEFAULT 'wb'",
            'round':         'INTEGER',
            'pos_in_round':  'INTEGER',
            'pool_index':    'INTEGER',
            'winner_id':     'INTEGER REFERENCES group_participants(id)',
        }
        cols_added = 0
        for col_name, col_def in new_fight_cols.items():
            if col_name not in fight_cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE fights ADD COLUMN {col_name} {col_def}"))
                cols_added += 1
        if cols_added > 0:
            logger.info(f"[DATABASE] Migration 3/4: ✓ Added {cols_added} metadata columns to fights")
            migration_count += 1

        # Migration 4: unique constraint on fight positions (KO/LB only, pool excluded via NULL round)
        constraints = inspector.get_unique_constraints('fights')
        constraint_names = {c['name'] for c in constraints}
        if 'uix_fight_position' not in constraint_names:
            logger.info("[DATABASE] Migration 4/4: Adding UNIQUE constraint on fight positions...")
            # Clean up duplicate fights before adding constraint
            with engine.begin() as conn:
                conn.execute(text("""
                    DELETE FROM fights
                    WHERE id NOT IN (
                        SELECT MIN(id)
                        FROM fights
                        WHERE round IS NOT NULL
                        GROUP BY bracket_id, bracket_phase, round, pos_in_round
                    )
                    AND round IS NOT NULL
                """))
                conn.execute(text(
                    "ALTER TABLE fights ADD CONSTRAINT uix_fight_position"
                    " UNIQUE (bracket_id, bracket_phase, round, pos_in_round)"
                ))
            logger.info("[DATABASE] Migration 4/4: ✓ UNIQUE constraint added")
            migration_count += 1
    
    if migration_count > 0:
        logger.info(f"[DATABASE] Applied {migration_count} migrations")
    else:
        logger.info("[DATABASE] No migrations needed")
    
    logger.info("[DATABASE] ✓ Database initialized successfully")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
