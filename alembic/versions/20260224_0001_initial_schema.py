# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initial schema — all 6 tables as of first deploy.

Revision ID: 0001
Revises:
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('participants',
        sa.Column('id',          sa.Integer(),      nullable=False),
        sa.Column('first_name',  sa.String(100),    nullable=False),
        sa.Column('last_name',   sa.String(100),    nullable=False),
        sa.Column('gender',      sa.String(1),      nullable=True),
        sa.Column('birth_date',  sa.Date(),         nullable=True),
        sa.Column('weight',      sa.Numeric(5, 2),  nullable=True),
        sa.Column('club',        sa.String(200),    nullable=True),
        sa.Column('association', sa.String(200),    nullable=True),
        sa.Column('valid',       sa.Boolean(),      nullable=True),
        sa.Column('paid',        sa.Boolean(),      nullable=True),
        sa.Column('doublestart', sa.String(10),     nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('mats',
        sa.Column('id',   sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('groups',
        sa.Column('id',           sa.Integer(),    nullable=False),
        sa.Column('gender',       sa.String(10),   nullable=True),
        sa.Column('age_group',    sa.String(20),   nullable=True),
        sa.Column('weight_class', sa.String(20),   nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('group_participants',
        sa.Column('id',             sa.Integer(), nullable=False),
        sa.Column('group_id',       sa.Integer(), nullable=False),
        sa.Column('participant_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'],       ['groups.id']),
        sa.ForeignKeyConstraint(['participant_id'], ['participants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('brackets',
        sa.Column('id',           sa.Integer(),    nullable=False),
        sa.Column('group_id',     sa.Integer(),    nullable=False),
        sa.Column('type',         sa.String(20),   nullable=True),
        sa.Column('status',       sa.String(20),   nullable=True),
        sa.Column('mat_id',       sa.Integer(),    nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id']),
        sa.ForeignKeyConstraint(['mat_id'],   ['mats.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('fights',
        sa.Column('id',             sa.Integer(), nullable=False),
        sa.Column('bracket_id',     sa.Integer(), nullable=False),
        sa.Column('participant1_id', sa.Integer(), nullable=True),
        sa.Column('participant2_id', sa.Integer(), nullable=True),
        sa.Column('status',         sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(['bracket_id'],      ['brackets.id']),
        sa.ForeignKeyConstraint(['participant1_id'], ['group_participants.id']),
        sa.ForeignKeyConstraint(['participant2_id'], ['group_participants.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('fights')
    op.drop_table('brackets')
    op.drop_table('group_participants')
    op.drop_table('groups')
    op.drop_table('mats')
    op.drop_table('participants')
