# Generation Method Selection Screen - Implementation Plan

**Date:** February 19, 2026  
**Status:** Planning Phase  
**Component:** New Screen between Group Preview and Bracket Viewer

---

## 📋 Overview

Create a new screen that appears after fighters are imported and shows:
1. **Fighter Table** (reuse existing table view)
2. **Generation Method Options** with auto-recommendations
3. **Preview of recommendation** with reasoning
4. **Generate button** to proceed

---

## 🗺️ Current Flow

```
File Loader
    ↓
Load File/Database
    ↓
Group Preview Window (shows fighters)
    ↓
Bracket Viewer (visualizes brackets)
```

## 📈 New Flow

```
File Loader
    ↓
Load File/Database
    ↓
Group Preview Window (shows fighters)
    ↓
[NEW] Generation Method Selection Screen ← NEW SCREEN
    ↓
Bracket Viewer (visualizes brackets)
```

---

## 🎯 Screen Components

### 1. **Header Section**
- Title: "Generation Method Selection"
- Subtitle: Shows bracket key (category)
- Count: "X fighters loaded"

### 2. **Fighter Table** (reuse from group preview)
- Columns: Name | Weight | Club | Age
- Scrollable view
- Read-only

### 3. **Generation Method Panel**
Three button options:
- **Pool System** - For small groups
- **Double Pool** - For medium groups  
- **KO Bracket** - For large groups

### 4. **Auto-Recommendation Panel**
- Shows recommended method
- Displays reasoning: "Based on X fighters..."
- Dynamic based on fighter count:
  - 1-5 fighters → Pool
  - 6-10 fighters → Double Pool
  - 11+ fighters → KO Bracket

### 5. **Method Details Panel** (Dynamic)
When a method is selected/highlighted, show:
- **Pool System:**
  - Description: "Fighters compete in groups, all play each other"
  - Count: "X will be in Y pools"
  - Pool size calculation

- **Double Pool:**
  - Description: "Two separate pools with semi-finals between winners"
  - Count: "X will be split into 2 pools"
  - Structure info

- **KO Bracket:**
  - Description: "Single elimination tournament"
  - Count: "X fighters in bracket"
  - Round info

### 6. **Control Buttons**
- "Back" - Go back to group preview
- "Generate with Selected Method" - (Primary button, enabled after selection)

---

## 💾 Data Structures

### Input
```python
# From previous screen
self.brackets  # Dict of {bracket_key: {fighters: [...]}}
current_bracket_key  # Current bracket being processed
```

### Output (to next screen)
```python
{
    'bracket_key': str,
    'method': 'pool' | 'double_pool' | 'ko_bracket',
    'fighters': [...],
    'recommendation': str,  # For logging
    'auto_recommended': bool  # Was this the auto recommendation?
}
```

---

## 🔢 Recommendation Logic

```
count = len(fighters)

if count <= 5:
    recommend = 'pool'
    reason = f"Pool system: {count} fighters - all play each other in one pool"
elif count <= 10:
    recommend = 'double_pool'
    reason = f"Double pool: {count} fighters - split between 2 pools"
else:
    recommend = 'ko_bracket'
    reason = f"KO bracket: {count} fighters - standard single elimination"

return recommend, reason
```

---

## 📐 Screen Layout

```
┌────────────────────────────────────────────────────┐
│        Generation Method Selection                 │
│        Category: M | U13 | -50kg                   │
│        12 fighters loaded                          │
├────────────────────────────────────────────────────┤
│                                                    │
│  Fighter Table (Scrollable)                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  Name          Weight  Club          Age           │
│  John Doe      65.5    Club A        13            │
│  Jane Smith    67.0    Club B        13            │
│  ...                                              │
│                                                    │
├────────────────────────────────────────────────────┤
│ AUTO-RECOMMENDATION:                              │
│ 🎯 Double Pool (12 fighters → 2 pools)            │
│     "Recommended for 6-10 fighters"               │
├────────────────────────────────────────────────────┤
│ SELECT GENERATION METHOD:                         │
│                                                    │
│  ⦿ Pool System           □ Double Pool   □ KO     │
│                                                    │
│  Description:                                     │
│  All fighters compete in one pool, playing        │
│  each other. Best for 5 or fewer fighters.        │
│                                                    │
├────────────────────────────────────────────────────┤
│ [Back]  [Generate with Selected Method] ────────▶ │
└────────────────────────────────────────────────────┘
```

---

## 🏗️ Implementation Steps

### Step 1: Create Screen Class
- File: `frontend/views/generation_method_screen.py`
- Class: `GenerationMethodScreen(tk.Frame)`
- Methods:
  - `__init__()` - Initialize
  - `init_ui()` - Build UI
  - `load_data(bracket_key, fighters)` - Load fighters and recommendations
  - `calculate_recommendation(fighters)` - Show auto recommendation
  - `on_method_select(method)` - Update preview when method selected
  - `on_generate()` - Generate and proceed
  - `on_back()` - Return to previous screen

