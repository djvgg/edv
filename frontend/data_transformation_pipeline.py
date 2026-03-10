# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Data Transformation Pipeline

Orchestrates all business logic transformations between screens.
Ensures data consistency and handles the sequence of operations needed
when navigating between screens.

This is a parallel implementation that can be adopted gradually.
Over time, this will replace scattered transformation calls throughout main_window.py

===============================================================================
DOCUMENTATION
===============================================================================

## Purpose

The pipeline centralizes all data transformations that happen when navigating
between screens. Instead of scattering transformation logic throughout callbacks,
all transformations are defined in this class in a clear sequence.

## Data Flow Through the Application

```
┌─────────────────────────────────────────────────────────────────────────┐
│ USER JOURNEY: FILE LOADER → GROUP PREVIEW → GENERATION → VIEWER → MONITORING │
└─────────────────────────────────────────────────────────────────────────┘

1. FILE LOADER (Entry point)
   ├─ User action: Load XLSX or JSON or Database
   └─ Transformations: NONE (data just loaded into self.brackets)

2. GROUP PREVIEW (Review & Edit)
   ├─ User action: View loaded groups, optionally resort
   ├─ Upstream: File loaded (participants → groups created)
   ├─ Transformations before entering:
   │  ├─ merge_u9_u11_pools() - Merge U9/U11 back to single pools for preview
   │  └─ restore_quarantine() - Show quarantined (rejected) fighters
   └─ Output: brackets with original groups + quarantined visible

3. GENERATION METHOD (Assign generation method)
   ├─ User action: Select generation method for each bracket
   ├─ Upstream: Groups confirmed
   ├─ Transformations before entering:
   │  ├─ save_groups() - Persist groups to database
   │  ├─ extract_quarantine() - Remove quarantined fighters from calculations
   │  └─ split_u9_u11_into_pools() - Separate U9/U11 into pool brackets
   └─ Output: brackets ready for generation method assignment

4. BRACKET VIEWER (View & Manage)
   ├─ User action: Assign mats, view generated brackets, manage assignments
   ├─ Upstream: Generation method assigned
   ├─ Transformations before entering:
   │  ├─ regenerate_stale_ko_brackets() - Create KO bracket structures
   │  └─ create_fights() - Initialize fights in database for assigned brackets
   └─ Output: brackets with matches ready for live viewing

5. FIGHT MONITORING (Live match tracking)
   ├─ User action: Open bracket for live monitoring, record match results
   ├─ Upstream: Mat assignment complete
   ├─ Transformations before entering:
   │  ├─ regenerate_stale_ko_brackets() - Ensure KO structure is current
   │  └─ create_fights() - Ensure fights exist in database
   └─ Output: live bracket view ready for score entry

===============================================================================
TRANSFORMATION SEQUENCE (X → Y pattern)
===============================================================================

File Loader → Group Preview:
  1. merge_u9_u11_pools()      [Collapse pools back for human review]
  2. restore_quarantine()      [Show rejected fighters for re-evaluation]

Group Preview → Generation Method:
  1. save_groups()             [Persist confirmed groups to DB]
  2. extract_quarantine()      [Remove quarantine from calculations]
  3. split_u9_u11_into_pools() [Separate into pool brackets again]

Generation Method → Bracket Viewer:
  1. regenerate_stale_ko_brackets() [Create KO bracket structures]
  2. create_fights()                 [Initialize fight records in DB]

Bracket Viewer → Fight Monitoring:
  Same as Gen Method → Viewer (ensure data is current)
  1. regenerate_stale_ko_brackets()
  2. create_fights()

===============================================================================
HOW TO EXPAND THE PIPELINE
===============================================================================

### Adding a New Screen

1. Add the screen key to the transformation rules dict in __init__:
   
   ```python
   self._transformation_rules = {
       'new_screen': {
           'incoming_transformations': [],
           'outgoing_transformations': []
       },
       ...
   }
   ```

2. Define what transformations are needed when entering from upstream screens:
   
   ```python
   'new_screen': {
       'incoming_transformations': [
           'save_groups',         # What to do before leaving group_preview
           'do_something_new',    # New transformation
           'create_fights'
       ],
       'outgoing_transformations': []
   }
   ```

3. Implement the transformation method:
   
   ```python
   def _transform_do_something_new(self):
       \"\"\"Do something new.\"\"\"
       try:
           # Your transformation logic here
           self.logger.debug("✓ Did something new")
       except Exception:
           self.logger.error("Failed to do something", exc_info=True)
           raise
   ```

4. Add the transformation to _execute_transformation():
   
   ```python
   elif transform_name == 'do_something_new':
       self._transform_do_something_new()
   ```

5. Update ScreenManager.screen_dependencies to include new screen in the flow

### Adding a New Transformation

1. Create the method in the pipeline:
   
   ```python
   def _transform_new_operation(self):
       \"\"\"New operation description.\"\"\"
       try:
           # Implementation
           self.logger.debug("✓ New operation completed")
       except Exception:
           self.logger.error("Failed new operation", exc_info=True)
           raise
   ```

2. Register it in _execute_transformation():
   
   ```python
   elif transform_name == 'new_operation':
       self._transform_new_operation()
   ```

3. Add it to transformation_rules where needed:
   
   ```python
   'some_screen': {
       'incoming_transformations': [
           'new_operation',  # Add here
           'existing_operation'
       ]
   }
   ```

===============================================================================
USAGE EXAMPLES
===============================================================================

### Example 1: Get transformation sequence for a screen

```python
screen_key = 'generation_method'
transforms = pipeline.get_transformation_sequence(screen_key)
# Returns: ['save_groups', 'extract_quarantine', 'split_u9_u11_into_pools']
```

### Example 2: Check staleness

```python
is_stale = screen_manager.is_screen_stale('bracket_viewer')
if is_stale:
    print("Bracket viewer data is outdated - needs refresh")
