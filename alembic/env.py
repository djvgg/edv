# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Alembic environment — connects to the project DB and loads all models."""

import os
import sys
from logging.config import fileConfig

from alembic import context

# ── project imports ────────────────────────────────────────────────────────────
# Add the edv_backend root to sys.path so all project imports resolve.
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)          # edv_backend/
if _root not in sys.path:
    sys.path.insert(0, _root)

# Import models so Alembic's autogenerate can detect schema changes.
import backend.data.models  # noqa: F401
from backend.data.database import Base, DATABASE_URL

# ── Alembic Config ─────────────────────────────────────────────────────────────
config = context.config
config.set_main_option('sqlalchemy.url', DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Run migrations ─────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live DB connection."""
    from sqlalchemy import create_engine
    connectable = create_engine(config.get_main_option('sqlalchemy.url'))
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
