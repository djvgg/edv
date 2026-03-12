# Bracket Printing Feature - Implementation Plan

**Created:** March 11, 2026  
**Status:** Planning  
**Priority:** Standard

---

## 1. Feature Overview

Enable users to print assigned brackets (KO and Pool brackets) by generating PDFs that match the on-screen visualization and integrating with system printer functionality. **Approach: Reuse existing bracket rendering logic, output to PDF instead of Tkinter canvas.**

### Why PDF-First Approach?
- Reuses existing `bracket_renderer.py` and `pool_renderer.py` visualization logic
- Automatically handles any bracket size (flexible, no template limits)
- Maintains exact visual parity with on-screen display
- Single rendering engine for UI + Print output
- No template management overhead

### User Flow
1. User selects an assigned bracket in the UI
2. User clicks "Print Bracket" button
3. System uses existing bracket rendering logic to generate PDF
4. System sends PDF to printer
5. Printed bracket ready at physical printer

---

## 2. System Analysis

### Current Architecture Understanding

#### Bracket Structure
- **Location:** `backend/data/models.py` (Bracket model)
- **Repository:** `backend/data/repositories/bracket_repository.py`
- **Service:** `backend/services/bracket_service.py`
- **Reconstruction:** `backend/services/bracket_reconstruction_service.py`

#### Bracket Data
```
Bracket Model includes:
- id: int
- group_id: int (FK -> Group)
- bracket_type: str ('ko' or 'pool')
- mat_id: int (assigned mat, nullable)
- status: str ('in_progress', 'completed')
- first_place, second_place, third_place_1, third_place_2: int (placements)
```

#### Related Data
- **Group:** Contains participants, age_group, weight_class
- **Fight:** Contains round, match results, participants involved
- **Mat:** Physical tournament mat (mat_number)
- **GroupParticipant:** Participant with rank, status

#### UI Structure
- **Main Window:** `frontend/views/main_window.py`
- **Bracket Viewer:** `frontend/views/table_and_bracket_viewer.py`
- **Navigation:** `frontend/navigation_bar.py`
- **Screen Manager:** `frontend/screen_manager.py`

#### Existing Rendering Utilities (REUSE THESE!)
- **Bracket Renderer:** `frontend/utils/bracket_renderer.py`
  - `build_bracket_rounds()` - Structure bracket data from DB
  - `calculate_box_size()` - Dynamic sizing for any bracket
  - `draw_bracket_on_canvas()` - Render bracket matches & connectors
  
- **Pool Renderer:** `frontend/utils/pool_renderer.py`
  - `split_into_pools()` - Organize participants into pools
  - `generate_fight_schedule()` - Round-robin match scheduling
  - `draw_pools_on_canvas()` - Render pool table & results

---

## 3. Implementation Architecture

### 3.1 Create Bracket PDF Renderer Service

**Location:** `backend/services/bracket_pdf_generator.py`

**Strategy: Map Tkinter Canvas Drawing → ReportLab PDF Canvas**

Instead of creating entirely new rendering logic, we'll:
1. Extract bracket/pool data from database
2. Reuse calculation logic from `bracket_renderer.py` and `pool_renderer.py`
3. Translate canvas coordinates and drawing operations to PDF using ReportLab
4. Generate a PDF with identical visual output to the on-screen view

**Responsibilities:**
- Retrieve bracket data from repository
- Transform bracket data into drawing format (rounds, matches)
- Calculate layout (coordinates, sizes) - same as viewer
- Draw to PDF canvas instead of Tkinter canvas
- Support both KO and Pool brackets with flexible sizing

**Core Methods:**
```python
class BracketPDFGenerator:
    def generate_bracket_pdf(bracket_id: int, output_path: str) -> str
    def generate_pool_pdf(bracket_id: int, output_path: str) -> str
    
    # Helpers - translate canvas logic to PDF
    def draw_ko_bracket_to_pdf(bracket_data: dict, c: Canvas) -> None
    def draw_pool_to_pdf(bracket_data: dict, c: Canvas) -> None
    def draw_bracket_boxes(c: Canvas, rounds, positions) -> None
    def draw_connectors(c: Canvas, rounds, positions) -> None
    def draw_pool_table(c: Canvas, pool_data) -> None
```

**Key Advantage:** When bracket_renderer.py changes, both UI and PDF automatically benefit from the same improvements.

### 3.2 Create Printing Service Layer

