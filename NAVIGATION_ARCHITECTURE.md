# Centralized Navigation Bar Architecture

## Current Navigation Flow

Your application currently uses a **sequential screen model** where windows are shown/hidden via `show_*()` methods. Here's the complete flow:

```
main_window.py (BracketViewerApp) owns all screens
│
├─ show_file_loader()                    [FileLoaderScreen]
│  └─ callbacks: on_load_xlsx, on_load_database, on_load_json, on_split_gender
│
├─ show_group_preview_window()           [GroupPreviewScreen]
│  ├─ on_back → show_file_loader()
│  ├─ on_continue → show_generation_method_screen()
│  └─ on_resort → quarantine_service.resort_brackets()
│
├─ show_generation_method_screen()       [GenerationMethodScreen]
│  └─ on_generation_complete → on_generation_methods_selected()
│
├─ show_bracket_viewer()                 [TableAndBracketViewer]
│  └─ delegates to show_new_bracket_viewer()
│
└─ show_fight_monitoring_comparison()    [Comparison view]
```

---

## Methods Called During Window Transitions

### When entering a window:

1. **Clear existing widgets**: `for widget in self.winfo_children(): widget.destroy()`
2. **Window resize** (in some cases): `self.geometry('WIDTHxHEIGHT')`
3. **Create new screen**: `screen = ScreenClass(self, ...)`
4. **Pack/display**: `screen.pack(fill=tk.BOTH, expand=True)`
5. **Set up callbacks** (wire navigation):
   ```python
   screen.on_back = self.show_file_loader
   screen.on_continue = self.show_next_screen
   screen.on_data_changed = self.handle_data_change
   ```
6. **Load application state data** (if needed): `screen.load_data(self.brackets)`
7. **Register UI services** (feedback/status):
   ```python
   self.ui_feedback.set_status_label_reference(screen.status_label, screen.status_var)
   ```

### When leaving a window (what currently happens):

1. **Callback execution**: `on_back` or `on_continue` is called
2. **Data persistence**: `self.db_service.save_brackets(self.brackets, ...)`
3. **Service cleanup**: `quarantine_service.extract_quarantine()` / `restore_quarantine()`
4. **Data transformation**: `split_u9_u11_into_pools()` / `merge_u9_u11_pools()`
5. **Widget destruction**: All child widgets destroyed
6. **App-level state updates**: `self.bracket_generation_methods = final_assignments`

---

## Proposed Browser Tab Navigation Bar

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  < │ [FileLoader] │ [GroupPreview] │ [GenMethod] │ [...] │ >  │
├─────────────────────────────────────────────────────────┤
│                                                             │
│                    Current Screen Content                   │
│                                                             │
└─────────────────────────────────────────────────────────┘
```

### Features

1. **Grow dynamically**: Each completed screen adds a tab that persists
2. **Back/Forward navigation**: Click any tab to navigate to that screen
3. **State preservation**: Each tab remembers its state until app closes
4. **Data propagation**: Changes in upstream screens invalidate downstream data
5. **Smart refresh**: Downstream screens detect upstream changes and refresh automatically
6. **Main app close handler**: `on_closing()` handles cleanup for entire app

---

## Lifecycle Hooks to Implement

### For Each Screen: Implement these methods

```python
class ScreenBase(tk.Frame):
    """Base class for all screens with navigation lifecycle"""
    
    def on_show(self):
        """
        Called when the screen becomes active (after pack/display)
        
        Default behavior:
        1. Check if screen is stale (via screen_manager.is_screen_stale(self.screen_key))
        2. If stale: reload data from main_window state
        3. Refresh UI widgets with new data
        4. Reset any cached state
        
        Override to customize refresh logic.
        """
        # Default: reload data from main_window.brackets if stale
        if self.screen_manager.is_screen_stale(self.screen_key):
            self.load_data(self.main_window.brackets)
        pass
    
    def on_hide(self):
        """
        Called BEFORE switching away from this screen
        
        Default behavior:
        1. Save current form state to screen_manager
        2. Validate data
        3. Return True if OK to proceed, False to block transition
        
        Override to customize.
        """
        # Save state
        self.screen_manager.save_screen_state(self.screen_key, {})
        # Return True to allow navigation
        return True
    
    def can_navigate_from(self) -> bool:
        """Check if screen allows navigation away. Show error if not."""
        # Validate required fields
        # Check for unsaved changes
        # Show messagebox if blocking
        return True
    
    def can_navigate_to(self) -> bool:
        """Check if all prerequisites are met to enter this screen"""
        # Check parent screen data exists
        # Verify dependencies
        # Check if upstream screens are complete
        return True
