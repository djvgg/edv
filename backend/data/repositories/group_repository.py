# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional
from ..models import Group, GroupParticipant


class GroupRepository:
    def __init__(self, db):
        self.db = db

    def get_or_create(self, name: str, gender: str = None,
                      age_group: str = None, weight_class: str = None) -> Group:
        """Return existing group by name or create a new one."""
        group = self.db.query(Group).filter_by(name=name).first()
        if group is None:
            group = Group(name=name, gender=gender,
                          age_group=age_group, weight_class=weight_class)
            self.db.add(group)
            self.db.commit()
            self.db.refresh(group)
        return group

    def get_by_name(self, name: str) -> Group:
        return self.db.query(Group).filter_by(name=name).first()

    def clear_group_participants(self) -> None:
        """Clear only group_participants — leaves groups intact."""
        self.db.query(GroupParticipant).delete()
        self.db.commit()

    def add_participant(self, group_id: int, participant_id: int) -> GroupParticipant:
        """Link a participant to a group. Returns existing row if already linked."""
        existing = (
            self.db.query(GroupParticipant)
            .filter_by(group_id=group_id, participant_id=participant_id)
            .first()
        )
        if existing:
            return existing
        gp = GroupParticipant(group_id=group_id, participant_id=participant_id)
        self.db.add(gp)
        self.db.commit()
        self.db.refresh(gp)
        return gp

    def get_participants(self, group_id: int) -> List[GroupParticipant]:
        return (
            self.db.query(GroupParticipant)
            .filter(GroupParticipant.group_id == group_id)
            .all()
        )

    def get_all(self) -> List[Group]:
        return self.db.query(Group).all()

    def get_by_id(self, group_id: int) -> Optional[Group]:
        return self.db.query(Group).filter(Group.id == group_id).first()
