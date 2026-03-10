# UI/Database Architecture Issue Analysis

**Date:** 2026-03-09  
**Severity:** 🔴 HIGH - Architectural Flaw  
**File:** `frontend/views/_table_bracket_assignment.py`

---

## Problem Statement

The UI layer directly calls database service methods, violating the **Separation of Concerns** principle.

### Evidence

**File:** `frontend/views/_table_bracket_assignment.py`

```python
class _AssignmentMixin:
    def assign_to_table(self, table_num):
        # ... UI logic ...
        
        # ❌ UI DIRECTLY CALLS DATABASE
        self.main_window.db_service.assign_and_create_fights(
            bracket_key,
            table_num=table_num,
            fight_pairs=bracket_data.get('bracket', []),
            bracket_type=self.main_window.bracket_generation_methods.get(bracket_key, 'ko'),
            fighters=bracket_data.get('fighters', []),
            pool_size=bracket_data.get('pool_size'),
        )
        # ... more UI logic ...

    def unassign_bracket(self, bracket_key=None):
        # ... UI logic ...
        
        # ❌ UI DIRECTLY CALLS DATABASE
        self.main_window.db_service.unassign_bracket_from_table(bracket_key)
        # ... more UI logic ...
```

### Why This Is a Problem

1. **Tight Coupling**
   - UI code is tightly coupled to database implementation
   - Changes to database layer require UI changes
   - Cannot swap database implementations easily

2. **Testing Difficulty**
   - UI tests require full database setup
   - Cannot test UI logic in isolation
   - Mocking becomes complex

3. **Violation of Separation of Concerns**
   - UI should handle presentation and user interaction
   - Database should handle persistence
   - Business logic mixed with presentation logic

4. **Maintainability**
   - Hard to understand responsibilities
   - Changes ripple across layers
   - Code reuse difficult

5. **Scalability Issues**
   - Cannot easily add transaction management
   - Difficult to add async operations
   - Hard to add caching or other middleware

---

## Current Architecture (Problematic)

```
┌─────────────────────────────────────┐
│       UI Layer (Tkinter)            │
│   _table_bracket_assignment.py      │
│                                     │
│   ┌──────────────┐                 │
│   │ Button Click │                 │
│   └──────┬───────┘                 │
│          │                          │
│          │ Direct Call ❌           │
│          ▼                          │
│   ┌──────────────────┐             │
│   │ main_window      │             │
│   │  .db_service     │◄────────────┤───┐
│   │  .brackets       │             │   │
│   │  .bracket_table_ │             │   │
│   │   assignment     │             │   │
│   └──────────────────┘             │   │
└─────────────────────────────────────┘   │
                                          │
                                          │
┌─────────────────────────────────────┐   │
│    Database Layer                   │   │
│    backend/data/database.py         │   │
│                                     │   │
│    assign_and_create_fights()      │◄──┘
│    unassign_bracket_from_table()    │
│                                     │
└─────────────────────────────────────┘
```

---

## Recommended Architecture (Clean)

```
┌─────────────────────────────────────┐
│       UI Layer (Tkinter)            │
│   _table_bracket_assignment.py      │
│                                     │
│   ┌──────────────┐                 │
│   │ Button Click │                 │
│   └──────┬───────┘                 │
│          │                          │
│          │ Emit Event ✅            │
│          ▼                          │
│   ┌──────────────────┐             │
│   │ Event/Callback   │             │
│   └──────┬───────────┘             │
└──────────┼─────────────────────────┘
           │
           │
┌──────────▼─────────────────────────┐
│    Service/Controller Layer        │
│    backend/services/               │
│    tournament_service.py           │
│                                    │
│  • Business logic                  │
│  • Validation                      │
│  • Orchestration                   │
│  • Transaction management          │
│                                    │
│   assign_bracket_to_table()        │
│   unassign_bracket()               │
│                                    │
└──────────┬─────────────────────────┘
           │
           │
┌──────────▼─────────────────────────┐
│    Database Layer (Repository)     │
│    backend/data/                   │
│                                    │
│  • Pure persistence logic          │
│  • CRUD operations                 │
│  • Query building                  │
│                                    │
└────────────────────────────────────┘
```

