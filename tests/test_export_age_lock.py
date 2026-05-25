# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the age-lock filter on the weigh-in JSON export.

`split_gender_to_json_with_tolerances` must omit participants whose (gendered)
age class is locked — same rule the re-import path already enforces. The
behaviour is unit-tested through the extracted helper `_export_age_class_locked`
so no XLSX fixture is needed.

The tests are self-calibrating: they ask the service which age groups a given
birthyear resolves to (via the real bracket config), then lock one of those —
so they don't hardcode the event-year → age-group mapping.
"""

import pytest

from frontend.services.data_loader_service import DataLoaderService
from utils.helpers import age_group_from_bracket_key

# A youth birthyear that resolves to a gendered (U13+) bracket under the
# shipped config. Read back dynamically below, so the exact group doesn't matter.
BIRTHYEAR = 2011


@pytest.fixture
def svc():
    return DataLoaderService(ui_feedback=None, task_runner=None, db_service=None)


def _age_groups_for(svc, birthyear, gender='male'):
    keys = svc._participant_bracket_keys({
        'Name': 'Probe Athlete', 'Birthyear': birthyear,
        'Gender': gender, 'Weight': 0, 'Doublestart': 'nein',
    })
    return {ag for ag in (age_group_from_bracket_key(k) for k in keys) if ag}


class TestExportAgeLockFilter:
    def test_no_locks_never_filters(self, svc):
        assert svc._export_age_class_locked(
            'Probe Athlete', BIRTHYEAR, 'male', 'nein', set()) is False
        assert svc._export_age_class_locked(
            'Probe Athlete', BIRTHYEAR, 'male', 'nein', None) is False

    def test_probe_resolves_to_an_age_group(self, svc):
        # Sanity: the config must place this birthyear into at least one bracket,
        # otherwise the lock tests below would be vacuously true.
        assert _age_groups_for(svc, BIRTHYEAR)

    def test_participant_in_locked_age_class_is_filtered(self, svc):
        locked = next(iter(_age_groups_for(svc, BIRTHYEAR)))
        assert svc._export_age_class_locked(
            'Probe Athlete', BIRTHYEAR, 'male', 'nein', {locked}) is True

    def test_participant_in_unlocked_age_class_is_kept(self, svc):
        # Lock an age group this participant is definitely not in.
        unrelated = {'__NoSuchAgeGroup__'}
        assert svc._export_age_class_locked(
            'Probe Athlete', BIRTHYEAR, 'male', 'nein', unrelated) is False

    def test_gender_scoped_lock_only_hits_matching_gender(self, svc):
        groups = _age_groups_for(svc, BIRTHYEAR, gender='male')
        age = next(iter(groups))
        # Lock the male scope of that age group.
        male_lock = {f'm|{age}'}
        assert svc._export_age_class_locked(
            'Probe Athlete', BIRTHYEAR, 'male', 'nein', male_lock) is True
        # A female athlete of the same birthyear/age must not be caught by the
        # male-scoped lock.
        assert svc._export_age_class_locked(
            'Probe Athlete', BIRTHYEAR, 'female', 'nein', male_lock) is False
