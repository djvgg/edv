# Application Screen Flow Diagram

Complete navigation map showing all screens and their connections in the Tournament Bracket Manager.

```mermaid
graph TD
    Start["🎬 Application Start<br/>BracketViewerApp.__init__"]
    
    Start --> MainWindow["🪟 Main Window<br/>BracketViewerApp<br/>main_window.py:1-1450<br/><br/>Status Bar & Progress Display"]
    
    MainWindow --> FileLoaderScreen["📂 File Loader Screen<br/>FileLoaderScreen<br/>file_loader_screen.py:33-197<br/><br/>4 Data Source Options"]
    
    %% File Loader Screen buttons
    FileLoaderScreen -->|"Button: Load Participant<br/>List XLSX"| LoadXLSXPath["📥 load_from_xlsx<br/>main_window.py:703-740<br/><br/>→ Call load_participants_from_xlsx<br/>→ Export brackets<br/>→ Show group preview"]
    
    FileLoaderScreen -->|"Button: Load Tournament<br/>Registration XLSX"| LoadTournamentXLSXPath["📥 load_tournament_and_generate<br/>main_window.py:744-810<br/><br/>→ Call load_participants_from_xlsx<br/>→ Normalize participants<br/>→ Export brackets<br/>→ Show group preview"]
    
    FileLoaderScreen -->|"Button: Load from<br/>Database"| LoadDatabasePath["🗄️ load_from_database<br/>main_window.py:812-860<br/><br/>→ Fetch participants from DB<br/>→ Export brackets<br/>→ Show group preview"]
    
    FileLoaderScreen -->|"Button: Load M/W<br/>JSON Files"| LoadJSONPath["📄 load_from_json_files<br/>main_window.py:862-955<br/><br/>→ Load JSON files (M/W)<br/>→ Export brackets<br/>→ Show group preview"]
    
    FileLoaderScreen -->|"Button: Split M/W<br/>Contestants"| SplitGenderPath["⚙️ split_gender_json<br/>main_window.py:957-1050<br/><br/>Utility to convert XLSX → JSON<br/>Returns to File Loader"]
    
    %% All paths converge to Group Preview
    LoadXLSXPath --> GroupPreviewScreen["👥 Group Preview Screen<br/>GroupPreviewScreen<br/>group_preview_screen.py:32-349<br/><br/>Left: Searchable bracket list<br/>Right: Participant details<br/>Bottom: Back/Continue buttons"]
    
    LoadTournamentXLSXPath --> GroupPreviewScreen
    LoadDatabasePath --> GroupPreviewScreen
    LoadJSONPath --> GroupPreviewScreen
    
    SplitGenderPath --> FileLoaderScreen["📂 Back to File Loader"]
    
    %% Group Preview navigation
    GroupPreviewScreen -->|"Button: Back"| FileLoaderScreen
    
    GroupPreviewScreen -->|"Button: Continue"| GenerationMethodScreen["🎯 Generation Method Screen<br/>GenerationMethodScreen<br/>generation_method_screen.py:43-603<br/><br/>Left: Unassigned brackets<br/>Right: 4 Generation Methods<br/>- Pools (≤5)<br/>- Double Pools (6-10)<br/>- KO Brackets (11+)<br/>- Special Cases"]
    
    GroupPreviewScreen -->|"Select group or<br/>double-click"| BracketPreview["🔍 Show Bracket Preview<br/>group_preview_screen.py:310-349<br/><br/>Display bracket structure<br/>in dialog window"]
    
    BracketPreview --> GroupPreviewScreen
    
    %% Generation Method navigation
    GenerationMethodScreen -->|"Button: Back"| GroupPreviewScreen
    
    GenerationMethodScreen -->|"All brackets assigned<br/>& Continue clicked"| GenerateAndView["⚙️ Generate & View<br/>main_window.py:459-490<br/><br/>→ Store method assignments<br/>→ Generate bracket structures<br/>→ Cache brackets<br/>→ Show bracket viewer"]
    
    GenerateAndView --> BracketViewerFrame["📊 Bracket Viewer Frame<br/>Embedded in MainWindow<br/>main_window.py:265-660<br/><br/>Multiple Display Modes:<br/>- Tree View (tournament structure)<br/>- Canvas View (pool/bracket draw)<br/>- Table View (participant details)<br/>- JSON View (raw data)<br/><br/>Features:<br/>✓ Multi-bracket tabs<br/>✓ Zoom & pan controls<br/>✓ Export/print options<br/>✓ Real-time updates"]
    
    BracketViewerFrame -->|"Button: Back (from<br/>method selection)"| GroupPreviewScreen
    
    BracketViewerFrame -->|"Button: Switch View<br/>or Select Bracket"| BracketViewerFrame
    
    BracketViewerFrame -->|"Right-click context<br/>menu on bracket"| ContextMenu["📋 Context Menu<br/>main_window.py:650-660<br/><br/>- View details<br/>- Export bracket<br/>- Print bracket<br/>- Copy to clipboard"]
    
    ContextMenu --> BracketViewerFrame
    
    BracketViewerFrame -->|"Button: Export All<br/>Brackets"| ExportPath["💾 Export Brackets<br/>main_window.py:1050-1130<br/><br/>→ Generate PDF/Excel files<br/>→ Save to disk<br/>→ Show success dialog"]
    
    ExportPath --> BracketViewerFrame
    
    BracketViewerFrame -->|"Button: New Tournament<br/>or File → Open"| FileLoaderScreen
    
    %% Styling
    style Start fill:#5f9ea0,stroke:#4a90a0,color:#fff
    style MainWindow fill:#4a90a0,stroke:#3a7a90,color:#fff
    style FileLoaderScreen fill:#6b7a90,stroke:#5a6a80,color:#fff
    style GroupPreviewScreen fill:#6b7a90,stroke:#5a6a80,color:#fff
    style GenerationMethodScreen fill:#6b7a90,stroke:#5a6a80,color:#fff
    style BracketViewerFrame fill:#5a7a90,stroke:#4a6a80,color:#fff
    style BracketPreview fill:#7a8aa0,stroke:#6a7a90,color:#fff
    style ContextMenu fill:#7a8aa0,stroke:#6a7a90,color:#fff
    style LoadXLSXPath fill:#7a9aa0,stroke:#6a8a90,color:#fff
    style LoadTournamentXLSXPath fill:#7a9aa0,stroke:#6a8a90,color:#fff
    style LoadDatabasePath fill:#7a9aa0,stroke:#6a8a90,color:#fff
    style LoadJSONPath fill:#7a9aa0,stroke:#6a8a90,color:#fff
    style SplitGenderPath fill:#8a9aa0,stroke:#7a8a90,color:#fff
    style GenerateAndView fill:#7a9aa0,stroke:#6a8a90,color:#fff
    style ExportPath fill:#8a9aa0,stroke:#7a8a90,color:#fff
```

