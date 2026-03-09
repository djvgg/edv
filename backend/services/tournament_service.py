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

import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger  # noqa: E402
from utils.helpers import normalize_gender as _normalize_gender, split_name as _split_name, parse_bracket_key as _parse_bracket_key  # noqa: E402


class TournamentService:
    """
    Orchestrates all repository operations for a tournament day.
    Receives a SQLAlchemy session on init; all repositories share it.
    """

    def __init__(self, db):
        self.db = db
        self.logger = get_logger('tournament_service')
        self.participants = ParticipantRepository(db)
        self.groups       = GroupRepository(db)
        self.brackets     = BracketRepository(db)
        self.fights       = FightRepository(db)

    # ------------------------------------------------------------------
    # Screen 1 — Load XLSX / JSON / DB
    # ------------------------------------------------------------------

    def add_participants(self, raw_participants: List[dict]) -> int:
        """
        Add participants to DB, skipping duplicates.
        Returns count of newly inserted participants.
        """
        new_count = 0
        for p in raw_participants:
            mapped = self._map_to_model(p)
            if not self._participant_exists(mapped):
                self.db.add(Participant(**mapped))
                new_count += 1
        self.db.commit()
        return new_count

    def _participant_exists(self, mapped: dict) -> bool:
        """Check if participant already exists by natural key."""
        q = self.db.query(Participant).filter(
            Participant.first_name == mapped['first_name'],
            Participant.last_name == mapped['last_name'],
            Participant.gender == mapped['gender'],
        )
        if mapped.get('birth_date'):
            q = q.filter(Participant.birth_date == mapped['birth_date'])
        if mapped.get('club'):
            q = q.filter(Participant.club == mapped['club'])
        if mapped.get('association'):
            q = q.filter(Participant.association == mapped['association'])
        return q.first() is not None

    def flush_database(self) -> None:
        """
        Wipe ALL tournament data table-by-table in FK-dependency order.

        Uses DELETE (not TRUNCATE) so the same pattern can be reused later
        for selective deletion (e.g. delete fights for one bracket only).
        """
        # Children first → parents last (reverse FK order)
        # brackets must come before group_participants: brackets.first/second/third_place are FKs → group_participants
        for table in ('fights', 'brackets', 'group_participants', 'groups', 'mats', 'participants'):
            self.db.execute(text(f"DELETE FROM {table}"))
        # Reset all sequences so IDs start from 1 on next insert
        for seq in ('fights_id_seq', 'group_participants_id_seq', 'brackets_id_seq',
                     'groups_id_seq', 'mats_id_seq', 'participants_id_seq'):
            self.db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1"))
        self.db.commit()

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

        # Normalize doublestart value (accepts German: ja/nein/höher)
        ds_raw = str(raw.get('Doppelstart', raw.get('Doublestart', 'nein'))).strip().lower()
        if ds_raw in ('höher', 'hoeher', 'higher'):
            doublestart = 'höher'
        elif ds_raw in ('ja', 'yes', 'true', '1', 'y'):
            doublestart = 'ja'
        else:
            doublestart = 'nein'

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
            'doublestart': doublestart,
        }

    # ------------------------------------------------------------------
    # After load — initialize all possible groups from config
    # ------------------------------------------------------------------

    def initialize_all_groups(self) -> None:
        """
        Populate the groups table with every valid category from bracket_config.xlsx
        plus the special QUARANTINE group.

        Additive: only inserts groups that don't exist yet, preserving existing
        groups and their associated brackets/fights.
        """
        from utils import bracket_utils
        bracket_utils.ensure_config_loaded()

        combos = bracket_utils.bracket_config.get_all_group_combinations()
        for combo in combos:
            existing = self.groups.get_by_name(combo['name'])
            if not existing:
                self.db.add(Group(
                    name=combo['name'],
                    gender=combo.get('gender'),
                    age_group=combo.get('age_group'),
                    weight_class=combo.get('weight_class'),
                ))

        # QUARANTINE is always present regardless of config
        if not self.groups.get_by_name('QUARANTINE'):
            self.db.add(Group(name='QUARANTINE'))

        self.db.commit()

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
        Sync group_participants from the current brackets dict.
        Groups must already exist (call initialize_all_groups first).

        Additive: only adds group_participant links that don't exist yet.
        Does not touch existing fights or brackets.
        """
        for bracket_key, bracket_data in brackets_dict.items():
            group = self.groups.get_by_name(bracket_key)
            if not group:
                continue  # skip Unassigned / unknown keys

            for fighter in bracket_data.get('fighters', []):
                participant = self._find_participant(fighter)
                if participant:
                    existing = self.db.query(GroupParticipant).filter_by(
                        group_id=group.id, participant_id=participant.id
                    ).first()
                    if not existing:
                        self.groups.add_participant(group.id, participant.id)

    # Screen 3 — Generation Method confirmed
    # ------------------------------------------------------------------

    def save_brackets(self, brackets_dict: dict, generation_methods: dict) -> None:
        """
        Write brackets table only. Groups and group_participants must already exist.
        Upserts: creates new bracket rows or updates bracket_type if the row already exists.
        Skips brackets that have no assigned method yet.
        """
        for bracket_key, bracket_data in brackets_dict.items():
            group = self.groups.get_by_name(bracket_key)
            if not group:
                continue

            method = generation_methods.get(bracket_key)
            if not method:
                continue  # skip unassigned brackets

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
        group = self.groups.get_by_name(bracket_key)
        if not group:
            self.logger.warning(f"assign_mat: No group found for '{bracket_key}'")
            return
        bracket = self.brackets.get_by_group(group.id)
        if bracket:
            mat = self.brackets.get_or_create_mat(mat_number)
            self.brackets.assign_mat(bracket.id, mat.id)
            self.logger.info(f"assign_mat: '{bracket_key}' (bracket {bracket.id}) → mat {mat.id} (number {mat_number})")
        else:
            self.logger.warning(f"assign_mat: No bracket for group '{bracket_key}' (group {group.id})")

    def unassign_mat(self, bracket_key: str) -> None:
        """Called when a bracket is removed from its mat."""
        group = self.groups.get_by_name(bracket_key)
        if not group:
            self.logger.warning(f"unassign_mat: No group found for '{bracket_key}'")
            return
        bracket = self.brackets.get_by_group(group.id)
        if bracket:
            self.brackets.unassign_mat(bracket.id)
            self.logger.info(f"unassign_mat: '{bracket_key}' (bracket {bracket.id}) → mat removed")

    # ------------------------------------------------------------------
    # Monitoring Window — opened per bracket
    # ------------------------------------------------------------------

    def open_bracket_for_monitoring(
        self,
        bracket_key: str,
        fight_pairs: List[tuple],
        bracket_type: str = 'ko',
        fighters: List[dict] = None,
        pool_size: int = None,
    ) -> list:
        """
        Called when the monitoring window opens for a bracket.
        Inserts fight rows for the first time and returns Fight objects.

        fight_pairs: list of (fighter1_name, fighter2_name) — WB round-0 pairs for KO brackets.
                     Ignored for pool/double brackets (pairs are generated from fighters list).
        bracket_type: 'pools' | 'double' | 'ko' | 'special'
        fighters:     full fighters list (needed for pool pair generation)
        pool_size:    max fighters per pool (for U9/U11 multi-pool splits)
        """
        group = self.groups.get_by_name(bracket_key)
        if not group:
            raise ValueError(f"No group in DB for key: {bracket_key!r}")
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            raise ValueError(f"No bracket in DB for key: {bracket_key!r}")

        # Return existing fights if monitoring was already opened for this bracket
        existing = self.fights.get_by_bracket(bracket.id)
        if existing:
            self.logger.info(f"Bracket {bracket_key} (ID {bracket.id}): Found {len(existing)} existing fights, returning them")
            return existing

        self.logger.info(f"Bracket {bracket_key} (ID {bracket.id}): No existing fights, will create new ones")

        if bracket_type in ('pools', 'double'):
            enriched = self._build_pool_pairs(group.id, fighters or [], pool_size, bracket_type)
        else:
            # KO / special: fight_pairs are round-0 WB name pairs.
            # IMPORTANT: We store ALL positions (including byes) so that DB
            # pos_in_round always matches the rendering position indices.
            # Bye matches get status='bye' and are auto-completed.
            enriched = []
            seen_pairs = set()

            for i, (name1, name2) in enumerate(fight_pairs):
                is_bye = (name1 == 'Freilos' or name2 == 'Freilos')
                is_phantom = (name1 == 'Freilos' and name2 == 'Freilos')

                gp1 = self._find_group_participant(group.id, name1)
                gp2 = self._find_group_participant(group.id, name2)

                if is_phantom:
                    self.logger.debug(f"  pos {i}: Phantom match (Freilos vs Freilos) — skipped")
                    continue

                if is_bye:
                    # Bye match: one real fighter, one Freilos
                    real_gp = gp1 or gp2
                    real_name = name1 if gp1 else name2
                    if not real_gp:
                        self.logger.warning(f"  pos {i}: Bye match but no real fighter found ({name1} vs {name2})")
                        continue
                    # Store bye: both participant slots point to the real fighter
                    # (Freilos has no DB entry). winner_id set immediately.
                    enriched.append({
                        'p1': real_gp.id,
                        'p2': real_gp.id,
                        'bracket_phase': 'wb',
                        'round': 0,
                        'pos_in_round': i,
                        'pool_index': None,
                        'status': 'bye',
                        'winner_id': real_gp.id,
                    })
                    self.logger.info(f"  pos {i}: BYE — {real_name} advances automatically")
                    continue

                if not gp1 or not gp2:
                    self.logger.warning(f"  pos {i}: Missing participant — {name1} (gp={gp1}) vs {name2} (gp={gp2})")
                    continue

                # Duplicate check
                canonical = tuple(sorted([gp1.id, gp2.id]))
                if canonical in seen_pairs:
                    self.logger.warning(f"  pos {i}: Duplicate pairing {name1} vs {name2} — skipped")
                    continue
                seen_pairs.add(canonical)

                enriched.append({
                    'p1': gp1.id,
                    'p2': gp2.id,
                    'bracket_phase': 'wb',
                    'round': 0,
                    'pos_in_round': i,
                    'pool_index': None,
                })
                self.logger.info(f"  pos {i}: {name1} vs {name2}")

            self.logger.info(f"Bracket {bracket_key}: {len(enriched)} fight rows from {len(fight_pairs)} pairs (including byes)")

        self.brackets.set_status(bracket.id, 'in_progress')
        return self.fights.create_fights(bracket.id, enriched)

    # ------------------------------------------------------------------
    # Monitoring — result persistence
    # ------------------------------------------------------------------

    def record_ko_result(
        self,
        bracket_key: str,
        phase: str,          # 'wb' or 'lb'
        round_num: int,
        pos: int,
        winner_name: str,
        p1_name: str = None,
        p2_name: str = None,
    ) -> bool:
        """
        Persist the result of a KO or LB fight.

        Looks up the fight by position.  If no row exists yet (rounds 1+ are
        created lazily, not upfront) it creates one from p1_name / p2_name —
        both are required for lazy creation to succeed.

        Returns True if the fight was found / created and the winner recorded.
        """
        self.logger.info(
            f"record_ko_result: '{bracket_key}' {phase} R{round_num} pos{pos} "
            f"winner='{winner_name}' p1='{p1_name}' p2='{p2_name}'"
        )

        group = self.groups.get_by_name(bracket_key)
        if not group:
            self.logger.warning(f"  → No group for '{bracket_key}'")
            return False
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            self.logger.warning(f"  → No bracket for group {group.id}")
            return False

        fight = self.fights.get_by_position(bracket.id, phase, round_num, pos)
        if fight:
            self.logger.info(
                f"  → Found existing fight #{fight.id} "
                f"(gp{fight.participant1_id} vs gp{fight.participant2_id}, "
                f"status={fight.status})"
            )
            # Don't overwrite a bye match
            if fight.status == 'bye':
                self.logger.info(f"  → Fight #{fight.id} is a bye, skipping result update")
                return True
        else:
            self.logger.info(f"  → No fight at {phase} R{round_num} pos{pos}, will lazy-create")
            # Lazy creation — participants only known when the fight is reachable
            if not p1_name or not p2_name:
                self.logger.warning("  → Cannot lazy-create: p1_name or p2_name missing")
                return False
            gp1 = self._find_group_participant(group.id, p1_name)
            gp2 = self._find_group_participant(group.id, p2_name)
            if not gp1 or not gp2:
                self.logger.warning(f"  → Cannot lazy-create: gp1={gp1}, gp2={gp2}")
                return False
            created = self.fights.create_fights(bracket.id, [{
                'p1': gp1.id, 'p2': gp2.id,
                'bracket_phase': phase, 'round': round_num, 'pos_in_round': pos,
            }])
            fight = created[0]
            self.logger.info(f"  → Lazy-created fight #{fight.id} (gp{gp1.id} vs gp{gp2.id})")

        winner_gp = self._find_group_participant(group.id, winner_name)
        if not winner_gp:
            self.logger.warning(f"  → Winner '{winner_name}' not found in group {group.id}")
            return False

        self.fights.set_result(fight.id, winner_gp.id)
        self.logger.info(f"  → Fight #{fight.id}: winner set to gp{winner_gp.id} ('{winner_name}')")

        # Write win/loss indicator: winner gets 1, loser gets 0
        if fight.participant1_id == winner_gp.id:
            self.fights.set_score(fight.id, '1', '0')
        else:
            self.fights.set_score(fight.id, '0', '1')

        return True

    def reset_ko_result(
        self,
        bracket_key: str,
        phase: str,
        round_num: int,
        pos: int,
    ) -> bool:
        """Clear the result of a KO or LB fight (user de-selected the winner)."""
        group = self.groups.get_by_name(bracket_key)
        if not group:
            return False
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            return False

        fight = self.fights.get_by_position(bracket.id, phase, round_num, pos)
        if not fight:
            return True  # Nothing to reset — that is fine

        self.fights.reset_result(fight.id)
        return True

    def delete_ko_fight(
        self,
        bracket_key: str,
        phase: str,
        round_num: int,
        pos: int,
    ) -> None:
        """
        Delete a lazily-created fight row so it can be re-created with the
        correct participants when an upstream result is changed or undone.
        """
        group = self.groups.get_by_name(bracket_key)
        if not group:
            return
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            return
        self.fights.delete_by_position(bracket.id, phase, round_num, pos)

    def compute_and_store_placements(self, bracket_key: str) -> dict:
        """
        Compute final placements for a KO bracket and store them.

        Returns dict with keys: first, second, third_1, third_2
        (each is a GroupParticipant ID or None).
        """
        group = self.groups.get_by_name(bracket_key)
        if not group:
            self.logger.warning(f"compute_placements: No group for '{bracket_key}'")
            return {}
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            self.logger.warning(f"compute_placements: No bracket for '{bracket_key}'")
            return {}

        fights = self.fights.get_by_bracket(bracket.id)
        if not fights:
            return {}

        # Find the WB final (highest round number in 'wb' phase)
        wb_fights = [f for f in fights if f.bracket_phase == 'wb']
        if not wb_fights:
            return {}

        max_wb_round = max(f.round for f in wb_fights if f.round is not None)
        wb_final = [f for f in wb_fights if f.round == max_wb_round]

        first_gp = None
        second_gp = None
        if wb_final and wb_final[0].winner_id:
            final = wb_final[0]
            first_gp = final.winner_id
            # Loser of the final = 2nd place
            second_gp = (final.participant2_id
                         if final.winner_id == final.participant1_id
                         else final.participant1_id)

        # 3rd place: last LB round survivors
        lb_fights = [f for f in fights if f.bracket_phase == 'lb']
        third_1 = None
        third_2 = None
        if lb_fights:
            max_lb_round = max(f.round for f in lb_fights if f.round is not None)
            last_lb = [f for f in lb_fights if f.round == max_lb_round]
            # In Judo: both last-LB-round survivors are 3rd place (no 3rd-place fight)
            third_place_gps = set()
            for f in last_lb:
                if f.winner_id:
                    third_place_gps.add(f.winner_id)
                else:
                    # If not decided yet, both are candidates
                    third_place_gps.add(f.participant1_id)
                    third_place_gps.add(f.participant2_id)
            # Remove already-placed people and Freilos/None values
            third_place_gps -= {first_gp, second_gp, None}
            third_list = sorted(x for x in third_place_gps if x is not None)
            third_1 = third_list[0] if len(third_list) > 0 else None
            third_2 = third_list[1] if len(third_list) > 1 else None

        result = {
            'first': first_gp,
            'second': second_gp,
            'third_1': third_1,
            'third_2': third_2,
        }

        self.logger.info(
            f"Placements for '{bracket_key}': "
            f"1st=gp{first_gp}, 2nd=gp{second_gp}, "
            f"3rd=gp{third_1} & gp{third_2}"
        )

        # Store in DB
        self.brackets.set_placements(
            bracket.id,
            first=first_gp,
            second=second_gp,
            third_1=third_1,
            third_2=third_2,
        )

        # Mark bracket completed if we have at least 1st place
        if first_gp:
            self.brackets.set_status(bracket.id, 'completed')

        return result

    def record_pool_score(
        self,
        bracket_key: str,
        fighter1_name: str,
        fighter2_name: str,
        score1: str,
        score2: str,
        winner_name: Optional[str] = None,
    ) -> bool:
        """
        Persist a pool fight score.
        Looks up the fight by participant IDs (order-insensitive).
        score1 corresponds to fighter1, score2 to fighter2.
        """
        group = self.groups.get_by_name(bracket_key)
        if not group:
            return False
        bracket = self.brackets.get_by_group(group.id)
        if not bracket:
            return False

        gp1 = self._find_group_participant(group.id, fighter1_name)
        gp2 = self._find_group_participant(group.id, fighter2_name)
        if not gp1 or not gp2:
            return False

        fight = self.fights.get_by_participants(bracket.id, gp1.id, gp2.id)
        if not fight:
            return False

        # Align score1/score2 with the DB slot order (participant1/participant2)
        if fight.participant1_id == gp1.id:
            self.fights.set_score(fight.id, score1, score2)
        else:
            self.fights.set_score(fight.id, score2, score1)

        if winner_name:
            winner_gp = gp1 if winner_name == fighter1_name else gp2
            self.fights.set_result(fight.id, winner_gp.id)

        return True

    def _build_pool_pairs(
        self,
        group_id: int,
        fighters: List[dict],
        pool_size: Optional[int],
        method: str,
    ) -> List[dict]:
        """
        Generate all round-robin fight pairs for pool and double-pool brackets,
        look up GroupParticipant IDs, and attach bracket position metadata.

        Pool split rules:
            'double'         → always 2 pools, split in half
            'pools' + size   → split into groups of pool_size
            'pools' no size  → single pool (all fighters together)
        """
        from itertools import combinations

        names = [f.get('Name', '') for f in fighters]

        if method == 'double':
            mid = len(names) // 2
            pools = [names[:mid], names[mid:]]
        elif pool_size and len(names) > pool_size:
            pools = [names[i:i + pool_size] for i in range(0, len(names), pool_size)]
        else:
            pools = [names]

        enriched = []
        for pool_idx, pool in enumerate(pools):
            for pos, (n1, n2) in enumerate(combinations(pool, 2)):
                gp1 = self._find_group_participant(group_id, n1)
                gp2 = self._find_group_participant(group_id, n2)
                if gp1 and gp2:
                    enriched.append({
                        'p1': gp1.id,
                        'p2': gp2.id,
                        'bracket_phase': 'pool',
                        'round': None,
                        'pos_in_round': pos,
                        'pool_index': pool_idx,
                    })
        return enriched

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
