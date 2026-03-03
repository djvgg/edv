<!-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
SPDX-License-Identifier: CC0-1.0 -->

# Database Plan — SQLAlchemy Implementation

## Schema (Final, Normalized)

```
participants        — every registered person (first_name, last_name, club, association, valid, paid)
groups              — age/gender/weight categories, UNIQUE per combination
group_participants  — n:m junction (person ↔ group, handles double-start cleanly)
brackets            — tournament bracket per group (type, status, mat assignment)
mats                — physical fighting areas (1–4)
fights              — individual fights with scores, created at monitoring time
```

### Normalization notes
- `participants`: `birth_date` nullable — XLSX gives no birth date, only age is needed for bracket
  logic. `birth_date` kept for future use. Age is NOT stored (derivable from birth_date, or
  calculated at load time and passed to bracket logic without persisting).
- `groups`: `bracket_key` NOT stored — derivable as `f"{gender} | {age_group} | {weight_class}"`.
  Constructed in application code when needed.
- `group_participants`: pure junction table — no `punkte`, `ubw`, `platz`, `start_nr`, `pool_label`.
  All derived from fights at query time.
- `brackets`: no `total_fights` / `finished_fights` — both derivable via COUNT on `fights`.
- `fights`: `bracket_id` kept as a practical denormalization for direct lookups
  (technically derivable via participant1 → group_participants → group → bracket).

---

## Work Package 1 — Setup SQLAlchemy

**Goal:** Get SQLAlchemy wired into the project.

### Steps

1. Add `sqlalchemy` to `requirements.txt`
2. Create `backend/data/database.py`
   - Build DATABASE_URL from existing `DB_CONFIG`
   - Create engine, `SessionLocal` factory, `Base` declarative base
   - `init_db()` calls `Base.metadata.create_all()` — creates all tables on app startup
   - `get_db()` context manager for repository use

```python
# backend/data/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .db_config import DB_CONFIG

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables if they do not exist. Called once at app startup."""
    import backend.data.models  # noqa: F401 — must be imported before create_all
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

3. Call `init_db()` in `main.py` before the GUI starts:

```python
# main.py
from backend.data.database import init_db
init_db()
```

### Docker — no SQL init files needed

Since `init_db()` creates tables at app startup, the SQL init files are no longer needed.

- Delete `db_init/2_data.sql`
- Delete `db_init/1_schema.sql`
- The `db_init/` folder can be removed or left empty

Docker starts PostgreSQL → app runs `init_db()` → tables exist → ready.
One source of truth: the SQLAlchemy models.

---

## Work Package 2 — Define Models

**Goal:** All 6 tables as SQLAlchemy model classes in one file.

### File: `backend/data/models.py`

```python
# backend/data/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Date,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class Participant(Base):
    __tablename__ = 'participants'

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

    group_participants = relationship('GroupParticipant', back_populates='participant')


class Group(Base):
    __tablename__ = 'groups'
    __table_args__ = (
        UniqueConstraint('gender', 'age_group', 'weight_class'),
    )

    id           = Column(Integer, primary_key=True)
    gender       = Column(String(1),  nullable=False)
    age_group    = Column(String(20), nullable=False)  # U9, U11, U13, U15, U18, 18+
    weight_class = Column(String(20), nullable=False)  # -52kg, no-class, etc.

    group_participants = relationship('GroupParticipant', back_populates='group')
    bracket            = relationship('Bracket', back_populates='group', uselist=False)


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
    bracket_type = Column(String(20))                  # pools, double, ko, special
    status       = Column(String(20), default='pending')  # pending, in_progress, completed

    group  = relationship('Group',   back_populates='bracket')
    mat    = relationship('Mat',     back_populates='brackets')
    fights = relationship('Fight',   back_populates='bracket')


class Fight(Base):
    __tablename__ = 'fights'

    id              = Column(Integer, primary_key=True)
    bracket_id      = Column(Integer, ForeignKey('brackets.id'),          nullable=False)
    participant1_id = Column(Integer, ForeignKey('group_participants.id'), nullable=False)
    participant2_id = Column(Integer, ForeignKey('group_participants.id'), nullable=False)
    fight_number    = Column(Integer)
    score1          = Column(String(20))
    score2          = Column(String(20))
    duration        = Column(String(20))
    status          = Column(String(20), default='pending')

    bracket      = relationship('Bracket',          back_populates='fights')
    participant1 = relationship('GroupParticipant', foreign_keys=[participant1_id],
                                back_populates='fights_as_p1')
    participant2 = relationship('GroupParticipant', foreign_keys=[participant2_id],
                                back_populates='fights_as_p2')
```

---

## Work Package 3 — Repositories

**Goal:** One repository class per domain. Each receives a SQLAlchemy session on init.

### File structure

```
backend/data/repositories/
    participant_repository.py   ← rewrite (currently uses raw psycopg2)
    group_repository.py         ← new
    bracket_repository.py       ← new
    fight_repository.py         ← new
