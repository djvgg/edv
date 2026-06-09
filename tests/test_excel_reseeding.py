# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Phase 2 (E2) Excel→DB re-seeding — read/match + single-pool apply.

Isolated SQLite (no Postgres). Mirrors the real models. Verifies that an edited
pool sheet (names reordered) re-maps the existing pool fights' participants from
the new seed order + the canonical `combinations(range(n), 2)` pairing, never
touching pos_in_round/fight_number, and that the pre-start guard blocks a
re-seed once a result exists.
"""

import os
import sys
import tempfile
from itertools import combinations

import pytest
import xlrd
from xlutils.copy import copy as xl_copy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.data.models import Base, Participant, Group, GroupParticipant, Bracket, Fight  # noqa: E402
from backend.services.excel_form_filler import fill_pool_form  # noqa: E402
from backend.services.excel_seeding_reimport import (  # noqa: E402
    apply_pool_reseeding, _gp_display_name, read_id_records, read_edited_seeding,
)

_NAMES = [('Anna', 'Alpha'), ('Bea', 'Beta'), ('Cara', 'Gamma'),
          ('Dina', 'Delta'), ('Ella', 'Epsilon')]


def _make_pool_bracket(db, names=_NAMES):
    g = Group(name='w | U13 | -40kg', gender='w', age_group='U13', weight_class='-40kg')
    db.add(g)
    db.flush()
    gps = []
    for fn, ln in names:
        p = Participant(first_name=fn, last_name=ln)
        db.add(p)
        db.flush()
        gp = GroupParticipant(group_id=g.id, participant_id=p.id)
        db.add(gp)
        db.flush()
        gps.append(gp)
    br = Bracket(group_id=g.id, bracket_type='pools', status='pending')
    db.add(br)
    db.flush()
    pairs = list(combinations(range(len(gps)), 2))
    for pos, (ia, ib) in enumerate(pairs):
        db.add(Fight(bracket_id=br.id, bracket_phase='pool', pos_in_round=pos, pool_index=0,
                     participant1_id=gps[ia].id, participant2_id=gps[ib].id, status='pending'))
    db.commit()
    return g, br, gps


def _export_and_swap(db, g, gps, names, swap=(0, 2)):
    """Export the pool, then swap two visible name cells (operator reorder)."""
    fighters = [{'ID': gp.id, 'Name': f'{names[i][0]} {names[i][1]}', 'Verein': ''}
                for i, gp in enumerate(gps)]
    path = os.path.join(tempfile.gettempdir(), 'reseed_test.xls')
    fill_pool_form(path, [{'pool_name': g.name, 'fighters': fighters}], age_class=g.name)
    recs = read_id_records(path)
    cell = {int(r['slot']): (int(r['sheet']), int(r['row']), int(r['col'])) for r in recs}
    nm = {gp.id: _gp_display_name(gp) for gp in gps}
    order = [gp.id for gp in gps]
    a, b = swap
    rb = xlrd.open_workbook(path, formatting_info=True)
    wb = xl_copy(rb)
    wb.get_sheet(cell[a][0]).write(cell[a][1], cell[a][2], nm[order[b]])
    wb.get_sheet(cell[b][0]).write(cell[b][1], cell[b][2], nm[order[a]])
    wb.save(path)
    return path


@pytest.fixture
def db():
    eng = create_engine('sqlite://')
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


def test_pool_reseeding_applies_name_swap(db):
    g, br, gps = _make_pool_bracket(db)
    order = [gp.id for gp in gps]
    path = _export_and_swap(db, g, gps, _NAMES, swap=(0, 2))

    res = apply_pool_reseeding(path, db=db, commit=True)
    assert res['ok'], res.get('reason')

    expected = order[:]
    expected[0], expected[2] = order[2], order[0]
    pairs = list(combinations(range(len(gps)), 2))
    fights = db.query(Fight).filter_by(bracket_id=br.id).order_by(Fight.pos_in_round).all()
    for f in fights:
        ia, ib = pairs[f.pos_in_round]
        assert (f.participant1_id, f.participant2_id) == (expected[ia], expected[ib])
    # fight_number / pos_in_round untouched
    assert all(f.fight_number is None for f in fights)


def test_pool_reseeding_blocked_after_result(db):
    g, br, gps = _make_pool_bracket(db)
    path = _export_and_swap(db, g, gps, _NAMES, swap=(0, 2))
    first = db.query(Fight).filter_by(bracket_id=br.id).order_by(Fight.pos_in_round).first()
    first.winner_id = first.participant1_id
    db.commit()

    res = apply_pool_reseeding(path, db=db, commit=False)
    assert not res['ok']
    assert 'Ergebnis' in res['reason']


_NAMES6 = _NAMES + [('Finn', 'Zeta')]


def test_double_pool_reseeding_per_pool(db):
    """Double pool (2×3): a swap in pool A re-maps only pool A's fights; the
    per-pool pos_in_round (both pools 0,1,2 with round=NULL) coexist — proving
    the unique constraint doesn't collide on NULL round."""
    # Group + 6 participants
    g = Group(name='m | U15 | -60kg', gender='m', age_group='U15', weight_class='-60kg')
    db.add(g)
    db.flush()
    gps = []
    for fn, ln in _NAMES6:
        p = Participant(first_name=fn, last_name=ln)
        db.add(p)
        db.flush()
        gp = GroupParticipant(group_id=g.id, participant_id=p.id)
        db.add(gp)
        db.flush()
        gps.append(gp)
    br = Bracket(group_id=g.id, bracket_type='double', status='pending')
    db.add(br)
    db.flush()
    # Half-split into 2 pools of 3; per-pool combinations, round=NULL.
    pools = [gps[:3], gps[3:]]
    for pool_idx, pool in enumerate(pools):
        for pos, (ia, ib) in enumerate(combinations(range(len(pool)), 2)):
            db.add(Fight(bracket_id=br.id, bracket_phase='pool', round=None, pos_in_round=pos,
                         pool_index=pool_idx, participant1_id=pool[ia].id,
                         participant2_id=pool[ib].id, status='pending'))
    db.commit()  # must not raise on duplicate (NULL round) — part of the check

    # Export double pool (2 blocks) + swap pool A slot0<->slot2
    fighters_a = [{'ID': gps[i].id, 'Name': f'{_NAMES6[i][0]} {_NAMES6[i][1]}', 'Verein': ''} for i in range(3)]
    fighters_b = [{'ID': gps[i].id, 'Name': f'{_NAMES6[i][0]} {_NAMES6[i][1]}', 'Verein': ''} for i in range(3, 6)]
    path = os.path.join(tempfile.gettempdir(), 'reseed_double.xls')
    fill_pool_form(path, [{'pool_name': 'A', 'fighters': fighters_a},
                          {'pool_name': 'B', 'fighters': fighters_b}], age_class=g.name)
    recs = read_id_records(path)
    cell = {(int(r['block']), int(r['slot'])): (int(r['sheet']), int(r['row']), int(r['col'])) for r in recs}
    nm = {gp.id: _gp_display_name(gp) for gp in gps}
    rb = xlrd.open_workbook(path, formatting_info=True)
    wb = xl_copy(rb)
    wb.get_sheet(cell[(0, 0)][0]).write(cell[(0, 0)][1], cell[(0, 0)][2], nm[gps[2].id])
    wb.get_sheet(cell[(0, 2)][0]).write(cell[(0, 2)][1], cell[(0, 2)][2], nm[gps[0].id])
    wb.save(path)

    res = apply_pool_reseeding(path, db=db, commit=True)
    assert res['ok'], res.get('reason')

    expected_a = [gps[2].id, gps[1].id, gps[0].id]  # pool A slot0<->slot2 swapped
    expected_b = [gps[3].id, gps[4].id, gps[5].id]  # pool B unchanged
    pairs = list(combinations(range(3), 2))
    for f in db.query(Fight).filter_by(bracket_id=br.id).all():
        exp = expected_a if f.pool_index == 0 else expected_b
        ia, ib = pairs[f.pos_in_round]
        assert (f.participant1_id, f.participant2_id) == (exp[ia], exp[ib]), (f.pool_index, f.pos_in_round)