**Location:** `backend/services/printing_service.py`

**Responsibilities:**
- Orchestrate bracket PDF generation
- Handle printer operations
- Manage temporary file cleanup

**Core Methods:**
```python
class PrintingService:
    def print_bracket(bracket_id: int, printer_name: str = None) -> bool
    def get_available_printers() -> List[str]
    def get_default_printer() -> str
```

### 3.3 Create Printer Integration Module

**Location:** `backend/services/printer_service.py`

**Strategy: Cross-platform printing via system commands**

Uses native OS print commands via `subprocess`:
- **Windows:** `print /D:printer_name` command
- **Linux:** `lp` command (CUPS)
- **macOS:** `lp` command (CUPS)

**Responsibilities:**
- Detect available printers (platform-aware)
- Send files to printer using native OS commands
- Handle errors gracefully
- Platform detection and command routing

**Dependencies:**
- None! Uses only Python standard library (`subprocess`, `platform`)

**Core Methods:**
```python
class PrinterService:
    def get_available_printers() -> List[str]  # Platform-specific detection
    def print_file(file_path: str, printer_name: str = None, copies: int = 1) -> bool
    def get_default_printer() -> str
    def _get_printers_windows() -> List[str]
    def _get_printers_linux() -> List[str]
    def _get_printers_macos() -> List[str]
```

---

## 4. Data Flow Architecture

### 4.1 PDF Generation Pipeline (Leveraging Existing Rendering)

```
Bracket ID (User clicks Print)
    ↓
BracketRepository.get_by_id(bracket_id)
    ↓
Bracket Model + Group/Fight data loaded
    ↓
BracketPDFGenerator.generate_bracket_pdf():
    ├─ Get bracket type (KO or Pool)
    ├─ Extract bracket data (participants, rounds, results)
    ├─ Call existing bracket_renderer.py logic to get layout:
    │  ├─ build_bracket_rounds() → structured rounds
    │  ├─ calculate_box_size() → dimensions for PDF
    │  └─ compute_bracket_rounds() → box coordinates
    ├─ Create ReportLab PDF canvas
    ├─ Translate viewer drawing calls → PDF drawing:
    │  ├─ draw_bracket_on_canvas() → PDF rectangles & lines
    │  └─ draw_pools_on_canvas() → PDF table cells
    └─ Save PDF → Returns file path
    ↓
PrintingService.print_bracket():
    ├─ Get generated PDF path
    ├─ Get printer (default or user-selected)
    └─ PrinterService.print_file() → Print queue
    ↓
Physical Printer Output
```

### 4.2 Why This Approach is Better

1. **No Template Constraints:** Handles any bracket size automatically
2. **No Code Duplication:** Reuses existing bracket_renderer.py functions
3. **Visual Parity:** PDF matches exactly what's on screen
4. **Maintainable:** Improvements to rendering help both UI and PDF
5. **Fast Development:** Minimal new code needed

### 4.3 UI Integration Points

**Main Window Enhancement:**
- Add "Print Bracket" button in bracket viewer toolbar
- Show printer selection dialog
- Display print status/confirmation

**File Structure Update:**
```
frontend/
    views/
        table_and_bracket_viewer.py (UPDATE: add print button)
        printer_selection_dialog.py (NEW)
```

---

## 5. Implementation Phases

### Phase 1: Foundation & PDF Rendering Core
- [ ] Create `backend/services/bracket_pdf_generator.py` with ReportLab integration
- [ ] Study/copy existing bracket_renderer.py drawing logic for PDF translation
- [ ] Create `backend/services/printing_service.py` orchestrator
- [ ] Create `backend/services/printer_service.py` for Windows printing
- [ ] Write unit tests for PDF generation (KO brackets)
- [ ] Write unit tests for PDF generation (Pool brackets)

### Phase 2: Bracket Rendering to PDF
- [ ] Implement `draw_ko_bracket_to_pdf()` - translate canvas KO logic to PDF
- [ ] Implement connectors/lines for KO brackets in PDF
- [ ] Test with various KO bracket sizes
- [ ] Implement `draw_pool_to_pdf()` - translate canvas pool logic to PDF
- [ ] Test with various pool sizes (2, 3, 4, 5+ fighters)

### Phase 3: Printer Integration  
- [ ] Implement printer detection (Windows)
- [ ] Implement print job sending
- [ ] Test with actual printer (or print-to-file)
- [ ] Handle error cases (no printer, offline printer)