```

---

## State Diagram: Screen Transitions

```
┌──────────────┐  load_data()  ┌──────────────┐  selection    ┌──────────────┐
│              │──────────────>│              │──────────────>│              │
│ FileLoader   │               │GroupPreview  │               │GenMethod     │
│              │<──────────────│              │<──────────────│              │
└──────────────┘   on_back()   └──────────────┘   on_back()   └──────────────┘
                                                    │
                        callbacks wired            │ on_generation_complete()
                                                    v
                                              ┌──────────────┐
                                              │              │
                                              │BracketViewer │
                                              │              │
                                              └──────────────┘
```

---

## Navigation Bar Component Structure

### `NavigationBar` (new class to create)

```python
class NavigationBar(tk.Frame):
    """
    Browser-style tab navigation bar
    
    Features:
    - Displays tabs for each visited screen
    - Click tab to navigate between screens
    - Arrows for scrolling through tabs (if too many)
    - Visual indication of active tab
    """
    
    def __init__(self, parent, on_tab_click):
        # on_tab_click(screen_key) -> callback when tab clicked
        pass
    
    def add_tab(self, screen_key, label, locked=False):
        """Add a new tab to the navigation bar (persists until app closes)"""
        pass
    
    def set_active_tab(self, screen_key):
        """Highlight current active tab"""
        pass
```

### `DataTransformationPipeline` (new manager to create)

```python
class DataTransformationPipeline:
    """
    Handles data transformations between screens based on business logic.
    
    Responsibilities:
    - Define transformation rules (e.g., before entering GenMethod, split U9/U11)
    - Execute db_service calls in correct order
    - Handle data state machine (FileLoader → GroupPreview → GenMethod → BracketViewer)
    - Triggered when screens become stale or when navigating forward
    
    Example transformations:
    - Entering GroupPreview from FileLoader: restore_quarantine(), merge_u9_u11_pools()
    - Leaving GroupPreview for GenMethod: save_groups(), extract_quarantine(), split_u9_u11_into_pools()
    - Leaving GenMethod: save_brackets(), regenerate_stale_ko_brackets()
    """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.db_service = main_window.db_service
        pass
    
    def transform_before_entering(self, screen_key):
        """
        Execute transformations before showing a screen.
        Called by ScreenManager when navigating or when screen is stale.
        
        Example flow:
        - Entering GenMethod from GroupPreview (stale):
          1. Call db_service.save_groups(self.main_window.brackets)
          2. Call quarantine_service.extract_quarantine(self.main_window.brackets)
          3. Call split_u9_u11_into_pools(self.main_window.brackets)
        """
        pass
    
    def transform_after_leaving(self, screen_key):
        """
        Execute transformations after hiding a screen.
        Triggered by screen.on_hide() or when invalidating downstream.
        """
        pass
```

### `ScreenManager` (centralized navigation controller to create)

```python
class ScreenManager:
    """
    Manages screen transitions, state, and navigation bar updates
    
    Responsibilities:
    - Execute lifecycle hooks (on_hide, on_show, on_close)
    - Update navigation bar
    - Maintain screen stack/history
    - Handle screen transitions with validation
    - Coordinate with DataTransformationPipeline for data consistency
    - Manage cleanup when navigating away
    """
    
    def __init__(self, main_window, nav_bar, data_pipeline):
        self.main_window = main_window
        self.nav_bar = nav_bar
        self.data_pipeline = data_pipeline  # NEW: Reference to transformation manager
        self.current_screen = None
        self.screen_history = []  # Stack of screen keys
        self.screen_instances = {}  # {screen_key: screen_instance}
        self.screen_state = {}  # {screen_key: state_dict}
        self.screen_staleness = {}  # NEW: {screen_key: is_stale}
        pass
    
    def register_screen(self, screen_key, screen_class, label, locked=False):
        """Register a screen that can be navigated to"""
        pass
    
    def navigate_to(self, screen_key, **kwargs) -> bool:
        """
        Navigate to a screen.
        
        Returns True if navigation succeeded, False if blocked.
        
        Steps:
        1. Call current_screen.can_navigate_from()
        2. Call new_screen.can_navigate_to()
        3. Call current_screen.on_hide()
        4. If new_screen is stale: call data_pipeline.transform_before_entering(screen_key)
        5. Restore or create new_screen
        6. Call new_screen.on_show()
        7. Update nav bar active tab
        8. Mark screen as not stale
        
        Note: Does NOT remove tabs. All visited screens persist in tab bar.
        """
        pass
    
    def invalidate_downstream(self, screen_key):
        """
        Invalidate all screens that depend on screen_key.
        Called when upstream data changes.
        
        Steps:
        1. Mark all downstream screens as stale
        2. If currently viewing a downstream screen:
           - Call data_pipeline.transform_before_entering(current_screen)
           - Trigger screen.on_show() to refresh
        
        Example: User loads new data in FileLoader
        -> invalidate_downstream('file_loader')
        -> GroupPreview, GenMethod, BracketViewer marked as stale
        -> If viewing GroupPreview: pipeline transforms data, then refresh UI
        -> When user navigates to GenMethod: pipeline transforms again, then show
        """
        pass
    
    def go_back(self):
        """Navigate to previous screen in history"""
        pass
    
    def close_app(self):
        """
        Close the entire application (called by main_window.on_closing())
        
        Steps:
        1. Call current_screen.on_hide() for cleanup
        2. Call cleanup on all screen instances in history
        3. Shut down task runner
        4. Close logger
        """
        pass
    
    def unlock_screen(self, screen_key):
        """Enable a screen in the navigation bar"""
        pass
    
    def get_screen_state(self, screen_key):
        """Get saved state for a screen"""
        pass
    
    def save_screen_state(self, screen_key, state):
        """Save screen state for restoration"""
        pass
    
    def is_screen_stale(self, screen_key) -> bool:
        """Check if screen has stale data (upstream was modified)"""
        pass
