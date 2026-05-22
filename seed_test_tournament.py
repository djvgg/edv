# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later
"""Seed a minimal KO tournament for end-to-end verification of the score
pipeline. NOT a production tool. Only used by the Welle-1 verification.

Creates:
- 4 participants (drawn from existing members)
- 1 group 'm | U15 | -66kg'
- 4 group_participants
- 1 KO bracket
- 3 fights (semi1, semi2, final) — final has NULL participants until propagation
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
            ('Anna',  'Adler',   date(2010, 5, 1)),
            ('Bea',   'Berger',  date(2010, 8, 12)),
            ('Clara', 'Cordes',  date(2010, 3, 20)),
            ('Dora',  'Dahler',  date(2010, 11, 7)),
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

        group = Group(name='w | U15 | -52kg (test)', gender='w', age_group='U15', weight_class='-52kg')
        session.add(group)
        session.flush()

        group_participants = [
            GroupParticipant(group_id=group.id, participant_id=p.id) for p in participants
        ]
        session.add_all(group_participants)
        session.flush()

        bracket = Bracket(group_id=group.id, bracket_type='ko', status='pending')
        session.add(bracket)
        session.flush()

        gp_ids = [gp.id for gp in group_participants]
        fights = [
            Fight(bracket_id=bracket.id, participant1_id=gp_ids[0],
                  participant2_id=gp_ids[1], fight_number=1, status='pending',
                  bracket_phase='wb', round=0, pos_in_round=0),
            Fight(bracket_id=bracket.id, participant1_id=gp_ids[2],
                  participant2_id=gp_ids[3], fight_number=2, status='pending',
                  bracket_phase='wb', round=0, pos_in_round=1),
            Fight(bracket_id=bracket.id, participant1_id=None,
                  participant2_id=None, fight_number=3, status='pending',
                  bracket_phase='wb', round=1, pos_in_round=0),
        ]
        session.add_all(fights)
        session.commit()

        print(f"OK — group_id={group.id}, bracket_id={bracket.id}, "
              f"fights={[f.id for f in fights]}")


if __name__ == '__main__':
    main()
