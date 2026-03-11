# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional
from sqlalchemy import or_, and_
from ..models import Fight


class FightRepository:
    def __init__(self, db):
        self.db = db

    def create_fights(self, bracket_id: int, fight_pairs: List[dict], table_id: str = None) -> List[Fight]:
        """
        Bulk insert fight rows for a bracket.

        Each dict in fight_pairs must have:
            p1           — GroupParticipant ID for fighter 1
            p2           — GroupParticipant ID for fighter 2
        Optional (default shown):
            bracket_phase — 'wb' | 'pool' | 'lb'   (default 'wb')
            round         — int or None             (default None)
            pos_in_round  — int or None             (default index i)
            pool_index    — int or None             (default None)
            status        — 'pending' | 'bye'       (default 'pending')
            winner_id     — int or None             (default None, set for byes)
        table_id: mat number string to stamp on each fight (e.g. '1', '2')
        """
        existing_count = self.db.query(Fight).filter(Fight.bracket_id == bracket_id).count()
        start_num = existing_count + 1
        fights = [
            Fight(
                bracket_id=bracket_id,
                participant1_id=fp['p1'],
                participant2_id=fp['p2'],
                fight_number=start_num + i,
                bracket_phase=fp.get('bracket_phase', 'wb'),
                round=fp.get('round'),
                pos_in_round=fp.get('pos_in_round', i),
                pool_index=fp.get('pool_index'),
                status=fp.get('status', 'pending'),
                winner_id=fp.get('winner_id'),
                table_id=table_id,
            )
            for i, fp in enumerate(fight_pairs)
        ]
        self.db.add_all(fights)
        self.db.commit()
        return fights

    def update_score(
        self,
        fight_id: int,
        score1: str,
        score2: str,
        duration: str,
    ) -> None:
        self.db.query(Fight).filter(Fight.id == fight_id).update(
            {'score1': score1, 'score2': score2, 'duration': duration}
        )
        self.db.commit()

    def set_status(self, fight_id: int, status: str) -> None:
        self.db.query(Fight).filter(Fight.id == fight_id).update({'status': status})
        self.db.commit()

    def get_by_position(
        self, bracket_id: int, phase: str, round_num: int, pos: int
    ) -> Optional[Fight]:
        """Look up a single fight by its bracket position (KO / LB fights)."""
        return (
            self.db.query(Fight)
            .filter(
                Fight.bracket_id   == bracket_id,
                Fight.bracket_phase == phase,
                Fight.round         == round_num,
                Fight.pos_in_round  == pos,
            )
            .first()
        )

    def get_by_participants(
        self, bracket_id: int, p1_id: int, p2_id: int
    ) -> Optional[Fight]:
        """Look up a fight by participant IDs regardless of slot order (pool fights)."""
        return (
            self.db.query(Fight)
            .filter(
                Fight.bracket_id == bracket_id,
                or_(
                    and_(Fight.participant1_id == p1_id, Fight.participant2_id == p2_id),
                    and_(Fight.participant1_id == p2_id, Fight.participant2_id == p1_id),
                ),
            )
            .first()
        )

    def set_result(self, fight_id: int, winner_id: int) -> None:
        """Mark a fight as completed and record the winner."""
        self.db.query(Fight).filter(Fight.id == fight_id).update(
            {'winner_id': winner_id, 'status': 'completed'}
        )
        self.db.commit()

    def reset_result(self, fight_id: int) -> None:
        """Clear a fight result (user de-selected the winner)."""
        self.db.query(Fight).filter(Fight.id == fight_id).update(
            {'winner_id': None, 'status': 'pending', 'score1': None, 'score2': None}
        )
        self.db.commit()

    def set_score(self, fight_id: int, score1: str, score2: str) -> None:
        """Update raw score strings (used for pool score cells)."""
        self.db.query(Fight).filter(Fight.id == fight_id).update(
            {'score1': score1, 'score2': score2}
        )
        self.db.commit()

    def get_by_bracket(self, bracket_id: int) -> List[Fight]:
        return (
            self.db.query(Fight)
            .filter(Fight.bracket_id == bracket_id)
            .order_by(Fight.bracket_phase, Fight.round, Fight.pos_in_round)
            .all()
        )

    def count_finished(self, bracket_id: int) -> int:
        return (
            self.db.query(Fight)
            .filter(Fight.bracket_id == bracket_id, Fight.status == 'completed')
            .count()
        )

    def delete_by_position(
        self, bracket_id: int, phase: str, round_num: int, pos: int
    ) -> None:
        """Delete a single fight by bracket position (used when undoing results
        so lazily-created rounds can be re-created with correct participants)."""
        self.db.query(Fight).filter(
            Fight.bracket_id    == bracket_id,
            Fight.bracket_phase == phase,
            Fight.round         == round_num,
            Fight.pos_in_round  == pos,
        ).delete()
        self.db.commit()