---

## Solution Approaches

### Option 1: Event/Callback Pattern (Recommended for Tkinter) ✅

**Pros:**
- ✅ Clean separation
- ✅ Works well with Tkinter
- ✅ Easy to test
- ✅ Minimal refactoring

**Implementation:**

```python
# In main_window.py or a service layer
class TournamentController:
    """Orchestrates tournament operations between UI and database."""
    
    def __init__(self, db_service, state):
        self.db_service = db_service
        self.state = state  # TournamentState
    
    def assign_bracket_to_table(self, bracket_key: str, table_num: int) -> bool:
        """Business logic for bracket assignment."""
        # Validation
        if bracket_key not in self.state.brackets:
            return False
        
        # Update state
        self.state.bracket_table_assignment[bracket_key] = table_num
        
        # Persist to database
        bracket_data = self.state.brackets[bracket_key]
        self.db_service.assign_and_create_fights(
            bracket_key,
            table_num=table_num,
            fight_pairs=bracket_data.get('bracket', []),
            bracket_type=self.state.bracket_generation_methods.get(bracket_key, 'ko'),
            fighters=bracket_data.get('fighters', []),
            pool_size=bracket_data.get('pool_size'),
        )
        
        return True
    
    def unassign_bracket(self, bracket_key: str) -> bool:
        """Business logic for bracket unassignment."""
        if bracket_key not in self.state.bracket_table_assignment:
            return False
        
        self.state.bracket_table_assignment[bracket_key] = None
        self.db_service.unassign_bracket_from_table(bracket_key)
        return True


# In _table_bracket_assignment.py (UI)
class _AssignmentMixin:
    def assign_to_table(self, table_num):
        """UI handler for table assignment."""
        if not self.bracket_listbox.curselection():
            messagebox.showinfo('No Selection', 'Please select a bracket first.')
            return
        
        display_text = self.bracket_listbox.get(self.bracket_listbox.curselection()[0])
        bracket_key = self.bracket_listbox_map.get(display_text, display_text)
        
        # ✅ Call controller instead of database
        success = self.controller.assign_bracket_to_table(bracket_key, table_num)
        
        if success:
            self.update_bracket_list()
            self.update_table_panels()
            self.logger.info(f"Assigned '{bracket_key}' to Matte {table_num}")
        else:
            messagebox.showerror('Error', 'Failed to assign bracket')
```

---

### Option 2: Service Locator Pattern

**Pros:**
- ✅ Decouples UI from services
- ✅ Easy to swap implementations
- ✅ Good for dependency injection

**Cons:**
- ⚠️ More complex
- ⚠️ Can hide dependencies

---

### Option 3: Command Pattern

**Pros:**
- ✅ Very clean separation
- ✅ Easy to add undo/redo
- ✅ Easy to test
- ✅ Easy to add logging/auditing

**Cons:**
- ⚠️ More code
- ⚠️ More complex for simple operations

---

## Implementation Plan (Option 1 - Recommended)

### Phase 1: Create Service Layer ✅

1. **Create `backend/services/tournament_service.py`**

