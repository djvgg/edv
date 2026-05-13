# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Add persistent age-class locks for weigh-in imports.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'age_class_locks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scope_key', sa.String(30), nullable=False),
        sa.Column('age_group', sa.String(20), nullable=False),
        sa.Column('gender', sa.String(10), nullable=True),
        sa.Column('locked_at', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_key', name='uix_age_class_lock_scope'),
    )


def downgrade() -> None:
    op.drop_table('age_class_locks')
