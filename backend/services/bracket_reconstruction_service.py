# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket Reconstruction Service

Transforms Fight records from DB back into bracket visualization data structures.
Handles both KO and pool brackets by reverse-mapping DB participant IDs to original
participant ordering using the deterministic fight generation algorithm.
"""

from typing import List, Dict, Optional, Tuple

from utils.logging import get_logger

logger = get_logger('bracket_reconstruction')


class BracketReconstructionService:
    """
    Reconstructs bracket data from database Fight records.
    
    The service reverses the deterministic fight generation algorithm to recover:
    - Original pool participant ordering (for pool brackets)
    - KO bracket structure with winners (for KO brackets)
    - Fight results and match metadata
    """

    def __init__(self, db_service):
        """
        Args:
            db_service: DatabaseService instance (provides access to repositories)
        """
        self.db_service = db_service
        self.logger = logger

    def _get_session(self):
        """Get a database session for queries."""
        from ..data.database import SessionLocal
        return SessionLocal()

    def reconstruct_bracket_from_db(
        self,
        bracket_id: int,
        bracket_key: str,
        bracket_type: str = 'ko',
        pool_size: int = None,
    ) -> Dict:
        """
        Reconstruct a complete bracket dict from DB fights.
        
        Args:
            bracket_id: Database bracket ID
            bracket_key: Human-readable bracket key (for logging)
            bracket_type: 'ko', 'pools', or 'double'
            pool_size: Max fighters per pool (if applicable)
        
        Returns:
            Dict matching the format of self.brackets[bracket_key]:
            {
                'fighters': [participant dicts],
                'bracket': [(fighter1, fighter2), ...],  # KO pairs
                'bracket_phase': 'pool' or 'wb',
                'pool_size': pool_size,
                'is_quarantine': False
            }
        """
        self.logger.info(f"Reconstructing bracket '{bracket_key}' (ID {bracket_id}, type={bracket_type})")
        
        # Fetch all fights for this bracket from DB using TournamentService
        def _fetch_fights(svc):
            return svc.fights.get_by_bracket(bracket_id)
        
        from .database_service import DatabaseService
        db_svc = DatabaseService()
        fights = db_svc._execute_with_session(_fetch_fights)
        
        if not fights:
            self.logger.warning(f"No fights found for bracket ID {bracket_id}")
            return {
                'fighters': [],
                'bracket': [],
                'bracket_phase': 'wb' if bracket_type != 'pools' else 'pool',
                'pool_size': pool_size,
                'is_quarantine': False,
            }

        self.logger.info(f"Found {len(fights)} fight records")

        # Separate by phase
        pool_fights = [f for f in fights if f.bracket_phase == 'pool']
        ko_fights = [f for f in fights if f.bracket_phase != 'pool']

        bracket_data = {
            'fighters': [],
            'bracket': [],
            'bracket_phase': 'pool' if pool_fights else 'wb',
            'pool_size': pool_size,
            'is_quarantine': False,
        }

        if pool_fights:
            # Reconstruct pool bracket
            self.logger.info(f"Reconstructing pool bracket with {len(pool_fights)} pool fights")
            fighter_list = self._reconstruct_pool_order(pool_fights)
            bracket_data['fighters'] = fighter_list
            bracket_data['bracket_phase'] = 'pool'
        else:
            # Reconstruct KO bracket
            self.logger.info(f"Reconstructing KO bracket with {len(ko_fights)} KO fights")
            fighter_list = self._reconstruct_ko_participants(ko_fights)
            bracket_data['fighters'] = fighter_list
            bracket_data['bracket'] = self._reconstruct_ko_pairs(ko_fights)
            bracket_data['bracket_phase'] = 'wb'

        return bracket_data

    def _reconstruct_pool_order(self, pool_fights: List) -> List[Dict]:
        """
        Reconstruct original pool participant ordering by solving the position mapping.
        
        The fight generation algorithm is deterministic:
        - For pool_size=3: fights = [(0,2), (1,2), (0,1)]
        - For pool_size=4: fights = [(0,3), (1,2), (0,2), (1,3), (0,1), (2,3)]
        
        We match DB fights to expected positions and solve the inverse mapping.
        
        Args:
            pool_fights: List of Fight objects with bracket_phase='pool'
        
        Returns:
            List of participant dicts ordered by original pool position
        """
        self.logger.debug(f"Reconstructing pool order from {len(pool_fights)} fights")

        # Get unique pool_index values
        pool_indices = set(f.pool_index for f in pool_fights if f.pool_index is not None)
        self.logger.debug(f"Found {len(pool_indices)} pools: {sorted(pool_indices)}")

        all_participants = []

        for pool_idx in sorted(pool_indices):
            pool_fights_in_idx = [f for f in pool_fights if f.pool_index == pool_idx]
            self.logger.debug(f"Pool {pool_idx}: {len(pool_fights_in_idx)} fights")

            # Determine pool size from number of unique participants
            participant_ids = set()
            for f in pool_fights_in_idx:
                if f.participant1_id:
                    participant_ids.add(f.participant1_id)
                if f.participant2_id:
                    participant_ids.add(f.participant2_id)

            pool_size = len(participant_ids)
            self.logger.debug(f"Pool {pool_idx}: determined pool_size={pool_size}")

            # Generate expected fight schedule for this pool size
            expected_fights = self._generate_fight_schedule(pool_size)
            self.logger.debug(f"Expected {len(expected_fights)} fights for pool_size={pool_size}: {expected_fights}")

            # Solve position mapping by matching DB fights to expected positions
            position_map = self._solve_position_mapping(
                pool_fights_in_idx,
                expected_fights,
                pool_size
            )

            if not position_map:
                self.logger.warning(f"Could not solve position mapping for pool {pool_idx}")
                continue

            # Extract participants in mapped order
            self.logger.debug(f"Position map for pool {pool_idx}: {position_map}")

            pool_participants = []
            for pos in range(pool_size):
                participant_id = position_map.get(pos)
                if participant_id:
                    participant = self._get_participant_dict(participant_id)
                    if participant:
                        pool_participants.append(participant)
                        self.logger.debug(f"Pool {pool_idx}, position {pos}: {participant.get('Name', 'Unknown')}")

            all_participants.extend(pool_participants)

        return all_participants

    def _solve_position_mapping(
        self,
        db_fights: List,
        expected_fights: List[List[Tuple[int, int]]],
        pool_size: int,
    ) -> Dict[int, int]:
        """
        Solve the position mapping by matching DB fight participant IDs to expected positions.
        
        Args:
            db_fights: List of Fight objects from DB (all with same pool_index)
            expected_fights: List of (pos1, pos2) index pairs from algorithm
            pool_size: Size of pool
        
        Returns:
            Dict mapping position (0..pool_size-1) to participant ID
        """
        # Build participant ID pairs from DB fights
        db_fight_pairs = set()
        for f in db_fights:
            if f.participant1_id and f.participant2_id:
                # Normalize to sorted tuple (order doesn't matter in pool)
                pair = tuple(sorted([f.participant1_id, f.participant2_id]))
                db_fight_pairs.add(pair)

        self.logger.debug(f"DB fights: {db_fight_pairs}")

        # Try to solve: find position mapping where algorithm generates expected pairs
        # This is a constraint satisfaction problem — use brute force for small pools
        from itertools import permutations

        participant_ids = sorted(set(
            pid for f in db_fights
            for pid in [f.participant1_id, f.participant2_id]
            if pid is not None
        ))

        if len(participant_ids) != pool_size:
            self.logger.warning(
                f"Participant count mismatch: found {len(participant_ids)} "
                f"but expected {pool_size}"
            )

        # Try permutations to find matching assignment
        for perm in permutations(participant_ids):
            # For this permutation, check if it generates the expected fight pairs
            expected_pairs = set(
                tuple(sorted([perm[pos1], perm[pos2]]))
                for expected_fight_list in expected_fights
                for pos1, pos2 in expected_fight_list
            )

            if expected_pairs == db_fight_pairs:
                # Found matching permutation!
                position_map = {i: perm[i] for i in range(len(perm))}
                self.logger.info(f"Solved position mapping: {position_map}")
                return position_map

        self.logger.warning("Could not solve position mapping (no permutation matched)")
        # Fallback: return arbitrary mapping
        return {i: pid for i, pid in enumerate(participant_ids)}

    def _reconstruct_ko_participants(self, ko_fights: List) -> List[Dict]:
        """
        Extract unique participants from KO fights (those in round 0).
        
        Args:
            ko_fights: List of Fight objects with bracket_phase in ('wb', 'lb')
        
        Returns:
            List of participant dicts from round 0
        """
        # Get first round (round=0, bracket_phase='wb')
        first_round = [f for f in ko_fights if f.bracket_phase == 'wb' and f.round == 0]

        participant_ids = set()
        for f in first_round:
            participant_ids.add(f.participant1_id)
            participant_ids.add(f.participant2_id)

        participants = []
        for pid in sorted(participant_ids):
            participant = self._get_participant_dict(pid)
            if participant:
                participants.append(participant)
                self.logger.debug(f"KO participant: {participant.get('Name', 'Unknown')}")

        return participants

    def _reconstruct_ko_pairs(self, ko_fights: List) -> List[Tuple[str, str]]:
        """
        Reconstruct bracket pairs from KO fights (round 0).
        
        Args:
            ko_fights: List of Fight objects
        
        Returns:
            List of (name1, name2) tuples in round order
        """
        first_round = [f for f in ko_fights if f.bracket_phase == 'wb' and f.round == 0]
        first_round.sort(key=lambda f: f.pos_in_round or 0)

        pairs = []
        for f in first_round:
            p1 = self._get_participant_dict(f.participant1_id)
            p2 = self._get_participant_dict(f.participant2_id)

            p1_name = p1.get('Name', 'Unknown') if p1 else 'Unknown'
            p2_name = p2.get('Name', 'Unknown') if p2 else 'Unknown'

            pairs.append((p1_name, p2_name))
            self.logger.debug(f"KO pair: {p1_name} vs {p2_name}")

        return pairs

    def _get_participant_dict(self, participant_id: int) -> Optional[Dict]:
        """
        Fetch participant data and convert to display dict.
        
        Args:
            participant_id: GroupParticipant ID
        
        Returns:
            Dict with 'Name' and 'Verein' keys, or None if not found
        """
        def _fetch_participant(svc):
            from ..data.models import GroupParticipant, Participant
            
            gp = svc.db.query(GroupParticipant).filter_by(id=participant_id).first()
            if not gp:
                return None
            
            # Get linked Participant for full info
            participant = svc.db.query(Participant).filter_by(
                first_name=gp.participant.first_name,
                last_name=gp.participant.last_name
            ).first()
            
            if not participant:
                return None
            
            return {
                'Name': f"{participant.first_name} {participant.last_name}".strip(),
                'Verein': participant.club or '',
                'ID': participant_id,
            }
        
        try:
            result = self.db_service._execute_with_session(_fetch_participant)
            return result
        except Exception as e:
            self.logger.warning(f"Error fetching participant {participant_id}: {e}")
            return None

    @staticmethod
    def _generate_fight_schedule(pool_size: int) -> List[List[Tuple[int, int]]]:
        """
        Generate the deterministic fight schedule for a pool of given size.
        
        This matches the algorithm in pool_renderer.py `_generate_fight_schedule()`.
        
        Args:
            pool_size: Number of fighters in pool
        
        Returns:
            List of fight lists, each containing (pos1, pos2) pairs
        """
        if pool_size < 2:
            return []

        if pool_size == 2:
            # Best of three (see pool_renderer._generate_fight_schedule): the two
            # fighters meet three times so a 2-person bracket is decided by 2 of 3.
            return [[(0, 1)], [(0, 1)], [(0, 1)]]

        if pool_size == 3:
            return [[(0, 2)], [(1, 2)], [(0, 1)]]
        elif pool_size == 4:
            return [
                [(0, 3)],
                [(1, 2)],
                [(0, 2)],
                [(1, 3)],
                [(0, 1)],
                [(2, 3)],
            ]
        elif pool_size == 5:
            return [
                [(0, 4)],
                [(1, 3)],
                [(0, 2)],
                [(1, 4)],
                [(2, 3)],
                [(0, 3)],
                [(1, 2)],
                [(3, 4)],
                [(0, 1)],
                [(2, 4)],
            ]

        # For larger pools, use circle method
        n = pool_size if pool_size % 2 == 0 else pool_size + 1
        players = list(range(n))
        all_matches = []

        for round_num in range(n - 1):
            matches = []
            for i in range(n // 2):
                p1 = players[i]
                p2 = players[n - 1 - i]
                if p1 < pool_size and p2 < pool_size:
                    matches.append((p1, p2))
            if matches:
                all_matches.append(matches)

            players = [players[0]] + [players[-1]] + players[1:-1]

        return all_matches
