# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional
from ..models import Bracket, Mat


class BracketRepository:
    def __init__(self, db):
        self.db = db

    def create(self, group_id: int, bracket_type: str) -> Bracket:
        bracket = Bracket(group_id=group_id, bracket_type=bracket_type)
        self.db.add(bracket)
        self.db.commit()
        self.db.refresh(bracket)
        return bracket

    def update_type(self, bracket_id: int, bracket_type: str) -> None:
        self.db.query(Bracket).filter(Bracket.id == bracket_id).update(
            {'bracket_type': bracket_type}
        )
        self.db.commit()

    def assign_mat(self, bracket_id: int, mat_id: int) -> None:
        self.db.query(Bracket).filter(Bracket.id == bracket_id).update(
            {'mat_id': mat_id}
        )
        self.db.commit()

    def set_status(self, bracket_id: int, status: str) -> None:
        self.db.query(Bracket).filter(Bracket.id == bracket_id).update(
            {'status': status}
        )
        self.db.commit()

    def get_by_group(self, group_id: int) -> Optional[Bracket]:
        return self.db.query(Bracket).filter(Bracket.group_id == group_id).first()

    def get_by_mat(self, mat_id: int) -> List[Bracket]:
        return self.db.query(Bracket).filter(Bracket.mat_id == mat_id).all()

    def get_all(self) -> List[Bracket]:
        return self.db.query(Bracket).all()

    # --- Mat helpers ---

    def get_or_create_mat(self, mat_number: int) -> Mat:
        mat = self.db.query(Mat).filter(Mat.mat_number == mat_number).first()
        if mat is None:
            mat = Mat(mat_number=mat_number)
            self.db.add(mat)
            self.db.commit()
            self.db.refresh(mat)
        return mat

    def get_all_mats(self) -> List[Mat]:
        return self.db.query(Mat).order_by(Mat.mat_number).all()
