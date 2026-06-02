# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""The official DJB Doppel-KO forms are the authoritative fight-order oracle.

These tests decode ``backend/services/templates/ko_{8,16,32}.xls`` back into a
Kampffolge graph (see ``ko_form_decoder``) and assert that the order the suite
*fights* matches the order the printed form *prescribes*. The same canonical
structure is implemented live in JudgeFrontend's ``_LB_STRUCTURE`` /
``_drop_loser_to_lb`` / ``_advance_lb_winner`` (its own tests assert the seed
pairings); decoding the form here pins that structure to its paper source, so a
swapped template or a silent structure change is caught on the spot.

The decoder needs ``xlrd < 2.0`` (the edv venv has 1.2). Cross-repo note: the
JudgeFrontend venv ships xlrd 2.0 and cannot read these .xls forms — which is
why the Excel-order oracle lives here in edv, next to the templates.
"""

from ko_form_decoder import decode_form, realised_order


# ── Canonical feeder graphs decoded from the forms ───────────────────────────
# feeder = ('los', n) | ('W', kf) winner-of | ('L', kf) loser-of.

CANONICAL_8 = {
    1: (("los", 1), ("los", 5)),
    2: (("los", 3), ("los", 7)),
    3: (("los", 2), ("los", 6)),
    4: (("los", 4), ("los", 8)),
    5: (("L", 1), ("L", 2)),          # Trostrunde: R0 losers, top half
    6: (("L", 3), ("L", 4)),          # Trostrunde: R0 losers, bottom half
    7: (("W", 1), ("W", 2)),          # semifinal top
    8: (("W", 3), ("W", 4)),          # semifinal bottom
    9: (("W", 5), ("L", 8)),          # bronze — winner(TR top) vs loser(SF BOTTOM): CROSS
    10: (("W", 6), ("L", 7)),         # bronze — winner(TR bottom) vs loser(SF TOP): CROSS
    11: (("W", 7), ("W", 8)),         # final
}

CANONICAL_16 = {
    1: (("los", 1), ("los", 9)),
    2: (("los", 5), ("los", 13)),
    3: (("los", 3), ("los", 11)),
    4: (("los", 7), ("los", 15)),
    5: (("los", 2), ("los", 10)),
    6: (("los", 6), ("los", 14)),
    7: (("los", 4), ("los", 12)),
    8: (("los", 8), ("los", 16)),
    9: (("W", 1), ("W", 2)),          # quarterfinals
    10: (("W", 3), ("W", 4)),
    11: (("W", 5), ("W", 6)),
    12: (("W", 7), ("W", 8)),
    13: (("L", 1), ("L", 2)),         # LB round 0: R0 losers paired
    14: (("L", 3), ("L", 4)),
    15: (("L", 5), ("L", 6)),
    16: (("L", 7), ("L", 8)),
    17: (("W", 13), ("L", 11)),       # LB round 1: QF loser enters CROSSED (p^2)
    18: (("W", 14), ("L", 12)),
    19: (("W", 15), ("L", 9)),
    20: (("W", 16), ("L", 10)),
    21: (("W", 9), ("W", 10)),        # semifinals
    22: (("W", 11), ("W", 12)),
    23: (("W", 17), ("W", 18)),       # LB round 2: merge
    24: (("W", 19), ("W", 20)),
    25: (("W", 23), ("L", 21)),       # bronze — SF loser, pos-preserving (cross was at r1)
    26: (("W", 24), ("L", 22)),
    27: (("W", 21), ("W", 22)),       # final
}

# Order actually fought when the lower Los always wins: (kf, (los_a, los_b)).
REALISED_8 = [
    (1, (1, 5)), (2, (3, 7)), (3, (2, 6)), (4, (4, 8)),
    (5, (5, 7)), (6, (6, 8)), (7, (1, 3)), (8, (2, 4)),
    (9, (5, 4)), (10, (6, 3)), (11, (1, 2)),
]

REALISED_16 = [
    (1, (1, 9)), (2, (5, 13)), (3, (3, 11)), (4, (7, 15)),
    (5, (2, 10)), (6, (6, 14)), (7, (4, 12)), (8, (8, 16)),
    (9, (1, 5)), (10, (3, 7)), (11, (2, 6)), (12, (4, 8)),
    (13, (9, 13)), (14, (11, 15)), (15, (10, 14)), (16, (12, 16)),
    (17, (9, 6)), (18, (11, 8)), (19, (10, 5)), (20, (12, 7)),
    (21, (1, 3)), (22, (2, 4)), (23, (6, 8)), (24, (5, 7)),
    (25, (6, 3)), (26, (5, 4)), (27, (1, 2)),
]


# ── 8er ──────────────────────────────────────────────────────────────────────

def test_8er_form_matches_canonical_structure():
    assert decode_form(8) == CANONICAL_8


def test_8er_realised_fight_order():
    assert realised_order(decode_form(8)) == REALISED_8


def test_8er_bronze_pairing_is_crossed():
    """Each bronze takes the loser of the OTHER half's semifinal (judo cross)."""
    g = decode_form(8)
    assert g[9] == (("W", 5), ("L", 8))   # TR-top winner vs SF-bottom loser
    assert g[10] == (("W", 6), ("L", 7))  # TR-bottom winner vs SF-top loser


# ── 16er ─────────────────────────────────────────────────────────────────────

def test_16er_form_matches_canonical_structure():
    assert decode_form(16) == CANONICAL_16


def test_16er_realised_fight_order():
    assert realised_order(decode_form(16)) == REALISED_16


