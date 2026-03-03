# TODO: Database Integration — Fight Monitoring & Bracket Logic

**Author:** Session from 2026-03-03
**Status:** Work in progress — DB was down at end of session, changes untested after last round of edits

---

## What we were trying to do today

The goal was to get the **fights table** working correctly end-to-end:
1. Load participants from JSON
2. Assign brackets to mats
3. Open fight monitoring → fights get created in DB
4. Click through a KO bracket (pick winners) → results saved to DB
5. When bracket is done → **1st, 2nd, and two 3rd places** are stored in DB

We used the bracket **m | U15 | +66kg** (7 fighters, KO type) as the test case.

---

## Errors found

### Bug 1: Duplicate fights in DB (ROOT CAUSE FOUND & FIXED)

**Symptom:** Bracket 14 (m | U15 | +66kg) had "Frank Meyer vs Georg Patel" at BOTH wb R0 pos2 AND wb R0 pos3. One was pending (phantom), one was completed.

**Root cause:** Position index mismatch between in-memory rendering and DB.

How it happens:
- 7 fighters in KO → bracket pads to 8 (next power of 2) → 4 R0 matches, one is a Freilos (bye)
- **In-memory rendering** uses positions 0, 1, 2, 3 (all 4 slots including the bye)
- **Old DB code** filtered out Freilos matches and renumbered: 0, 1, 2 (only 3 real fights)
- When user clicks match at **rendering position 3**, the click handler sends `pos=3` to DB
- DB has no fight at pos 3 → `record_ko_result()` **lazily creates** a new fight → duplicate!

**Fix applied (in `tournament_service.py`):**
- `open_bracket_for_monitoring()` now stores ALL positions including byes
- Bye matches get `status='bye'` and `winner_id` pre-set (the real fighter auto-wins)
- Both `p1` and `p2` point to the real fighter (Freilos has no DB entry)
- DB positions now always match rendering positions — no more mismatch

**Fix applied (in `fight_repository.py`):**
- `create_fights()` now accepts optional `status` and `winner_id` fields in the fight dict

