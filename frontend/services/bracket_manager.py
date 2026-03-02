# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bracket management utilities shared across views."""

from utils.logging import get_logger

logger = get_logger('bracket_manager')


def regenerate_stale_ko_brackets(brackets, bracket_generation_methods, make_bracket_fn):
    """Regenerate stale KO pairings for every bracket whose bracket field is
    empty or out-of-date (i.e. len differs from fighters count).

    Called before fight monitoring opens so _render_ko always sees correct data.
    Pool brackets are skipped — they don't use the bracket field.
    """
    for bracket_key, bracket_data in brackets.items():
        if bracket_data.get('is_quarantine'):
            continue
        method = bracket_generation_methods.get(bracket_key, 'ko')
        if method in ('pools', 'double'):
            continue  # Pool brackets don't use the bracket field

        fighters = bracket_data.get('fighters', [])
        current_bracket = bracket_data.get('bracket', [])

        # Rebuild if empty or stale (fighter count changed since last build)
        if not current_bracket or len(current_bracket) != len(fighters) // 2:
            normalized = [
                {'Name': p.get('Name', f"{p.get('Firstname', '')} {p.get('Lastname', '')}".strip()),
                 'Verein': p.get('Club', p.get('Verein', p.get('verein', p.get('club', ''))))}
                for p in fighters if isinstance(p, dict)
            ]
            if normalized:
                bracket_data['bracket'] = make_bracket_fn(normalized)
                logger.debug(
                    f"Regenerated bracket for {bracket_key}: "
                    f"{len(normalized)} fighters → {len(bracket_data['bracket'])} pairs"
                )
