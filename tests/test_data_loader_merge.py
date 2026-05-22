# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for DataLoaderService merge / skip-identical logic (P4, P6).

Covers two behaviours:
    • `_bracket_fighter_signature` — natural-key set for participants
    • `_merge_brackets_preserving_age_locks` — keeps locked classes,
      Quarantine, and (new in P4) classes whose participants are unchanged
"""

import pytest

from frontend.services.data_loader_service import DataLoaderService


def _bracket(*fighter_keys):
    """Build a fake bracket dict from (first, last, gender) tuples."""
    return {
        'fighters': [
            {'Firstname': f, 'Lastname': l, 'Gender': g}
            for (f, l, g) in fighter_keys
        ],
        'bracket': [],
    }


@pytest.fixture
def svc():
    """Loader without UI / DB — only the pure-function helpers we need."""
    return DataLoaderService(ui_feedback=None, task_runner=None, db_service=None)


class TestFighterSignature:
    def test_empty_bracket_has_empty_signature(self, svc):
        assert svc._bracket_fighter_signature({}) == frozenset()
        assert svc._bracket_fighter_signature({'fighters': []}) == frozenset()

    def test_signature_normalises_case_and_whitespace(self, svc):
        a = _bracket(('Tom', 'Kranz', 'm'))
        b = {'fighters': [{'Firstname': ' tom ', 'Lastname': 'KRANZ', 'Gender': 'M'}]}
        assert svc._bracket_fighter_signature(a) == svc._bracket_fighter_signature(b)

    def test_signature_independent_of_order(self, svc):
        a = _bracket(('Tom', 'Kranz', 'm'), ('Anna', 'Müller', 'w'))
        b = _bracket(('Anna', 'Müller', 'w'), ('Tom', 'Kranz', 'm'))
        assert svc._bracket_fighter_signature(a) == svc._bracket_fighter_signature(b)

    def test_different_fighters_different_signature(self, svc):
        a = _bracket(('Tom', 'Kranz', 'm'))
        b = _bracket(('Anna', 'Müller', 'w'))
        assert svc._bracket_fighter_signature(a) != svc._bracket_fighter_signature(b)

    def test_participants_key_also_supported(self, svc):
        """Some import paths use 'participants', others 'fighters' — both must work."""
        a = _bracket(('Tom', 'Kranz', 'm'))
        b = {'participants': [{'Firstname': 'Tom', 'Lastname': 'Kranz', 'Gender': 'm'}]}
        assert svc._bracket_fighter_signature(a) == svc._bracket_fighter_signature(b)


class TestMergeBrackets:
    """Behavioural tests for _merge_brackets_preserving_age_locks."""

    def test_fresh_import_takes_new_brackets(self, svc):
        new = {'m | U13 | -50kg': _bracket(('Tom', 'Kranz', 'm'))}
        merged = svc._merge_brackets_preserving_age_locks(
            existing_brackets={}, new_brackets=new, locked_age_classes=set(),
        )
        assert merged == new

    def test_quarantine_always_preserved(self, svc):
        existing = {'QUARANTINE_unpaid': _bracket(('X', 'Y', 'm'))}
        new = {'m | U13 | -50kg': _bracket(('Tom', 'Kranz', 'm'))}
        merged = svc._merge_brackets_preserving_age_locks(
            existing_brackets=existing, new_brackets=new, locked_age_classes=set(),
        )
        assert 'QUARANTINE_unpaid' in merged
        assert 'm | U13 | -50kg' in merged

    def test_locked_age_class_preserved_from_existing(self, svc):
        """Brackets in a locked age class stay as in the existing dict."""
        existing = {'m | U13 | -50kg': _bracket(('Old', 'Fighter', 'm'))}
        new = {'m | U13 | -50kg': _bracket(('New', 'Fighter', 'm'))}
        merged = svc._merge_brackets_preserving_age_locks(
            existing_brackets=existing, new_brackets=new,
            locked_age_classes={'U13'},
        )
        # We kept the old fighter, the new import was ignored.
        names = [f['Firstname'] for f in merged['m | U13 | -50kg']['fighters']]
        assert names == ['Old']

    def test_p4_skip_when_fighter_signature_identical(self, svc):
        """P4 — same participants → keep existing bracket data (incl. seeding)."""
        existing = {
            'm | U13 | -50kg': {
                'fighters': [
                    {'Firstname': 'Tom', 'Lastname': 'Kranz', 'Gender': 'm'},
                    {'Firstname': 'Lukas', 'Lastname': 'Brandt', 'Gender': 'm'},
                ],
                'bracket': ['seeded-pairing-from-existing'],  # sentinel
            },
        }
        new = {
            'm | U13 | -50kg': {
                'fighters': [
                    # Same fighters, different order → signature still matches.
                    {'Firstname': 'Lukas', 'Lastname': 'Brandt', 'Gender': 'm'},
                    {'Firstname': 'Tom', 'Lastname': 'Kranz', 'Gender': 'm'},
                ],
                'bracket': [],
            },
        }
        merged = svc._merge_brackets_preserving_age_locks(
            existing_brackets=existing, new_brackets=new, locked_age_classes=set(),
        )
        # The existing seeding sentinel is preserved — the new bracket was skipped.
        assert merged['m | U13 | -50kg']['bracket'] == ['seeded-pairing-from-existing']

    def test_p4_replace_when_fighters_differ(self, svc):
        existing = {
            'm | U13 | -50kg': _bracket(
                ('Tom', 'Kranz', 'm'), ('Lukas', 'Brandt', 'm'),
            ),
        }
        new = {
            'm | U13 | -50kg': _bracket(
                ('Tom', 'Kranz', 'm'),
                ('Different', 'Person', 'm'),  # one fighter changed
            ),
        }
        merged = svc._merge_brackets_preserving_age_locks(
            existing_brackets=existing, new_brackets=new, locked_age_classes=set(),
        )
        names = sorted(f['Lastname'] for f in merged['m | U13 | -50kg']['fighters'])
        assert names == ['Kranz', 'Person']

    def test_unaffected_age_groups_kept(self, svc):
        """A class in an age-group that's *not* touched by the import survives."""
        existing = {
            'm | U13 | -50kg': _bracket(('Tom', 'Kranz', 'm')),
            'w | U18 | -52kg': _bracket(('Anna', 'Müller', 'w')),
        }
        # New import only touches U13.
        new = {'m | U13 | -50kg': _bracket(('Tom', 'Kranz', 'm'))}
        merged = svc._merge_brackets_preserving_age_locks(
            existing_brackets=existing, new_brackets=new, locked_age_classes=set(),
        )
        assert 'w | U18 | -52kg' in merged
