# Integration Review — Critical Issues in Commits Zwischenstand & Hilfe

**Date:** 2026-03-04  
**Status:** These issues are BLOCKING the DB integration from working correctly

---

## Issue 1: GUI Calls DB Directly — VIOLATES Architecture

**Documented requirement (IGNORED):** main_window.py line 80: 
> "DO NOT add more logic to main_window. Wire services to callbacks instead."

**Violations in fight_monitoring_window.py:**
- Line 742: `self.db_service.record_fight_result()` during RENDER (wrong layer)
- Lines 1028, 1090, 1150: DB calls in click handlers (GUI owns business logic)
- Lines 1015-1025: CASCADE deletion logic in GUI (should be in service)

**Correct flow:** `GUI → Controller → BracketManagerService → TournamentService → DB`  
**Actual flow:** `GUI → DB` (no business logic layer)

---

## Issue 2: Duplicate DB Calls in 3 Locations

**File:** main_window.py

Same operation `create_fights_for_bracket()` called from:
1. Line 676 (show_fight_monitoring_screen)
2. Line 834 (_on_assign_bracket)
3. Line 902 (auto_assign_tables)

**Problem:** If user edits fighters (changes bye count), fights don't regenerate — DB still has old pair count.

**Should be:** `BracketManagerService.assign_and_create_fights()` (ONE place only)

---

## Issue 3: Missing Validations on Bracket Assignment

**File:** main_window.py line 811+

**Missing checks:**
- ✗ Can't prevent reassigning completed bracket
- ✗ Can't prevent reassigning already-assigned bracket
- ✗ Can't prevent reassigning in-progress bracket
- ✗ No DB-level `UNIQUE` constraint on `(bracket_id, mat_id)`

**Consequence:** Data orphaning, fights in inconsistent sessions

---

## Issue 4: Bye Results Written on EVERY RENDER

**File:** fight_monitoring_window.py lines 742, 917, 938

**Event:** Render called on zoom, click, resize, canvas update (3-5 times per user action)

**Code:**
```python
if self.db_service and 'Freilos' in (match['p1'], match['p2']):
    self.db_service.record_fight_result(...)  # ← EXECUTES ON EVERY RENDER
```

**Consequence:** DB write spam, wasted connections, bloated transaction logs

---

## Issue 5: ORM Misuse — Bulk Updates Without Refresh

**File:** bracket_repository.py line 20+

**Pattern:**
```python
def update_type(self, bracket_id: int, bracket_type: str) -> None:
    self.db.query(Bracket).filter(...).update({'bracket_type': bracket_type})
    self.db.commit()
    # NO .refresh() — object in memory is now STALE
```

**Consequence:** Silent data inconsistency bugs

**Fix:** Always `.refresh()` after bulk update

---

## Issue 6: Schema Missing Critical Constraints

**Missing:**
1. `UNIQUE(bracket_id, bracket_phase, round, pos_in_round)` on fights
2. `UNIQUE(mat_id) WHERE mat_id IS NOT NULL` on brackets
3. Placement relationships marked `viewonly=True` (forces raw SQL instead of ORM)

**Consequence:** Duplicates allowed at DB level, ORM can't express relationships

---

## Issue 7: Services NOT Fully Implemented

**Files:** main_window.py lines 84-94 shows PLANNED architecture

**Architecture planned:**
```
1. DataLoaderService      — load_and_generate, quarantine
2. BracketManagerService  — assign_to_table, unassign, sync fights
3. BracketRendererService — render_bracket, pool rendering
4. UIFeedbackService      — progress, status
5. ScreenManagerService   — show_* methods
```

