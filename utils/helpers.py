# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Shared domain helpers — pure functions with no external dependencies.

Import from here instead of defining locally in each module.
"""


def normalize_gender(raw: str) -> str:
    """Normalize any gender string to canonical 'm' or 'w'.

    Accepts German and English variants in any case:
        m / male / maennlich / männlich / mann  → 'm'
        w / f / female / weiblich / frau        → 'w'

    Falls back to first character of the input, or 'm' on empty input.
    """
    v = str(raw).lower().strip()
    if v in ('m', 'male', 'maennlich', 'männlich', 'mann'):
        return 'm'
    if v in ('w', 'f', 'female', 'weiblich', 'frau'):
        return 'w'
    return v[0] if v else 'm'


def split_name(full_name: str) -> tuple:
    """Split 'Vorname Nachname' → (first_name, last_name).

    Uses rsplit so multi-word first names are preserved:
        'John Doe'          → ('John', 'Doe')
        'John Van Der Berg' → ('John Van Der', 'Berg')

    Must match the logic in _map_participant_data() so DB lookups are consistent.
    """
    parts = full_name.rsplit(' ', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return full_name, ''


def parse_bracket_key(bracket_key: str) -> tuple:
    """Parse 'M | U13 | -50kg' → ('M', 'U13', '-50kg').

    Raises ValueError for keys that are not in the expected 3-part format
    (e.g. 4-part 'Unassigned | ...' keys should be filtered before calling this).
    """
    parts = [p.strip() for p in bracket_key.split('|')]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    raise ValueError(f"Cannot parse bracket key: {bracket_key!r}")
