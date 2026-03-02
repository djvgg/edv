# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import date
from typing import List, Optional

from sqlalchemy import text

from ..data.models import Group, Participant, GroupParticipant
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
    if v in ('w', 'f', 'female', 'weiblich', 'frau'):
        return 'w'
    return v[0] if v else 'm'  # best-effort fallback


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
        """Map participant dict to Participant model kwargs.

        Both sources use Jahrgang (birth year) — stored directly as Jan 1 of that year.
          XLSX: 'Age' field contains birth year, club key = 'Verein'
          JSON: 'Birthyear' field contains birth year, club key = 'Club'
        """
        first_name, last_name = _split_name(raw.get('Name', ''))

        birth_date = None
        birthyear = raw.get('Birthyear') or raw.get('Age')
        if birthyear is not None:
            try:
                birth_date = date(int(birthyear), 1, 1)
            except (ValueError, TypeError):
                pass

        return {
            'first_name':  first_name,
            'last_name':   last_name,
            'gender':      _normalize_gender(raw.get('Gender', '')),
            'birth_date':  birth_date,
            'weight':      raw.get('Weight'),
            'club':        raw.get('Verein') or raw.get('Club') or '',
            'association': raw.get('Association', ''),
            'valid':       bool(raw.get('Valid', False)),
            'paid':        bool(raw.get('Paid', False)),
        }

    # ------------------------------------------------------------------
    # After load — initialize all possible groups from config
    # ------------------------------------------------------------------

    def initialize_all_groups(self) -> None:
        """
        Populate the groups table with every valid category from bracket_config.xlsx
        plus the special QUARANTINE group.

        Always called right after save_participants (which already truncated groups).
        Uses a single bulk transaction — all groups are committed atomically.
        """
        from utils import bracket_utils
        bracket_utils.ensure_config_loaded()

        # Wipe dependents in FK order so the groups table is empty before we fill it.
        # (save_participants already truncated everything, but this is safe to repeat
        #  and makes initialize_all_groups callable on its own too.)
        self.db.execute(text(
            "TRUNCATE TABLE fights, brackets, group_participants, groups"
            " RESTART IDENTITY CASCADE"
        ))
        self.db.commit()

        combos = bracket_utils.bracket_config.get_all_group_combinations()
        for combo in combos:
            self.db.add(Group(
                name=combo['name'],
                gender=combo.get('gender'),
                age_group=combo.get('age_group'),
                weight_class=combo.get('weight_class'),
            ))

        # QUARANTINE is always present regardless of config
        self.db.add(Group(name='QUARANTINE'))

        self.db.commit()  # single atomic commit for all groups

    # Screen 2 — participant edit (single-row update from Edit_Participants dialog)
    # ------------------------------------------------------------------

    def update_participant(self, fighter: dict, new_bracket_key: str) -> None:
        """
        Update one participant's fields in DB and move them to the correct group.

        Called by edit_participant_dialog after the user confirms changes.
        The fighter dict at call time has:
          - fighter['Name']       → OLD full name (not updated by dialog) — used as lookup key
          - fighter['Firstname']  → NEW first name
          - fighter['Lastname']   → NEW last name
          - fighter['Weight']     → NEW weight
          - fighter['Birthyear']  → NEW birth year
          - fighter['Club']       etc.

        new_bracket_key is the group name the fighter ended up in after the in-memory
        bracket movement (could be same group, a different weight/age group, or QUARANTINE).
        """
        participant = self._find_participant(fighter)
        if not participant:
            return

        # ── Update participant fields ──
        first_name = fighter.get('Firstname', '').strip()
        last_name  = fighter.get('Lastname',  '').strip()
        if first_name:
            participant.first_name = first_name
        if last_name is not None:
            participant.last_name = last_name

        birthyear = fighter.get('Birthyear') or fighter.get('Age')
        if birthyear:
            try:
                participant.birth_date = date(int(birthyear), 1, 1)
            except (ValueError, TypeError):
                pass

        weight = fighter.get('Weight')
        if weight is not None:
            participant.weight = weight

        club = fighter.get('Club') or fighter.get('Verein')
        if club is not None:
            participant.club = club

        association = fighter.get('Association')
        if association is not None:
            participant.association = association

        participant.valid = bool(fighter.get('Valid', participant.valid))
        participant.paid  = bool(fighter.get('Paid',  participant.paid))

        raw_gender = fighter.get('Gender', '')
        if raw_gender:
            participant.gender = _normalize_gender(raw_gender)

        # ── Move group_participants to the new group ──
        new_group = self.groups.get_by_name(new_bracket_key)
        if new_group:
            gp = (
                self.db.query(GroupParticipant)
                .filter_by(participant_id=participant.id)
                .first()
            )
            if gp:
                gp.group_id = new_group.id
            else:
                self.db.add(GroupParticipant(
                    group_id=new_group.id,
                    participant_id=participant.id,
                ))

        self.db.commit()

    # Screen 2 — Group Preview (after load, and after any edits)
    # ------------------------------------------------------------------

    def save_groups(self, brackets_dict: dict) -> None:
        """
        Re-sync group_participants from the current brackets dict.
        Groups must already exist (call initialize_all_groups first).
        Clears group_participants, fights, brackets (FK order) then re-inserts.

        Called immediately after load and again when leaving group preview.
        """
        self.db.execute(text(
            "TRUNCATE TABLE fights, brackets, group_participants"
            " RESTART IDENTITY CASCADE"
        ))
        self.db.commit()

        for bracket_key, bracket_data in brackets_dict.items():
            group = self.groups.get_by_name(bracket_key)
            if not group:
                continue  # skip Unassigned / unknown keys

            for fighter in bracket_data.get('fighters', []):
                participant = self._find_participant(fighter)
                if participant:
                    self.groups.add_participant(group.id, participant.id)

    # Screen 3 — Generation Method confirmed
    # ------------------------------------------------------------------

    def save_brackets(self, brackets_dict: dict, generation_methods: dict) -> None:
        """
        Write brackets table only. Groups and group_participants must already exist.
        Clears fights and brackets first (FK order), then re-inserts.
        """
        self.db.execute(text(
            "TRUNCATE TABLE fights, brackets RESTART IDENTITY CASCADE"
        ))
        self.db.commit()

        for bracket_key, bracket_data in brackets_dict.items():
            group = self.groups.get_by_name(bracket_key)
            if not group:
                continue

            method = generation_methods.get(bracket_key, 'ko')
            existing_bracket = self.brackets.get_by_group(group.id)
            if existing_bracket:
                self.brackets.update_type(existing_bracket.id, method)
            else:
                self.brackets.create(group.id, method)

    def save_groups_and_brackets(
        self,
        brackets_dict: dict,
        generation_methods: dict,
    ) -> None:
        """Convenience: write group_participants + brackets in one call."""
        self.save_groups(brackets_dict)
        self.save_brackets(brackets_dict, generation_methods)

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