### Phase 4: UI Integration
- [ ] Add "Print Bracket" button to `table_and_bracket_viewer.py`
- [ ] Create `printer_selection_dialog.py` for printer choice
- [ ] Connect button to PrintingService
- [ ] Add status messages and error handling
- [ ] Test end-to-end: Click button → PDF → Printer

### Phase 5: Polish & Testing
- [ ] Handle edge cases (empty brackets, single participant, etc)
- [ ] Temporary file cleanup/management
- [ ] Logging and debugging
- [ ] Performance optimization (large brackets)
- [ ] Documentation complete

---

## 6. Directory Structure

```
edv_backend/
├── backend/
│   └── services/
│       ├── bracket_pdf_generator.py (NEW - PDF rendering)
│       ├── printing_service.py (NEW - orchestration)
│       └── printer_service.py (NEW - Windows printer control)
├── frontend/
│   └── views/
│       ├── table_and_bracket_viewer.py (UPDATE - add print button)
│       └── printer_selection_dialog.py (NEW - printer choice)
├── tests/
│   ├── test_bracket_pdf_generator.py (NEW)
│   ├── test_printing_service.py (NEW)
│   └── test_printer_service.py (NEW)
└── temp/ (NEW - for temporary PDF files, auto-cleanup)
```

No templates needed! Rendering logic is embedded in PDF generator.

---

## 7. Dependencies Required

### Core Dependencies
```
reportlab>=4.0.0         # PDF generation with drawing capabilities
```

### No Additional Dependencies!
- Printer control uses native OS commands via Python `subprocess` module (standard library)
- Works on Windows, Linux, and macOS without extra packages

### Add to `requirements.txt`:
```
reportlab>=4.0.0
```

**Why this approach?**
- ReportLab: Rich drawing API (shapes, lines, text) - perfect for translating canvas operations
- subprocess + platform detection: Zero external dependencies, works on all OS
- No need for `pywin32` or system-specific libraries
- Lighter dependency footprint

---

## 8. Data Format Specifications

### Input Data (From Database)

The `BracketPDFGenerator` receives bracket data via these repositories:

**For KO Brackets:**
- `BracketRepository.get_by_id(bracket_id)` → Bracket model
- `GroupRepository.get_by_id(bracket.group_id)` → Group with participants
- `FightRepository.get_by_group(group_id)` → Fight results and rounds

**For Pool Brackets:**
- Same as above, with pool-specific fight scheduling

### Output Data Structure (Used Internally)

The PDF generator internally structures data the same way as the viewer:

```python
bracket_data = {
    'bracket_type': 'ko' | 'pool',
    'age_group': 'U9' | 'U11' | ... | '18+',
    'weight_class': 'string',
    'mat_number': int,
    'tournament_date': date,
    
    'participants': [
        {'seed': int, 'name': str, 'club': str, 'id': int},
        ...
    ],
    
    'rounds': [  # From bracket_renderer.build_bracket_rounds()
        {
            'round_number': int,
            'matches': [
                ('Fighter1', 'Fighter2', 'Club1', 'Club2'),
                ...
            ]
        },
        ...
    ],
    
    'placements': {
        'first': str,
        'second': str,
        'third_1': str,
        'third_2': str,
    }
}
```

### PDF Output Specifications

- **Page Size:** A4 (configurable)
- **Orientation:** Portrait (for most brackets) or Landscape (for large brackets)
- **Scaling:** Auto-adjusted to fit page based on bracket complexity
- **Content:** Identical visual representation to on-screen viewer
- **Format:** Standard PDF (viewable, searchable, printable)

---

## 9. Error Handling Strategy

### Potential Errors & Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Template not found | User hasn't provided Excel template | Show error dialog, guide to upload template |
| No printer available | No printers installed/configured | Show error, allow file-only export |
| Bracket data incomplete | Bracket not fully assigned | Show warning, export available data |
| File permission denied | Can't write to temp/output folder | Request admin rights, use alternate location |
| PDF generation failed | Complex bracket layout | Fallback to Excel or simpler PDF |
| Print job failed | Printer offline/error | Show error, keep generated file for manual printing |

### Logging Strategy
- Log all print operations to `logs/bracket_printing/`
- Include timestamps, bracket IDs, format, printer name
- Capture errors with full stack traces for debugging

---

## 10. Testing Strategy