```

---

## DataTransformationPipeline: Transformation Rules

The pipeline defines what happens before entering each screen:

```
SCREEN_KEY: 'file_loader'
├─ Upstream: None (start of flow)
├─ Transformations: (none)
└─ DB calls: (none)

SCREEN_KEY: 'group_preview'
├─ Upstream: 'file_loader' must load data
├─ Transformations:
│  ├─ quarantine_service.restore_quarantine(brackets)
│  └─ merge_u9_u11_pools(brackets)
└─ DB calls:
   └─ (data loaded from db_service already)

SCREEN_KEY: 'generation_method'
├─ Upstream: 'group_preview' must have valid groups
├─ Transformations:
│  ├─ db_service.save_groups(brackets)
│  ├─ quarantine_service.extract_quarantine(brackets)
│  └─ split_u9_u11_into_pools(brackets)
└─ DB calls: (included above)

SCREEN_KEY: 'bracket_viewer'
├─ Upstream: 'generation_method' must have method assignments
├─ Transformations:
│  ├─ regenerate_stale_ko_brackets(brackets, methods, make_bracket)
│  └─ create_fights_for_bracket() for each assigned bracket
└─ DB calls: (included above + db_service.create_fights_for_bracket)
```

**Key principle**: Each screen's on_show() can safely assume its input data has been transformed correctly by the pipeline.

---

### Phase 1: Base Infrastructure
- [ ] Create `DataTransformationPipeline` class with transformation rules
- [ ] Create `NavigationBar` class
- [ ] Create `ScreenManager` class (with reference to DataTransformationPipeline)
- [ ] Create `ScreenBase` base class with lifecycle hooks and staleness checking
- [ ] Add lifecycle hook methods to all existing screens:
  - [ ] FileLoaderScreen
  - [ ] GroupPreviewScreen
  - [ ] GenerationMethodScreen
  - [ ] TableAndBracketViewer
  - [ ] FightMonitoringScreen

### Phase 2: Integration
- [ ] Add `NavigationBar` to `BracketViewerApp`
- [ ] Create `DataTransformationPipeline` instance in `BracketViewerApp`
- [ ] Create `ScreenManager` instance in `BracketViewerApp` (pass pipeline reference)
- [ ] Convert `show_*()` methods to use `ScreenManager.navigate_to()`
- [ ] Replace callback chains with `ScreenManager.navigate_to()` calls
- [ ] Wire lifecycle hooks to all screens
- [ ] Wire screens to call `invalidate_downstream()` when data changes

### Phase 3: Features
- [ ] Implement tab scrolling for many screens
- [ ] Implement state preservation/restoration
- [ ] Add locking mechanism for screens with prerequisites
- [ ] Add visual feedback for locked vs unlocked screens
- [ ] Implement tab removal when navigating back (via clear_tabs_after)

### Phase 4: Polish
- [ ] Add keyboard shortcuts (Ctrl+Tab for next, Ctrl+Shift+Tab for previous)
- [ ] Persist navigation history for session recovery
- [ ] Add tooltips showing screen status
- [ ] Style tabs to match dark theme

---

## Example Usage After Refactoring

```python
# Current way (in multiple callback chains):
def show_file_loader(self):
    for widget in self.winfo_children():
        widget.destroy()
    loader = FileLoaderScreen(self)
    loader.pack(fill=tk.BOTH, expand=True)
    loader.on_continue = self.show_group_preview_window

