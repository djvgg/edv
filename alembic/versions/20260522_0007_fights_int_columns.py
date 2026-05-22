# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""M7 — Convert fights.{score1,score2,duration,table_id} from VARCHAR(20) to INTEGER.

Status bleibt VARCHAR(20) (Enum-Träger: pending/finished/bye).

Begründung: WS-Handler in JudgeFrontend rechnet numerisch; Postgres-implicit-
conversion versteckte den TypeError. Architekt-Entscheidung 2026-05-22 (Welle 1),
dokumentiert in WSP/.claude/crew/outbox/wsp-architect-2026-05-22-welle1.md.

Defensiv geschrieben: prüft data_type pro Spalte vor ALTER, damit auf einem
schon migrierten / per ORM neu aufgesetzten Schema ein No-op resultiert.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

_INT_COLS = ('score1', 'score2', 'duration', 'table_id')


def _current_type(conn, column_name: str) -> str | None:
    row = conn.execute(sa.text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'fights' AND column_name = :col"
    ), {'col': column_name}).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()
    for col in _INT_COLS:
        dtype = _current_type(conn, col)
        if dtype == 'character varying':
            conn.execute(sa.text(
                f"ALTER TABLE fights ALTER COLUMN {col} TYPE integer "
                f"USING NULLIF({col}, '')::integer"
            ))
        # else: schon integer (ORM-create_all-Pfad) oder Spalte fehlt → nichts zu tun


def downgrade() -> None:
    conn = op.get_bind()
    for col in _INT_COLS:
        dtype = _current_type(conn, col)
        if dtype == 'integer':
            conn.execute(sa.text(
                f"ALTER TABLE fights ALTER COLUMN {col} TYPE varchar(20) "
                f"USING {col}::varchar(20)"
            ))
