<!-- SPDX-FileCopyrightText: 2026 TOP Team Combat Control
SPDX-License-Identifier: CC0-1.0 -->

# TODO — Next Session

## Priority 1 — Fight Score Write-Through (WP12)
The monitoring window (`fight_monitoring_window.py`) handles click-to-record winners
but does NOT yet write scores to the DB. Need to wire:
- `FightRepository.update_score(fight_id, score1, score2, duration)`
- `FightRepository.set_status(fight_id, 'completed')`
- `BracketRepository.set_status(bracket_id, 'completed')` when all fights done

The monitoring screen currently stores results in `self.match_results` (in-memory dict).
Need to pass a `_with_db` callback or service reference into `FightMonitoringScreen`
so it can persist on each click.

Key question to discuss: does the monitoring window get a service instance passed in,
or does it call back to main_window which calls `_with_db`?

## Priority 2 — "Load from DB" path
Currently `fetch_participants_from_db()` reads participants from DB and returns
`{Name, Gender, Age, Weight, Verein}` dicts. Age is calculated from `birth_date`.
This path should now work since we store birth_date from XLSX load.

Need to test: close app → reopen → "Load from DB" → verify brackets generate correctly
with same groups as original XLSX load.

## Priority 3 — Cleanup (quick)
- Delete `db_init/1_schema.sql` and `db_init/2_data.sql` — SQLAlchemy owns schema now
- These files are stale and misleading

## Priority 4 — HTTP API layer (bigger task, plan first)
When website wants to POST participants directly to the DB, we need FastAPI endpoints.
The repositories are already FastAPI-compatible (`get_db()` generator pattern).
Rough plan:
- Add `fastapi` and `uvicorn` to `requirements.txt`
- Create `backend/api/` with route handlers
- `POST /participants` → `ParticipantRepository.add_bulk()`
- `GET /participants` → `ParticipantRepository.get_all()`
- Run FastAPI alongside the Tkinter app (separate thread or process)

Discuss with user: should the website replace XLSX entirely, or run alongside?

## Notes for next session
- Colleague is implementing new XLSX reader with proper fields (first_name, last_name,
  birth_date separately instead of combined Name + Age). When that lands, update
  `_map_to_model` in `tournament_service.py` to use the new fields directly.
- The `members` table in old schema is dead — confirm with team before dropping it.
- Test data has some very large groups (m|18+|-60kg has 116 fighters) — check if
  real tournament data will be more reasonable.
