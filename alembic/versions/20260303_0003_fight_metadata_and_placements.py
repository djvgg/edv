# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""M3+M4 — Fight metadata columns, placement columns, and unique constraint.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # M3: bracket position metadata
    op.add_column('fights', sa.Column('bracket_phase', sa.String(10),
                                      nullable=False, server_default='wb'))
    op.add_column('fights', sa.Column('round',        sa.Integer(), nullable=True))
    op.add_column('fights', sa.Column('pos_in_round', sa.Integer(), nullable=True))
    op.add_column('fights', sa.Column('pool_index',   sa.Integer(), nullable=True))
    op.add_column('fights', sa.Column('winner_id',    sa.Integer(),
                                      sa.ForeignKey('group_participants.id'), nullable=True))

    # Placement columns on brackets
    op.add_column('brackets', sa.Column('first_place',   sa.Integer(),
                                        sa.ForeignKey('group_participants.id'), nullable=True))
    op.add_column('brackets', sa.Column('second_place',  sa.Integer(),
                                        sa.ForeignKey('group_participants.id'), nullable=True))
    op.add_column('brackets', sa.Column('third_place_1', sa.Integer(),
                                        sa.ForeignKey('group_participants.id'), nullable=True))
    op.add_column('brackets', sa.Column('third_place_2', sa.Integer(),
                                        sa.ForeignKey('group_participants.id'), nullable=True))

    # M4: deduplicate + unique constraint
    op.execute("""
        DELETE FROM fights
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM fights
            WHERE round IS NOT NULL
            GROUP BY bracket_id, bracket_phase, round, pos_in_round
        )
        AND round IS NOT NULL
    """)
    op.create_unique_constraint(
        'uix_fight_position', 'fights',
        ['bracket_id', 'bracket_phase', 'round', 'pos_in_round']
    )


def downgrade() -> None:
    op.drop_constraint('uix_fight_position', 'fights', type_='unique')
    op.drop_column('fights', 'winner_id')
    op.drop_column('fights', 'pool_index')
    op.drop_column('fights', 'pos_in_round')
    op.drop_column('fights', 'round')
    op.drop_column('fights', 'bracket_phase')
    op.drop_column('brackets', 'third_place_2')
    op.drop_column('brackets', 'third_place_1')
    op.drop_column('brackets', 'second_place')
    op.drop_column('brackets', 'first_place')
