# EDV Backend — Session Memory

## Project Overview
Tournament management desktop app (Tkinter) for Judo competitions.
Participants are loaded from XLSX or website → grouped into brackets → fights monitored live.

## Tech Stack
- Python + Tkinter (desktop GUI)
- PostgreSQL via SQLAlchemy ORM (psycopg2 driver)
- pandas for XLSX parsing
- DB credentials in `.env` (host=172.17.192.28, db=mydatabase, user=myuser)

## Key Files
| File | Role |
|---|---|
| `main.py` | Entry point — calls `init_db()` then `main()` |
| `backend/data/database.py` | Engine, Base, SessionLocal, `init_db()`, `get_db()` |
| `backend/data/models.py` | All 6 SQLAlchemy models |
| `backend/data/repositories/participant_repository.py` | ParticipantRepository + `fetch_participants_from_db()` |
| `backend/data/repositories/group_repository.py` | GroupRepository |
| `backend/data/repositories/bracket_repository.py` | BracketRepository + mat helpers |
| `backend/data/repositories/fight_repository.py` | FightRepository |
| `backend/services/tournament_service.py` | TournamentService — orchestrates all repos |
| `frontend/views/main_window.py` | Main GUI — BracketViewerApp (tk.Tk) |
| `frontend/views/fight_monitoring_window.py` | FightMonitoringScreen |
| `utils/bracket_utils.py` | Core bracket generation logic |
| `backend/data/repositories/config_repository.py` | Reads bracket_config.xlsx |

## Database Schema (6 tables)
```
participants        — every registered person
groups              — age/gender/weight categories (UNIQUE constraint)
group_participants  — n:m junction (participant ↔ group)
brackets            — one bracket per group (type, status, mat)
mats                — 4 physical fighting areas
fights              — individual fights (created when monitoring opens)
```

## Data Flow
```
XLSX load → normalize_participants() → in-memory dicts {Name, Gender, Age, Weight, Verein}
         → export_all_brackets()     → self.brackets {bracket_key: {fighters, bracket, pool_size}}
         → save_participants()       → DB TRUNCATE + re-insert (fresh start)
         → Screen 3 confirmed        → save_groups_and_brackets() → groups + group_participants + brackets
         → Mat assigned              → assign_mat() → brackets.mat_id updated
         → Monitoring opened         → open_bracket_for_monitoring() → fights created
```

## Bracket Key Format
`"{gender} | {age_group} | {weight_class}"` e.g. `"m | U13 | -50kg"`
Unassigned keys have 4 parts: `"Unassigned | {gender} | {age_group} | {weight_class}"` — skipped in DB save.

## Important Design Decisions
- **XLSX load = always fresh start**: `TRUNCATE ... RESTART IDENTITY CASCADE` wipes all 6 tables, resets sequences to 1
- **`birth_date` derived from Age**: `date(today.year - age, 1, 1)` — German tournaments use Jahrgang (birth year), Jan 1 is correct granularity
- **Duplicate name handling**: `_find_participant` disambiguates by weight first, then birth year — needed because same name can appear in different age/weight groups
- **`_with_db()` helper**: creates fresh SQLAlchemy session per call — thread-safe, errors logged but never crash the app
- **`get_db()` is FastAPI-compatible**: generator pattern — ready for web API layer later
- **`members` table is dead**: website will write to `participants` going forward

## DB Write Hook Points (in main_window.py)
| Screen | Event | Service call |
|---|---|---|
| Screen 1 | XLSX loaded | `save_participants()` |
| Screen 1 | JSON loaded | `save_participants()` |
| Screen 3 | Generation confirmed | `save_groups_and_brackets()` |
| Screen 4 | Mat assigned (manual) | `assign_mat()` |
| Screen 4 | Auto-assign | `assign_mat()` all in one session |
| Monitoring | Window opens | `open_bracket_for_monitoring()` per bracket |

## Known Limitations
- "Load from DB" only works correctly when data came from website (has real birth_date). XLSX-loaded data now also works since we derive birth_date from Age.
- No HTTP API layer yet — needed before website can send data. Repositories are FastAPI-ready.
- Old `db_init/1_schema.sql` and `db_init/2_data.sql` still exist — safe to delete (SQLAlchemy owns schema now).

## Verified Working (session 2026-02-24)
- 700 participants loaded, IDs 1–700 (TRUNCATE resets sequence)
- 700/700 group_participants linked (duplicate name fix working)
- 32 groups, 32 brackets, 4 mats, 98 fights
- 11/11 FK integrity tests passed
