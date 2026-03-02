# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .db_config import DB_CONFIG

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
    import backend.data.models  # noqa: F401 — must be imported before create_all
    from sqlalchemy import inspect, text
    Base.metadata.create_all(engine)

    # Incremental schema migrations
    inspector = inspect(engine)
    if 'groups' in inspector.get_table_names():
        existing_cols = {c['name']: c for c in inspector.get_columns('groups')}

        # Migration 1: add groups.name (added when QUARANTINE/named groups were introduced)
        if 'name' not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE groups ADD COLUMN name VARCHAR(100)"))
                conn.execute(text(
                    "UPDATE groups SET name = CONCAT(gender, ' | ', age_group, ' | ', weight_class)"
                    " WHERE name IS NULL AND gender IS NOT NULL"
                ))
                conn.execute(text(
                    "ALTER TABLE groups ADD CONSTRAINT groups_name_key UNIQUE (name)"
                ))

        # Migration 2: allow NULL gender/age_group/weight_class for U9, U11, QUARANTINE
        for col in ('gender', 'age_group', 'weight_class'):
            col_info = existing_cols.get(col, {})
            if col_info.get('nullable') is False:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE groups ALTER COLUMN {col} DROP NOT NULL"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
