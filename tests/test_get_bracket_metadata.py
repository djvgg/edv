# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""P2 — Test TournamentService.get_bracket_metadata against an in-memory DB.

Uses SQLite to avoid touching production Postgres. The Base + ORM models
are reused as-is, only the engine is swapped.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.data.database import Base
from backend.data.models import Group, Mat, Bracket
from backend.services.tournament_service import TournamentService


@pytest.fixture
def session():
    """Fresh in-memory SQLite DB with all tables for each test."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _seed(db, items):
    """Bulk-add ORM instances + commit."""
    db.add_all(items)
    db.commit()


class TestGetBracketMetadata:
    def test_empty_db_returns_empty_dict(self, session):
        svc = TournamentService(session)
        assert svc.get_bracket_metadata() == {}

    def test_bracket_with_mat_assignment(self, session):
        group = Group(
            name='m | U13 | -50kg',
            gender='m', age_group='U13', weight_class='-50kg',
        )
        mat = Mat(mat_number=1)
        _seed(session, [group, mat])

        bracket = Bracket(group_id=group.id, mat_id=mat.id, bracket_type='ko')
        _seed(session, [bracket])

        svc = TournamentService(session)
        result = svc.get_bracket_metadata()

        assert 'm | U13 | -50kg' in result
        assert result['m | U13 | -50kg'] == {
            'mat_number': 1, 'bracket_type': 'ko',
        }

    def test_bracket_without_mat(self, session):
        """Bracket exists, but no mat assigned yet — mat_number is None."""
        group = Group(
            name='w | U18 | -52kg',
            gender='w', age_group='U18', weight_class='-52kg',
        )
        _seed(session, [group])
        bracket = Bracket(group_id=group.id, mat_id=None, bracket_type='double')
        _seed(session, [bracket])

        svc = TournamentService(session)
        result = svc.get_bracket_metadata()
        assert result['w | U18 | -52kg'] == {
            'mat_number': None, 'bracket_type': 'double',
        }

    def test_multiple_brackets_returned(self, session):
        g1 = Group(name='m | U13 | -50kg', gender='m', age_group='U13', weight_class='-50kg')
        g2 = Group(name='w | U18 | -52kg', gender='w', age_group='U18', weight_class='-52kg')
        mat = Mat(mat_number=2)
        _seed(session, [g1, g2, mat])
        _seed(session, [
            Bracket(group_id=g1.id, mat_id=mat.id, bracket_type='ko'),
            Bracket(group_id=g2.id, mat_id=None, bracket_type='double'),
        ])

        svc = TournamentService(session)
        result = svc.get_bracket_metadata()
        assert len(result) == 2
        assert result['m | U13 | -50kg']['mat_number'] == 2
        assert result['w | U18 | -52kg']['bracket_type'] == 'double'

    def test_non_standard_group_name_skipped(self, session):
        """Groups without the canonical 3-part key are skipped (no crash)."""
        g1 = Group(name='m | U13 | -50kg', gender='m', age_group='U13', weight_class='-50kg')
        g2 = Group(name='QUARANTINE', gender=None, age_group=None, weight_class=None)
        _seed(session, [g1, g2])
        _seed(session, [
            Bracket(group_id=g1.id, bracket_type='ko'),
            Bracket(group_id=g2.id, bracket_type='quarantine'),
        ])

        svc = TournamentService(session)
        result = svc.get_bracket_metadata()
        # Only the standard one comes through.
        assert list(result.keys()) == ['m | U13 | -50kg']