**Current status:**
| Service | Status | Location |
|---------|--------|----------|
| DataLoaderService | ✗ NOT created | — |
| BracketManagerService | ⚠ PARTIAL (only `regenerate_stale_ko_brackets()`) | `frontend/services/bracket_manager.py` |
| BracketRendererService | ✗ NOT created | — |
| UIFeedbackService | ✓ CREATED & USED | `frontend/services/ui_feedback_service.py` |
| ScreenManagerService | ✗ NOT created | — |
| TaskRunner | ✓ CREATED & USED | `frontend/services/task_runner.py` |
| QuarantineService | ✓ CREATED & USED | `frontend/services/quarantine_service.py` |
| DatabaseService | ✓ CREATED & USED | `backend/services/database_service.py` |
| TournamentService | ✓ CREATED & USED | `backend/services/tournament_service.py` |
| BracketService | ✓ CREATED & USED | `backend/services/bracket_service.py` |

**What's missing:** 
- DataLoaderService (file loading logic scattered in main_window)
- BracketManagerService (fight management scattered in GUI click handlers)
- BracketRendererService (rendering logic in fight_monitoring_window)
- ScreenManagerService (show_* methods duplicate screen switching logic)

**Root cause of Issues 1, 2, 3, 4:** These missing services

---

## What Will Fail in Testing

1. ✗ **Duplicate fights will appear** → Cascade logic split between GUI and DB
2. ✗ **Bye results spam the DB** → Write spam on every mouse action
3. ✗ **Stale objects cause silent bugs** → Code reads old data
4. ✗ **Invalid bracket states allowed** → Can reassign completed brackets
5. ✗ **Data becomes inconsistent** → Orphaned fights, mixed sessions
6. ✗ **Hard to debug** → Logic scattered, no clear flow
7. ✗ **Can't add tests** → Can't test business logic without GUI

---

---

## Commit Analysis: "Fixed KO Bracket DB Writes" (3e6999a)

**What the commit addressed:** Issues 2 and 4 (duplicate fights, bye result spam)

**Solutions applied (DUCT-TAPE):**

| Issue | Band-Aid Applied | Root Cause (Still Unfixed) |
|-------|-----------------|--------------------------|
| **Duplicate fights** | Add `UNIQUE(bracket_id, bracket_phase, round, pos_in_round)` constraint at DB level + migration to clean up existing duplicates | 3 independent callers of `open_bracket_for_monitoring()` in main_window.py (lines 676, 834, 902) — should be 1 consolidated call |
| **Bye result spam** | Add `_bye_db_synced` tracking set to skip already-synced byes | `record_fight_result()` called from `_render()` pipeline on every mouse move — should be in event handlers only |
| **Fight numbering** | Count existing fights, start new at `existing_count + 1` | Dead field `fight_number` still exists; ordering uses `(bracket_phase, round, pos_in_round)` but legacy numbering creates confusion |

**What was fixed properly:**
- ✓ Fight order: Changed sorting from `fight_number` → `(bracket_phase, round, pos_in_round)` (correct)
- ✓ Placement trigger: Added `_maybe_compute_placements()` call after LB fights (correct)
- ✓ Window close: Added `on_closing()` handler (correct)

**Assessment:**
The commit prevented **symptoms** (duplicate data at DB) but did NOT fix **root causes** (architectural):
- UNIQUE constraint acts as safety net for bad architecture
- Bye tracking prevents spam but render pipeline still shouldn't call `record_fight_result()`
- Numbering workaround masks fact that 3 callers exist

**Result:** System now works but remains fragile. Any new code path that calls `open_bracket_for_monitoring()` will hit the UNIQUE constraint instead of being prevented architecturally.

---

## Severity

**These are foundational architectural issues — they prevent the integration from working correctly.**

**Status after "Fixed KO Bracket DB Writes":**
- ✓ Data corruption prevented (workaround)
- ✗ Root causes unfixed (3 callers still exist, render still calls DB)
- ✗ Architectural debt increased (workarounds now in codebase)

Most critical items to fix properly:
1. **Consolidate fight creation** (lines 676, 834, 902 → single entry point)
2. **Move result recording** (out of `_render()` → into click handlers)
3. **Create BracketManagerService** (centralize bracket + fight operations)
4. **Create DataLoaderService** (move file loading from main_window)
5. **Remove dead `fight_number` field** (now that we're using correct ordering)

Without fixing root causes, the system will accumulate more workarounds and become unmaintainable.
