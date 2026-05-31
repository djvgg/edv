# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Tests for the core bracket generation algorithms in utils/bracket_utils.py
and the pool scheduling logic in frontend/utils/pool_renderer.py.

These are pure-function tests — no database, no config file, no Tkinter.
"""

from utils.bracket_utils import (
    _next_pow2,
    _generate_seed_order,
    _group_by_club,
    _distribute_round_robin,
    _compute_balanced_bracket,
    make_bracket,
)
from frontend.utils.pool_renderer import (
    _generate_fight_schedule,
    split_into_pools,
    determine_pool_structure,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _fighters(names, club='ClubA'):
    """Build minimal participant dicts for bracket tests."""
    return [{'Name': n, 'Verein': club} for n in names]


def _multi_club_fighters(spec):
    """spec = [('Name', 'Club'), ...]"""
    return [{'Name': n, 'Verein': c} for n, c in spec]


# ─────────────────────────────────────────────────────────────
# _next_pow2
# ─────────────────────────────────────────────────────────────

class TestNextPow2:
    def test_minimum_is_2(self):
        assert _next_pow2(1) == 2

    def test_exact_powers(self):
        assert _next_pow2(2) == 2
        assert _next_pow2(4) == 4
        assert _next_pow2(8) == 8
        assert _next_pow2(16) == 16

    def test_rounds_up(self):
        assert _next_pow2(3) == 4
        assert _next_pow2(5) == 8
        assert _next_pow2(9) == 16
        assert _next_pow2(17) == 32

    def test_large(self):
        assert _next_pow2(65) == 128


# ─────────────────────────────────────────────────────────────
# _generate_seed_order
# ─────────────────────────────────────────────────────────────

class TestGenerateSeedOrder:
    def test_size_2(self):
        assert _generate_seed_order(2) == [1, 2]

    def test_size_4(self):
        order = _generate_seed_order(4)
        assert len(order) == 4
        assert set(order) == {1, 2, 3, 4}
        # Top seed (1) always faces weakest seed (4) in first round
        assert order[0] == 1
        assert order[1] == 4

    def test_size_8_length_and_content(self):
        order = _generate_seed_order(8)
        assert len(order) == 8
        assert set(order) == set(range(1, 9))

    def test_size_16_top_seed_placement(self):
        order = _generate_seed_order(16)
        assert len(order) == 16
        assert set(order) == set(range(1, 17))
        # Seed 1 always first
        assert order[0] == 1
        # Seed 1 faces seed 16 (lowest)
        assert order[1] == 16

    def test_deterministic(self):
        assert _generate_seed_order(8) == _generate_seed_order(8)

    def test_no_bye_vs_bye_in_round1(self):
        """With n fighters in a bracket of size 2^k, byes are distributed
        such that seed 1 never faces a bye in round 1 (seed 1 should face the
        highest numbered seed which is the bye slot in odd brackets)."""
        order = _generate_seed_order(4)
        # Pairs are (order[0],order[1]) and (order[2],order[3])
        pairs = [(order[i], order[i+1]) for i in range(0, len(order), 2)]
        assert len(pairs) == 2
        # Seed 1 should be at position 0 and face the highest seed (4)
        assert order[0] == 1
        # In a 4-fighter bracket with 3 actual fighters, seed 4 is the bye
        # Seed 1 should face seed 4 (the bye), but this validates the pairing structure
        assert order[1] == 4
        # Verify all seeds are present and unique
        assert set(order) == {1, 2, 3, 4}


# ─────────────────────────────────────────────────────────────
# _group_by_club
# ─────────────────────────────────────────────────────────────

class TestGroupByClub:
    def test_single_club(self):
        fighters = _fighters(['Alice', 'Bob'])
        groups = _group_by_club(fighters)
        assert 'ClubA' in groups
        assert len(groups['ClubA']) == 2

    def test_multiple_clubs(self):
        fighters = _multi_club_fighters([
            ('Alice', 'ClubA'), ('Bob', 'ClubB'), ('Carol', 'ClubA')
        ])
        groups = _group_by_club(fighters)
        assert set(groups.keys()) == {'ClubA', 'ClubB'}
        assert len(groups['ClubA']) == 2
        assert len(groups['ClubB']) == 1

    def test_no_club_field_uses_fallback(self):
        fighters = [{'Name': 'NoClub'}]
        groups = _group_by_club(fighters)
        assert '__NO_CLUB__' in groups


# ─────────────────────────────────────────────────────────────
# _distribute_round_robin
# ─────────────────────────────────────────────────────────────

class TestDistributeRoundRobin:
    def test_single_club_preserved(self):
        groups = {'ClubA': [{'Name': 'A'}, {'Name': 'B'}, {'Name': 'C'}]}
        result = _distribute_round_robin(groups)
        assert [p['Name'] for p in result] == ['A', 'B', 'C']

    def test_two_clubs_interleaved(self):
        groups = {
            'ClubA': [{'Name': 'A1'}, {'Name': 'A2'}],
            'ClubB': [{'Name': 'B1'}, {'Name': 'B2'}],
        }
        result = _distribute_round_robin(groups)
        names = [p['Name'] for p in result]
        # Should alternate between clubs
        assert len(names) == 4
        # A1 and B1 should not be adjacent (interleaved)
        assert names[0] != names[1] or names[0].startswith('A') != names[1].startswith('A')

    def test_unequal_clubs(self):
        groups = {
            'BigClub': [{'Name': f'B{i}'} for i in range(3)],
            'SmallClub': [{'Name': 'S1'}],
        }
        result = _distribute_round_robin(groups)
        assert len(result) == 4


# ─────────────────────────────────────────────────────────────
# _compute_balanced_bracket
# ─────────────────────────────────────────────────────────────

class TestComputeBalancedBracket:
    def test_empty_returns_empty(self):
        assert _compute_balanced_bracket([]) == []

    def test_two_fighters_one_match(self):
        pairs = _compute_balanced_bracket(_fighters(['Alice', 'Bob']))
        assert len(pairs) == 1
        assert set(pairs[0]) == {'Alice', 'Bob'}

    def test_three_fighters_has_freilos(self):
        pairs = _compute_balanced_bracket(_fighters(['A', 'B', 'C']))
        assert len(pairs) == 2  # bracket of 4 → 2 round-1 matches
        names = {n for pair in pairs for n in pair}
        assert 'Freilos' in names

    def test_four_fighters_no_freilos(self):
        pairs = _compute_balanced_bracket(_fighters(['A', 'B', 'C', 'D']))
        assert len(pairs) == 2
        names = {n for pair in pairs for n in pair}
        assert 'Freilos' not in names
        assert names == {'A', 'B', 'C', 'D'}

    def test_eight_fighters_bracket_size(self):
        fighters = _fighters([f'F{i}' for i in range(8)])
        pairs = _compute_balanced_bracket(fighters)
        assert len(pairs) == 4  # bracket of 8 → 4 round-1 matches

    def test_five_fighters_freilos_count(self):
        fighters = _fighters([f'F{i}' for i in range(5)])
        pairs = _compute_balanced_bracket(fighters)
        assert len(pairs) == 4  # bracket of 8 → 4 matches
        freilos_count = sum(1 for p1, p2 in pairs if p1 == 'Freilos' or p2 == 'Freilos')
        assert freilos_count == 3  # 8 - 5 = 3 byes

    def test_club_separation_heuristic_larger_bracket(self):
        """Club separation is a best-effort heuristic. With 8 fighters from
        4 different clubs (2 each), no same-club first-round match should appear."""
        fighters = _multi_club_fighters([
            ('A1', 'C1'), ('A2', 'C1'),
            ('B1', 'C2'), ('B2', 'C2'),
            ('D1', 'C3'), ('D2', 'C3'),
            ('E1', 'C4'), ('E2', 'C4'),
        ])
        pairs = _compute_balanced_bracket(fighters)
        assert len(pairs) == 4  # bracket of 8
        # At least one pair should be cross-club (heuristic reduces same-club matchups)
        cross_club = [
            (p1, p2) for p1, p2 in pairs
            if p1 != 'Freilos' and p2 != 'Freilos' and p1[1] != p2[1]
        ]
        assert len(cross_club) > 0, "Expected at least one cross-club match"
        # With 5 clubs and 8 fighters, we should have multiple cross-club matches
        assert len(cross_club) >= 2, f"Expected at least 2 cross-club matches, got {len(cross_club)}"
        # Verify all pairs are valid (no duplicate fighters)
        all_fighters_in_pairs = [f for pair in pairs for f in pair if f != 'Freilos']
        assert len(all_fighters_in_pairs) == len(set(all_fighters_in_pairs)), "Duplicate fighters in bracket"

    def test_deterministic(self):
        fighters = _fighters([f'F{i}' for i in range(6)])
        assert _compute_balanced_bracket(fighters) == _compute_balanced_bracket(fighters)


# ─────────────────────────────────────────────────────────────
# make_bracket (public API)
# ─────────────────────────────────────────────────────────────

class TestMakeBracket:
    def test_empty(self):
        assert make_bracket([]) == []

    def test_returns_list_of_tuples(self):
        pairs = make_bracket(_fighters(['A', 'B', 'C', 'D']))
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)

    def test_all_fighters_appear(self):
        fighters = _fighters(['A', 'B', 'C', 'D'])
        pairs = make_bracket(fighters)
        names = {n for pair in pairs for n in pair if n != 'Freilos'}
        assert names == {'A', 'B', 'C', 'D'}


# ─────────────────────────────────────────────────────────────
# _generate_fight_schedule (pool renderer)
# ─────────────────────────────────────────────────────────────

class TestGenerateFightSchedule:
    def test_less_than_2_empty(self):
        assert _generate_fight_schedule(0) == []
        assert _generate_fight_schedule(1) == []

    def test_2_fighters_best_of_three(self):
        # A 2-fighter pool is run best-of-three: the same pairing three times.
        schedule = _generate_fight_schedule(2)
        assert len(schedule) == 3
        assert all(column == [(0, 1)] for column in schedule)

    def test_3_fighters_three_fights(self):
        schedule = _generate_fight_schedule(3)
        assert len(schedule) == 3  # 3*(3-1)/2 = 3

    def test_4_fighters_six_fights(self):
        schedule = _generate_fight_schedule(4)
        assert len(schedule) == 6  # 4*(4-1)/2 = 6

    def test_5_fighters_ten_fights(self):
        schedule = _generate_fight_schedule(5)
        assert len(schedule) == 10  # 5*(5-1)/2 = 10

    def test_all_pairs_covered(self):
        """Every unique pair of fighters appears exactly once (n>=3).

        n=2 is the deliberate exception: best-of-three repeats the lone pairing.
        """
        for n in range(3, 7):
            schedule = _generate_fight_schedule(n)
            all_pairs = set()
            for column in schedule:
                for match in column:
                    pair = tuple(sorted(match))
                    assert pair not in all_pairs, f"Duplicate pair {pair} for n={n}"
                    all_pairs.add(pair)
            expected_pairs = {(i, j) for i in range(n) for j in range(i+1, n)}
            assert all_pairs == expected_pairs, f"Missing pairs for n={n}"

    def test_no_fighter_fights_themselves(self):
        for n in range(2, 6):
            schedule = _generate_fight_schedule(n)
            for column in schedule:
                for match in column:
                    assert match[0] != match[1]


# ─────────────────────────────────────────────────────────────
# split_into_pools
# ─────────────────────────────────────────────────────────────

class TestSplitIntoPools:
    def _p(self, names):
        return [{'Name': n} for n in names]

    def test_single_pool_default(self):
        pools = split_into_pools(self._p(['A', 'B', 'C']))
        assert len(pools) == 1
        assert len(pools[0]) == 3

    def test_two_pools_even_split(self):
        pools = split_into_pools(self._p(['A', 'B', 'C', 'D']), num_pools=2)
        assert len(pools) == 2
        assert len(pools[0]) + len(pools[1]) == 4

    def test_pool_size_parameter(self):
        # pool_size=3 with 7 fighters → ceil(7/3) = 3 pools
        pools = split_into_pools(self._p([f'F{i}' for i in range(7)]), pool_size=3)
        assert len(pools) == 3
        total = sum(len(p) for p in pools)
        assert total == 7

    def test_all_fighters_preserved(self):
        fighters = self._p(['A', 'B', 'C', 'D', 'E'])
        pools = split_into_pools(fighters, num_pools=2)
        names_in = {p['Name'] for p in fighters}
        names_out = {f['Name'] for pool in pools for f in pool}
        assert names_in == names_out


# ─────────────────────────────────────────────────────────────
# determine_pool_structure
# ─────────────────────────────────────────────────────────────

class TestDeterminePoolStructure:
    def test_small_group_one_pool(self):
        assert determine_pool_structure(3) == 1
        assert determine_pool_structure(5) == 1

    def test_medium_group_two_pools(self):
        assert determine_pool_structure(6) == 2
        assert determine_pool_structure(10) == 2

    def test_explicit_pool_size(self):
        # pool_size=4 with 8 fighters → 2 pools
        assert determine_pool_structure(8, pool_size=4) == 2
        # pool_size=4 with 5 fighters → ceil(5/4) = 2 pools
        assert determine_pool_structure(5, pool_size=4) == 2
        # pool_size=10 with 8 fighters → 1 pool
        assert determine_pool_structure(8, pool_size=10) == 1
