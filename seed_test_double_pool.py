# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later
"""Mini-Doppelpool-Bracket fuer die Welle-2B.2-Verifikation.

8 Teilnehmer, 2 Pools (je 4) Round-Robin = 12 Pool-Fights.
KO-Stage (3 Fights: HF1, HF2, Finale) wird vom Backend lazy/eager
nach Pool-Abschluss erzeugt. NICHT produktiv.
"""
import sys
from datetime import date
from itertools import combinations

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
            ('Ida',     'Ihle',     date(2010, 1, 1)),
            ('Jana',    'Just',     date(2010, 2, 1)),
            ('Kira',    'Klar',     date(2010, 3, 1)),
            ('Lena',    'Lutz',     date(2010, 4, 1)),
            ('Mara',    'Mai',      date(2010, 5, 1)),
            ('Nora',    'Nann',     date(2010, 6, 1)),
            ('Olga',    'Opel',     date(2010, 7, 1)),
            ('Petra',   'Pfaff',    date(2010, 8, 1)),
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
            name='w | U15 | -63kg (double-pool-test)',
            gender='w', age_group='U15', weight_class='-63kg',
        )
        session.add(group)
        session.flush()

        gps = [
            GroupParticipant(group_id=group.id, participant_id=p.id) for p in participants
        ]
        session.add_all(gps)
        session.flush()

        bracket = Bracket(group_id=group.id, bracket_type='double', status='pending')
        session.add(bracket)
        session.flush()

        # Pool A = gp[0..3], Pool B = gp[4..7]. Je 4 Teilnehmer -> 6 Round-Robin-Fights.
        pool_a = list(range(0, 4))
        pool_b = list(range(4, 8))

        fights = []
        fn = 0
        for pool_idx, pool in enumerate([pool_a, pool_b]):
            for pos, (a, b) in enumerate(combinations(pool, 2)):
                fn += 1
                fights.append(Fight(
                    bracket_id=bracket.id,
                    participant1_id=gps[a].id,
                    participant2_id=gps[b].id,
                    fight_number=fn,
                    status='pending',
                    bracket_phase='pool',
                    round=None,
                    pos_in_round=None,
                    pool_index=pool_idx,
                ))
        session.add_all(fights)
        session.commit()

        print(
            f"OK — group_id={group.id}, bracket_id={bracket.id}, "
            f"gps={[gp.id for gp in gps]}, fights_count={len(fights)}"
        )


if __name__ == '__main__':
    main()
