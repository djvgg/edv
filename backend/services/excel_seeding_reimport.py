# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Phase 2 (E2) — read an edited Excel form back to a new seeding.

The operator reorders the participant NAMES in the slot rows of an exported
pool/KO sheet (Merlin's choice 2026-06-04). This module reads such a sheet and
derives the new seed order, matched to ``participant_id`` — **scoped to the one
bracket** (the hidden ``_ids`` sheet from the export yields the bracket's
participant-id set; we match the reordered visible names against that small set).
See the Excel-roundtrip invariant in WSP/CLAUDE.md.

This is the read/match foundation. Applying the new seeding to the DB (recompute
the pool fights' participant ids / regenerate the KO tree) is the separate apply
step — see `inbox/wsp-coder/edv-excel-reseeding-apply.md`.
"""

from itertools import combinations
from typing import Any, Dict, List, Optional

import xlrd

ID_SHEET = '_ids'
_FREILOS = 'freilos'


def _norm(value: Any) -> str:
    """Whitespace-collapsed, case-folded name for tolerant comparison."""
    return ' '.join(str(value or '').split()).casefold()


def read_id_records(path: str) -> Optional[List[Dict[str, Any]]]:
    """Return the hidden ``_ids`` records as dicts, or None if absent."""
    wb = xlrd.open_workbook(path)
    if ID_SHEET not in wb.sheet_names():
        return None
    sh = wb.sheet_by_name(ID_SHEET)
    if sh.nrows < 2:
        return []
    header = [str(sh.cell_value(0, c)) for c in range(sh.ncols)]
    return [
        {header[c]: sh.cell_value(r, c) for c in range(sh.ncols)}
        for r in range(1, sh.nrows)
    ]


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def read_edited_seeding(path: str, id_to_name: Dict[int, str]) -> Optional[Dict[str, Any]]:
    """Derive the new seeding from an edited sheet.

    Args:
        path: the edited .xls (must carry the hidden ``_ids`` sheet).
        id_to_name: ``{participant_id -> display name}`` for THIS bracket's
            participants (caller builds it from the `_ids` id set via the DB,
            formatting names exactly like the export does — "Nachname, Vorname").

    Returns ``{bracket, kind, new_seed: {(block, slot) -> participant_id|None},
    unmatched: [((block, slot), name)], ambiguous: [((block, slot), name, [ids])]}``
    or None if the sheet has no ``_ids`` region. ``block`` is the pool index for
    double pools (0 for single pool / KO).
    """
    records = read_id_records(path)
    if not records:
        return None

    wb = xlrd.open_workbook(path)

    name_to_ids: Dict[str, List[int]] = {}
    for pid, name in id_to_name.items():
        name_to_ids.setdefault(_norm(name), []).append(pid)

    new_seed: Dict[Any, Optional[int]] = {}
    unmatched: List[Any] = []
    ambiguous: List[Any] = []
    bracket = records[0].get('bracket')
    kind = records[0].get('kind')

    for rec in records:
        slot = _as_int(rec.get('slot'))
        block = _as_int(rec.get('block')) or 0
        si, row, col = _as_int(rec.get('sheet')), _as_int(rec.get('row')), _as_int(rec.get('col'))
        if slot is None or si is None or row is None or col is None:
            continue
        key = (block, slot)
        visible = wb.sheet_by_index(si).cell_value(row, col)
        norm = _norm(visible)
        if not norm or norm == _FREILOS:
            new_seed[key] = None
            continue
        ids = name_to_ids.get(norm, [])
        if len(ids) == 1:
            new_seed[key] = ids[0]
        elif not ids:
            unmatched.append((key, str(visible)))
            new_seed[key] = None
        else:
            # Identical name within the bracket: tie-break to the original
            # participant at this slot if it's a candidate, else flag (never
            # silently guess).
            orig = _as_int(rec.get('participant_id'))
            if orig in ids:
                new_seed[key] = orig
            else:
                ambiguous.append((key, str(visible), ids))
                new_seed[key] = ids[0]

    return {
        'bracket': bracket,
        'kind': kind,
        'new_seed': new_seed,
        'unmatched': unmatched,
        'ambiguous': ambiguous,
    }


# ---------------------------------------------------------------------------
# Apply step (single pool) — write the re-seeding to the DB.
# ---------------------------------------------------------------------------

def _gp_display_name(gp) -> str:
    """Format a GroupParticipant's name exactly like the export
    (`_format_name(..., 'name')` = "Nachname, Vorname"), so the matcher lines up."""
    from backend.services.excel_form_filler import _format_name
    p = gp.participant
    full = f"{(getattr(p, 'first_name', '') or '').strip()} {(getattr(p, 'last_name', '') or '').strip()}".strip()
    return _format_name({'Name': full}, 'name')


def apply_pool_reseeding(xls_path: str, db=None, commit: bool = False) -> Dict[str, Any]:
    """Apply an edited SINGLE-pool sheet's name reorder to the DB as a re-seed.

    Re-maps each existing pool fight's participant ids from the new seed order +
    the canonical position-pairing (`combinations(range(n), 2)`, mirroring
    `tournament_service._build_pool_pairs`). NEVER touches `fight_number`,
    `pos_in_round` or the schedule pattern. Pre-start only.

    Returns a result dict: ``{ok, reason?, bracket?, changes?, committed?, n?}``.
    With ``commit=False`` it only computes the diff (for a confirmation dialog).
    """
    from backend.data.database import SessionLocal
    from backend.data.models import Group, Bracket, GroupParticipant, Fight

    own = db is None
    if own:
        db = SessionLocal()
    try:
        records = read_id_records(xls_path)
        if not records:
            return {'ok': False, 'reason': 'Keine _ids-Region — kein edv-Export?'}
        bracket_name = records[0].get('bracket')
        kind = records[0].get('kind')
        if kind != 'pool':
            return {'ok': False, 'reason': f'Nur Einzel-Pool-Re-Seeding hier (kind={kind!r}); KO später'}

        group = db.query(Group).filter_by(name=bracket_name).one_or_none()
        if group is None:
            return {'ok': False, 'reason': f'Gruppe nicht gefunden: {bracket_name!r}'}
        bracket = db.query(Bracket).filter_by(group_id=group.id).one_or_none()
        if bracket is None:
            return {'ok': False, 'reason': f'Bracket nicht gefunden für {bracket_name!r}'}
        if bracket.bracket_type not in ('pools', 'double'):
            return {'ok': False, 'reason': f'Nur Pool/Doppelpool (bracket_type={bracket.bracket_type!r}); KO später'}

        fights = (db.query(Fight)
                  .filter_by(bracket_id=bracket.id, bracket_phase='pool')
                  .order_by(Fight.pos_in_round).all())
        if not fights:
            return {'ok': False, 'reason': 'keine Pool-Kämpfe im Bracket'}

        # Pre-start guard: no recorded results anywhere in the bracket.
        played = [f for f in fights
                  if f.winner_id is not None or f.score1 is not None or f.score2 is not None
                  or (f.status or 'pending') not in ('pending',)]
        if played:
            return {'ok': False,
                    'reason': f'{len(played)} Kampf/Kämpfe haben schon Ergebnisse — Re-Seeding nur vor dem ersten Kampf'}

        gps = db.query(GroupParticipant).filter_by(group_id=group.id).all()
        id_to_name = {gp.id: _gp_display_name(gp) for gp in gps}
        seeding = read_edited_seeding(xls_path, id_to_name)
        if seeding is None:
            return {'ok': False, 'reason': 'Seeding nicht lesbar'}
        if seeding['unmatched'] or seeding['ambiguous']:
            return {'ok': False, 'reason': 'Namen nicht eindeutig zuordenbar — bitte manuell prüfen',
                    'unmatched': seeding['unmatched'], 'ambiguous': seeding['ambiguous']}

        new_seed = seeding['new_seed']  # {(block, slot) -> gp.id}

        # Group fights by pool (pool_index None → single pool 0). Each pool is a
        # round-robin whose pos_in_round indexes combinations(range(n_pool), 2)
        # — exactly what tournament_service._build_pool_pairs produced. The
        # export's `block` == pool_index (double-pool half-split matches
        # split_into_pools), so new_seed[(pool, slot)] gives the new occupant.
        fights_by_pool: Dict[int, List[Any]] = {}
        for f in fights:
            fights_by_pool.setdefault(f.pool_index if f.pool_index is not None else 0, []).append(f)

        changes: List[Dict[str, Any]] = []
        for pool, pool_fights in fights_by_pool.items():
            slots = [s for (b, s) in new_seed if b == pool]
            if not slots:
                return {'ok': False, 'reason': f'keine Seeding-Daten für Pool {pool}'}
            n_pool = max(slots) + 1
            pairs = list(combinations(range(n_pool), 2))
            if n_pool == 2:
                pairs = pairs * 3
            if len(pool_fights) != len(pairs):
                return {'ok': False,
                        'reason': f'Pool {pool}: Struktur passt nicht (n={n_pool} → {len(pairs)} Kämpfe erwartet, {len(pool_fights)} gefunden)'}
            for f in sorted(pool_fights, key=lambda x: (x.pos_in_round if x.pos_in_round is not None else 0)):
                p = f.pos_in_round
                if p is None or p >= len(pairs):
                    return {'ok': False, 'reason': f'Pool {pool}: pos {p} außerhalb des Schedules (n={n_pool})'}
                ia, ib = pairs[p]
                new_p1, new_p2 = new_seed.get((pool, ia)), new_seed.get((pool, ib))
                if (new_p1, new_p2) != (f.participant1_id, f.participant2_id):
                    changes.append({'pos': p, 'pool': pool, 'fight_id': f.id,
                                    'old': (f.participant1_id, f.participant2_id),
                                    'new': (new_p1, new_p2)})
                if commit:
                    f.participant1_id = new_p1
                    f.participant2_id = new_p2
        n = len(gps)
        if commit:
            db.commit()
        return {'ok': True, 'bracket': bracket_name, 'committed': commit, 'n': n,
                'changes': changes, 'names': id_to_name}
    finally:
        if own:
            db.close()


# ---------------------------------------------------------------------------
# Apply step (KO / Doppel-KO) — emergency manual override (regenerate r0).
# ---------------------------------------------------------------------------

def apply_ko_reseeding(xls_path: str, db=None, commit: bool = False) -> Dict[str, Any]:
    """Emergency manual KO/Doppel-KO re-seed from an edited sheet (Merlin 2026-06-04).

    The operator reorders names across the Los positions in the exported KO sheet
    to override edv's auto club-balanced snake seeding. We rebuild the WB round-0
    pairing **positionally** (adjacent Los: pos p = Los[2p] vs Los[2p+1], the
    binary-tree layout JF expects) from the new order, then DELETE the bracket's
    fights and recreate round 0 — mirroring tournament_service's bye handling
    (real-vs-Freilos → `p1==p2` bye + auto-winner; Freilos-vs-Freilos → skipped).

    **Pre-start only.** This resets `fight_number`/`table_id` for the bracket
    (accepted: pre-start, no order/results to lose; re-assign the mat afterward).
    JF re-derives the eager tree + loser bracket on next load.

    Returns ``{ok, reason?, bracket?, committed?, size?, pairs?}``.
    """
    from backend.data.database import SessionLocal
    from backend.data.models import Group, Bracket, GroupParticipant, Fight

    own = db is None
    if own:
        db = SessionLocal()
    try:
        records = read_id_records(xls_path)
        if not records:
            return {'ok': False, 'reason': 'Keine _ids-Region — kein edv-Export?'}
        if records[0].get('kind') != 'ko':
            return {'ok': False, 'reason': f"Kein KO-Bogen (kind={records[0].get('kind')!r})"}
        bracket_name = records[0].get('bracket')

        group = db.query(Group).filter_by(name=bracket_name).one_or_none()
        if group is None:
            return {'ok': False, 'reason': f'Gruppe nicht gefunden: {bracket_name!r}'}
        bracket = db.query(Bracket).filter_by(group_id=group.id).one_or_none()
        if bracket is None:
            return {'ok': False, 'reason': f'Bracket nicht gefunden für {bracket_name!r}'}
        if bracket.bracket_type not in ('ko', 'special'):
            return {'ok': False, 'reason': f'Kein KO-Bracket (bracket_type={bracket.bracket_type!r})'}

        all_fights = db.query(Fight).filter_by(bracket_id=bracket.id).all()
        played = [f for f in all_fights
                  if f.winner_id is not None or f.score1 is not None or f.score2 is not None
                  or (f.status or 'pending') not in ('pending', 'bye')]
        if played:
            return {'ok': False,
                    'reason': f'{len(played)} Kampf/Kämpfe haben schon Ergebnisse — Re-Seeding nur vor dem ersten Kampf'}

        gps = db.query(GroupParticipant).filter_by(group_id=group.id).all()
        id_to_name = {gp.id: _gp_display_name(gp) for gp in gps}
        seeding = read_edited_seeding(xls_path, id_to_name)
        if seeding is None:
            return {'ok': False, 'reason': 'Seeding nicht lesbar'}
        if seeding['unmatched'] or seeding['ambiguous']:
            return {'ok': False, 'reason': 'Namen nicht eindeutig zuordenbar — bitte manuell prüfen',
                    'unmatched': seeding['unmatched'], 'ambiguous': seeding['ambiguous']}

        new_seed = seeding['new_seed']  # {(0, Los-1) -> gp.id|None}
        slots = [s for (b, s) in new_seed if b == 0]
        if not slots:
            return {'ok': False, 'reason': 'keine Los-Daten im Bogen'}
        size = max(slots) + 1
        los_gp = [new_seed.get((0, s)) for s in range(size)]  # gp.id or None (=Freilos)

        # WB round-0 rows from adjacent Los pairs (binary-tree layout).
        new_rows = []           # (pos, p1, p2, status, winner)
        for p in range(size // 2):
            a, b = los_gp[2 * p], los_gp[2 * p + 1]
            if a is None and b is None:
                continue                                   # phantom (Freilos vs Freilos) → skipped
            if a is None or b is None:                     # bye
                real = a if a is not None else b
                new_rows.append((p, real, real, 'bye', real))
            else:
                new_rows.append((p, a, b, 'pending', None))

        def nm(pid):
            return id_to_name.get(pid, f"#{pid}") if pid is not None else "Freilos"

        preview = [{'pos': pos, 'p1': nm(p1), 'p2': ('Freilos' if status == 'bye' else nm(p2)),
                    'bye': status == 'bye'} for pos, p1, p2, status, _w in new_rows]

        if commit:
            for f in all_fights:
                db.delete(f)
            db.flush()
            for pos, p1, p2, status, winner in new_rows:
                db.add(Fight(bracket_id=bracket.id, bracket_phase='wb', round=0,
                             pos_in_round=pos, pool_index=None,
                             participant1_id=p1, participant2_id=p2,
                             status=status, winner_id=winner))
            db.commit()

        return {'ok': True, 'bracket': bracket_name, 'committed': commit,
                'size': size, 'pairs': len(new_rows), 'names': id_to_name, 'preview': preview}
    finally:
        if own:
            db.close()
