# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later
"""Mini-Pool-Bracket fuer die Welle-2B.1-Verifikation.

4 Teilnehmer, 1 Pool, 6 Round-Robin-Fights. NICHT produktiv.
"""
import sys
from datetime import date

sys.path.insert(0, '.')

from backend.data.database import SessionLocal
from backend.data.models import (
    Bracket,
    Fight,
    Group,
    GroupParticipant,
    Participant,
)


def main():
    with SessionLocal() as session:
        athletes = [
            ('Eva',     'Eberhard', date(2010, 1, 1)),
            ('Frieda',  'Funk',     date(2010, 2, 1)),
            ('Greta',   'Graf',     date(2010, 3, 1)),
            ('Helene',  'Heins',    date(2010, 4, 1)),
        ]
        participants = []
        for fn, ln, dob in athletes:
            p = Participant(
                first_name=fn, last_name=ln, gender='w', birth_date=dob,
                club='Testverein', valid=True, paid=True,
            )
            session.add(p)
            participants.append(p)
        session.flush()

        group = Group(
            name='w | U15 | -57kg (pool-test)',
            gender='w', age_group='U15', weight_class='-57kg',
        )
        session.add(group)
        session.flush()

        gps = [
            GroupParticipant(group_id=group.id, participant_id=p.id) for p in participants
        ]
        session.add_all(gps)
        session.flush()

        bracket = Bracket(group_id=group.id, bracket_type='pools', status='pending')
        session.add(bracket)
        session.flush()

        # Round-Robin: 4er Pool -> 6 Fights (1v2, 1v3, 1v4, 2v3, 2v4, 3v4).
        pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        fights = []
        for i, (a, b) in enumerate(pairs):
            fights.append(Fight(
                bracket_id=bracket.id,
                participant1_id=gps[a].id,
                participant2_id=gps[b].id,
                fight_number=i + 1,
                status='pending',
                bracket_phase='pool',
                round=None,
                pos_in_round=None,
                pool_index=0,
            ))
        session.add_all(fights)
        session.commit()

        print(
            f"OK — group_id={group.id}, bracket_id={bracket.id}, "
            f"gps={[gp.id for gp in gps]}, fights={[f.id for f in fights]}"
        )


if __name__ == '__main__':
    main()
