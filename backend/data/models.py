# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Date, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Participant(Base):
    __tablename__ = 'participants'
    __table_args__ = (
        # Two athletes can share a name, but not the same name + gender +
        # birth year + club combination.
        UniqueConstraint('first_name', 'last_name', 'gender', 'birth_date', 'club',
                         name='uix_participant_identity'),
    )

    id          = Column(Integer, primary_key=True)
    first_name  = Column(String(100), nullable=False)
    last_name   = Column(String(100), nullable=False)
    gender      = Column(String(1))        # 'm' or 'w'
    birth_date  = Column(Date, nullable=True)
    weight      = Column(Numeric(5, 2))
    club        = Column(String(200))
    association = Column(String(200))
    valid       = Column(Boolean, default=False)
    paid        = Column(Boolean, default=False)
    doublestart = Column(String(10), default='nein')   # 'nein', 'ja', 'höher'

    group_participants = relationship('GroupParticipant', back_populates='participant')


class Group(Base):
    __tablename__ = 'groups'

    id           = Column(Integer, primary_key=True)
    name         = Column(String(100), nullable=False, unique=True)  # 'm | U15 | -66kg' or 'QUARANTINE'
    gender       = Column(String(10),  nullable=True)   # 'm', 'w', None for QUARANTINE/U9/U11
    age_group    = Column(String(20),  nullable=True)   # 'U13', 'U15', None for QUARANTINE
    weight_class = Column(String(20),  nullable=True)   # '-66kg', 'no-class', None for QUARANTINE

    group_participants = relationship('GroupParticipant', back_populates='group')
    bracket            = relationship('Bracket', back_populates='group', uselist=False)


class AgeClassLock(Base):
    __tablename__ = 'age_class_locks'
    __table_args__ = (
        UniqueConstraint('scope_key', name='uix_age_class_lock_scope'),
    )

    id         = Column(Integer, primary_key=True)
    scope_key  = Column(String(30), nullable=False)
    age_group  = Column(String(20), nullable=False)
    gender     = Column(String(10), nullable=True)
    locked_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    reason     = Column(String(200), nullable=True)


class GroupParticipant(Base):
    __tablename__ = 'group_participants'

    id             = Column(Integer, primary_key=True)
    group_id       = Column(Integer, ForeignKey('groups.id'),       nullable=False)
    participant_id = Column(Integer, ForeignKey('participants.id'), nullable=False)

    group       = relationship('Group',       back_populates='group_participants')
    participant = relationship('Participant', back_populates='group_participants')
    fights_as_p1 = relationship('Fight', foreign_keys='Fight.participant1_id',
                                back_populates='participant1')
    fights_as_p2 = relationship('Fight', foreign_keys='Fight.participant2_id',
                                back_populates='participant2')


class Mat(Base):
    __tablename__ = 'mats'

    id         = Column(Integer, primary_key=True)
    mat_number = Column(Integer, nullable=False)

    brackets = relationship('Bracket', back_populates='mat')


class Bracket(Base):
    __tablename__ = 'brackets'

    id           = Column(Integer, primary_key=True)
    group_id     = Column(Integer, ForeignKey('groups.id'), nullable=False)
    mat_id       = Column(Integer, ForeignKey('mats.id'),   nullable=True)
    bracket_type = Column(String(20))                       # pools, double, ko, special
    status       = Column(String(20), default='pending')    # pending, in_progress, completed

    # Placements — set when bracket status → 'completed'
    first_place    = Column(Integer, ForeignKey('group_participants.id'), nullable=True)
    second_place   = Column(Integer, ForeignKey('group_participants.id'), nullable=True)
    third_place_1  = Column(Integer, ForeignKey('group_participants.id'), nullable=True)
    third_place_2  = Column(Integer, ForeignKey('group_participants.id'), nullable=True)

    group  = relationship('Group',   back_populates='bracket')
    mat    = relationship('Mat',     back_populates='brackets')
    fights = relationship('Fight',   back_populates='bracket')

    # Placement relationships (viewonly to avoid cascade conflicts)
    first_place_gp   = relationship('GroupParticipant', foreign_keys=[first_place],   viewonly=True)
    second_place_gp  = relationship('GroupParticipant', foreign_keys=[second_place],  viewonly=True)
    third_place_1_gp = relationship('GroupParticipant', foreign_keys=[third_place_1], viewonly=True)
    third_place_2_gp = relationship('GroupParticipant', foreign_keys=[third_place_2], viewonly=True)


class Fight(Base):
    __tablename__ = 'fights'
    __table_args__ = (
        UniqueConstraint('bracket_id', 'bracket_phase', 'round', 'pos_in_round',
                         name='uix_fight_position'),
    )

    id              = Column(Integer, primary_key=True)
    bracket_id      = Column(Integer, ForeignKey('brackets.id'),          nullable=False)
    participant1_id = Column(Integer, ForeignKey('group_participants.id'), nullable=True)
    participant2_id = Column(Integer, ForeignKey('group_participants.id'), nullable=True)
    fight_number    = Column(Integer)
    score1          = Column(Integer, nullable=True)
    score2          = Column(Integer, nullable=True)
    duration        = Column(Integer, nullable=True)
    status          = Column(String(20), default='pending')

    # Bracket position metadata
    bracket_phase = Column(String(10), nullable=False, default='wb')
    # 'pool' — round-robin fight within a pool
    # 'wb'   — winners bracket (main elimination tree)
    # 'lb'   — losers bracket (double elimination)
    round         = Column(Integer, nullable=True)
    # wb: 0=first round, 1=second, … deepest=final
    # lb: mirrors the wb round the loser dropped from (lb.round=R ↔ lost in wb.round=R)
    # pool: NULL  (pool_index identifies the pool instead)
    pos_in_round  = Column(Integer, nullable=True)
    # 0-indexed position within the round, or fight sequence within a pool
    pool_index    = Column(Integer, nullable=True)
    # pool/double-pool: which pool this fight belongs to (0=pool A, 1=pool B, …)
    # wb/lb: NULL

    # Mat / table assignment (set when bracket is assigned to a mat)
    table_id      = Column(Integer, nullable=True)

    # Result
    winner_id     = Column(Integer, ForeignKey('group_participants.id'), nullable=True)
    # NULL = fight not yet decided; set when status → 'completed'

    winner = relationship('GroupParticipant', foreign_keys=[winner_id])

    bracket      = relationship('Bracket',          back_populates='fights')
    participant1 = relationship('GroupParticipant', foreign_keys=[participant1_id],
                                back_populates='fights_as_p1')
    participant2 = relationship('GroupParticipant', foreign_keys=[participant2_id],
                                back_populates='fights_as_p2')
