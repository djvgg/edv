# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for the ↻ Aktualisieren persist glue.

`TableAndBracketViewer._persist_assigned_to_db` writes the in-memory brackets +
the fights of every mat-assigned bracket to the DB (idempotent), so JudgeFrontend
sees them. Driven against a stub `self` + a MagicMock main_window — no Tkinter / DB.
"""

import logging
import types
from unittest.mock import MagicMock

from frontend.views.table_and_bracket_viewer import TableAndBracketViewer


def _view():
    return types.SimpleNamespace(logger=logging.getLogger("test.manual_refresh"))


def test_persist_saves_brackets_and_creates_fights_for_assigned():
    mw = MagicMock()
    mw.brackets = {
        "A": {"bracket": [("x", "y")], "fighters": [], "pool_size": None},
        "B": {"bracket": [], "fighters": [{"name": "z"}], "pool_size": 4},
    }
    mw.bracket_generation_methods = {"A": "ko", "B": "pools"}
    mw.bracket_table_assignment = {"A": 1, "B": 2, "C": None}   # C unassigned → skip
    mw.db_service.assign_and_create_fights.return_value = True

    n = TableAndBracketViewer._persist_assigned_to_db(_view(), mw)

    assert n == 2
    mw.db_service.save_brackets.assert_called_once_with(
        mw.brackets, mw.bracket_generation_methods)
    assert mw.db_service.assign_and_create_fights.call_count == 2
    # B is a pool bracket → its type + fighters get forwarded.
    b_call = next(c for c in mw.db_service.assign_and_create_fights.call_args_list
                  if c.args[0] == "B")
    assert b_call.kwargs["bracket_type"] == "pools"
    assert b_call.kwargs["pool_size"] == 4
    assert b_call.kwargs["table_num"] == 2


def test_persist_skips_when_no_in_memory_brackets():
    mw = MagicMock()
    mw.brackets = {}
    assert TableAndBracketViewer._persist_assigned_to_db(_view(), mw) == 0
    mw.db_service.save_brackets.assert_not_called()


def test_persist_counts_only_successful():
    mw = MagicMock()
    mw.brackets = {"A": {"bracket": [], "fighters": [], "pool_size": None},
                   "B": {"bracket": [], "fighters": [], "pool_size": None}}
    mw.bracket_generation_methods = {"A": "ko", "B": "ko"}
    mw.bracket_table_assignment = {"A": 1, "B": 1}
    mw.db_service.assign_and_create_fights.side_effect = [True, False]   # B fails silently

    n = TableAndBracketViewer._persist_assigned_to_db(_view(), mw)
    assert n == 1   # only A counted
