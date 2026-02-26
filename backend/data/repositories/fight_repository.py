# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Tuple
from ..models import Fight


class FightRepository:
    def __init__(self, db):
        self.db = db

    def create_fights(self, bracket_id: int, fight_pairs: List[Tuple[int, int]]) -> List[Fight]:
        """
        Bulk insert fight rows for a bracket.
        fight_pairs: list of (participant1_id, participant2_id) — GroupParticipant IDs.
        """
        fights = [
            Fight(
                bracket_id=bracket_id,
                participant1_id=p1,
                participant2_id=p2,
                fight_number=i + 1,
            )
            for i, (p1, p2) in enumerate(fight_pairs)
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

    def get_by_bracket(self, bracket_id: int) -> List[Fight]:
        return (
            self.db.query(Fight)
            .filter(Fight.bracket_id == bracket_id)
            .order_by(Fight.fight_number)
            .all()
        )

    def count_finished(self, bracket_id: int) -> int:
        return (
            self.db.query(Fight)
            .filter(Fight.bracket_id == bracket_id, Fight.status == 'completed')
            .count()
        )
