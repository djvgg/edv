# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for frontend/state.py — TournamentState."""

from frontend.state import TournamentState


class TestTournamentState:
    def test_initial_state_all_empty_dicts(self):
        state = TournamentState()
        assert state.brackets == {}
        assert state.bracket_generation_methods == {}
        assert state.bracket_table_assignment == {}
        assert state.match_results == {}
        assert state.loser_match_results == {}
        assert state.pool_cell_values == {}
        assert state.ko_bracket_data == {}
        assert state.ko_match_results == {}

    def test_mutations_persist(self):
        state = TournamentState()
        state.brackets['m | U13 | -50kg'] = {'fighters': ['Alice', 'Bob']}
        state.bracket_generation_methods['m | U13 | -50kg'] = 'ko'
        assert len(state.brackets) == 1
        assert state.bracket_generation_methods['m | U13 | -50kg'] == 'ko'

    def test_reset_clears_all_state(self):
        state = TournamentState()
        state.brackets['key'] = {}
        state.match_results['key'] = {(0, 0): 'Alice'}
        state.bracket_table_assignment['key'] = 2
        state.ko_match_results['key'] = {(1, 0): 'Bob'}

        state.reset()

        assert state.brackets == {}
        assert state.match_results == {}
        assert state.bracket_table_assignment == {}
        assert state.ko_match_results == {}

    def test_reset_is_idempotent(self):
        state = TournamentState()
        state.reset()
        state.reset()  # Should not raise
        assert state.brackets == {}

    def test_shared_reference_semantics(self):
        """Mutations via a reference to the dict are visible on state."""
        state = TournamentState()
        brackets_ref = state.brackets
        brackets_ref['new_key'] = {'fighters': []}
        assert 'new_key' in state.brackets
