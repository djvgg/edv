# Tournament Bracket Manager - Architecture Documentation

**Date:** February 19, 2026  
**Project:** EDV Backend - TOP Team Combat Control  
**License:** GPL-3.0-or-later

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Design Patterns](#design-patterns)
6. [Available Helper Methods](#available-helper-methods)
7. [Creating New Screens](#creating-new-screens)
8. [Data Flow](#data-flow)

---

## Project Overview

**Tournament Bracket Manager** is a Tkinter-based desktop application for managing and visualizing tournament brackets, pools, and participant data for combat sports competitions.

### Key Features
- Tournament bracket generation and visualization
- Pool-based participant grouping (U9, U11)
- Single elimination and pool formats
- Participant loading from XLSX files
- Bracket caching and state management
- Dark theme UI with consistent styling

### Technology Stack
- **Frontend:** Tkinter (Python GUI framework)
- **Backend:** Python services and repositories
- **Data:** SQLite (via db_config), XLSX files
- **Styling:** Custom dark theme (CSS-like approach)
- **Logging:** Custom logging module

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Frontend (Tkinter)                                  │   │
│  │  - main_window.py (BracketViewerApp)                │   │
│  │  - Screens & Views                                  │   │
│  │  - Widget Management                                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   UTILITIES & STYLING LAYER                  │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Frontend Utils   │  │ Styling System   │                 │
│  │ - Renderers      │  │ - COLORS         │                 │
│  │ - Caching        │  │ - FONTS          │                 │
│  │ - Loaders        │  │ - Style Functions│                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                      │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Services (backend/services/)                        │   │
│  │  - bracket_service.py (wrapper layer)               │   │
│  │  - Coordinates business operations                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   DATA & UTILITIES LAYER                     │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Repositories     │  │ Utilities        │                 │
│  │ - Config         │  │ - bracket_utils  │                 │
│  │ - Participants   │  │ - create_config  │                 │
│  │ - Data models    │  │ - Logging        │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL RESOURCES                        │
│                                                               │
│  - Database (SQLite via db_config)                          │
│  - Excel Files (.xlsx)                                      │
│  - Configuration Files                                      │
│  - judgefrontend Library (optional, flexible xlsx)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
edv_backend/
│
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── README.md                        # Project README
├── ARCHITECTURE.md                  # This file
│
├── frontend/                        # PRESENTATION LAYER
│   ├── __init__.py
│   ├── styles.py                    # Global styling system
│   ├── STYLES_GUIDE.md             # Styling documentation
│   │
│   ├── views/                       # Screen implementations
│   │   ├── __init__.py
│   │   └── main_window.py          # Main application window (1500+ lines)
│   │
│   └── utils/                       # Frontend utilities
│       ├── __init__.py
│       ├── bracket_renderer.py      # Bracket visualization
│       ├── pool_renderer.py         # Pool visualization
│       ├── participant_loader.py    # XLSX loading & normalization
│       └── bracket_cache.py         # Caching mechanisms
│
├── backend/                         # BUSINESS LOGIC & DATA LAYER
│   ├── __init__.py
│   │
│   ├── services/                    # Service layer (thin wrappers)
│   │   ├── __init__.py
│   │   └── bracket_service.py       # Bracket operations wrapper
│   │
│   └── data/                        # Data layer
│       ├── __init__.py
│       ├── db_config.py             # Database configuration
│       │
│       └── repositories/            # Data access patterns
│           ├── __init__.py
│           ├── config_repository.py # Configuration access
│           └── participant_repository.py  # Participant queries
│
├── utils/                           # SHARED UTILITIES
│   ├── __init__.py
│   ├── bracket_utils.py             # Core bracket logic (373 lines)
│   ├── create_bracket_config_excel.py # Config generation
│   │
│   └── logging/                     # Logging system
│       ├── __init__.py
│       └── (logging module files)
│
├── cache/                           # Runtime cache
│   └── *.json                       # Cached bracket data
│
├── config/                          # Configuration files
│   └── bracket_config.xlsx          # Bracket configuration
│   └── bracket_config.xlsx.license
│
├── logs/                            # Organized logging
│   ├── bracket_service/
│   ├── bracket_utils/
│   └── (other logs)
│
├── db_init/                         # Database initialization
│   ├── 1_schema.sql
│   └── 2_data.sql
│
└── LICENSES/                        # License files
    ├── CC0-1.0.txt
    └── GPL-3.0-or-later.txt
```

---

## Core Components

### 1. **Frontend Layer** (`frontend/`)

#### Main Application Window (`views/main_window.py`)
- **Class:** `BracketViewerApp(tk.Tk)`
- **Purpose:** Main application window and screen management
- **Key Responsibilities:**
  - Window initialization and layout
  - Screen switching logic
  - Event handling and callbacks
  - State management
  - Threading for background operations

```python
class BracketViewerApp(tk.Tk):
    def __init__(self):
        # Window setup, logging, configuration
        # Data structure initialization
        # TTK styling for dark theme
        # Event protocol setup (WM_DELETE_WINDOW)
        pass
```

#### Styling System (`styles.py`)
- **Purpose:** Centralized style management
- **Components:**
  - `COLORS` - Color palette (dark theme)
  - `FONTS` - Typography system
  - `BUTTON_STYLES` - Pre-defined button styles
  - `FRAME_STYLES` - Frame styling
  - `LABEL_STYLES` - Label styling
  - Style application functions

```python
# Apply styles to widgets
from frontend.styles import apply_button_style, COLORS, FONTS

button = tk.Button(root, text="Click")
apply_button_style(button, style='primary')
```

### 2. **Frontend Utilities** (`frontend/utils/`)

#### Bracket Renderer (`bracket_renderer.py`)
Provides visualization functions for tournament brackets:

| Function | Purpose |
|----------|---------|
| `build_bracket_rounds()` | Convert bracket tuples to rounds with participant info |
| `calculate_box_size()` | Dynamic sizing based on content and zoom |
| `draw_bracket_on_canvas()` | Render bracket visualization on Tkinter canvas |

**Example:**
```python
from frontend.utils import build_bracket_rounds, calculate_box_size, draw_bracket_on_canvas

# Build rounds from bracket data
rounds = build_bracket_rounds(bracket_tuples, participants)

# Calculate optimal sizing
boxWidth, boxHeight, xGap, yGap = calculate_box_size(rounds, zoom_level=1.0)

# Draw on canvas
draw_bracket_on_canvas(
    canvas=my_canvas,
    rounds=rounds,
    positions=calculated_positions,
    boxWidth=boxWidth,
    boxHeight=boxHeight,
    zoom_level=1.0,
    colors=COLORS,
    fonts=FONTS
)
```

#### Pool Renderer (`pool_renderer.py`)
Handles pool-based groupings (for U9/U11):

| Function | Purpose |
|----------|---------|
| `split_into_pools()` | Group participants into pools |
| `determine_pool_structure()` | Determine optimal pool layout |
| `calculate_pool_positions()` | Calculate pool positioning on canvas |
| `draw_pools_on_canvas()` | Render pools on canvas |
| `draw_pool_table()` | Render pool results table |

#### Participant Loader (`participant_loader.py`)
XLSX handling with fallback support:

| Function | Purpose |
|----------|---------|
| `load_participants_from_xlsx()` | Load from XLSX (tries judgefrontend, falls back to pandas) |
| `normalize_participants()` | Standardize field names (Name, Verein, Gender, Age, Weight) |

#### Bracket Cache (`bracket_cache.py`)
JSON-based caching for generated brackets:

| Function | Purpose |
|----------|---------|
| `save_bracket_to_cache()` | Persist bracket to JSON |
| `load_bracket_from_cache()` | Restore bracket from JSON |
| `clear_bracket_cache()` | Clear cache files |

### 3. **Backend Services** (`backend/services/`)

#### Bracket Service (`bracket_service.py`)
Thin wrapper layer delegating to `bracket_utils`:

| Function | Purpose |
|----------|---------|
| `set_bracket_config()` | Initialize configuration |
| `get_age_group()` | Get age category (U9, U11, U13, etc.) |
| `get_weight_class()` | Get weight category |
| `get_pool_size()` | Get pool size for age group |
| `make_bracket()` | Generate bracket |
| `export_all_brackets()` | Export brackets to files |

### 4. **Backend Data Layer** (`backend/data/`)

#### Repositories
- **ConfigRepository** - Excel config access
- **ParticipantRepository** - Database queries

#### Database Config (`db_config.py`)
Database connection and configuration

### 5. **Utilities** (`utils/`)

#### Bracket Utils (`bracket_utils.py`)
Core business logic for bracket generation (373 lines):
- Age group calculations
- Weight class lookups
- Pool size configuration
- Bracket generation algorithms
- Export functionality

---

## Design Patterns

### 1. **MVC Architecture (loosely)**
- **Model:** Data layer (repositories, db_config)
- **View:** Frontend/views (BracketViewerApp)
- **Controller:** Backend/services (bridge between view and model)

### 2. **Repository Pattern**
Data access abstraction through repositories:
```python
from backend.data.repositories.config_repository import ConfigRepository

config = ConfigRepository(config_path)
age_group = config.get_age_group(age)
```

### 3. **Service Wrapper Pattern**
Thin service layer delegates to utility functions:
```python
# backend/services/bracket_service.py
from utils.bracket_utils import make_bracket as _make_bracket

def make_bracket(...):
    ensure_config_loaded()
    return _make_bracket(...)
```

### 4. **Utility Functions Over Classes**
Most operations implemented as pure functions for testability:
```python
# Frontend utilities are stateless functions
rounds = build_bracket_rounds(bracket, participants)
size = calculate_box_size(rounds, zoom)
```

### 5. **Styling System**
Centralized style definitions with application functions:
```python
from frontend.styles import COLORS, apply_button_style

apply_button_style(button, style='primary')  # Uses COLORS and FONTS
```

### 6. **Caching Pattern**
JSON-based caching for expensive operations:
```python
from frontend.utils import save_bracket_to_cache, load_bracket_from_cache

# Load or generate
bracket = load_bracket_from_cache(key) or make_bracket(...)
save_bracket_to_cache(key, bracket)
```

---

## Available Helper Methods

### Frontend Utilities Exported (`frontend/utils/__init__.py`)

```python
# Bracket Rendering (3 functions)
- build_bracket_rounds(bracket, normalized_participants)
- calculate_box_size(rounds, zoom_level)
- draw_bracket_on_canvas(canvas, rounds, positions, boxWidth, boxHeight, zoom_level, colors, fonts)

# Pool Rendering (6 functions)
- draw_pools_on_canvas(canvas, pools, positions, pool_size, zoom_level, colors, fonts)
- draw_pool_table(canvas, pool, positions, pool_size, zoom_level, colors, fonts)
- split_into_pools(participants, pool_size)
- determine_pool_structure(num_pools)
- calculate_pool_box_size(pool_size, zoom_level)
- calculate_pool_positions(num_pools, canvas_width, canvas_height, pool_size, zoom_level)

# Participant Loading (2 functions)
- load_participants_from_xlsx(file_path)
- normalize_participants(raw_participants)

# Caching (3 functions)
- save_bracket_to_cache(key, bracket_data)
- load_bracket_from_cache(key)
- clear_bracket_cache()
```

### Styling Functions (`frontend/styles.py`)

```python
# Style Application Functions
- apply_button_style(widget, style)       # 'primary', 'success', 'secondary', 'small'
- apply_entry_style(widget)
- apply_label_style(widget, style)
- apply_listbox_style(widget)
- apply_table_panel_style(widget)
- create_dark_frame(parent)

# Style Dictionaries (Direct Access)
- COLORS                 # Dict with 20+ colors
- FONTS                  # Dict with typography presets
- BUTTON_STYLES          # Dict with 4 button style presets
- FRAME_STYLES           # Dict with frame styles
- LABEL_STYLES           # Dict with label styles
```

### Bracket Service Functions (`backend/services/bracket_service.py`)

```python
- set_bracket_config(path)
- ensure_config_loaded()
- get_age_group(age, event_year=None)
- get_weight_class(weight, gender, age_group=None)
- get_pool_size(age_group)
- make_bracket(...)
- export_all_brackets(...)
```

### Logging (`utils/logging/`)

```python
from utils.logging import get_logger

logger = get_logger('module_name')  # Get module-specific logger
logger.debug(msg)
logger.info(msg)
logger.warning(msg)
logger.error(msg)
```

---

## Creating New Screens

### Step 1: Define Screen Structure

Create a new file in `frontend/views/`:
```
frontend/views/
├── main_window.py          (existing)
├── my_new_screen.py        (new)
└── __init__.py
```

### Step 2: Create Screen Class

Follow the Tkinter pattern with consistent styling:

```python
# frontend/views/my_new_screen.py
import tkinter as tk
from tkinter import ttk
import sys
import os

# Setup imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from ..styles import (
    COLORS, FONTS,
    apply_button_style,
    apply_label_style,
    create_dark_frame
)

logger = get_logger('my_new_screen')

class MyNewScreen(tk.Frame):
    """Description of the screen's purpose."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        
        # Setup logging
        self.logger = logger
        
        # Initialize UI components
        self.init_ui()
    
    def init_ui(self):
        """Initialize user interface components."""
        
        # Create title
        title = tk.Label(
            self,
            text="My New Screen",
            bg=COLORS['bg_dark'],
            **FONTS['heading_lg']
        )
        apply_label_style(title, 'heading_lg')
        title.pack(pady=10)
        
        # Create content frame
        content = create_dark_frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add your widgets here...
        
    def load_data(self):
        """Load data for this screen."""
        pass
    
    def on_action(self):
        """Handle user actions."""
        pass
```

### Step 3: Integrate Screen into Main Window

Edit `frontend/views/main_window.py` to add screen management:

```python
# In BracketViewerApp.__init__()
from .my_new_screen import MyNewScreen

self.screens = {
    'home': MainFrame(self),
    'my_new_screen': MyNewScreen(self),
}

def show_screen(self, screen_name):
    """Switch between screens."""
    for screen in self.screens.values():
        screen.pack_forget()
    
    if screen_name in self.screens:
        self.screens[screen_name].pack(fill=tk.BOTH, expand=True)
        if hasattr(self.screens[screen_name], 'load_data'):
            self.screens[screen_name].load_data()
```

### Step 4: Add Navigation

```python
# In your main window or screen
nav_button = tk.Button(
    self,
    text="Go to My Screen",
    command=lambda: self.master.show_screen('my_new_screen')
)
apply_button_style(nav_button, style='primary')
nav_button.pack()
```

### Best Practices for New Screens

1. **Inherit from `tk.Frame`** for modular, reusable screens
2. **Use `COLORS` and `FONTS`** from styles.py for consistency
3. **Apply styles** using helper functions (apply_button_style, etc.)
4. **Organize layout** with logical frames and sections
5. **Use `get_logger()`** for screen-specific logging
6. **Implement `load_data()`** method for dynamic content
7. **Handle threading** for long-running operations using `threading.Thread()`
8. **Clean up resources** on screen close (file handles, threads)

### Example: Simple Data Entry Screen

```python
class ParticipantEntryScreen(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = get_logger('participant_entry')
        
        self.init_ui()
    
    def init_ui(self):
        # Title
        title = tk.Label(self, text="Add Participant", 
                        bg=COLORS['bg_dark'], font=FONTS['heading_lg'])
        title.pack(pady=10)
        
        # Form frame
        form = create_dark_frame(self)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Name field
        tk.Label(form, text="Name:", bg=COLORS['bg_panel'], 
                fg=COLORS['text_primary']).pack(anchor='w', pady=5)
        name_entry = tk.Entry(form, bg=COLORS['bg_input'], 
                             fg=COLORS['text_primary'])
        apply_entry_style(name_entry)
        name_entry.pack(fill=tk.X, pady=5)
        
        # Club field
        tk.Label(form, text="Club:", bg=COLORS['bg_panel'],
                fg=COLORS['text_primary']).pack(anchor='w', pady=5)
        club_entry = tk.Entry(form, bg=COLORS['bg_input'],
                             fg=COLORS['text_primary'])
        apply_entry_style(club_entry)
        club_entry.pack(fill=tk.X, pady=5)
        
        # Submit button
        submit = tk.Button(form, text="Add Participant",
                          command=self.on_submit)
        apply_button_style(submit, style='primary')
        submit.pack(pady=20)
        
        self.entries = {
            'name': name_entry,
            'club': club_entry,
        }
    
    def on_submit(self):
        data = {k: v.get() for k, v in self.entries.items()}
        self.logger.info(f"Submitting: {data}")
        # Process data...
```

---

## Data Flow

### Bracket Generation Flow

```
User Input (XLSX File)
    ↓
load_participants_from_xlsx()
    ↓
normalize_participants()              [frontend/utils/]
    ↓
make_bracket()                        [backend/services] → [utils/bracket_utils]
    ↓
get_age_group(), get_weight_class()   [bracket_utils]
    ↓
matches configuration + algorithm     [bracket_utils]
    ↓
Bracket data (tuples)
    ↓
save_bracket_to_cache()               [frontend/utils/]
    ↓
build_bracket_rounds()                [frontend/utils/]
    ↓
calculate_box_size()                  [frontend/utils/]
    ↓
draw_bracket_on_canvas()              [frontend/utils/]
    ↓
Visual Bracket on Canvas              [main_window.py]
```

### Pool Generation Flow

```
Normalized Participants
    ↓
get_pool_size()                       [bracket_service]
    ↓
split_into_pools()                    [frontend/utils/]
    ↓
Pool Groups (lists of participants)
    ↓
determine_pool_structure()            [frontend/utils/]
    ↓
Pool Layout (dimensions & positions)
    ↓
calculate_pool_positions()            [frontend/utils/]
    ↓
draw_pools_on_canvas()                [frontend/utils/]
    ↓
Visual Pools on Canvas                [main_window.py]
```

### Configuration Access Flow

```
Application Start
    ↓
set_bracket_config(config_path)       [bracket_service, bracket_utils]
    ↓
ConfigRepository(path)                [backend/data/repositories]
    ↓
Excel Config (.xlsx) → Memory
    ↓
get_age_group(), get_weight_class()   [On demand]
    ↓
Cached Configuration Object
    ↓
Available to all services
```

---

## Key Takeaways for Development

### ✅ DO:
- Use `frontend.styles` for all styling
- Create reusable utility functions
- Use repositories for data access
- Implement screen-specific loggers
- Cache expensive operations
- Handle threading for long operations
- Follow Python naming conventions (snake_case)

### ❌ DON'T:
- Hardcode colors or fonts
- Create direct database queries in views
- Mix business logic with UI code
- Create tight coupling between screens
- Ignore error handling
- Forget to log important operations

---

## Configuration Management

The application uses Excel-based configuration (`config/bracket_config.xlsx`):

```python
from backend.data.repositories.config_repository import ConfigRepository

config = ConfigRepository('path/to/bracket_config.xlsx')
age_group = config.get_age_group(age)
weight_class = config.get_weight_class(weight, gender, age_group)
pool_size = config.get_pool_size(age_group)
```

---

## Database Schema

Located in `db_init/`:
- `1_schema.sql` - Table definitions
- `2_data.sql` - Initial data

Access via `backend/data/db_config.py` and repositories.

---

## Logging System

```python
from utils.logging import get_logger

logger = get_logger('module_name')  # Creates log file in logs/module_name/

logger.debug("Detailed information")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
```

Logs are organized by module in `logs/` directory.

---

## Summary

This architecture provides:
- **Clear separation of concerns** (frontend, backend, data)
- **Reusable components** (utilities, styling, renderers)
- **Testable functions** (pure functions in utils)
- **Consistent UI** (centralized styling)
- **Extensibility** (easy to add new screens and services)
- **Maintainability** (logical organization and clear patterns)

Use this documentation as a reference when creating new screens and features.