```

### Pattern (same for all)

```python
class ParticipantRepository:
    def __init__(self, db):
        self.db = db

    def add(self, participant: Participant) -> Participant:
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant
```

### Key methods per repository

**`ParticipantRepository`**
- `add_bulk(participants_data)` — bulk insert from XLSX/JSON load
- `get_all()` — fetch all participants
- `get_by_id(id)`
- `clear_all()` — wipe table for fresh tournament day

**`GroupRepository`**
- `get_or_create(gender, age_group, weight_class)` → Group
- `add_participant(group_id, participant_id)` → GroupParticipant
- `get_participants(group_id)` → list of GroupParticipant

**`BracketRepository`**
- `create(group_id, bracket_type)` → Bracket
- `update_type(bracket_id, bracket_type)` — when user changes pool→ko etc.
- `assign_mat(bracket_id, mat_id)` — on mat assignment
- `set_status(bracket_id, status)`
- `get_by_group(group_id)` → Bracket
- `get_by_mat(mat_id)` → list of Bracket

**`FightRepository`**
- `create_fights(bracket_id, fight_pairs)` — bulk insert on monitoring window open
- `update_score(fight_id, score1, score2, duration)` — write-through on score entry
- `set_status(fight_id, status)`
- `get_by_bracket(bracket_id)` → list of Fight
- `count_finished(bracket_id)` → int

---

## Work Package 4 — DB Write Flow (agreed)

The DB is written in stages as the user moves through the app screens:

```
SCREEN 1 — Load XLSX / JSON
    → ParticipantRepository.clear_all()       clear previous day
    → ParticipantRepository.add_bulk()        write all participants

SCREEN 2 — Group Preview (user may reassign people between groups)
    → changes held in memory only

SCREEN 3 — Generation Method (user assigns pool/ko type)
    → on confirm:
        GroupRepository.get_or_create()       write groups
        GroupRepository.add_participant()     write group_participants
        BracketRepository.create()            write brackets with type

    → if user changes type afterwards:
        BracketRepository.update_type()       update bracket_type

SCREEN 4 — Mat Assignment
    → MatRepository / init 4 mat rows if not present
    → BracketRepository.assign_mat()          on each assignment

MONITORING WINDOW — opened per bracket
    → FightRepository.create_fights()         generate + insert fight rows HERE
                                              (fight IDs born at this point)
    → FightRepository.update_score()          on each score entry (write-through)
    → BracketRepository.set_status()          when all fights done
```

### New service: `backend/services/tournament_service.py`

Orchestrates repositories, called from `main_window.py`:

```python
class TournamentService:
    def __init__(self, db):
        self.db = db
        self.participants = ParticipantRepository(db)
        self.groups       = GroupRepository(db)
        self.brackets     = BracketRepository(db)
        self.fights       = FightRepository(db)

    def save_participants(self, raw_participants):
        """Called immediately after XLSX/JSON load."""

    def save_groups_and_brackets(self, brackets_dict):
        """Called after generation method screen is confirmed."""

    def update_bracket_type(self, bracket_key, new_type):
        """Called when user changes pool→ko etc."""

    def assign_mat(self, bracket_key, mat_number):
        """Called on mat assignment."""

    def open_bracket_for_monitoring(self, bracket_key):
        """Generates and inserts fight rows. Returns fight IDs."""
```

---

## Work Package 5 — Migrate Existing Code

- Rewrite `participant_repository.py` (raw psycopg2 → SQLAlchemy)
- Update `main_window.py` `load_from_database()` to use new repository
- Delete `db_init/2_data.sql`
- Delete `db_init/1_schema.sql`

---

## Integration Map

```
main_window.py
    │
    ├── XLSX/JSON loaded
    │       └── TournamentService.save_participants()
    │
    ├── Generation method confirmed
    │       └── TournamentService.save_groups_and_brackets()
    │
    ├── Bracket type changed
    │       └── TournamentService.update_bracket_type()
    │
    ├── Mat assigned
    │       └── TournamentService.assign_mat()
    │
    └── Monitor Tournament opened (per bracket)
            └── TournamentService.open_bracket_for_monitoring()
                    → fight rows created here
                    └── FightRepository.update_score()  on each score
```

---

## File Checklist

| File | Action |
|------|--------|
| `requirements.txt` | add `sqlalchemy` |
| `backend/data/database.py` | new — engine, Base, init_db(), get_db() |
| `backend/data/models.py` | new — all 6 model classes |
| `backend/data/repositories/participant_repository.py` | rewrite (psycopg2 → SQLAlchemy) |
| `backend/data/repositories/group_repository.py` | new |
| `backend/data/repositories/bracket_repository.py` | new |
| `backend/data/repositories/fight_repository.py` | new |
| `backend/services/tournament_service.py` | new |
| `frontend/views/main_window.py` | wire TournamentService at each screen transition |
| `main.py` | add `init_db()` call before GUI starts |
| `db_init/2_data.sql` | delete |
| `db_init/1_schema.sql` | delete |

---

## Implementation Order

```
1. requirements.txt              add sqlalchemy
2. database.py                   engine + Base + init_db()
3. models.py                     all 6 model classes
4. main.py                       call init_db() — verify tables created in PostgreSQL
5. participant_repository.py     rewrite
6. group_repository.py           new
7. bracket_repository.py         new
8. fight_repository.py           new
9. tournament_service.py         orchestration layer
10. main_window.py               wire service at each screen transition
11. delete db_init SQL files
12. monitoring_window.py         fight score write-through (separate work package)
```
