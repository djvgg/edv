# Component Dependency Map

**Visual Guide to Project Structure and Dependencies**

---

## Layer Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                          │
│                   (User Interface - Tkinter)                     │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  frontend/views/main_window.py                             │  │
│  │  - BracketViewerApp(tk.Tk) - Main application window       │  │
│  │  - Screen management & navigation                          │  │
│  │  - Event handlers & callbacks                              │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                 ↓
                          USES / IMPORTS
                                 ↓
┌──────────────────────────────────────────────────────────────────┐
│                       STYLING & UTILITIES                        │
│                                                                   │
│  ┌──────────────────────┐    ┌─────────────────────────────┐   │
│  │ frontend/styles.py   │    │ frontend/utils/             │   │
│  │                      │    │ - bracket_renderer.py       │   │
│  │ COLORS {}           │    │ - pool_renderer.py          │   │
│  │ FONTS {}            │    │ - participant_loader.py     │   │
│  │ BUTTON_STYLES {}    │    │ - bracket_cache.py          │   │
│  │ apply_*_style() fn. │    │                             │   │
│  └──────────────────────┘    └─────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                 ↓
                          USES / IMPORTS
                                 ↓
┌──────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  backend/services/bracket_service.py                       │  │
│  │  - Thin wrapper/coordinator                                │  │
│  │  - set_bracket_config(),  ensure_config_loaded()          │  │
│  │  - get_age_group(), get_weight_class(), get_pool_size()   │  │
│  │  - make_bracket(), export_all_brackets()                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                 ↓
                          DELEGATES TO
                                 ↓
┌──────────────────────────────────────────────────────────────────┐
│                   DATA & CORE LOGIC LAYER                        │
│                                                                   │
│  ┌──────────────────────────┐  ┌───────────────────────────┐   │
│  │ /utils/bracket_utils.py  │  │ backend/data/             │   │
│  │                          │  │                           │   │
│  │ · Bracket algorithms    │  │ repositories/             │   │
│  │ · Pool calculations     │  │ - config_repository.py    │   │
│  │ · Config loading        │  │ - participant_repository.│   │
│  │ · Export logic          │  │                           │   │
│  │ · Age/weight classes   │  │ db_config.py              │   │
│  │                          │  │ - Database setup          │   │
│  └──────────────────────────┘  └───────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                 ↓
                          ACCESSES / USES
                                 ↓