## Screen Navigation Summary

### Primary Flow (Normal Tournament Import)
1. **Main Window** → Application entry point, manages all screens
2. **File Loader Screen** → Select data import method (4 options)
3. **Group Preview Screen** → Review loaded bracket groups & participants
4. **Generation Method Screen** → Assign brackets to generation methods
5. **Bracket Viewer** → Final display of generated brackets

### Utility Flow
- **File Loader Screen** → **Split Gender Utility** → Back to **File Loader Screen**

### Circular Navigation
- **Bracket Viewer** ↔ **File Loader Screen** (load new tournament)
- **Group Preview** ↔ **File Loader Screen** (back button)
- **Generation Method** ↔ **Group Preview** (back button)
- **Bracket Viewer** ↔ **Generation Method** (back button via view mode)

---

## Screen Details

### 1. Main Window
**File**: `frontend/views/main_window.py` (1-1450)

**Purpose**: Main application window and screen orchestrator

**Components**:
- Status bar (top)
- Progress bar / loading dialog
- Main content frame (holds primary screen)
- Menu bar with file operations

**Responsibilities**:
- Initialize all screens
- Route callbacks between screens
- Manage bracket data
- Handle file dialogs
- Cache bracket data

**Key Methods**:
- `show_group_preview_window()` - Display group preview
- `show_generation_method_screen()` - Display method assignment
- `show_bracket_viewer()` - Display final brackets
- `load_from_xlsx()` - Load participant list
- `load_tournament_and_generate()` - Load tournament registration
- `load_from_database()` - Load from PostgreSQL
- `load_from_json_files()` - Load M/W JSON files
- `split_gender_json()` - Split gender utility

---

### 2. File Loader Screen
**File**: `frontend/views/file_loader_screen.py` (33-197)

**Purpose**: Data source selection and import entry point

**Layout**:
- Title & subtitle
- Info label
- 4 primary buttons
- 1 utility button
- Status label

**Buttons** & Actions:
1. **Load Participant List (XLSX)**
   - Opens file dialog
   - Calls `main_window.load_from_xlsx()`
   - Navigates → Group Preview

2. **Load Tournament Registration (XLSX)**
   - Opens file dialog
   - Calls `main_window.load_tournament_and_generate()`
   - Handles tournament-specific format
   - Navigates → Group Preview

3. **Load from Database**
   - Connects to PostgreSQL
   - Calls `main_window.load_from_database()`
   - Navigates → Group Preview

4. **Load M/W JSON Files**
   - File dialog for JSON files
   - Calls `main_window.load_from_json_files()`
   - Navigates → Group Preview

5. **Split M/W Contestants** (Utility)
   - XLSX to JSON converter
   - Calls `main_window.split_gender_json()`
   - Returns to File Loader (no navigation)

**Data Flow**:
- User clicks button
- Dialog or processing begins
- Participants loaded → brackets generated
- Delegates to `main_window` callback
- Callback handles → Group Preview transition

---

### 3. Group Preview Screen
**File**: `frontend/views/group_preview_screen.py` (32-349)

**Purpose**: Preview bracket groups and participants before generation method selection

**Layout**:
- Top: Title with participant count
- Left panel: Searchable bracket list
  - Search box (real-time filter)
  - ListBox of bracket keys
  - Count label