def test_16er_repechage_entry_is_crossed():
    """QF loser pos p enters LB round 1 at pos p^2 (half-swap cross)."""
    g = decode_form(16)
    # lb r1 fights are Kf17..20; their loser-feeder is the crossed QF loser.
    qf_loser = {17: ("L", 11), 18: ("L", 12), 19: ("L", 9), 20: ("L", 10)}
    for kf, feeder in qf_loser.items():
        assert feeder in g[kf], f"Kf{kf} should pull crossed QF loser {feeder}"


# ── 32er ──────────────────────────────────────────────────────────────────────
# The 32er form differs structurally from 8er/16er: the two Trostrunde champions
# fold BACK into the medal round (Kf59/60) against the WB semifinal winners.
# Losers of Kf59/60 take bronze; winners go to the final. Losers of the LB
# semifinals Kf57/58 take 5th. Confirmed off the physical sheet by Merlin
# (2026-06-02). The backward connector lines are encoded as decoder feedback
# edges (ko_form_decoder._FEEDBACK_EDGES); everything else is read from the form.

CANONICAL_32 = {
    1: (("los", 1), ("los", 17)), 2: (("los", 9), ("los", 25)),
    3: (("los", 5), ("los", 21)), 4: (("los", 13), ("los", 29)),
    5: (("los", 3), ("los", 19)), 6: (("los", 11), ("los", 27)),
    7: (("los", 7), ("los", 23)), 8: (("los", 15), ("los", 31)),
    9: (("los", 2), ("los", 18)), 10: (("los", 10), ("los", 26)),
    11: (("los", 6), ("los", 22)), 12: (("los", 14), ("los", 30)),
    13: (("los", 4), ("los", 20)), 14: (("los", 12), ("los", 28)),
    15: (("los", 8), ("los", 24)), 16: (("los", 16), ("los", 32)),
    17: (("W", 1), ("W", 2)), 18: (("W", 3), ("W", 4)),
    19: (("W", 5), ("W", 6)), 20: (("W", 7), ("W", 8)),
    21: (("W", 9), ("W", 10)), 22: (("W", 11), ("W", 12)),
    23: (("W", 13), ("W", 14)), 24: (("W", 15), ("W", 16)),
    25: (("L", 13), ("L", 14)), 26: (("L", 15), ("L", 16)),   # LB R0: R0 losers
    27: (("L", 9), ("L", 10)), 28: (("L", 11), ("L", 12)),
    29: (("L", 5), ("L", 6)), 30: (("L", 7), ("L", 8)),
    31: (("L", 1), ("L", 2)), 32: (("L", 3), ("L", 4)),
    33: (("W", 17), ("W", 18)), 34: (("W", 19), ("W", 20)),   # WB quarterfinals
    35: (("W", 21), ("W", 22)), 36: (("W", 23), ("W", 24)),
    37: (("W", 25), ("L", 21)), 38: (("W", 26), ("L", 22)),   # LB R1: R1 losers, crossed
    39: (("W", 27), ("L", 23)), 40: (("W", 28), ("L", 24)),
    41: (("W", 29), ("L", 17)), 42: (("W", 30), ("L", 18)),
    43: (("W", 31), ("L", 19)), 44: (("W", 32), ("L", 20)),
    45: (("W", 33), ("W", 34)), 46: (("W", 35), ("W", 36)),   # WB semifinals
    47: (("W", 37), ("W", 38)), 48: (("W", 39), ("W", 40)),   # LB R2: merge
    49: (("W", 41), ("W", 42)), 50: (("W", 43), ("W", 44)),
    51: (("W", 47), ("L", 33)), 52: (("W", 48), ("L", 34)),   # LB R3: QF losers, crossed
    53: (("W", 49), ("L", 35)), 54: (("W", 50), ("L", 36)),
    55: (("W", 51), ("W", 52)), 56: (("W", 53), ("W", 54)),   # LB R4: merge
    57: (("W", 55), ("L", 46)), 58: (("L", 45), ("W", 56)),   # LB R5: SF losers, crossed
    59: (("W", 45), ("W", 57)), 60: (("W", 46), ("W", 58)),   # medal round: SF winner vs TR champ
    61: (("W", 59), ("W", 60)),                               # final
}


def test_32er_form_matches_canonical_structure():
    assert decode_form(32) == CANONICAL_32


def test_32er_trostrunde_folds_into_medal_round():
    """What makes the 32er different from 8er/16er: the Trostrunde champions
    (winners of Kf57/58) re-enter at Kf59/60 against the WB semifinal winners,
    and the final pulls from those, not from the semifinals directly."""
    g = decode_form(32)
    assert g[59] == (("W", 45), ("W", 57))   # SF-top winner vs Trostrunde champ
    assert g[60] == (("W", 46), ("W", 58))   # SF-bottom winner vs Trostrunde champ
    assert g[61] == (("W", 59), ("W", 60))   # final


def test_32er_medal_structure():
    """1st/2nd from the final, two 3rd from the medal-round losers, two 5th from
    the LB-semifinal losers — verified by simulating "lower Los always wins"."""
    order = dict(realised_order(decode_form(32)))
    lo = lambda kf: max(order[kf])   # the loser when the lower Los wins
    hi = lambda kf: min(order[kf])
    assert (hi(61), lo(61)) == (1, 2)        # final → 1st, 2nd
    assert {lo(59), lo(60)} == {3, 4}        # medal-round losers → two 3rd places
    assert {lo(57), lo(58)} == {5, 6}        # LB-semifinal losers → two 5th places