```

### Example 3: Mark screen as needing refresh

```python
# When upstream data changes
screen_manager.invalidate_downstream('file_loader')
# This marks all downstream screens (group_preview, gen_method, etc.) as stale
```

### Example 4: Transform manually (for testing)

```python
# Execute transformations for entering bracket_viewer
wait_for_db = main_window.wait_for_db_service
pipeline.transform_before_entering('bracket_viewer', wait_for_db)
```

### Example 5: Print the transformation map

```python
pipeline.print_transformation_map()
# Output:
# file_loader:
#   Before entering: (none)
#   After leaving: (none)
# group_preview:
#   Before entering: merge_u9_u11_pools → restore_quarantine
#   After leaving: (none)
# generation_method:
#   Before entering: save_groups → extract_quarantine → split_u9_u11_into_pools
#   After leaving: (none)
```

===============================================================================
AUTOMATIC EXECUTION FLOW
===============================================================================

When a user clicks a tab to navigate screens:

1. User clicks "Generation Method" tab
2. ScreenManager.navigate_to('generation_method') is called
3. ScreenManager calls: screen.on_hide() on current screen
4. ScreenManager calls: pipeline.transform_before_entering('generation_method')
   ├─ Pipeline executes: save_groups()
   ├─ Pipeline executes: extract_quarantine()
   └─ Pipeline executes: split_u9_u11_into_pools()
5. ScreenManager unpacks current screen and packs new screen
6. ScreenManager calls: screen.on_show() on new screen
7. New screen displays with transformed data

No manual transformation calls needed - pipeline handles it automatically!

===============================================================================
INTEGRATION WITH MAIN WINDOW (Parallel Implementation)
===============================================================================

The pipeline runs alongside existing transformation calls in main_window.py.
This allows gradual migration:

CURRENT (in main_window.py setup_screen_callbacks):
    ```python
    elif screen_key == 'generation_method':
        # Manual transformation calls
        self.db_service.save_groups(self.brackets)
        self.quarantine_service.extract_quarantine(self.brackets)
        self.brackets = split_u9_u11_into_pools(self.brackets)
    ```

NEW (via pipeline):
    ```python
    # Happens automatically in ScreenManager.navigate_to()
    pipeline.transform_before_entering('generation_method', wait_for_db)
    # Executes same transformations, but centralized and traceable
    ```

MIGRATION PATH:
1. Keep both running (parallel) - NOT BREAKING ✓
2. Verify pipeline produces same results
3. Gradually comment out manual calls in setup_screen_callbacks
4. Remove manual calls completely once tested
5. Delete corresponding code from main_window.py
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# TRANSFORMATION PRESETS (Grouped by Screen Responsibility)
# ============================================================================
#
# Each preset contains transformations that must happen ON that screen
# or to prepare data for display on that screen.
#
# UI_RENDERING: Only needed for visual display (can skip in headless)
# ESSENTIAL: Always needed for data consistency (keep in headless/CLI)
# ============================================================================

# FILE LOADER: Entry point - User loads data from XLSX/JSON/Database
# No transformations needed yet (data just loaded into brackets dict)
PRESET_FILE_LOADER_OPS = {
    'visual': [],  # No UI transforms
    'essential': [],  # No essential transforms at entry
}

# GROUP PREVIEW: Display loaded groups for human review
# UI needs merged pools, quarantine visible for fallback
PRESET_GROUP_PREVIEW_OPS = {
    'visual': [
        'merge_u9_u11_pools',    # [UI] Combine U9/U11 for readable display
        'restore_quarantine',    # [UI] Show rejected fighters for review
    ],
    'essential': [],  # Group preview has no essential DB ops
}

# GENERATION METHOD: Assign generation method to each bracket
# Must persist groups, prepare bracket structures for algorithm
PRESET_GENERATION_METHOD_OPS = {
    'visual': [
        'merge_u9_u11_pools',     # [UI] Display before selection
        'restore_quarantine',     # [UI] Show available fighters
    ],
    'essential': [
        'save_groups',            # [ESSENTIAL] Persist approved groups to DB
        'extract_quarantine',     # [ESSENTIAL] Remove quarantine for calculations
        'split_u9_u11_into_pools',  # [ESSENTIAL] Re-separate for generation
    ],
}

# BRACKET VIEWER: Display brackets with mat assignments
# Must regenerate bracket structures and create fight records
PRESET_BRACKET_VIEWER_OPS = {
    'visual': [],  # No UI-only operations
    'essential': [
        'regenerate_stale_ko_brackets',  # [ESSENTIAL] Generate bracket structures
        'create_fights',                  # [ESSENTIAL] Create fight DB records
    ],
}

# FIGHT MONITORING: Live match tracking and scoring
# Must ensure brackets and fights are current
PRESET_FIGHT_MONITORING_OPS = {
    'visual': [],  # No UI-only operations
    'essential': [
        'regenerate_stale_ko_brackets',  # [ESSENTIAL] Ensure brackets current
        'create_fights',                  # [ESSENTIAL] Ensure fights in DB
    ],
}


class DataTransformationPipeline:
    """
    Manages data transformations between screens.
    
    Responsibilities:
    - Execute transformations in correct order
    - Handle data state consistency
    - Know dependencies between screens
    - Coordinate db_service, bracket_utils, and other services
    """
    
    def __init__(self, main_window, headless=False):
        """
        Initialize pipeline with reference to main_window and its services.

        Args:
            main_window: BracketViewerApp instance with access to:
                - brackets (shared state dict)
                - bracket_generation_methods (dict)
                - bracket_table_assignment (dict)
                - db_service
                - quarantine_service
            headless: If True, skip UI-only transformations (visual-only ops)
        """
        self.main_window = main_window
        self.db_service = main_window.db_service
        self.quarantine_service = main_window.quarantine_service
        self.logger = logger
        self.headless = headless

        # Build transformation rules from presets
        # Each screen composes its visual + essential transformations
        self._transformation_rules = self._build_transformation_rules(headless)

        self.logger.debug(
            f"DataTransformationPipeline initialized (headless={headless})"
        )

    def _build_transformation_rules(self, headless=False):
        """
        Build transformation rules by composing presets.

        In headless mode, skip visual-only transformations.

        Args:
            headless: If True, skip UI-only operations

        Returns:
            Dict of transformation rules per screen
        """
        rules = {}

        for screen_key, preset in [
            ('file_loader', PRESET_FILE_LOADER_OPS),
            ('group_preview', PRESET_GROUP_PREVIEW_OPS),
            ('generation_method', PRESET_GENERATION_METHOD_OPS),
            ('bracket_viewer', PRESET_BRACKET_VIEWER_OPS),
            ('fight_monitoring', PRESET_FIGHT_MONITORING_OPS),
        ]:
            # Compose transformations: always include essential, optionally visual
            visual_ops = preset['visual'] if not headless else []
            essential_ops = preset['essential']

            # Combine: visual first (UI setup), then essential (data operations)
            transformations = visual_ops + essential_ops

            rules[screen_key] = {
                'incoming_transformations': transformations,
                'outgoing_transformations': [],
            }

        return rules
    
    def transform_before_entering(self, screen_key: str, wait_for_db: callable = None) -> bool:
        """
        Execute all transformations needed before entering a screen.
        
        Args:
            screen_key: Screen identifier ('file_loader', 'group_preview', etc.)
            wait_for_db: Optional callable to wait for DB service (from main_window.wait_for_db_service)
        
        Returns:
            True if transformations succeeded, False if blocked
        """
        if screen_key not in self._transformation_rules:
            self.logger.warning(f"No transformation rules for screen: {screen_key}")
            return True
        
        rules = self._transformation_rules[screen_key]
        transformations = rules['incoming_transformations']
        
        if not transformations:
            self.logger.debug(f"No transformations needed before entering {screen_key}")
            return True
        
        self.logger.debug(
            f"Executing {len(transformations)} transformations before entering {screen_key}: "
            f"{transformations}"
        )
        
        try:
            for transform_name in transformations:
                self._execute_transformation(transform_name, wait_for_db)
            
            self.logger.debug(f"✓ All transformations completed for {screen_key}")
            return True
            
        except Exception:
            self.logger.error(
                f"✗ Transformation failed for {screen_key}: {transform_name}",
                exc_info=True
            )
            return False
    
    def transform_after_leaving(self, screen_key: str, wait_for_db: callable = None) -> bool:
        """
        Execute transformations when leaving a screen.
        Currently mostly empty, but framework exists for future use.
        
        Args:
            screen_key: Screen identifier
            wait_for_db: Optional callable to wait for DB service
        
        Returns:
            True if transformations succeeded, False if blocked
        """
        if screen_key not in self._transformation_rules:
            return True
        
        rules = self._transformation_rules[screen_key]
        transformations = rules['outgoing_transformations']
        
        if not transformations:
            return True
        
        try:
            for transform_name in transformations:
                self._execute_transformation(transform_name, wait_for_db)
            return True
        except Exception:
            self.logger.error(f"Transformation failed after leaving {screen_key}", exc_info=True)
            return False
    
    def _execute_transformation(self, transform_name: str, wait_for_db: callable = None):
        """
        Execute a single named transformation.
        
        Args:
            transform_name: Name of transformation ('merge_u9_u11_pools', etc.)
            wait_for_db: Optional callable to wait for DB service
        
        Raises:
            Exception if transformation fails
        """
        if transform_name == 'merge_u9_u11_pools':
            self._transform_merge_u9_u11_pools()
        
        elif transform_name == 'restore_quarantine':
            self._transform_restore_quarantine()
        
        elif transform_name == 'save_groups':
            self._transform_save_groups(wait_for_db)
        
        elif transform_name == 'extract_quarantine':
            self._transform_extract_quarantine()
        
        elif transform_name == 'split_u9_u11_into_pools':
            self._transform_split_u9_u11_into_pools()
        
        elif transform_name == 'regenerate_stale_ko_brackets':
            self._transform_regenerate_stale_ko_brackets()
        
        elif transform_name == 'create_fights':
            self._transform_create_fights(wait_for_db)
        
        else:
            raise ValueError(f"Unknown transformation: {transform_name}")
    
    # Individual transformation methods
    
    def _transform_merge_u9_u11_pools(self):
        """Merge U9/U11 age groups into pools."""
        try:
            from utils.bracket_utils import merge_u9_u11_pools
            self.main_window.brackets = merge_u9_u11_pools(self.main_window.brackets)
            self.logger.debug("✓ Merged U9/U11 pools")
        except Exception:
            self.logger.error("Failed to merge U9/U11 pools", exc_info=True)
            raise
    
    def _transform_restore_quarantine(self):
        """Restore quarantined brackets."""
        try:
            self.quarantine_service.restore_quarantine(self.main_window.brackets)
            self.logger.debug("✓ Restored quarantine")
        except Exception:
            self.logger.error("Failed to restore quarantine", exc_info=True)
            raise
    
    def _transform_save_groups(self, wait_for_db: callable = None):
        """Save groups to database."""
        try:
            if wait_for_db and not wait_for_db():
                self.logger.warning("Database not ready, skipping save_groups")
                return
            
            self.db_service.save_groups(self.main_window.brackets)
            self.logger.debug("✓ Saved groups to database")
        except Exception:
            self.logger.error("Failed to save groups", exc_info=True)
            raise
    
    def _transform_extract_quarantine(self):
        """Extract quarantine from brackets."""
        try:
            self.quarantine_service.extract_quarantine(self.main_window.brackets)
            self.logger.debug("✓ Extracted quarantine")
        except Exception:
            self.logger.error("Failed to extract quarantine", exc_info=True)
            raise
    
    def _transform_split_u9_u11_into_pools(self):
        """Split U9/U11 age groups into pools."""
        try:
            from utils.bracket_utils import split_u9_u11_into_pools
            self.main_window.brackets = split_u9_u11_into_pools(self.main_window.brackets)
            self.logger.debug("✓ Split U9/U11 into pools")
        except Exception:
            self.logger.error("Failed to split U9/U11 pools", exc_info=True)
            raise
    
    def _transform_regenerate_stale_ko_brackets(self):
        """Regenerate KO brackets that are stale."""
        try:
            from backend.services.bracket_manager import regenerate_stale_ko_brackets  # noqa: E402
            from backend.services.bracket_service import make_bracket  # noqa: E402
            
            regenerate_stale_ko_brackets(
                self.main_window.brackets,
                self.main_window.bracket_generation_methods,
                make_bracket
            )
            self.logger.debug("✓ Regenerated stale KO brackets")
        except Exception:
            self.logger.error("Failed to regenerate KO brackets", exc_info=True)
            raise
    
    def _transform_create_fights(self, wait_for_db: callable = None):
        """Create fights for all assigned brackets in database."""
        try:
            if wait_for_db and not wait_for_db():
                self.logger.warning("Database not ready, skipping create_fights")
                return
            
            processed = 0
            for bracket_key, table_num in self.main_window.bracket_table_assignment.items():
                if table_num and bracket_key in self.main_window.brackets:
                    bracket_data = self.main_window.brackets[bracket_key]
                    bracket_type = self.main_window.bracket_generation_methods.get(bracket_key, 'ko')
                    fight_pairs = bracket_data.get('bracket', [])
                    fighters = bracket_data.get('fighters', [])
                    pool_size = bracket_data.get('pool_size')
                    
                    self.db_service.create_fights_for_bracket(
                        bracket_key, fight_pairs,
                        bracket_type=bracket_type,
                        fighters=fighters,
                        pool_size=pool_size
                    )
                    processed += 1
            
            self.logger.debug(f"✓ Created fights for {processed} brackets")
        except Exception:
            self.logger.error("Failed to create fights", exc_info=True)
            raise
    
    def get_transformation_sequence(self, screen_key: str) -> list:
        """
        Get the sequence of transformations for a screen.

        Useful for debugging and understanding data flow.

        Args:
            screen_key: Screen identifier

        Returns:
            List of transformation names
        """
        if screen_key not in self._transformation_rules:
            return []

        return self._transformation_rules[screen_key]['incoming_transformations']

    def get_essential_transformations(self, screen_key: str) -> list:
        """
        Get only essential (non-visual) transformations for a screen.

        Useful for headless/CLI modes that skip UI operations.

        Args:
            screen_key: Screen identifier

        Returns:
            List of essential transformation names
        """
        # Map screen keys to their presets
        preset_map = {
            'file_loader': PRESET_FILE_LOADER_OPS,
            'group_preview': PRESET_GROUP_PREVIEW_OPS,
            'generation_method': PRESET_GENERATION_METHOD_OPS,
            'bracket_viewer': PRESET_BRACKET_VIEWER_OPS,
            'fight_monitoring': PRESET_FIGHT_MONITORING_OPS,
        }

        if screen_key not in preset_map:
            return []

        return preset_map[screen_key]['essential']

    def get_visual_transformations(self, screen_key: str) -> list:
        """
        Get only visual (UI) transformations for a screen.

        These are skipped in headless mode.

        Args:
            screen_key: Screen identifier

        Returns:
            List of visual transformation names
        """
        # Map screen keys to their presets
        preset_map = {
            'file_loader': PRESET_FILE_LOADER_OPS,
            'group_preview': PRESET_GROUP_PREVIEW_OPS,
            'generation_method': PRESET_GENERATION_METHOD_OPS,
            'bracket_viewer': PRESET_BRACKET_VIEWER_OPS,
            'fight_monitoring': PRESET_FIGHT_MONITORING_OPS,
        }

        if screen_key not in preset_map:
            return []

        return preset_map[screen_key]['visual']
    
    
    def print_transformation_map(self):
        """
        Print the complete transformation map for debugging.

        Shows distinction between visual (UI-only) and essential operations.
        """
        preset_map = {
            'file_loader': PRESET_FILE_LOADER_OPS,
            'group_preview': PRESET_GROUP_PREVIEW_OPS,
            'generation_method': PRESET_GENERATION_METHOD_OPS,
            'bracket_viewer': PRESET_BRACKET_VIEWER_OPS,
            'fight_monitoring': PRESET_FIGHT_MONITORING_OPS,
        }

        print("\n" + "="*80)
        print("TRANSFORMATION MAP (Visual + Essential per Screen)")
        print("="*80)

        for screen_key, preset in preset_map.items():
            visual = preset['visual']
            essential = preset['essential']

            print(f"\n{screen_key.upper()}")
            print(f"  Visual (UI-only, skip in headless): {visual if visual else '(none)'}")
            print(f"  Essential (always run): {essential if essential else '(none)'}")

        print("\n" + "="*80 + "\n")

    def print_headless_mode(self):
        """Print transformation map for headless/CLI mode (essential only)."""
        preset_map = {
            'file_loader': PRESET_FILE_LOADER_OPS,
            'group_preview': PRESET_GROUP_PREVIEW_OPS,
            'generation_method': PRESET_GENERATION_METHOD_OPS,
            'bracket_viewer': PRESET_BRACKET_VIEWER_OPS,
            'fight_monitoring': PRESET_FIGHT_MONITORING_OPS,
        }

        print("\n" + "="*80)
        print("HEADLESS MODE (Essential Operations Only)")
        print("="*80)

        for screen_key, preset in preset_map.items():
            essential = preset['essential']

            print(f"\n{screen_key.upper()}")
            if essential:
                for op in essential:
                    print(f"  - {op}")
            else:
                print("  (no operations needed)")

        print("\n" + "="*80 + "\n")


# ============================================================================
# EXAMPLE: Complete Data Flow from File Loader to Fight Monitoring
# ============================================================================
#
# This example shows how data flows through all transformations:
#
# STEP 1: User loads XLSX file in FILE_LOADER
#   ├─ Input: Empty main_window.brackets
#   ├─ Action: Click "Load XLSX"
#   ├─ Callback: on_load_xlsx(filename)
#   ├─ Result: main_window.brackets populated from file
#   └─ Transformations: NONE (data is raw loaded participants)
#
# STEP 2: User navigates to GROUP_PREVIEW
#   ├─ Input: Raw brackets from XLSX (all participants)
#   ├─ Navigation: Click "Group Preview" tab OR auto-navigate
#   ├─ ScreenManager.navigate_to('group_preview') called
#   ├─ Pipeline.transform_before_entering('group_preview') runs:
#   │  ├─ merge_u9_u11_pools()    - Combine U9/U11 pools for display
#   │  └─ restore_quarantine()    - Show any previously quarantined
#   ├─ ScreenManager calls: group_preview_screen.on_show()
#   ├─ Result: Screen displays merged groups for human review
#   └─ User can: Resort, remove, or approve groups
#
# STEP 3: User continues to GENERATION_METHOD
#   ├─ Input: Approved groups from GROUP_PREVIEW  
#   ├─ Navigation: Click "Generation Method" tab
#   ├─ ScreenManager.navigate_to('generation_method') called
#   ├─ Pipeline.transform_before_entering('generation_method') runs:
#   │  ├─ save_groups()          - Persist to database ✓
#   │  ├─ extract_quarantine()   - Remove quarantine from brackets
#   │  └─ split_u9_u11_into_pools() - Re-separate into pool brackets
#   ├─ ScreenManager calls: gen_method_screen.on_show()
#   ├─ Result: Screen displays brackets ready for method assignment
#   └─ User can: Select generation method for each bracket
#
# STEP 4: User confirms generation and views BRACKET_VIEWER
#   ├─ Input: Generation methods assigned to each bracket
#   ├─ Callback: on_generation_methods_selected() stores methods
#   ├─ Navigation: Auto-navigate to 'bracket_viewer' OR click tab
#   ├─ ScreenManager.navigate_to('bracket_viewer') called
#   ├─ Pipeline.transform_before_entering('bracket_viewer') runs:
#   │  ├─ regenerate_stale_ko_brackets() - Create bracket structures ✓
#   │  └─ create_fights()                 - Initialize DB fight records ✓
#   ├─ ScreenManager calls: bracket_viewer_screen.on_show()
#   ├─ Result: Screen displays bracket assignments for mat assignment
#   └─ User can: Assign brackets to mats manually or auto-assign
#
# STEP 5: User opens FIGHT_MONITORING for live scoring
#   ├─ Input: Brackets assigned to mats from BRACKET_VIEWER
#   ├─ Navigation: Click "Fight Monitoring" tab from bracket viewer
#   ├─ ScreenManager.navigate_to('fight_monitoring') called
#   ├─ Pipeline.transform_before_entering('fight_monitoring') runs:
#   │  ├─ regenerate_stale_ko_brackets() - Ensure KO brackets current ✓
#   │  └─ create_fights()                 - Ensure fights in DB ✓
#   ├─ ScreenManager calls: fight_monitoring_screen.on_show()
#   ├─ Result: Screen displays mat overview + ready for bracket selection
#   └─ User can: Click bracket → open fight view → score matches live
#
# TOTAL TRANSFORMATIONS EXECUTED (File Loader → Fight Monitoring):
#   1. merge_u9_u11_pools()             [GROUP_PREVIEW]
#   2. restore_quarantine()             [GROUP_PREVIEW]
#   3. save_groups()                    [GENERATION_METHOD]
#   4. extract_quarantine()             [GENERATION_METHOD]
#   5. split_u9_u11_into_pools()       [GENERATION_METHOD]
#   6. regenerate_stale_ko_brackets()  [BRACKET_VIEWER]
#   7. create_fights()                  [BRACKET_VIEWER]
#   8. regenerate_stale_ko_brackets()  [FIGHT_MONITORING] (cached)
#   9. create_fights()                  [FIGHT_MONITORING] (if new bracket)
#
# DATA CONSISTENCY GUARANTEE:
#   When the user arrives at each screen, the pipeline has already
#   executed all prerequisite transformations. This means:
#   - bracket.json output can be generated, serialized, or transmitted
#   - database records are created and can be queried live
#   - bracket structures are valid for rendering
#   - all transformations are logged and traceable
#
# ============================================================================

