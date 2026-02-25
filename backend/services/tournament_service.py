# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import date
from typing import List, Optional

from sqlalchemy import text

from ..data.models import Participant, GroupParticipant
from ..data.repositories.participant_repository import ParticipantRepository
from ..data.repositories.group_repository import GroupRepository
from ..data.repositories.bracket_repository import BracketRepository
from ..data.repositories.fight_repository import FightRepository


def _parse_bracket_key(bracket_key: str):
    """Parse 'M | U13 | -50kg' → ('M', 'U13', '-50kg')."""
    parts = [p.strip() for p in bracket_key.split('|')]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    raise ValueError(f"Cannot parse bracket key: {bracket_key!r}")


def _split_name(full_name: str):
    """
    Split 'Vorname Nachname' → (first_name, last_name).
    Uses rsplit so multi-word first names are preserved:
      'John Doe'          → ('John', 'Doe')
      'John Van Der Berg' → ('John Van Der', 'Berg')
    Must match the logic used in _map_participant_data() so lookups are consistent.
    """
    parts = full_name.rsplit(' ', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return full_name, ''


def _normalize_gender(raw: str) -> str:
    """Normalize any gender string to 'm' or 'w'."""
    v = str(raw).lower().strip()
    if v in ('m', 'male', 'maennlich', 'männlich'):
        return 'm'
    if v in ('w', 'f', 'female', 'weiblich'):
        return 'w'
    return v[:1]  # best-effort fallback


class TournamentService:
    """
    Orchestrates all repository operations for a tournament day.
    Receives a SQLAlchemy session on init; all repositories share it.
    """

    def __init__(self, db):
        self.db = db
        self.participants = ParticipantRepository(db)
        self.groups       = GroupRepository(db)
        self.brackets     = BracketRepository(db)
        self.fights       = FightRepository(db)

    # ------------------------------------------------------------------
    # Screen 1 — Load XLSX / JSON / DB
    # ------------------------------------------------------------------

    def save_participants(self, raw_participants: List[dict]) -> List[Participant]:
        """
        Wipe ALL tournament data and bulk-insert new participants.
        Called on every XLSX / JSON load — this is always a fresh start.
        Deletes in reverse FK order to avoid constraint violations.
        """
        # TRUNCATE resets auto-increment sequences back to 1.
        # CASCADE handles FK order automatically.
        self.db.execute(text(
            "TRUNCATE TABLE fights, group_participants, brackets, groups, mats, participants"
            " RESTART IDENTITY CASCADE"
        ))
        self.db.commit()

        mapped = [self._map_to_model(p) for p in raw_participants]
        return self.participants.add_bulk(mapped)

    @staticmethod
    def _map_to_model(raw: dict) -> dict:
        """Map bracket-layer dict format to Participant model kwargs."""
        first_name, last_name = _split_name(raw.get('Name', ''))

        # Derive birth_date from Age (Jahrgang = current_year - age).
        # Stored as Jan 1 of birth year — German tournaments classify by
        # Jahrgang, not exact birthday, so this is the correct granularity.
        birth_date = None
        age = raw.get('Age')
        if age is not None:
            try:
                birth_year = date.today().year - int(age)
                birth_date = date(birth_year, 1, 1)
            except (ValueError, TypeError):
                pass

        return {
            'first_name': first_name,
            'last_name':  last_name,
            'gender':     _normalize_gender(raw.get('Gender', '')),
            'birth_date': birth_date,
            'weight':     raw.get('Weight'),
            'club':       raw.get('Verein', ''),
        }

    # ------------------------------------------------------------------
    # Screen 3 — Generation Method confirmed
    # ------------------------------------------------------------------

    def save_groups_and_brackets(
        self,
        brackets_dict: dict,
        generation_methods: dict,
    ) -> None:
        """
        Write groups, group_participants, and brackets to DB.

        brackets_dict:      {bracket_key: {'fighters': [...], ...}}
        generation_methods: {bracket_key: method_name}
        """
        for bracket_key, bracket_data in brackets_dict.items():
            try:
                gender, age_group, weight_class = _parse_bracket_key(bracket_key)
            except ValueError:
                continue  # skip malformed / Unassigned keys

            group = self.groups.get_or_create(gender, age_group, weight_class)

            for fighter in bracket_data.get('fighters', []):
                participant = self._find_participant(fighter)
                if participant:
                    self.groups.add_participant(group.id, participant.id)

            method = generation_methods.get(bracket_key, 'ko')
            existing_bracket = self.brackets.get_by_group(group.id)
            if existing_bracket:
                self.brackets.update_type(existing_bracket.id, method)
            else:
                self.brackets.create(group.id, method)

    def update_bracket_type(self, bracket_key: str, new_type: str) -> None:
        """Called when user changes bracket type (pool → ko etc.)."""
        gender, age_group, weight_class = _parse_bracket_key(bracket_key)
        group = self.groups.get_or_create(gender, age_group, weight_class)
        bracket = self.brackets.get_by_group(group.id)
        if bracket:
            self.brackets.update_type(bracket.id, new_type)

    # ------------------------------------------------------------------
    # Screen 4 — Mat Assignment
    # ------------------------------------------------------------------

    def assign_mat(self, bracket_key: str, mat_number: int) -> None:
        """Called when a bracket is assigned to a mat."""
        gender, age_group, weight_class = _parse_bracket_key(bracket_key)
        group = self.groups.get_or_create(gender, age_group, weight_class)
        bracket = self.brackets.get_by_group(group.id)
        if bracket:
            mat = self.brackets.get_or_create_mat(mat_number)
            self.brackets.assign_mat(bracket.id, mat.id)

    # ------------------------------------------------------------------
    # Monitoring Window — opened per bracket
    # ------------------------------------------------------------------

    def open_bracket_for_monitoring(
        self,
        bracket_key: str,
        fight_pairs: List[tuple],
    ) -> list:
        """
        Called when the monitoring window opens for a bracket.
        Inserts fight rows for the first time and returns Fight objects.

        fight_pairs: list of (fighter1_name, fighter2_name) strings
                     taken from brackets_dict[bracket_key]['bracket']
        """
        gender, age_group, weight_class = _parse_bracket_key(bracket_key)
        group = self.groups.get_or_create(gender, age_group, weight_class)
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            raise ValueError(f"No bracket in DB for key: {bracket_key!r}")

        # Return existing fights if monitoring was already opened for this bracket
        existing = self.fights.get_by_bracket(bracket.id)
        if existing:
            return existing

        # Map fighter names → GroupParticipant IDs
        gp_pairs = []
        for name1, name2 in fight_pairs:
            gp1 = self._find_group_participant(group.id, name1)
            gp2 = self._find_group_participant(group.id, name2)
            if gp1 and gp2:
                gp_pairs.append((gp1.id, gp2.id))

        self.brackets.set_status(bracket.id, 'in_progress')
        return self.fights.create_fights(bracket.id, gp_pairs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_participant(self, fighter: dict) -> Optional[Participant]:
        """
        Look up a Participant by name, disambiguating by weight then birth year
        when multiple people share the same name (e.g. two 'Clara Meier' in
        different age/weight groups).
        """
        first_name, last_name = _split_name(fighter.get('Name', ''))
        candidates = (
            self.db.query(Participant)
            .filter_by(first_name=first_name, last_name=last_name)
            .all()
        )
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # Disambiguate by weight — most reliable tiebreaker from XLSX
        weight = fighter.get('Weight')
        if weight is not None:
            try:
                weight_matches = [
                    c for c in candidates
                    if c.weight is not None and abs(float(c.weight) - float(weight)) < 0.01
                ]
                if len(weight_matches) == 1:
                    return weight_matches[0]
                if weight_matches:
                    candidates = weight_matches  # narrow field, continue
            except (ValueError, TypeError):
                pass

        # Disambiguate by birth year derived from age
        age = fighter.get('Age')
        if age is not None:
            try:
                birth_year = date.today().year - int(age)
                year_matches = [
                    c for c in candidates
                    if c.birth_date is not None and c.birth_date.year == birth_year
                ]
                if len(year_matches) == 1:
                    return year_matches[0]
                if year_matches:
                    candidates = year_matches
            except (ValueError, TypeError):
                pass

        return candidates[0]  # best-effort fallback

    def _find_group_participant(
        self, group_id: int, fighter_name: str
    ) -> Optional[GroupParticipant]:
        """
        Look up a GroupParticipant by group_id and fighter name.
        Since group_id already scopes to one bracket, name is unique here —
        the duplicate-name problem is resolved at the group_participants level.
        """
        first_name, last_name = _split_name(fighter_name)
        return (
            self.db.query(GroupParticipant)
            .join(Participant)
            .filter(
                GroupParticipant.group_id == group_id,
                Participant.first_name == first_name,
                Participant.last_name == last_name,
            )
            .first()
        )
