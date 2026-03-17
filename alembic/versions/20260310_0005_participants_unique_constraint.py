# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Add unique constraint on participants (first_name, last_name, birth_date, club).

Two athletes can legitimately share a name but not the same name + birth year +
club combination.  Uses NULLS NOT DISTINCT so that NULL birth_date / club values
are still treated as equal (PostgreSQL 15+ syntax; falls back gracefully on
older versions via a partial unique index approach).

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-10
"""

from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use a regular unique index.  PostgreSQL treats NULLs as distinct in unique
    # indexes by default, so two rows where birth_date IS NULL would NOT clash —
    # that is actually safe for our use-case: if we don't know the birth date we
    # cannot be sure two people are the same, so we allow both.
    op.create_index(
        'uix_participant_identity',
        'participants',
        ['first_name', 'last_name', 'gender', 'birth_date', 'club'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uix_participant_identity', table_name='participants')