### Unit Tests
- [ ] `test_bracket_printing.py` - Data extraction and transformation
- [ ] `test_excel_exporter.py` - Excel generation with template
- [ ] `test_pdf_exporter.py` - PDF generation
- [ ] `test_printer_service.py` - Printer detection

### Integration Tests
- [ ] End-to-end: Bracket → Excel → Print
- [ ] End-to-end: Bracket → PDF → Print
- [ ] Error scenarios: Missing printer, template, etc
- [ ] Multiple brackets in sequence

### Manual Testing
- [ ] Print to actual printer
- [ ] Verify visual formatting/layout
- [ ] Test different bracket types (KO vs Pool)
- [ ] Test edge cases (very long names, etc)

---

## 11. Security & Permissions Considerations

- [ ] Validate file paths (no path traversal)
- [ ] Secure temporary file handling (delete after print)
- [ ] Restrict printer access if needed
- [ ] Audit logging for sensitive bracket data printing
- [ ] GDPR compliance for participant data export

---

## 12. Performance Considerations

- [ ] Cache bracket data to avoid repeated DB queries
- [ ] Lazy-load template files
- [ ] Async printing to not block UI
- [ ] Clean up temporary files periodically
- [ ] Handle large brackets efficiently

---

## 13. Configuration Options

### Settings to Support
```python
PRINTING_CONFIG = {
    'temp_dir': 'edv_backend/temp/',
    'template_dir': 'edv_backend/templates/',
    'default_format': 'excel',  # or 'pdf'
    'default_printer': None,  # system default
    'keep_temp_files': False,  # clean up after print
    'enable_pdf': True,
    'enable_excel': True,
}
```

---

## 13. User Interface Mockup

### Print Bracket Dialog

```
Bracket Viewer (existing)
    ↓
User clicks: [Print Bracket] button (NEW)
    ↓
Printer Selection Dialog:
┌─────────────────────────────────────┐
│  Select Printer                     │
├─────────────────────────────────────┤
│                                     │
│  Available Printers:                │
│                                     │
│  ○ System Default                  │
│  ○ Brother HL-L8360CDW             │
│  ○ HP LaserJet Pro                 │
│  ○ Send to PDF file                │
│                                     │
│  Copies: [1]                        │
│                                     │
│      [Cancel]     [Print]           │
│                                     │
└─────────────────────────────────────┘
    ↓
Generates PDF (progress indicator)
    ↓
Sends to printer queue
    ↓
Success message / PDF saved locally
```

---

## 15. Success Criteria

- [x] Plan document created
- [ ] Service layer complete and tested
- [ ] Excel export works with provided template
- [ ] PDF export works (or marked as optional)
- [ ] Printer detection works on Windows
- [ ] Print dialog fully functional
- [ ] End-to-end test successful
- [ ] Documentation complete
- [ ] No regressions in existing functionality

---

## 16. Notes & Key Decisions

### Why PDF-Only (Not Excel Templates)?
- **Flexible:** No size constraints - handles any bracket automatically
- **Consistent:** Matches exact UI output (same rendering code)
- **Maintainable:** Single rendering implementation for UI + PDF
- **Fast:** No template parsing or column mapping overhead
- **Scalable:** Pool sizes 2-10+, KO brackets any size

### Cross-Platform Printing via Subprocess
Instead of OS-specific libraries (pywin32, PyObjC, pycups):
- Uses native OS print commands: `print` (Windows), `lp` (Linux/macOS)
- Called via Python `subprocess.run()` with platform detection
- No external dependencies beyond standard library
- Graceful fallback/error handling

**Platform Support:**
```python
system = platform.system()
# 'Windows' → uses 'print' command
# 'Linux' → uses 'lp' command (CUPS)
# 'Darwin' → uses 'lp' command (CUPS)
```

### Temporary File Handling
- Generate PDFs to temp directory: `edv_backend/temp/bracket_TIMESTAMP.pdf`
- Keep files for ~1 hour in case user wants to resend
- Auto-cleanup on startup to remove old temp files
- Or delete immediately after printing if desired

### Next Steps
1. ✅ Planning complete - PDF-first approach approved
2. ✅ Cross-platform printing via subprocess decided
3. 👉 **Phase 1:** Create `bracket_pdf_generator.py` skeleton
4. Study and copy `bracket_renderer.py` drawing logic
5. Implement ReportLab canvas translation
6. Test PDF generation with sample brackets
7. Continue with printer integration and UI
