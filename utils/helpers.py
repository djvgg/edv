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


def age_group_from_bracket_key(bracket_key: str) -> str | None:
    """Return the age group represented by a bracket/list key.

    Supported examples:
        'm | U13 | -50kg' -> 'U13'
        'U9'              -> 'U9'
        'U11 | Pool 2'    -> 'U11'

    Returns None for non-competition buckets such as QUARANTINE_*.
    """
    if not bracket_key:
        return None

    key = str(bracket_key).strip()
    if not key or key.startswith('QUARANTINE_'):
        return None

    if key in ('U9', 'U11', 'U13', 'U15', 'U18', '18+'):
        return key

    parts = [p.strip() for p in key.split('|')]
    if len(parts) == 2 and parts[0] in ('U9', 'U11') and parts[1].lower().startswith('pool'):
        return parts[0]
    if len(parts) == 3:
        return parts[1]

    return None


def age_class_scope_key(age_group: str, gender: str | None = None) -> str:
    """Build the stable lock key for an age class, optionally gender-scoped."""
    age = str(age_group).strip()
    if gender:
        return f"{normalize_gender(gender)}|{age}"
    return age


def lock_matches_age_group(scope_key: str, age_group: str, gender: str | None = None) -> bool:
    """Return True if a persisted age-class lock applies to this age/gender."""
    if not scope_key or not age_group:
        return False

    scope = str(scope_key).strip()
    if scope == age_group:
        return True

    if '|' not in scope:
        return False

    locked_gender, locked_age = [part.strip() for part in scope.split('|', 1)]
    return locked_age == age_group and normalize_gender(gender or locked_gender) == locked_gender


def bracket_key_matches_age_lock(bracket_key: str, locked_age_classes: set | list | tuple) -> bool:
    """Return True if a bracket key belongs to any locked age-class scope."""
    age_group = age_group_from_bracket_key(bracket_key)
    if not age_group:
        return False

    gender = None
    try:
        gender, _, _ = parse_bracket_key(bracket_key)
    except ValueError:
        pass

    return any(lock_matches_age_group(scope, age_group, gender) for scope in locked_age_classes or [])
