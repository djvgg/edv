# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Dict
from datetime import date
from ..models import Participant


def _calculate_age(birth_date: date) -> int:
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def fetch_participants_from_db() -> List[Dict]:
    """
    Module-level convenience function for loading participants.
    Used by main_window.py to load participants from the database.
    Returns dicts in the format the bracket generator expects.
    """
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        return ParticipantRepository(db).get_all_as_dicts()
    finally:
        db.close()


class ParticipantRepository:
    def __init__(self, db):
        self.db = db

    def add_bulk(self, participants_data: List[Dict]) -> List[Participant]:
        """Bulk insert participants from a list of dicts (XLSX/JSON/website format)."""
        objects = [Participant(**data) for data in participants_data]
        self.db.add_all(objects)
        self.db.commit()
        return objects

    def get_all(self) -> List[Participant]:
        return self.db.query(Participant).all()

    def get_all_as_dicts(self) -> List[Dict]:
        """Return participants in the dict format the bracket generator expects."""
        rows = self.db.query(Participant).all()
        result = []
        for p in rows:
            age = _calculate_age(p.birth_date) if p.birth_date else None
            # Need strict mapping back to frontend model here
            is_valid = p.valid if p.valid is not None else True
            is_paid = p.paid if p.paid is not None else True
            gender_mapped = 'male' if p.gender == 'm' else ('female' if p.gender == 'w' else p.gender)
            result.append({
                'ID': p.id,
                'Firstname': p.first_name,
                'Lastname': p.last_name,
                'Name':    f"{p.first_name} {p.last_name}".strip(),
                'Birthyear': p.birth_date.year if p.birth_date else None,
                'Age':     age,
                'Club': p.club or '',
                'Verein':  p.club or '',
                'Association': p.association or '',
                'Weight':  float(p.weight) if p.weight else None,
                'Valid': is_valid,
                'Paid': is_paid,
                'Gender': gender_mapped
            })
        return result

    def get_by_id(self, participant_id: int) -> Participant:
        return self.db.query(Participant).filter(Participant.id == participant_id).first()

    def clear_all(self) -> None:
        """Wipe all participants — called at the start of a fresh tournament day."""
        self.db.query(Participant).delete()
        self.db.commit()
