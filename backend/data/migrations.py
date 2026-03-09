# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Incremental schema migrations for existing databases.

Called by init_db() after Base.metadata.create_all().  Each function is
idempotent — it checks whether the change is needed before applying it.

History
-------
M1  add_groups_name             — groups.name VARCHAR(100) UNIQUE
M2  allow_null_group_columns    — groups.gender/age_group/weight_class → nullable
M3  add_fight_metadata_columns  — fights: bracket_phase, round, pos_in_round,
                                          pool_index, winner_id
M4  add_fight_position_unique   — UNIQUE (bracket_id, bracket_phase, round, pos_in_round)

For new databases all columns are created via create_all() from the current
models — these migrations only run on pre-existing databases that are missing
the columns/constraints.
"""

from sqlalchemy import inspect, text


def apply_migrations(engine, logger) -> int:
    """Apply all pending migrations. Returns the count of migrations applied."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    count = 0

    if 'groups' in tables:
        group_cols = {c['name']: c for c in inspector.get_columns('groups')}
        count += _m1_add_groups_name(engine, logger, group_cols)
        count += _m2_allow_null_group_columns(engine, logger, group_cols)

    if 'fights' in tables:
        fight_col_names = {c['name'] for c in inspector.get_columns('fights')}
        fight_constraints = {c['name'] for c in inspector.get_unique_constraints('fights')}
        count += _m3_add_fight_metadata_columns(engine, logger, fight_col_names)
        count += _m4_add_fight_position_unique(engine, logger, fight_col_names, fight_constraints)

    if count:
        logger.info(f"[MIGRATIONS] Applied {count} migration(s)")
    else:
        logger.info("[MIGRATIONS] Schema is up to date")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Individual migrations
# ─────────────────────────────────────────────────────────────────────────────

def _m1_add_groups_name(engine, logger, existing_cols: dict) -> int:
    """M1 — Add groups.name VARCHAR(100) UNIQUE.

    Backfills existing rows from gender | age_group | weight_class.
    Introduced when QUARANTINE/named groups were added.
    """
    if 'name' in existing_cols:
        return 0

    logger.info("[MIGRATIONS] M1: Adding groups.name column...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE groups ADD COLUMN name VARCHAR(100)"))
        conn.execute(text(
            "UPDATE groups SET name = CONCAT(gender, ' | ', age_group, ' | ', weight_class)"
            " WHERE name IS NULL AND gender IS NOT NULL"
        ))
        conn.execute(text(
            "ALTER TABLE groups ADD CONSTRAINT groups_name_key UNIQUE (name)"
        ))
    logger.info("[MIGRATIONS] M1: ✓ groups.name added")
    return 1


def _m2_allow_null_group_columns(engine, logger, existing_cols: dict) -> int:
    """M2 — Drop NOT NULL from groups.gender, age_group, weight_class.

    Required for U9/U11 (no weight class) and QUARANTINE groups.
    """
    nullable_cols = ('gender', 'age_group', 'weight_class')
    needs_fix = [
        col for col in nullable_cols
        if existing_cols.get(col, {}).get('nullable') is False
    ]
    if not needs_fix:
        return 0

    logger.info(f"[MIGRATIONS] M2: Dropping NOT NULL from {needs_fix}...")
    for col in needs_fix:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE groups ALTER COLUMN {col} DROP NOT NULL"))
    logger.info("[MIGRATIONS] M2: ✓ Nullable constraints updated")
    return 1


def _m3_add_fight_metadata_columns(engine, logger, existing_col_names: set) -> int:
    """M3 — Add bracket position metadata to fights table.

    Columns: bracket_phase, round, pos_in_round, pool_index, winner_id.
    Used for KO/LB position tracking and duplicate-fight prevention.
    """
    new_cols = {
        'bracket_phase': "VARCHAR(10) NOT NULL DEFAULT 'wb'",
        'round':         'INTEGER',
        'pos_in_round':  'INTEGER',
        'pool_index':    'INTEGER',
        'winner_id':     'INTEGER REFERENCES group_participants(id)',
    }
    missing = {k: v for k, v in new_cols.items() if k not in existing_col_names}
    if not missing:
        return 0

    logger.info(f"[MIGRATIONS] M3: Adding {len(missing)} metadata column(s) to fights...")
    for col_name, col_def in missing.items():
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE fights ADD COLUMN {col_name} {col_def}"))
    logger.info(f"[MIGRATIONS] M3: ✓ Added {list(missing)}")
    return 1


def _m4_add_fight_position_unique(engine, logger,
                                   existing_col_names: set,
                                   existing_constraints: set) -> int:
    """M4 — Add UNIQUE (bracket_id, bracket_phase, round, pos_in_round).

    Prevents duplicate fight rows for the same bracket slot.
    Deduplicates existing rows before adding the constraint.
    Only applies to KO/LB rows (round IS NOT NULL); pool rows are excluded.
    """
    required_cols = {'bracket_phase', 'round', 'pos_in_round'}
    if not required_cols.issubset(existing_col_names):
        return 0  # M3 hasn't run yet — will be applied next startup
    if 'uix_fight_position' in existing_constraints:
        return 0

    logger.info("[MIGRATIONS] M4: Adding UNIQUE constraint on fight positions...")
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
    logger.info("[MIGRATIONS] M4: ✓ UNIQUE constraint added")
    return 1
