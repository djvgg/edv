# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for TournamentConfigScreen._apply_tolerances_to_existing_brackets.

We test the *logic* without instantiating Tk widgets. The screen is
created via __new__ + manual attribute injection, so the real __init__
(which builds a UI) is skipped. Only the pure re-bucketing method is
exercised.
"""

from types import SimpleNamespace

import pytest

from frontend.views.tournament_config_screen import TournamentConfigScreen


class _FakeConfigRepo:
    """Minimal config_repo that maps weight → weight class for w/18+ tests.

    We mimic real classes: -52, -57, -63, -70, -78, +78 (only the ones used).
    """
    def get_weight_class(self, weight, gender, age_group):
        if weight is None or weight <= 0:
            return 'unknown'
        for max_w, label in [(52, '-52kg'), (57, '-57kg'), (63, '-63kg'),
                             (70, '-70kg'), (78, '-78kg')]:
            if weight <= max_w:
                return label
        return '+78kg'


def _make_screen(brackets, tolerances=None, locked=None, monkeypatch=None):
    """Construct a TournamentConfigScreen without running its Tk __init__."""
    screen = TournamentConfigScreen.__new__(TournamentConfigScreen)
    screen.logger = SimpleNamespace(
        info=lambda *a, **k: None, debug=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )
    screen.main_window = SimpleNamespace(
        brackets=brackets,
        tolerances=tolerances or {},
        locked_age_classes=set(locked or []),
    )
    # Monkey-patch the ConfigRepository import inside the method.
    import frontend.views.tournament_config_screen as mod
    monkeypatch.setattr(mod, 'ConfigRepository', lambda *_a, **_kw: _FakeConfigRepo())
    return screen


def _fighter(first, last, weight):
    return {'Firstname': first, 'Lastname': last, 'Gender': 'w', 'Weight': weight}


class TestApplyTolerances:
    def test_no_tolerance_no_move(self, monkeypatch):
        brackets = {
            'w | 18+ | -78kg': {'fighters': [_fighter('A', 'X', 77.5)], 'bracket': ['x']},
        }
        screen = _make_screen(brackets, tolerances={}, monkeypatch=monkeypatch)
        moved = screen._apply_tolerances_to_existing_brackets()
        assert moved == 0
        # Seeding sentinel preserved when nothing moved.
        assert brackets['w | 18+ | -78kg']['bracket'] == ['x']

    def test_fighter_drops_into_lower_class(self, monkeypatch):
        """78.9kg in +78 — tolerance 1kg → 77.9 → must drop to -78kg."""
        brackets = {
            'w | 18+ | +78kg': {
                'fighters': [_fighter('Lena', 'Bauer', 78.9)],
                'bracket': ['seed'],
            },
        }
        screen = _make_screen(
            brackets, tolerances={('w', '18+'): 1.0}, monkeypatch=monkeypatch,
        )
        moved = screen._apply_tolerances_to_existing_brackets()
        assert moved == 1
        assert 'w | 18+ | -78kg' in brackets
        names = [f['Lastname'] for f in brackets['w | 18+ | -78kg']['fighters']]
        assert 'Bauer' in names
        # Source bracket lost the fighter.
        assert not any(
            f['Lastname'] == 'Bauer'
            for f in brackets['w | 18+ | +78kg'].get('fighters', [])
        )
        # Seeding invalidated for both source and target.
        assert brackets['w | 18+ | +78kg']['bracket'] == []
        assert brackets['w | 18+ | -78kg']['bracket'] == []

    def test_fighter_stays_when_class_unchanged(self, monkeypatch):
        """65kg in -70 — tolerance 1kg → 64 → still -70 (since -63kg max=63)."""
        brackets = {
            'w | 18+ | -70kg': {
                'fighters': [_fighter('A', 'X', 65)],
                'bracket': ['seed'],
            },
        }
        screen = _make_screen(
            brackets, tolerances={('w', '18+'): 1.0}, monkeypatch=monkeypatch,
        )
        assert screen._apply_tolerances_to_existing_brackets() == 0
        assert brackets['w | 18+ | -70kg']['bracket'] == ['seed']

    def test_locked_age_class_not_moved(self, monkeypatch):
        """A locked age class is skipped — even if tolerance would move a fighter."""
        brackets = {
            'w | 18+ | +78kg': {'fighters': [_fighter('A', 'X', 78.9)], 'bracket': ['s']},
        }
        screen = _make_screen(
            brackets, tolerances={('w', '18+'): 1.0},
            locked={'18+'},  # locked!
            monkeypatch=monkeypatch,
        )
        assert screen._apply_tolerances_to_existing_brackets() == 0

    def test_quarantine_skipped(self, monkeypatch):
        brackets = {
            'QUARANTINE_unpaid': {'fighters': [_fighter('A', 'X', 78.9)], 'bracket': []},
        }
        screen = _make_screen(
            brackets, tolerances={('w', '18+'): 1.0}, monkeypatch=monkeypatch,
        )
        assert screen._apply_tolerances_to_existing_brackets() == 0
        # Quarantine bucket untouched.
        assert brackets['QUARANTINE_unpaid']['fighters'][0]['Lastname'] == 'X'

    def test_multiple_fighters_one_moves(self, monkeypatch):
        brackets = {
            'w | 18+ | +78kg': {
                'fighters': [
                    _fighter('Heavy', 'Big', 85),       # stays
                    _fighter('Light', 'Small', 78.9),   # moves
                ],
                'bracket': ['seed'],
            },
        }
        screen = _make_screen(
            brackets, tolerances={('w', '18+'): 1.0}, monkeypatch=monkeypatch,
        )
        moved = screen._apply_tolerances_to_existing_brackets()
        assert moved == 1
        # Heavy remains, Light moved.
        remaining = [f['Lastname'] for f in brackets['w | 18+ | +78kg']['fighters']]
        assert remaining == ['Big']
        assert any(
            f['Lastname'] == 'Small'
            for f in brackets['w | 18+ | -78kg']['fighters']
        )
