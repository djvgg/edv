# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
TournamentState — single container for all in-memory tournament data.

Replaces the 8 parallel dicts that were scattered across BracketViewerApp.
Pass self.state to child screens instead of 8 separate kwargs.
"""


class TournamentState:
    """All mutable tournament data for the current session.

    Lifecycle:
        Created in BracketViewerApp.__init__.
        Cleared on flush/reload via reset().
        Passed by reference to child screens so mutations are shared.
    """

    def __init__(self):
        # {bracket_key: {fighters, bracket, pool_size, ...}}
        self.brackets: dict = {}

        # {bracket_key: 'ko' | 'pools' | 'double'}
        self.bracket_generation_methods: dict = {}

        # {bracket_key: table_number | None}
        self.bracket_table_assignment: dict = {}

        # {bracket_key: {(round_idx, match_idx): winner_name}}
        self.match_results: dict = {}

        # {bracket_key: {(lb_round, lb_match): winner_name}}
        self.loser_match_results: dict = {}

        # {bracket_key: {(pool_idx, row, fight_num): score}}
        self.pool_cell_values: dict = {}

        # {bracket_key: {'p0_1st': name, 'p0_2nd': name, ...}}
        self.ko_bracket_data: dict = {}

        # {bracket_key: {(round, match): winner_name}}
        self.ko_match_results: dict = {}

    def reset(self):
        """Clear all state (called on database flush or fresh load)."""
        self.brackets.clear()
        self.bracket_generation_methods.clear()
        self.bracket_table_assignment.clear()
        self.match_results.clear()
        self.loser_match_results.clear()
        self.pool_cell_values.clear()
        self.ko_bracket_data.clear()
        self.ko_match_results.clear()