# New way:
def show_file_loader(self):
    self.screen_manager.navigate_to('file_loader')

# Or even automatic:
# User clicks button on FileLoader
# FileLoader.on_continue_clicked() calls:
self.on_continue()  # Navigation wired automatically
```

---

## Data Flow: With DataTransformationPipeline

```
1. User completes FileLoader screen
   ├─ FileLoader.on_hide() validates data
   ├─ ScreenManager.navigate_to('group_preview')
   │  ├─ data_pipeline.transform_before_entering('group_preview')
   │  │  ├─ restore_quarantine(brackets)
   │  │  ├─ merge_u9_u11_pools(brackets)
   │  │  └─ load_data(brackets) into preview
   │  ├─ GroupPreview.on_show() displays data
   │  └─ Updates nav bar: Add GroupPreview tab, set active
   
2. User navigates forward through: FileLoader → GroupPreview → GenMethod → BracketViewer
   └─ Each navigation calls data_pipeline.transform_before_entering(screen_key)
   
3. User clicks back to FileLoader and LOADS DIFFERENT DATA
   ├─ FileLoader.on_hide() persists new data to db_service
   ├─ ScreenManager.invalidate_downstream('file_loader')
   │  ├─ Mark GroupPreview, GenMethod, BracketViewer as stale
   │  └─ If currently viewing GroupPreview:
   │     ├─ data_pipeline.transform_before_entering('group_preview') [NEW DATA]
   │     ├─ GroupPreview.on_show() [DETECTS STALE, REFRESHES]
   │     └─ UI updates with new data
   │
   ├─ ScreenManager.navigate_to('group_preview')
   ├─ GroupPreview.on_show() checks is_screen_stale()
   └─ Reloads UI with new data
   
4. When user moves from GroupPreview → GenMethod (after data change):
   ├─ GroupPreview.on_hide() - save any edits
   ├─ ScreenManager.navigate_to('gen_method')
   ├─ data_pipeline.transform_before_entering('gen_method')
   │  ├─ db_service.save_groups(brackets)
   │  ├─ quarantine_service.extract_quarantine(brackets)
   │  ├─ split_u9_u11_into_pools(brackets)
   │  └─ data ready for generation method assignment
   ├─ GenMethod.on_show() displays transformed data
   └─ Navigation complete
   
5. Data flows through the app via:
   ├─ main_window.brackets (shared state)
   ├─ db_service (persistence layer)
   ├─ data_pipeline (transformation layer)
   ├─ screen_manager.get_screen_state() / save_screen_state()
   ├─ screen_manager.is_screen_stale() (check if needs refresh)
   └─ Each screen calls invalidate_downstream() when it modifies data

6. App closes:
   ├─ User clicks main window X button
   ├─ main_window.on_closing() calls screen_manager.close_app()
   ├─ All screen cleanup happens (saved via on_hide())
   ├─ Task runner shuts down
   └─ Logger closes
```

---

## Critical Design Notes

1. **DataTransformationPipeline owns business logic**:
   - All data transformations (split_u9_u11, extract_quarantine, etc.) triggered by pipeline
   - Pipeline knows the order and conditions for transformations
   - ScreenManager calls pipeline BEFORE showing a screen
   - Ensures data consistency across all screens
   
2. **Staleness tracking enables smart refresh**:
   - When upstream screen changes, invalidate_downstream() marks screens as stale
   - On navigation or during invalidation, pipeline transforms the data
   - Screens detect staleness in on_show() and reload UI
   - Prevents orphaned/out-of-sync state
   
3. **Data transformation sequence matters**:
   - FileLoader → GroupPreview: restore_quarantine, merge_u9_u11
   - GroupPreview → GenMethod: save_groups, extract_quarantine, split_u9_u11
   - GenMethod → BracketViewer: save_brackets, create_fights
   - Pipeline encodes this sequence
   
4. **Screen lifecycle with pipeline**:
   - navigate_to() calls transform_before_entering() then on_show()
   - invalidate_downstream() calls transform_before_entering() if viewing stale screen
   - Screens don't worry about data state, pipeline handles it
   
5. **Unidirectional data flow**: 
   - FileLoader → (GroupPreview) → (GenMethod) → (BracketViewer)
   - Earlier screens can invalidate later screens
   - Later screens cannot affect earlier screens
   - Pipeline ensures data flows forward correctly
   
6. **Auto-redirect screens** (exceptions):
   - Skip adding to nav bar if auto-redirecting
   - Example: Rejection summary → auto-closes after display
   
7. **Data invalidation cascade**:
   - Each screen that modifies data should call `screen_manager.invalidate_downstream()`
   - Pipeline will re-transform all downstream screens when accessed
   - All tabs persist until app closes

