# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for utils/helpers.py — the canonical domain utility functions."""

import pytest
from utils.helpers import (
    age_group_from_bracket_key,
    bracket_key_matches_age_lock,
    normalize_gender,
    parse_bracket_key,
    split_name,
)


class TestNormalizeGender:
    def test_canonical_m(self):
        assert normalize_gender('m') == 'm'

    def test_canonical_w(self):
        assert normalize_gender('w') == 'w'

    def test_german_maennlich(self):
        assert normalize_gender('männlich') == 'm'

    def test_german_maennlich_ascii(self):
        assert normalize_gender('maennlich') == 'm'

    def test_german_mann(self):
        assert normalize_gender('mann') == 'm'

    def test_german_weiblich(self):
        assert normalize_gender('weiblich') == 'w'

    def test_german_frau(self):
        assert normalize_gender('frau') == 'w'

    def test_english_male(self):
        assert normalize_gender('male') == 'm'

    def test_english_female(self):
        assert normalize_gender('female') == 'w'

    def test_english_f(self):
        assert normalize_gender('f') == 'w'

    def test_case_insensitive_upper(self):
        assert normalize_gender('M') == 'm'
        assert normalize_gender('W') == 'w'
        assert normalize_gender('MALE') == 'm'
        assert normalize_gender('FEMALE') == 'w'

    def test_strips_whitespace(self):
        assert normalize_gender('  m  ') == 'm'
        assert normalize_gender('\tw\n') == 'w'

    def test_empty_string_fallback(self):
        # Empty string → fallback 'm' (defined behaviour)
        assert normalize_gender('') == 'm'

    def test_unknown_value_returns_first_char(self):
        # Unrecognized values use first char as best-effort
        assert normalize_gender('xyz') == 'x'


class TestSplitName:
    def test_simple_two_part(self):
        assert split_name('John Doe') == ('John', 'Doe')

    def test_multi_word_first_name(self):
        # rsplit means last token is last name
        assert split_name('John Van Der Berg') == ('John Van Der', 'Berg')

    def test_single_word(self):
        # No space → full name is first name, last name is ''
        assert split_name('Madonna') == ('Madonna', '')

    def test_empty_string(self):
        assert split_name('') == ('', '')

    def test_german_name(self):
        assert split_name('Hans Müller') == ('Hans', 'Müller')

    def test_hyphenated_last_name(self):
        assert split_name('Anna Schmidt-Weber') == ('Anna', 'Schmidt-Weber')


class TestParseBracketKey:
    def test_standard_key(self):
        assert parse_bracket_key('m | U13 | -50kg') == ('m', 'U13', '-50kg')

    def test_female_key(self):
        assert parse_bracket_key('w | U15 | +70kg') == ('w', 'U15', '+70kg')

    def test_strips_whitespace(self):
        assert parse_bracket_key('m|U13|-50kg') == ('m', 'U13', '-50kg')

    def test_invalid_key_raises(self):
        with pytest.raises(ValueError):
            parse_bracket_key('Unassigned | m | U13 | -50kg')

    def test_invalid_two_part_raises(self):
        with pytest.raises(ValueError):
            parse_bracket_key('m | U13')

    def test_plus_weight_class(self):
        gender, age, weight = parse_bracket_key('m | 18+ | +100kg')
        assert gender == 'm'
        assert age == '18+'
        assert weight == '+100kg'


class TestAgeClassLocks:
    def test_age_group_from_standard_bracket_key(self):
        assert age_group_from_bracket_key('m | U13 | -50kg') == 'U13'

    def test_age_group_from_young_age_key(self):
        assert age_group_from_bracket_key('U9') == 'U9'

    def test_age_group_from_pool_key(self):
        assert age_group_from_bracket_key('U11 | Pool 2') == 'U11'

    def test_age_group_ignores_quarantine(self):
        assert age_group_from_bracket_key('QUARANTINE_unpaid') is None

    def test_bracket_matches_whole_age_lock(self):
        assert bracket_key_matches_age_lock('w | U15 | -63kg', {'U15'})

    def test_bracket_does_not_match_other_age_lock(self):
        assert not bracket_key_matches_age_lock('w | U15 | -63kg', {'U13'})

    def test_bracket_matches_gender_scoped_lock(self):
        assert bracket_key_matches_age_lock('m | U18 | -66kg', {'m|U18'})
        assert not bracket_key_matches_age_lock('w | U18 | -66kg', {'m|U18'})
