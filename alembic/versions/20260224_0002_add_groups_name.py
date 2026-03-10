# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""M1 — Add groups.name and make gender/age_group/weight_class nullable.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # M1: groups.name
    op.add_column('groups', sa.Column('name', sa.String(100), nullable=True))
    op.execute(
        "UPDATE groups SET name = CONCAT(gender, ' | ', age_group, ' | ', weight_class)"
        " WHERE name IS NULL AND gender IS NOT NULL"
    )
    op.alter_column('groups', 'name', nullable=False)
    op.create_unique_constraint('groups_name_key', 'groups', ['name'])

    # M2: allow NULLs for U9/U11/QUARANTINE groups
    op.alter_column('groups', 'gender',       nullable=True)
    op.alter_column('groups', 'age_group',    nullable=True)
    op.alter_column('groups', 'weight_class', nullable=True)


def downgrade() -> None:
    op.alter_column('groups', 'weight_class', nullable=False)
    op.alter_column('groups', 'age_group',    nullable=False)
    op.alter_column('groups', 'gender',       nullable=False)
    op.drop_constraint('groups_name_key', 'groups', type_='unique')
    op.drop_column('groups', 'name')