- Right panel: Participant details
  - TkTable display of participants
  - Scrollable
- Bottom buttons: Back & Continue

**Features**:
- Real-time search/filtering
- Participant detail preview
- Optional: Bracket structure preview in dialog
- Click-to-select group

**Interactions**:
- **Search box**: Filter bracket list
- **Back button**: Return to File Loader (reload data)
- **Continue button**: Proceed to Generation Method Screen
- **Double-click group**: Show detailed bracket preview

**Data Display**:
- Bracket keys: `{age_group}_{weight_class}_{gender}`
- Participant table: Name, Club, Birth Year, Weight, Payment Status

---

### 4. Generation Method Screen  
**File**: `frontend/views/generation_method_screen.py` (43-603)

**Purpose**: Assign each bracket to a generation method (Pools, KO, Special)

**Layout**:
- Top: Title
- Left panel: Unassigned brackets
  - Search box (filter)
  - ListBox of unassigned brackets
  - Drag/drop enabled
- Right panel: 2×2 grid of method tables
  - **Pools** (≤5 fighters)
  - **Double Pools** (6-10 fighters)
  - **KO Brackets** (11+ fighters)
  - **Special Cases** (edge cases)
- Bottom buttons: Back & Continue

**Features**:
- Drag-and-drop bracket assignment
- Method-specific assignment buttons
- Visual feedback on assignment
- Search/filter unassigned

**Interactions**:
1. Drag bracket from unassigned → method table
2. OR click bracket + click method button
3. Back button: Return to Group Preview
4. Continue button: Generate & show Bracket Viewer

**Data Storage**:
- `brackets` dict: `{bracket_key: {"tuple": data, "method": method_name}}`
- Passed to `main_window.generate_and_view()`

---

### 5. Bracket Viewer
**File**: `frontend/views/main_window.py` (265-660)

**Purpose**: Display generated brackets in multiple view modes

**Layout**:
- Top: Bracket tabs (one per bracket key)
- View mode selector (tabs): Tree / Canvas / Table / JSON
- Zoom controls (if Canvas mode)
- Pan controls (if Canvas mode)
- Status bar

**View Modes**:

1. **Tree View** (main_window.py:380-450)
   - Hierarchical tree of tournament structure
   - Expandable/collapsible nodes
   - Shows rounds, matchups, participants

2. **Canvas View** (main_window.py:450-550)
   - Visual bracket drawing
   - Zoom & pan support
   - Shows pool structure
   - Supports rendering via `draw_pools_on_canvas()`

3. **Table View** (main_window.py:550-600)
   - Participant table
   - Columns: Name, Club, Weight, Age, Status
   - Sortable

4. **JSON View** (main_window.py:600-650)
   - Raw JSON structure display
   - For debugging/export

**Features**:
- Tab switching between brackets
- Multi-view same bracket
- Zoom levels (Canvas)
- Export/Print options
- Copy to clipboard

**Context Menu** (right-click):
- View bracket details
- Export bracket (PDF/Excel)
- Print bracket
- Copy bracket data

**Buttons**:
- Back: Return to Generation Method Screen
- New Tournament: Return to File Loader
- Export All: Export all brackets

---

## Data Flow Summary

### From File Loader to Bracket Viewer

```
File Selection
    ↓
[Raw Participants from source]
    ↓
normalize_participants()
    ↓
[Standardized Participants]
    ↓
export_all_brackets()
    ↓
[Brackets with generation methods assigned]
    ↓
GroupPreviewScreen(show brackets/groups)
    ↓
User selects Continue
    ↓
GenerationMethodScreen(assign methods)
    ↓
User selects method for each bracket + Continue
    ↓
BracketViewerApp.generate_and_view()
    ↓
[Bracket structures generated]
    ↓
BracketViewerFrame(display final brackets)
```

---

## Key Navigation Patterns

### Pattern 1: Linear Flow with Preview
File Loader → Preview → Method Selection → Viewer

### Pattern 2: Back Navigation
Any screen can return to File Loader or previous screen

### Pattern 3: Context Menus
Right-click in Bracket Viewer shows action menu

### Pattern 4: Utility Function
Split Gender stays within same screen (non-modal)

### Pattern 5: Tab Switching
Within Bracket Viewer, tabs show different brackets

---

## Threading & Background Operations

- **File Loading**: Background thread (prevent UI freeze)
- **Bracket Generation**: Background thread
- **Progress Updates**: Status bar & progress indicator

All long operations delegate to threads managed in `main_window._load_*_thread()` methods.

---

## Configuration & Styling

All screens use centralized styling system:
- **Colors**: `frontend/styles.py:COLORS`
- **Fonts**: `frontend/styles.py:FONTS`
- **Button/Label Styles**: `frontend/styles.py:apply_*_style()`

---

## Future Enhancement Points

1. **Redo/Undo** in Generation Method Screen
2. **Save Tournament State** (save assignments)
3. **Load Tournament State** (reload assignments)
4. **Batch Operations** (multiple tournaments)
5. **Bracket Modification** (edit participants in Bracket Viewer)
6. **Live Scoring** integration (from weighin module)