```python
# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service layer for tournament operations."""

from typing import Optional
from utils.logging import get_logger

logger = get_logger('tournament_service')


class TournamentService:
    """Orchestrates tournament operations between UI and database."""
    
    def __init__(self, db_service, state):
        """Initialize with database service and tournament state.
        
        Args:
            db_service: Database service for persistence
            state: TournamentState for in-memory state
        """
        self.db_service = db_service
        self.state = state
    
    def assign_bracket_to_table(self, bracket_key: str, table_num: int) -> tuple[bool, Optional[str]]:
        """Assign a bracket to a table.
        
        Args:
            bracket_key: Bracket identifier (e.g., "M | U13 | -50kg")
            table_num: Table number (1-8)
        
        Returns:
            (success, error_message)
        """
        # Validation
        if bracket_key not in self.state.brackets:
            return False, f"Bracket '{bracket_key}' not found"
        
        if table_num < 1 or table_num > 8:
            return False, f"Invalid table number: {table_num}"
        
        # Update in-memory state
        self.state.bracket_table_assignment[bracket_key] = table_num
        
        # Persist to database
        try:
            bracket_data = self.state.brackets[bracket_key]
            self.db_service.assign_and_create_fights(
                bracket_key,
                table_num=table_num,
                fight_pairs=bracket_data.get('bracket', []),
                bracket_type=self.state.bracket_generation_methods.get(bracket_key, 'ko'),
                fighters=bracket_data.get('fighters', []),
                pool_size=bracket_data.get('pool_size'),
            )
            logger.info(f"Assigned '{bracket_key}' to table {table_num}")
            return True, None
        except Exception as e:
            logger.error(f"Failed to assign bracket: {e}")
            # Rollback in-memory state
            self.state.bracket_table_assignment[bracket_key] = None
            return False, str(e)
    
    def unassign_bracket(self, bracket_key: str) -> tuple[bool, Optional[str]]:
        """Unassign a bracket from its table.
        
        Args:
            bracket_key: Bracket identifier
        
        Returns:
            (success, error_message)
        """
        if bracket_key not in self.state.bracket_table_assignment:
            return False, "Bracket not currently assigned"
        
        old_table = self.state.bracket_table_assignment.get(bracket_key)
        if not old_table:
            return False, "Bracket not currently assigned to any table"
        
        try:
            self.state.bracket_table_assignment[bracket_key] = None
            self.db_service.unassign_bracket_from_table(bracket_key)
            logger.info(f"Unassigned '{bracket_key}' from table {old_table}")
            return True, None
        except Exception as e:
            logger.error(f"Failed to unassign bracket: {e}")
            # Rollback
            self.state.bracket_table_assignment[bracket_key] = old_table
            return False, str(e)
    
    def get_assigned_table(self, bracket_key: str) -> Optional[int]:
        """Get the table number a bracket is assigned to."""
        return self.state.bracket_table_assignment.get(bracket_key)
    
    def get_unassigned_brackets(self) -> list[str]:
        """Get list of brackets not assigned to any table."""
        return [
            k for k in self.state.brackets.keys()
            if not self.state.bracket_table_assignment.get(k)
        ]
```

### Phase 2: Update Main Window

2. **Modify `frontend/views/main_window.py`** (or wherever initialization happens)

```python
from backend.services.tournament_service import TournamentService

class MainWindow:
    def __init__(self, ...):
        # ... existing init ...
        
        # Create service layer
        self.tournament_service = TournamentService(
            db_service=self.db_service,
            state=self.state  # or however state is accessed
        )
```

### Phase 3: Update UI Mixin

3. **Modify `frontend/views/_table_bracket_assignment.py`**

Replace direct database calls with service calls:

