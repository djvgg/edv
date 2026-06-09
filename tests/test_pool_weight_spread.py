# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for weight-spread-based U9/U11 pool cutting in bracket_utils.

The two-stage split:
  Stage 1 (hard) — clusters whose head-to-tail weight spread ≤ max_weight_spread.
  Stage 2 (soft) — historical ceil(len/pool_size) even distribution per cluster.

A genuine outlier (cluster of one) becomes a 1-fighter Solo-Pool.
Without max_weight_spread the result is identical to the old count-only split.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.bracket_utils import (  # noqa: E402
    _cluster_by_weight_spread,
    _even_distribute,
    split_u9_u11_into_pools,
)


def _fighters(weights):
    """Build fighter dicts named after their weight, in the given order."""
    return [{'Name': f'F{w}', 'Weight': float(w)} for w in weights]


def _weights_per_pool(result, age_group='U11'):
    """Return [[weights of pool 1], [weights of pool 2], ...] in pool order."""
    pools = []
    i = 1
    while f'{age_group} | Pool {i}' in result:
        chunk = result[f'{age_group} | Pool {i}']['fighters']
        pools.append([int(f['Weight']) for f in chunk])
        i += 1
    return pools


def _bracket(weights, pool_size, max_spread=None, age_group='U11'):
    data = {'fighters': _fighters(weights), 'bracket': [], 'pool_size': pool_size}
    if max_spread is not None:
        data['max_weight_spread'] = max_spread
    return {age_group: data}


# --------------------------------------------------------------------------
# Stage-1 helper: weight-spread clustering
# --------------------------------------------------------------------------

def test_cluster_threshold_is_inclusive():
    # spread exactly == max_spread stays in one cluster
    clusters = _cluster_by_weight_spread(_fighters([18, 23]), max_spread=5)
    assert len(clusters) == 1

    # one kilo over → cut
    clusters = _cluster_by_weight_spread(_fighters([18, 24]), max_spread=5)
    assert len(clusters) == 2


def test_cluster_outlier_opens_new_cluster():
    clusters = _cluster_by_weight_spread(_fighters([18, 19, 40]), max_spread=5)
    assert [[int(f['Weight']) for f in c] for c in clusters] == [[18, 19], [40]]


# --------------------------------------------------------------------------
# Stage-2 helper: even distribution (unchanged historical behaviour)
# --------------------------------------------------------------------------

def test_even_distribute_balances_remainder():
    # 5 fighters, pool_size 4 → 3 + 2 (never 4 + 1)
    chunks = _even_distribute(_fighters([1, 2, 3, 4, 5]), pool_size=4)
    assert [len(c) for c in chunks] == [3, 2]


# --------------------------------------------------------------------------
# Case (a): main case — heavy group splits off, NO solo
# --------------------------------------------------------------------------

def test_main_case_splits_by_spread_no_solo():
    result = split_u9_u11_into_pools(
        _bracket([18, 20, 21, 23, 28, 30, 31], pool_size=4, max_spread=5)
    )
    assert _weights_per_pool(result) == [[18, 20, 21, 23], [28, 30, 31]]


# --------------------------------------------------------------------------
# Case (b): genuine outlier → Solo-Pool
# --------------------------------------------------------------------------

def test_outlier_becomes_solo_pool():
    result = split_u9_u11_into_pools(
        _bracket([18, 19, 40], pool_size=4, max_spread=5)
    )
    pools = _weights_per_pool(result)
    assert pools == [[18, 19], [40]]
    # the solo pool holds exactly one fighter
    assert len(result['U11 | Pool 2']['fighters']) == 1


# --------------------------------------------------------------------------
# Case (c): pool_size interacts with a single spread cluster → 3 + 2, no solo
# --------------------------------------------------------------------------

def test_pool_size_split_within_spread_cluster():
    # 5 fighters all within 5 kg, pool_size 4 → 3 + 2 (NOT 4 + 1)
    result = split_u9_u11_into_pools(
        _bracket([20, 21, 22, 23, 24], pool_size=4, max_spread=5)
    )
    pools = _weights_per_pool(result)
    assert [len(p) for p in pools] == [3, 2]
    # no 1-fighter pool was produced
    assert all(len(p) >= 2 for p in pools)


def test_spread_cluster_then_size_split_combined():
    # cluster {20..24} (size 5 → 3+2) and cluster {40,41} (size 2)
    result = split_u9_u11_into_pools(
        _bracket([20, 21, 22, 23, 24, 40, 41], pool_size=4, max_spread=5)
    )
    pools = _weights_per_pool(result)
    assert pools == [[20, 21, 22], [23, 24], [40, 41]]


# --------------------------------------------------------------------------
# Case (d): backward compatibility — no max_weight_spread ⇒ old even split
# --------------------------------------------------------------------------

def test_backward_compat_no_spread_is_count_only():
    # 7 fighters, pool_size 4, NO spread → ceil(7/4)=2 pools, balanced 4+3,
    # independent of the (large) weight gaps.
    result = split_u9_u11_into_pools(
        _bracket([18, 20, 21, 23, 28, 30, 31], pool_size=4, max_spread=None)
    )
    pools = _weights_per_pool(result)
    assert [len(p) for p in pools] == [4, 3]
    # spread is ignored: the heavy fighters stay mixed in by count only
    assert pools == [[18, 20, 21, 23], [28, 30, 31]]


def test_backward_compat_keeps_oversized_mixed_pool():
    # 8 fighters spanning 18..40, pool_size 4, NO spread → 4+4 by count,
    # a 22 kg-wide pool is tolerated (the very thing spread-cutting prevents).
    result = split_u9_u11_into_pools(
        _bracket([18, 19, 20, 21, 30, 35, 38, 40], pool_size=4, max_spread=None)
    )
    pools = _weights_per_pool(result)
    assert pools == [[18, 19, 20, 21], [30, 35, 38, 40]]


# --------------------------------------------------------------------------
# Non-U9/U11 and degenerate inputs are passed through untouched
# --------------------------------------------------------------------------

def test_non_pool_bracket_passthrough():
    other = {'fighters': _fighters([50, 60]), 'bracket': [('a', 'b')], 'pool_size': None}
    result = split_u9_u11_into_pools({'m | U15 | -60kg': other})
    assert result == {'m | U15 | -60kg': other}


def test_no_pool_size_passthrough():
    data = {'fighters': _fighters([18, 40]), 'bracket': [], 'pool_size': None,
            'max_weight_spread': 5}
    result = split_u9_u11_into_pools({'U11': data})
    # untouched: still the single 'U11' key, no pool split
    assert result == {'U11': data}
