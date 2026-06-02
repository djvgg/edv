# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Decode the official DJB Doppel-KO bracket forms into a fight-order graph.

The printed forms ``backend/services/templates/ko_{8,16,32}.xls`` are the
authoritative source for the suite's Doppel-KO structure (Kampffolge Nr. +
"Verlierer aus Kampf Nr." references). This module reads them back into a
machine-checkable graph so a test can assert that the order the system *fights*
matches the order the form *prescribes* (see ``test_ko_form_order.py``).

How the form encodes things (decoded geometrically + by cell style):
  * The Los column holds the seeding order (1..N down the page).
  * Every bout is a Kampffolge node, numbered 1..M, drawn as an *un-shaded*
    cell (``fill_pattern == 0``).
  * A feeder line into a bout is either a seed (Los), the winner of an earlier
    bout, or a *shaded* "Verlierer aus Kampf n" label (``fill_pattern == 1``).
    Shading is what distinguishes a loser-reference from a real bout when the
    same fight number appears twice (the global-numbering collision).
  * A bout's two feeders are the two nearest cells to its left that bracket its
    row (one above, one at/below).

Output: ``{kampffolge_number: (top_feeder, bottom_feeder)}`` where each feeder is
``('los', n)`` | ``('W', kf)`` (winner of fight ``kf``) | ``('L', kf)`` (loser of
fight ``kf``), or ``None`` when the form leaves a slot open.

Requires ``xlrd < 2.0`` (the edv venv has 1.2) — 2.0 dropped .xls support and
cannot read ``formatting_info``.
"""

import os

import xlrd

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backend", "services", "templates",
)

# Per-size layout: sheet index, Los column, Los row range, and the diagram
# columns that carry bout/feeder numbers (placement and legend columns excluded).
_FORM = {
    8:  {"path": "ko_8.xls",  "sheet": 1, "los_col": 0, "los_rows": range(11, 19),
         "cols": {2, 6, 10}},
    16: {"path": "ko_16.xls", "sheet": 1, "los_col": 0, "los_rows": range(11, 27),
         "cols": {2, 6, 10, 14, 24, 28, 32, 36, 40}},
    32: {"path": "ko_32.xls", "sheet": 0, "los_col": 2, "los_rows": range(9, 41),
         "cols": {6, 10, 14, 18, 21, 27, 31, 35, 39, 43, 47, 51}},
}

# Feedback edges the geometric reader cannot see: where a connector line runs
# *backwards* across the sheet (Trostrunde champions folding into the medal
# round), "nearest cell to the left" no longer identifies the true feeder. Only
# the 32er has this — its repechage winners cross back in. Confirmed off the
# physical DJB ko_32 sheet by Merlin (2026-06-02):
#   Kf59 = winner(SF Kf45) vs winner(Trostrunde Kf57)   -> loser = 3rd, winner -> final
#   Kf60 = winner(SF Kf46) vs winner(Trostrunde Kf58)   -> loser = 3rd, winner -> final
#   Kf61 = winner(Kf59)    vs winner(Kf60)              -> 1st / 2nd
# (Losers of Kf57/Kf58 are the two 5th places.) The 8er/16er forms have NO such
# feedback — their final is the two SF winners directly, bronze is the LB final.
_FEEDBACK_EDGES = {
    32: {
        59: (("W", 45), ("W", 57)),
        60: (("W", 46), ("W", 58)),
        61: (("W", 59), ("W", 60)),
    },
}


def _read_cells(size):
    cfg = _FORM[size]
    book = xlrd.open_workbook(
        os.path.join(_TEMPLATE_DIR, cfg["path"]), formatting_info=True)
    sheet = book.sheet_by_index(cfg["sheet"])
    val, fill = {}, {}
    for r in range(sheet.nrows):
        for c in range(sheet.ncols):
            raw = sheet.cell_value(r, c)
            if raw in ("", None):
                continue
            try:
                n = int(float(raw))
            except (ValueError, TypeError):
                continue
            val[(r, c)] = n
            fill[(r, c)] = book.xf_list[sheet.cell_xf_index(r, c)].background.fill_pattern
    return cfg, val, fill


def decode_form(size):
    """Return ``{kf: (top_feeder, bottom_feeder)}`` for the given draw size."""
    cfg, val, fill = _read_cells(size)
    los_col = cfg["los_col"]
    los = {r: val[(r, los_col)] for r in cfg["los_rows"] if (r, los_col) in val}
    cells = {rc: n for rc, n in val.items() if rc[1] in cfg["cols"]}

    # Bout nodes are the un-shaded cells. The same fight number can be printed
    # twice (a stray duplicate of a Los/placement label); keep the leftmost.
    node_cells = {}
    seen = set()
    for rc in sorted(cells, key=lambda rc: rc[1]):  # column ascending
        n = cells[rc]
        if fill[rc] == 0 and n not in seen and n > 0:
            node_cells[rc] = n
            seen.add(n)

    nums = sorted(node_cells.values())
    if nums != list(range(1, len(nums) + 1)):
        raise ValueError(f"ko_{size}: decoded nodes are not 1..M: {nums}")

    def feeders(node_rc):
        nr, nc = node_rc
        cand = [rc for rc in cells if rc[1] < nc]
        cand += [(r, los_col) for r in los]
        above = [rc for rc in cand if rc[0] < nr]
        below = [rc for rc in cand if rc[0] >= nr and rc != node_rc]
        nearest = lambda group: (
            min(group, key=lambda rc: (-rc[1], abs(rc[0] - nr))) if group else None)
        return nearest(above), nearest(below)

    def describe(rc):
        if rc is None:
            return None
        if rc[1] == los_col and rc[0] in los:
            return ("los", los[rc[0]])
        return ("W" if rc in node_cells else "L", cells[rc])

    graph = {}
    for rc, kf in sorted(node_cells.items(), key=lambda kv: kv[1]):
        top, bottom = feeders(rc)
        graph[kf] = (describe(top), describe(bottom))
    graph.update(_FEEDBACK_EDGES.get(size, {}))  # override backward-routed edges
    return graph


def realised_order(graph):
    """Simulate "the lower Los always wins" and return the order actually fought.

    Returns ``[(kf, (los_a, los_b)), ...]`` ordered by Kampffolge number — i.e.
    exactly which two fighters meet in each bout, in fight order.
    """
    winner, loser, participants = {}, {}, {}

    def resolve(feeder):
        kind, n = feeder
        if kind == "los":
            return n
        if kind == "W":
            return winner[n]
        return loser[n]  # 'L'

    for kf in sorted(graph):
        top, bottom = graph[kf]
        a = resolve(top) if top else None
        b = resolve(bottom) if bottom else None
        participants[kf] = (a, b)
        present = [x for x in (a, b) if x is not None]
        if present:
            winner[kf] = min(present)
            loser[kf] = max(present) if len(present) == 2 else None
    return [(kf, participants[kf]) for kf in sorted(graph)]