### Step 2: Integrate into Main Window
- Update `show_group_preview_window()` → calls new screen
- Add navigation to screen
- Pass fighter data to new screen

### Step 3: Connect to Bracket Viewer
- After generation, pass data to `show_bracket_viewer()`
- Update bracket viewer to use selected method

### Step 4: Implement Generation Logic
- Create `generate_pools()` - Group fighters into pools
- Create `generate_double_pools()` - Split into 2 pools
- Create `generate_ko_bracket()` - Single elimination bracket

---

## 🔗 Integration Points

### Input from previous screen:
```python
# From main_window.py
self.brackets[bracket_key] = {
    'fighters': [...],  # List of fighter dicts
    'metadata': {...}
}
```

### Output to next screen:
```python
# Pass to bracket viewer
{
    'generation_method': method,
    'bracket_data': generated_bracket,
    'fighters': fighters
}
```

---

## 🎨 Styling

Use existing styles:
- `COLORS['bg_dark']` - Background
- `COLORS['accent_blue']` - Selected/Primary
- `COLORS['accent_green']` - Recommendation
- `FONTS['heading_lg']` - Title
- `FONTS['body_md']` - Content
- `apply_button_style()` - Buttons
- `apply_label_style()` - Labels
- `create_dark_frame()` - Frames

---

## 📝 Fighter Table Display

Reuse existing code from `main_window.py`:
```python
# Reuse this pattern from group preview
header = f"{'Name':<35} {'Weight':<15} {'Club':<30} {'Age':<10}\n"
# Format fighters as rows with fixed-width spacing
```

---

## ♻️ Reuse Existing Functions

From `frontend/utils/`:
- `split_into_pools()` - Create pool groups
- `calculate_pool_positions()` - Layout pools
- `draw_pools_on_canvas()` - Visualize pools

From `backend/services/`:
- `make_bracket()` - Generate KO bracket
- `get_pool_size()` - Check config

---

## 🔄 Data Flow

```
Generation Method Screen
    ↓
Fighter Table View (from memory)
    ↓
Auto Recommendation:
  ├─ Count fighters
  └─ Return (method, reason)
    ↓
User selects method
    ↓
on_generate():
  ├─ If pool: split_into_pools()
  ├─ If double: split_into_pools(2 groups)
  └─ If ko: make_bracket()
    ↓
Pass to Bracket Viewer
    ↓
Visualize result
```

---

## 🧪 Testing Scenarios

### Test 1: Small Group (≤5 fighters)
- Load 3 fighters
- Should recommend: Pool
- Generate pools view

### Test 2: Medium Group (6-10 fighters)
- Load 8 fighters
- Should recommend: Double Pool
- Generate double pool view

### Test 3: Large Group (>10 fighters)
- Load 15 fighters
- Should recommend: KO Bracket
- Generate bracket view

### Test 4: Method Override
- Load 5 fighters (recommends pool)
- User selects KO bracket
- Generate bracket instead

---

## 🚀 Implementation Order

1. **Create screen file** - Empty class structure
2. **Build UI layout** - Title, table, buttons
3. **Implement table display** - Copy fighter data
4. **Add recommendation logic** - Calculate and show
5. **Add method selection** - Radio buttons/buttons
6. **Add method preview** - Show details
7. **Connect to main window** - Show after preview
8. **Implement generation** - Create pools/bracket
9. **Connect to viewer** - Pass data to next screen
10. **Test all scenarios** - Verify each path

---

## 📦 Files to Create/Modify

### Create
- `frontend/views/generation_method_screen.py` (NEW)

### Modify
- `frontend/views/main_window.py` - Add screen, integrate flow
- Maybe `frontend/utils/` - Add pool generation helpers if needed

### Config
- Add screen to imports
- Register in main window's screen management

---

## 💡 Key Decisions

1. **Method Selection:** Radio buttons selected? Or clickable cards?
   - **Decision:** Use radio buttons for clarity, with styled cards showing details

2. **Table Reuse:** Copy from group preview or create utility function?
   - **Decision:** Create helper function in `frontend/utils/` to avoid duplication

3. **Recommendation:** Auto-select or just show as suggestion?
   - **Decision:** Show as suggestion, let user choose, but highlight recommended

4. **Generation:** Do in main thread or background thread?
   - **Decision:** Background thread for large groups (show loading indicator)

---

## ✅ Success Criteria

- [x] Screen displays correctly between preview and viewer
- [x] Fighter table shows all imported fighters
- [x] Auto-recommendation calculates correctly
- [x] All 3 generation methods can be selected
- [x] Selected method generates appropriate output
- [x] Can proceed to bracket viewer with any method
- [x] Can go back to preview
- [x] Styling consistent with rest of app
- [x] Works with different group sizes

---

**This plan provides a clear roadmap for implementation!**
