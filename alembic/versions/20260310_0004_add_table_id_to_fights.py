# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""M5 — Add table_id column to fights (used by judgeFrontend for mat assignment).

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only add if not already present (column may exist from judgeFrontend migration)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'fights' AND column_name = 'table_id'"
    )).fetchone()
    if not result:
        op.add_column('fights', sa.Column('table_id', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('fights', 'table_id')