┌──────────────────────────────────────────────────────────────────┐
│                   EXTERNAL RESOURCES                             │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ · Database (Postgres via db_config                       │   │
│  │ · Excel Files (.xlsx) for config and participants        │   │
│  │ · JSON Cache Files (brackets_*.json)                     │   │
│  │ · Logging System (utils/logging/)                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Dependencies

### Main Window Dependencies
```
frontend/views/main_window.py
├── Imports from frontend/styles.py
│   ├── COLORS
│   ├── FONTS
│   ├── apply_button_style()
│   ├── apply_entry_style()
│   └── apply_label_style()
│
├── Imports from frontend/utils/
│   ├── calculate_box_size()
│   ├── load_participants_from_xlsx()
│   ├── normalize_participants()
│   └── draw_pools_on_canvas()
│
├── Imports from backend/services/
│   ├── bracket_service.set_bracket_config()
│   ├── bracket_service.make_bracket()
│   ├── bracket_service.export_all_brackets()
│   └── bracket_service.get_*() functions
│
├── Imports from backend/data/repositories/
│   └── fetch_participants_from_db()
│
└── Imports from utils/logging/
    └── get_logger()
```

### Bracket Service Dependencies
```
backend/services/bracket_service.py
├── Imports from utils/bracket_utils.py
│   ├── make_bracket()
│   ├── export_all_brackets()
│   ├── get_age_group()
│   ├── get_weight_class()
│   └── get_pool_size()
│
├── Imports from backend/data/repositories/
│   └── ConfigRepository
│
└── Imports from utils/logging/
    └── get_logger()
```

### Frontend Utils Dependencies
```
frontend/utils/
├── bracket_renderer.py
│   └── Pure functions (no external deps except tkinter)
│
├── pool_renderer.py
│   └── Pure functions (no external deps except tkinter)
│
├── participant_loader.py
│   ├── Fallback: judgefrontend.src.xlsxHandler (if available)
│   ├── Fallback: pandas (if available)
│   └── logging module
│
└── bracket_cache.py
    ├── json module
    ├── os/sys modules
    └── logging module
```

### Bracket Utils Dependencies
```
utils/bracket_utils.py
├── Imports from backend/data/repositories/
│   └── ConfigRepository
│
├── Imports from utils/logging/
│   └── get_logger()
│
└── Core Python modules
    ├── math
    ├── os
    └── sys
```

---

## Data Flow in Key Operations

### 1. Bracket Generation Flow

```
User selects XLSX → main_window calls load_participants_from_xlsx()
                                          ↓
                         normalize_participants()
                                          ↓
                   User presses "Generate Bracket"
                                          ↓
                  main_window calls bracket_service.make_bracket()
                                          ↓
                   bracket_service checks config (ensure_config_loaded())
                                          ↓
                    bracket_service delegates to bracket_utils.make_bracket()
                                          ↓
                bracket_utils.make_bracket():
                  ├─ get_age_group() from config
                  ├─ get_weight_class() from config
                  ├─ Algorithm: compute bracket pairings
                  └─ Return bracket tuples
                                          ↓
              main_window gets bracket data
                                          ↓
         main_window calls frontend/utils/bracket_renderer functions:
                  ├─ build_bracket_rounds()
                  ├─ calculate_box_size()
                  └─ draw_bracket_on_canvas()
                                          ↓
                      Bracket displayed on canvas
                                          ↓
          main_window optionally caches: bracket_cache.save_bracket_to_cache()
```

### 2. Pool Generation Flow

```
User has participants
         ↓
main_window calls bracket_service.get_pool_size('U9')
         ↓
bracket_service ensures config loaded
         ↓
Returns pool_size from bracket_utils.get_pool_size()
         ↓
main_window calls frontend/utils/pool_renderer.split_into_pools()
         ↓
Returns pools: [['P1','P2','P3','P4'], ['P5','P6','P7','P8'], ...]
         ↓
main_window calls determine_pool_structure()
         ↓
Returns (rows, cols) - layout grid
         ↓
main_window calls calculate_pool_positions()
         ↓
Returns positions dict mapping pool indices to (x, y) on canvas
         ↓
main_window calls draw_pools_on_canvas()
         ↓
Pools rendered on canvas
```

### 3. Configuration Loading Flow

```
Application startup
       ↓
main_window.py line ~93:
  set_bracket_config('config/bracket_config.xlsx')
       ↓
bracket_service.set_bracket_config():
  bracket_config = ConfigRepository(path)
       ↓
ConfigRepository:
  ├─ Read Excel file
  ├─ Parse sheets
  ├─ Store in memory
  └─ Ready for queries
       ↓
Any time bracket service calls:
  - get_age_group()
  - get_weight_class()
  - get_pool_size()
       ↓
  They check: ensure_config_loaded()
       ↓
  If not loaded, load it
       ↓
  Query config object
       ↓
  Return result
```

---

## File Dependency Matrix

| File | Depends On | Used By |
|------|-----------|---------|
| `main.py` | `views/main_window.py` | (entry point) |
| `frontend/views/main_window.py` | styles, utils, services, repositories, logging | (main app) |
| `frontend/styles.py` | tkinter | All frontend code |
| `frontend/utils/bracket_renderer.py` | tkinter | main_window |
| `frontend/utils/pool_renderer.py` | tkinter | main_window |
| `frontend/utils/participant_loader.py` | pandas/judgefrontend, logging | main_window |
| `frontend/utils/bracket_cache.py` | json, os, logging | main_window |
| `backend/services/bracket_service.py` | bracket_utils, repositories, logging | main_window |
| `utils/bracket_utils.py` | repositories, logging, math | bracket_service |
| `backend/data/repositories/config_repository.py` | openpyxl (xlsx) | bracket_utils, bracket_service |
| `backend/data/repositories/participant_repository.py` | db_config, db | main_window |
| `backend/data/db_config.py` | sqlite3 | repositories |
| `utils/logging/__init__.py` | logging module | All modules |

---

## Import Statement Reference

### Safe Imports (No Circular Dependencies)
```python
# ✅ In main_window.py, can safely import from:
from frontend.styles import COLORS, FONTS, apply_*_style
from frontend.utils import load_participants_from_xlsx, normalize_participants, ...
from backend.services.bracket_service import make_bracket, get_age_group, ...
from backend.data.repositories.participant_repository import fetch_participants_from_db
from utils.logging import get_logger

# ✅ In bracket_service.py, can safely import from:
from utils.bracket_utils import make_bracket as _make_bracket, ...
from backend.data.repositories.config_repository import ConfigRepository
from utils.logging import get_logger

# ✅ In bracket_utils.py, can safely import from:
from backend.data.repositories.config_repository import ConfigRepository
from utils.logging import get_logger

# ✅ In repositories, can safely import from:
from backend.data.db_config import get_connection
from utils.logging import get_logger
```

### Path Setup Patterns
```python
# Pattern 1: If file is in frontend/utils/, accessing main backend
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Pattern 2: If file is in backend/services/, accessing main backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Pattern 3: Relative imports within same package
from ..styles import COLORS  # From views/ → frontend/styles.py
from ..utils import load_participants_from_xlsx  # From views/ → frontend/utils/
```

---

## Module Initialization Order

When the application starts:

```
1. main.py
   └─ imports from frontend.views.main_window

2. main_window.py
   ├─ Import styles, frontend utils → (no backend calls yet)
   └─ Class definition: BracketViewerApp

3. BracketViewerApp.__init__()
   ├─ Initialize logging
   ├─ Initialize GUI
   ├─ Call set_bracket_config()
   │   └─ Initializes bracket_service.bracket_config
   │       └─ Creates ConfigRepository in memory
   └─ Ready for user interaction

4. User loads participants
   └─ Calls frontend utils → loads from XLSX/DB

5. User generates bracket
   └─ Calls bracket_service.make_bracket()
       └─ Queries ConfigRepository
       └─ Calls bracket_utils
           └─ Queries ConfigRepository

6. User views bracket
   └─ Calls frontend utils renderers
       └─ Pure functions, no external deps
```

---

## Adding a New Component

### Adding a New Utility Function

1. **Create in appropriate utils file:**
   ```python
   # frontend/utils/my_new_util.py
   def my_function(params):
       """Description."""
       return result
   ```

2. **Export from `__init__.py`:**
   ```python
   # frontend/utils/__init__.py
   from .my_new_util import my_function
   
   __all__ = [
       # ... existing ...
       'my_function',
   ]
   ```

3. **Use in main_window or other modules:**
   ```python
   from frontend.utils import my_function
   result = my_function(params)
   ```

### Adding a New Screen

1. **Create screen file:**
   ```python
   # frontend/views/my_screen.py
   class MyScreen(tk.Frame):
       pass
   ```

2. **Import in main_window:**
   ```python
   from .my_screen import MyScreen
   ```

3. **Register in BracketViewerApp:**
   ```python
   self.screens['my_screen'] = MyScreen(self)
   ```

4. **Add navigation:**
   ```python
   button = tk.Button(self, text="Go to My Screen",
                     command=lambda: self.show_screen('my_screen'))
   ```

### Adding a New Service Function

1. **Implement in utils/bracket_utils.py:**
   ```python
   def my_operation(params):
       ensure_config_loaded()
       return result
   ```

2. **Create wrapper in bracket_service.py:**
   ```python
   from utils.bracket_utils import my_operation as _my_operation
   
   def my_operation(params):
       ensure_config_loaded()
       return _my_operation(params)
   ```

3. **Use in main_window:**
   ```python
   from backend.services.bracket_service import my_operation
   result = my_operation(params)
   ```

### Adding a New Repository

1. **Create repository file:**
   ```python
   # backend/data/repositories/my_repository.py
   class MyRepository:
       def __init__(self, db_path):
           self.db = get_connection(db_path)
       
       def query_something(self):
           pass
   ```

2. **Use in services:**
   ```python
   from backend.data.repositories.my_repository import MyRepository
   repo = MyRepository()
   data = repo.query_something()
   ```

---

## Dependency Summary

### Hard Dependencies (Required)
- **tkinter** - Built-in Python GUI framework
- **sqlite3** - Built-in Database (via db_config)
- **logging** - Built-in Logging
- **json** - Built-in JSON (caching)

### Soft Dependencies (Optional with Fallbacks)
- **pandas** - For XLSX reading (fallback if judgefrontend not available)
- **openpyxl** - For Excel handling in ConfigRepository
- **judgefrontend.src.xlsxHandler** - Flexible XLSX parsing (tried first)

### External (Same Workspace)
- **libraries/** - Judgment frontend optional library

### Recommended but Not Required
- **docker** - For containerization
- **pytest** - For testing

---

## Performance Considerations

### Caching
- Bracket results are cached to JSON
- Config is loaded once and reused (global in bracket_service)
- Prevents repeated expensive calculations

### Threading
- Long operations like bracket generation should run on background threads
- Use `threading.Thread()` in main_window
- Update UI with `.after()` from worker thread

### Data Structure
- Brackets stored as tuples (immutable, hashable)
- Rounds as lists of tuples
- Efficient for caching and hashing

---

## Error Handling Strategy

```
User Action
    ↓
Main Window try/except
    ├─ Log error with logger.error()
    ├─ Show messagebox to user
    └─ Optionally recover gracefully
    ↓
Service Layer
    └─ Propagates exceptions (no catch)
    ↓
Utils Functions
    └─ Propagate exceptions or validate input
```

---

## Key Design Principles

1. **Separation of Concerns**
   - UI (frontend/views)
   - Styling (frontend/styles)
   - Utilities (frontend/utils)
   - Business Logic (backend/services)
   - Data Access (backend/data/repositories)

2. **DRY (Don't Repeat Yourself)**
   - Common styles defined once in styles.py
   - Common utilities exported from utils/__init__.py
   - Business logic in services/utils

3. **Testability**
   - Pure functions in utilities (no side effects)
   - Services are thin wrappers (easy to test)
   - Repositories abstract data access

4. **Maintainability**
   - Clear naming conventions
   - Logging throughout
   - Modular structure

5. **Extensibility**
   - Easy to add new screens
   - Easy to add new utilities
   - Easy to add new services
   - Pluggable repositories

---

**End of Dependency Map**