```python
class _AssignmentMixin:
    def assign_to_table(self, table_num):
        """Assign selected bracket to a table."""
        if not self.bracket_listbox.curselection():
            messagebox.showinfo('No Selection', 'Please select a bracket first.')
            return
        
        display_text = self.bracket_listbox.get(self.bracket_listbox.curselection()[0])
        bracket_key = self.bracket_listbox_map.get(display_text, display_text)
        
        # ✅ Use service layer instead of direct DB calls
        success, error = self.main_window.tournament_service.assign_bracket_to_table(
            bracket_key, table_num
        )
        
        if success:
            self.update_bracket_list()
            self.update_table_panels()
            self.logger.info(f"Assigned '{bracket_key}' to Matte {table_num}")
        else:
            messagebox.showerror('Error', f'Failed to assign bracket: {error}')
    
    def unassign_bracket(self, bracket_key=None):
        """Unassign bracket from its table."""
        if not bracket_key:
            selection = self.bracket_listbox.curselection()
            if not selection:
                messagebox.showinfo('No Selection', 'Please select a bracket first.')
                return
            bracket_key = self.bracket_listbox.get(selection[0])
        
        # ✅ Use service layer
        success, error = self.main_window.tournament_service.unassign_bracket(bracket_key)
        
        if success:
            self.update_bracket_list()
            self.update_table_panels()
            self.logger.info(f"Unassigned '{bracket_key}'")
        else:
            messagebox.showinfo('Error', error or 'Failed to unassign bracket')
```

### Phase 4: Add Tests

4. **Create `tests/test_tournament_service.py`**

Now you can test the business logic without a database or UI:

```python
# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for tournament service layer."""

import pytest
from unittest.mock import Mock, MagicMock

from backend.services.tournament_service import TournamentService
from frontend.state import TournamentState


class TestTournamentService:
    @pytest.fixture
    def mock_db_service(self):
        return Mock()
    
    @pytest.fixture
    def state(self):
        state = TournamentState()
        state.brackets = {
            'M | U13 | -50kg': {
                'bracket': [('Alice', 'Bob')],
                'fighters': [{'Name': 'Alice'}, {'Name': 'Bob'}],
            }
        }
        state.bracket_generation_methods = {'M | U13 | -50kg': 'ko'}
        return state
    
    @pytest.fixture
    def service(self, mock_db_service, state):
        return TournamentService(mock_db_service, state)
    
    def test_assign_bracket_success(self, service, mock_db_service):
        success, error = service.assign_bracket_to_table('M | U13 | -50kg', 1)
        
        assert success is True
        assert error is None
        assert service.state.bracket_table_assignment['M | U13 | -50kg'] == 1
        mock_db_service.assign_and_create_fights.assert_called_once()
    
    def test_assign_bracket_invalid_table(self, service):
        success, error = service.assign_bracket_to_table('M | U13 | -50kg', 99)
        
        assert success is False
        assert 'Invalid table number' in error
    
    def test_assign_bracket_not_found(self, service):
        success, error = service.assign_bracket_to_table('Nonexistent', 1)
        
        assert success is False
        assert 'not found' in error
    
    def test_unassign_bracket(self, service):
        # First assign
        service.assign_bracket_to_table('M | U13 | -50kg', 1)
        
        # Then unassign
        success, error = service.unassign_bracket('M | U13 | -50kg')
        
        assert success is True
        assert service.state.bracket_table_assignment['M | U13 | -50kg'] is None
```

---

## Benefits After Refactoring

1. **✅ Testability**
   - UI can be tested with mock service
   - Service can be tested with mock database
   - Each layer tested independently

2. **✅ Maintainability**
   - Clear responsibilities
   - Easy to locate business logic
   - Changes isolated to appropriate layer

3. **✅ Flexibility**
   - Can swap database implementations
   - Can add caching layer
   - Can add transaction management

4. **✅ Reusability**
   - Service layer can be used by CLI
   - Service layer can be used by API
   - UI components can be reused

---

## Timeline Estimate

- **Small Project:** 4-8 hours
  - Create service layer: 2 hours
  - Update UI: 2 hours
  - Add tests: 2-4 hours

- **Full Refactor:** 2-3 days
  - If multiple UI files need updating
  - If adding comprehensive tests
  - If adding transaction management

---

## Decision

**Status:** ⏳ Awaiting team decision

**Recommendation:** Implement Option 1 (Event/Callback with Service Layer)

---

**Analyzed By:** Code Quality Review  
**Date:** 2026-03-09  
**Priority:** HIGH (but not blocking if time-constrained)