**Fix applied (in `tournament_service.py` `record_ko_result()`):**
- Added check: if `fight.status == 'bye'`, skip result update (don't overwrite a bye)

### Bug 2: No placement fields (FIXED — schema added, logic added, UNTESTED with live data)

**Problem:** The DB had no way to store who got 1st, 2nd, 3rd place in a bracket.

**Fix applied:**
- Added 4 nullable FK columns to `brackets` table:
  - `first_place` → group_participants.id
  - `second_place` → group_participants.id
  - `third_place_1` → group_participants.id
  - `third_place_2` → group_participants.id
- Schema was applied via ALTER TABLE (needs to be re-applied if DB gets recreated)
- Judo rule: last LB round survivors **both get 3rd place** (no 3rd-place fight)

### Bug 3: Logging wasn't visible in terminal (FIXED)

**Problem:** Custom logger only printed `error` and `warning` to console. `info` only went to log files.

**Fix applied (in `utils/logging/logger.py`):**
- Added `self.console_handler.emit(log_entry)` to the `info` level handler
- Now `info`, `warning`, and `error` all print to terminal

---

## What was changed (files modified)

| File | What changed |
|------|-------------|
| `backend/data/models.py` | Added `first_place`, `second_place`, `third_place_1`, `third_place_2` columns + relationships to `Bracket` |
| `backend/data/repositories/bracket_repository.py` | Added `set_placements()` method |
| `backend/data/repositories/fight_repository.py` | `create_fights()` now accepts `status` and `winner_id` |
| `backend/services/tournament_service.py` | Rewrote Freilos handling in `open_bracket_for_monitoring()`, added `compute_and_store_placements()`, added extensive logging to `record_ko_result()`, `assign_mat()`, `unassign_mat()` |
| `backend/services/database_service.py` | Added `compute_placements()` facade, added logging to `assign_bracket_to_table()`, `create_fights_for_bracket()`, `record_fight_result()`, `reset_fight_result()`, `delete_fight_position()` |
| `frontend/views/fight_monitoring_window.py` | Added logging to `[WB CLICK]`, `[LB CLICK]`, `[MATTEN REFRESH]`, `_compute_rounds()`. Added `_maybe_compute_placements()` that auto-triggers when WB final is decided |
| `utils/logging/logger.py` | `info` level now also prints to console |

---

## How the DB + bracket logic works together

### The 6 tables

```
participants        — every registered person (from JSON or website)
groups              — categories like "m | U15 | -66kg" (UNIQUE name)
group_participants  — n:m junction: which participant is in which group
brackets            — one per group: type (ko/pools/double), status, mat assignment, placements
mats                — 4 physical fighting areas (mat 1-4)
fights              — individual fight rows with positions, scores, winners
```

### Data flow through the app screens

```
Screen 1 (File Load):
  JSON → normalize → save_participants() → TRUNCATE all 6 tables, insert participants
       → initialize_all_groups() → create all group rows from bracket_config.xlsx

Screen 2 (Group Preview):
  User reviews/edits groups → save_groups() → re-sync group_participants

Screen 3 (Generation Method):
  User picks KO/pools/double per bracket → save_brackets() → create bracket rows

Screen 4 (Mat Assignment):
  User drags brackets to mats 1-4 → assign_mat() → brackets.mat_id updated

Fight Monitoring:
  Opening monitoring screen → show_fight_monitoring_screen() iterates all assigned brackets:
    → create_fights_for_bracket() → open_bracket_for_monitoring()
      → For KO: creates wb R0 fight rows (including byes with status='bye')
      → For pools: creates all round-robin pairs
    → Existing fights are returned if already created (idempotent)

  User clicks a name to pick winner:
    → [WB CLICK] or [LB CLICK] logged
    → record_fight_result() → record_ko_result()
      → Finds fight by (bracket_id, phase, round, pos)
      → If not found (rounds 1+): lazily creates fight row from p1_name/p2_name
      → Sets winner_id, status='completed', score='1'/'0'

  When WB final winner is picked:
    → _maybe_compute_placements() triggers
    → compute_and_store_placements() reads all fights for the bracket
    → WB final winner = 1st, WB final loser = 2nd
    → Last LB round survivors = both 3rd (Judo rule: no 3rd-place fight)
    → Stored in brackets.first_place / second_place / third_place_1 / third_place_2
```

### KO bracket structure (example: 7 fighters)

```
WB (Winners Bracket):
  R0: 4 matches (pos 0-3), one is a bye
    pos0: Fighter A vs Fighter B
    pos1: Fighter C vs Fighter D
    pos2: Fighter E vs Fighter F
    pos3: Fighter G vs Freilos (bye) → G auto-advances

  R1 (Semi-finals): 2 matches
    pos0: winner(R0.0) vs winner(R0.1)
    pos1: winner(R0.2) vs winner(R0.3)

  R2 (Final): 1 match
    pos0: winner(R1.0) vs winner(R1.1) → WINNER = 1st place, LOSER = 2nd place

LB (Losers Bracket):
  LB R0: losers from WB R0 paired up
  LB R1: LB R0 winners vs WB R1 losers (injection round)
  ...continues until 2 survivors remain
  Last LB round: both survivors = 3rd place (NO fight between them)
```

### How fights are stored in DB

```sql
-- WB fight example
fights: id=1, bracket_id=14, participant1_id=27, participant2_id=28,
        bracket_phase='wb', round=0, pos_in_round=0,
        status='completed', winner_id=27, score1='1', score2='0'

-- Bye fight example (NEW)
fights: id=4, bracket_id=14, participant1_id=32, participant2_id=32,
        bracket_phase='wb', round=0, pos_in_round=3,
        status='bye', winner_id=32

-- Lazily created fight (rounds 1+)
fights: id=5, bracket_id=14, participant1_id=27, participant2_id=29,
        bracket_phase='wb', round=1, pos_in_round=0,
        status='completed', winner_id=27, score1='1', score2='0'

-- LB fight
fights: id=8, bracket_id=14, participant1_id=28, participant2_id=31,
        bracket_phase='lb', round=0, pos_in_round=0,
        status='completed', winner_id=28, score1='1', score2='0'
```

---

## End goal (how it SHOULD work when everything is done)

1. User loads JSON → all participants in DB
2. Groups auto-created from config
3. Brackets created with type (ko/pools/double)
4. Brackets assigned to mats 1-4
5. Monitoring opens → all R0 fights pre-created in DB (including byes)
6. User clicks through every match → results saved in real-time
7. Later rounds created lazily as winners become known
8. LB fights created lazily as losers drop down
9. When final is decided → placements auto-computed and stored
10. All of this visible in terminal via logging (look for `[WB CLICK]`, `[RECORD RESULT]`, `[PLACEMENTS]` etc.)
11. On app restart, existing fights are loaded from DB (idempotent — no duplicates)

---

## What's NOT working / still needs testing

### Critical (must fix)

- [ ] **Bye handling untested with live data** — The new bye logic (`status='bye'`, both p1/p2 = real fighter) was written but DB went down before we could test a fresh bracket creation. Need to load JSON, go through all screens, and verify R0 fights are correct.

- [ ] **Placement computation untested with fresh data** — We ran `compute_and_store_placements()` once on old (partially broken) data and it returned correct results. But `_maybe_compute_placements()` (auto-trigger on WB final click) was never tested in the actual GUI.

- [ ] **Schema migration on fresh DB** — If the DB gets recreated (TRUNCATE or drop_all), the 4 new columns need to exist. `init_db()` uses `Base.metadata.create_all()` which handles this — but verify it works. If not, run these ALTER TABLEs manually:
  ```sql
  ALTER TABLE brackets ADD COLUMN first_place INTEGER REFERENCES group_participants(id);
  ALTER TABLE brackets ADD COLUMN second_place INTEGER REFERENCES group_participants(id);
  ALTER TABLE brackets ADD COLUMN third_place_1 INTEGER REFERENCES group_participants(id);
  ALTER TABLE brackets ADD COLUMN third_place_2 INTEGER REFERENCES group_participants(id);
  ```

- [ ] **Old duplicate data still in DB** — We deleted one duplicate row (fight #3) manually, but if there are other brackets with similar issues from before the fix, they might still have duplicates. After DB is back, run:
  ```sql
  SELECT bracket_id, bracket_phase, round, pos_in_round, COUNT(*)
  FROM fights
  GROUP BY bracket_id, bracket_phase, round, pos_in_round
  HAVING COUNT(*) > 1;
  ```

### Architectural issues (found in code review — cause data inconsistency)

- [ ] **Bracket generation is NOT deterministic across restarts** — `bracket_utils.py` uses `_group_by_club()` → `_distribute_round_robin()` which iterates dict keys. If participants load in a different order (e.g. different JSON, or DB load), the club dict has different insertion order → different bracket pairings. This means **restarting the app can produce different fight matchups at the same positions**. Fix: sort club keys alphabetically before distributing, or persist the bracket pairs to DB.

- [ ] **`_clear_downstream()` doesn't sync to DB** — When a user changes an upstream WB result, `_clear_downstream()` in `fight_monitoring_window.py` deletes results from the in-memory `match_results` dict, BUT the DB delete calls happen separately in the click handler (only for direct children via `delete_fight_position`). The cascade logic between memory and DB is split across two places — easy to get out of sync. Same for `_clear_loser_downstream()`.

- [ ] **No unique constraint on fight positions** — The `fights` table has no `UNIQUE(bracket_id, bracket_phase, round, pos_in_round)` constraint. The DB happily accepts duplicate fights at the same position. Adding this constraint would catch bugs at the DB level instead of silently creating bad data:
  ```sql
  ALTER TABLE fights ADD CONSTRAINT uq_fight_position
    UNIQUE (bracket_id, bracket_phase, round, pos_in_round);
  ```

- [ ] **`fight_number` is broken for lazy-created fights** — `create_fights()` sets `fight_number = i + 1` based on the batch index. Lazy-created fights (rounds 1+) are always created in single-item batches, so they ALL get `fight_number=1`. The `get_by_bracket()` sorts by `fight_number`, which means lazy fights are in wrong order. Fix: compute fight_number from existing max, or use `(bracket_phase, round, pos_in_round)` for ordering instead.

- [ ] **New DB session per click** — `_execute_with_session()` in `database_service.py` creates a new `SessionLocal()` for every single operation. Each winner click = open connection → create TournamentService → query → commit → close. Under rapid clicking this could exhaust the connection pool. Consider keeping a session alive for the duration of the monitoring screen.

- [ ] **Bracket regen check is wrong** — `bracket_manager.py:29` checks `len(current_bracket) != len(fighters) // 2` to decide if a bracket is "stale". But with bye-padding (power-of-2), pair count != fighters//2. Example: 7 fighters → 4 pairs, but 7//2 = 3 → always triggers regen. This means brackets get regenerated unnecessarily on every monitoring open, and combined with the non-deterministic generation, can produce different pairings each time.

### Design consideration: split fights into multiple tables

The current single `fights` table tries to handle 3 very different fight structures with the same columns. This causes confusion and NULL-heavy rows:

| Column | KO fights | Pool fights | Double-pool fights |
|--------|-----------|-------------|-------------------|
| `bracket_phase` | 'wb' or 'lb' | 'pool' | 'pool' then 'wb' |
| `round` | 0, 1, 2... (elimination round) | NULL (not applicable) | NULL for pool phase, 0+ for KO phase |
| `pos_in_round` | position in that round | fight sequence in pool | mixed meaning |
| `pool_index` | NULL (not applicable) | 0, 1, 2... (which pool) | 0 or 1 (pool A/B) |
| `winner_id` | set on click | set on score entry | depends on phase |
| `score1/score2` | '1'/'0' (just win/loss) | actual Judo scores (e.g. '7', '10') | both patterns |

**Problems with one table:**
- `round` and `pool_index` are mutually exclusive — one is always NULL
- `score1/score2` means different things (win/loss flag vs actual score)
- `pos_in_round` has different semantics per type
- Queries need `WHERE bracket_phase = ...` everywhere
- Hard to add pool-specific fields (pool standings, points) without polluting KO rows
- Hard to add KO-specific fields (bye status, seed position) without polluting pool rows
- Double-pool brackets transition from pool phase to KO phase mid-bracket — the current schema can't cleanly represent this

**Suggested split:**

```
ko_fights (for KO and special brackets)
  — bracket_id, round, pos_in_round
  — participant1_id, participant2_id
  — winner_id, status ('pending'/'bye'/'completed')
  — phase ('wb'/'lb')

pool_fights (for pool and double-pool round-robin phase)
  — bracket_id, pool_index, fight_sequence
  — participant1_id, participant2_id
  — score1, score2, winner_id
  — status ('pending'/'completed')

double_pool_ko_fights (for the KO phase after double-pool round-robin)
  — same structure as ko_fights
  — OR: reuse ko_fights table with a flag indicating it came from a double-pool bracket
```

**Alternative (simpler):** Keep one `fights` table but add a `fight_type` column ('ko'/'pool'/'double_ko') and accept that some columns will be NULL. This is less clean but avoids migration complexity.

**Decision needed:** Is the split worth it now, or should we stabilize the current single-table approach first and split later? The single table works — it's just messy and harder to query/debug.

### Nice to have / future work

- [ ] **Add more logging** — Pool brackets (`_render_pool`, `_finish_pool`, pool score cell editing) have minimal logging. Same for the group preview and generation method screens.

- [ ] **LB placement auto-trigger** — Currently `_maybe_compute_placements()` only triggers on WB clicks. If the user clicks the last LB fight AFTER the WB final, placements won't update the 3rd-place fields. Should also trigger on LB clicks when bracket is fully decided.

- [ ] **Load fight results from DB on restart** — Currently `match_results` and `loser_match_results` dicts are empty on restart. The fight rows exist in DB but are NOT loaded back into memory. This means the bracket view shows all fights as undecided even though results are in DB. Need a method to rebuild in-memory state from DB fights.

- [ ] **Pool bracket placements** — `compute_and_store_placements()` only works for KO brackets. Pool brackets need a different logic (based on pool standings / points).

- [ ] **Display placements in UI** — The placement data is stored but never shown in the GUI. Could add a summary panel or overlay when a bracket is completed.

- [ ] **Bracket status tracking** — `_bracket_status()` in fight_monitoring_window.py computes status from in-memory data. Should also check/update the DB `brackets.status` field.

- [ ] **Pool cell values / KO bracket data not persisted** — `pool_cell_values` and `ko_bracket_data` dicts in fight_monitoring_window.py are in-memory only. Lost on restart.

---

## Log files location

All logs go to `logs/<logger_name>/`:
- `logs/tournament_service/app.info.log` — service-level operations
- `logs/database_service/app.info.log` — DB facade operations
- `logs/fight_monitoring/app.info.log` — GUI click events
- `logs/<name>/app.all.log` — everything combined per logger
- `logs/<name>/app.debug.log` — debug-level detail

After the logger fix, `info` level also prints to terminal/console.

---

## Quick test checklist

When DB is back up:

1. Start app, load JSON
2. Go through to mat assignment — check terminal for `[MAT ASSIGN]` logs
3. Open monitoring — check terminal for `[CREATE FIGHTS]` logs
4. Pick a 7-fighter KO bracket, click through all WB matches
   - Check terminal for `[WB CLICK]` and `[RECORD RESULT]` on each click
5. Click through all LB matches
   - Check terminal for `[LB CLICK]` and `[RECORD RESULT]`
6. Pick the WB final winner
   - Check terminal for `[PLACEMENTS]` log with 1st/2nd/3rd
7. Verify in DB:
   ```sql
   SELECT b.id, g.name, b.status, b.first_place, b.second_place, b.third_place_1, b.third_place_2
   FROM brackets b JOIN groups g ON b.group_id = g.id
   WHERE b.first_place IS NOT NULL;
   ```