def test_read_edited_seeding_reflects_swap(db):
    g, br, gps = _make_pool_bracket(db)
    order = [gp.id for gp in gps]
    path = _export_and_swap(db, g, gps, _NAMES, swap=(0, 2))
    id_to_name = {gp.id: _gp_display_name(gp) for gp in gps}
    seeding = read_edited_seeding(path, id_to_name)
    assert seeding['new_seed'][(0, 0)] == order[2]
    assert seeding['new_seed'][(0, 2)] == order[0]
    assert not seeding['unmatched'] and not seeding['ambiguous']


def _make_ko_bracket(db, n):
    g = Group(name='m | U15 | -73kg', gender='m', age_group='U15', weight_class='-73kg')
    db.add(g); db.flush()
    gps = []
    for i in range(n):
        p = Participant(first_name=f'V{i}', last_name=f'N{i}'); db.add(p); db.flush()
        gp = GroupParticipant(group_id=g.id, participant_id=p.id); db.add(gp); db.flush()
        gps.append(gp)
    br = Bracket(group_id=g.id, bracket_type='ko', status='pending'); db.add(br); db.flush()
    size = 1
    while size < n:
        size *= 2
    los = [gps[i].id if i < n else None for i in range(size)]
    for p in range(size // 2):
        a, b = los[2 * p], los[2 * p + 1]
        if a is None and b is None:
            continue
        if a is None or b is None:
            r = a or b
            db.add(Fight(bracket_id=br.id, bracket_phase='wb', round=0, pos_in_round=p,
                         participant1_id=r, participant2_id=r, status='bye', winner_id=r))
        else:
            db.add(Fight(bracket_id=br.id, bracket_phase='wb', round=0, pos_in_round=p,
                         participant1_id=a, participant2_id=b, status='pending'))
    db.commit()
    return g, br, gps


def _export_swap_ko(db, g, gps, n, swap):
    from backend.services.excel_form_filler import fill_ko_form
    fighters = [{'ID': gps[i].id, 'Name': f'V{i} N{i}', 'Verein': ''} for i in range(n)]
    path = os.path.join(tempfile.gettempdir(), 'ko_reseed_test.xls')
    fill_ko_form(path, fighters, age_class=g.name)
    recs = read_id_records(path)
    cell = {int(r['slot']): (int(r['sheet']), int(r['row']), int(r['col']))
            for r in recs if str(r.get('participant_id')) != ''}
    nm = {gps[i].id: _gp_display_name(gps[i]) for i in range(n)}
    a, b = swap
    rb = xlrd.open_workbook(path, formatting_info=True)
    wb = xl_copy(rb)
    wb.get_sheet(cell[a][0]).write(cell[a][1], cell[a][2], nm[gps[b].id])
    wb.get_sheet(cell[b][0]).write(cell[b][1], cell[b][2], nm[gps[a].id])
    wb.save(path)
    return path


def test_ko_reseeding_rebuilds_round0(db):
    from backend.services.excel_seeding_reimport import apply_ko_reseeding
    g, br, gps = _make_ko_bracket(db, 8)
    path = _export_swap_ko(db, g, gps, 8, (0, 2))  # swap Los1 <-> Los3
    res = apply_ko_reseeding(path, db=db, commit=True)
    assert res['ok'], res.get('reason')
    f = (db.query(Fight).filter_by(bracket_id=br.id, bracket_phase='wb', round=0)
         .order_by(Fight.pos_in_round).all())
    pairs = {x.pos_in_round: (x.participant1_id, x.participant2_id) for x in f}
    assert pairs[0] == (gps[2].id, gps[1].id)   # adjacent pairing, Los0<->Los2 swapped
    assert pairs[1] == (gps[0].id, gps[3].id)
    assert all(x.fight_number is None for x in f)  # regenerate resets fight_number (pre-start)


def test_ko_reseeding_blocked_after_result(db):
    from backend.services.excel_seeding_reimport import apply_ko_reseeding
    g, br, gps = _make_ko_bracket(db, 8)
    path = _export_swap_ko(db, g, gps, 8, (0, 2))
    first = db.query(Fight).filter_by(bracket_id=br.id).order_by(Fight.pos_in_round).first()
    first.winner_id = first.participant1_id
    first.status = 'finished'
    db.commit()
    res = apply_ko_reseeding(path, db=db, commit=False)
    assert not res['ok'] and 'Ergebnis' in res['reason']
