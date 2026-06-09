# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""edv-Spiegel des Pool-Tiebreakers (Decision 2026-06-08, CLAUDE.md).

Muss bit-identisch zu JF `main._compute_pool_standings` sein: Siege →
Subgruppen-H2H → stabile gp.id (Los); Punkte zählen NICHT. Isoliertes SQLite.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.data.models import Base, Bracket, Fight  # noqa: E402
from backend.services.tournament_service import TournamentService  # noqa: E402


@pytest.fixture
def db():
    eng = create_engine('sqlite://')
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _add(s, bid, pos, p1, p2, winner, s1, s2):
    s.add(Fight(bracket_id=bid, bracket_phase='pool', round=None, pos_in_round=pos,
                pool_index=0, participant1_id=p1, participant2_id=p2,
                score1=s1, score2=s2, winner_id=winner, status='finished'))


def test_h2h_beats_points(db):
    bid = 1
    db.add(Bracket(id=bid, group_id=1, bracket_type='pools', status='pending'))
    _add(db, bid, 0, 1, 3, 1, 100, 0)
    _add(db, bid, 1, 1, 4, 1, 100, 0)
    _add(db, bid, 2, 2, 1, 2, 1, 0)   # 2 schlägt 1
    _add(db, bid, 3, 2, 3, 2, 1, 0)
    _add(db, bid, 4, 3, 4, 3, 1, 0)
    _add(db, bid, 5, 4, 2, 4, 1, 0)
    db.commit()
    order = TournamentService(db).compute_pool_standings(bid)
    assert order[0] == 2 and order[1] == 1, order   # H2H schlägt Punkte
    assert set(order[2:]) == {3, 4}


def test_three_way_circle_falls_to_id(db):
    bid = 2
    db.add(Bracket(id=bid, group_id=1, bracket_type='pools', status='pending'))
    _add(db, bid, 0, 1, 2, 1, 10, 0)
    _add(db, bid, 1, 2, 3, 2, 10, 0)
    _add(db, bid, 2, 1, 3, 3, 0, 10)
    db.commit()
    assert TournamentService(db).compute_pool_standings(bid) == [1, 2, 3]


def test_transitive_pool(db):
    bid = 3
    db.add(Bracket(id=bid, group_id=1, bracket_type='pools', status='pending'))
    _add(db, bid, 0, 1, 2, 1, 10, 0)
    _add(db, bid, 1, 1, 3, 1, 10, 0)
    _add(db, bid, 2, 2, 3, 2, 10, 0)
    db.commit()
    assert TournamentService(db).compute_pool_standings(bid) == [1, 2, 3]
