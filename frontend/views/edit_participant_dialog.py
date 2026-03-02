# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import datetime
import tkinter as tk
from tkinter import messagebox

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from backend.services.bracket_service import get_age_group as get_age_group_with_fallback  # noqa: E402

from ..styles import COLORS, FONTS

class Edit_Participants(tk.Toplevel):
    def __init__(self, parent, bracket_key, fighter_idx):
        # We need parent.master as the master for Toplevel so it stays within the app context
        super().__init__(parent.master)
        self.parent = parent
        self.bracket_key = bracket_key
        self.fighter_idx = fighter_idx
        
        self.title("Edit Participant")
        self.geometry("500x680")
        self.configure(bg=COLORS['bg_dark'])
        self.transient(self.parent.master)
        self.resizable(False, False)
        
        # Center window on screen
        self.parent.update_idletasks()
        width = 500
        height = 680
        x = (self.parent.winfo_screenwidth() // 2) - (width // 2)
        y = (self.parent.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        self.grab_set()
        self._build_ui()

    def _get_available_age_classes(self, gender, current_age_group):
        """Get the next higher age class based on the fixed hierarchy."""
        AGE_CLASS_ORDER = ['U9', 'U11', 'U13', 'U15', 'U18', '18+']
        try:
            current_idx = AGE_CLASS_ORDER.index(current_age_group)
            return AGE_CLASS_ORDER[current_idx + 1:]
        except ValueError:
            return []

    def _get_available_weight_classes(self, gender, age_group):
        """Get all available weight classes for gender and age_group from config."""
        available_classes = []
        used_fallback = False
        
        if self.parent.config_repo:
            try:
                gender_norm = str(gender).lower().strip()
                if gender_norm in ('m', 'male', 'maennlich', 'männlich'):
                    gender_norm = 'm'
                elif gender_norm in ('w', 'f', 'female', 'weiblich', 'frau'):
                    gender_norm = 'w'
                
                df = self.parent.config_repo.weight_classes
                filtered = df[(df['Gender'] == gender_norm) & (df['AgeGroup'] == age_group)]
                available_classes = filtered['Label'].tolist()
            except Exception as e:
                self.parent.logger.warning(f"Config lookup failed, falling back to brackets: {e}")
        
        if not available_classes:
            used_fallback = True
            for bracket_key in self.parent.brackets.keys():
                parts = [p.strip() for p in bracket_key.split('|')]
                if len(parts) >= 3 and parts[0] == gender and parts[1] == age_group:
                    if parts[2] not in available_classes:
                        available_classes.append(parts[2])
        
        if used_fallback:
            def sort_key(x):
                if x == 'no-class':
                    return (0, 0)
                num_str = x.replace('kg', '').replace('-', '').replace('+', '')
                try:
                    num = float(num_str)
                except ValueError:
                    return (999, 0)
                is_plus = 1 if x.startswith('+') else 0
                return (num, is_plus)
            available_classes.sort(key=sort_key)
        
        return available_classes

    def _build_ui(self):
        """Build the edit participant dialog UI.
        
        ⚙️ INTEGRATIONS:
        
        1. **QuarantineService** (on save for QUARANTINE bracket):
           - Uses resort_brackets(brackets, edited_fighter) for proper state sync
           - Re-validates quarantine participants and moves valid ones to correct brackets
           - Maintains quarantine_bracket reference consistency
        
        2. **ConfigRepository** (real-time):
           - get_weight_class(weight, gender, age_group) → Shows auto-detected weight class as user types
           - get_age_group(birth_year) → Validates birth year & suggests primary age group  
           - get_all_eligible_age_groups(birth_year) → Shows all eligible age groups (double starts)
        
        3. **group_preview_screen._move_participant_to_bracket()** (for non-quarantine):
           - Direct bracket movement when age/weight class changes
           - Only used for non-quarantine brackets (QUARANTINE uses resort_brackets for state sync)
        
        4. **Inline Validation**:
           - Name format validation (letters, hyphens, spaces only)
           - Weight validation (numeric, 0.1-999.9 kg range)
           - Birth year validation (exactly 4 digits, age 6-120 years)
           - Age group mapping validation
        
        5. **TaskRunner** (optional future):
           - Could defer validation/re-sorting to background thread
        """
        bracket_key = self.bracket_key
        fighter_idx = self.fighter_idx
        
        is_quarantine = bracket_key == 'QUARANTINE'
        self.parent.logger.debug(f"EDIT_DIALOG: Opening dialog for bracket={bracket_key}, fighter_idx={fighter_idx}, is_quarantine={is_quarantine}")
        
        try:
            fighters = self.parent.brackets[bracket_key].get('fighters', [])
            if not (0 <= fighter_idx < len(fighters)):
                self.parent.logger.error(f"EDIT_DIALOG: Invalid fighter_idx {fighter_idx} for bracket {bracket_key}")
                self.destroy()
                return
            
            fighter = fighters[fighter_idx]
            self.parent.logger.debug(f"EDIT_DIALOG: Editing {fighter.get('Firstname', '')} {fighter.get('Lastname', '')} (ID: {fighter.get('ID', '?')})")
            gender, age_group, current_weight_class = self.parent._parse_bracket_key(bracket_key)
            if gender is None:
                gender = ""
            if age_group is None:
                age_group = ""
            if current_weight_class is None:
                current_weight_class = ""
            
            # For QUARANTINE or when gender is empty, use fighter's Gender field
            if not gender and fighter.get('Gender'):
                gender = str(fighter.get('Gender')).strip().lower()
                if gender:
                    gender = gender[0]  # Take first character (m, w, f)
                    self.parent.logger.debug(f"EDIT_DIALOG: Using fighter's Gender field: {gender}")
            
            first_name = fighter.get('Firstname', fighter.get('name', ''))
            last_name = fighter.get('Lastname', '')
            weight = fighter.get('Weight', fighter.get('weight', ''))
            club = fighter.get('Club', fighter.get('Verein', fighter.get('verein', fighter.get('club', ''))))
            association = fighter.get('Association', '')
            birth_year = fighter.get('Birthyear', fighter.get('BirthYear', fighter.get('birthyear', fighter.get('age', ''))))
            is_valid = fighter.get('Valid', False)
            is_paid = fighter.get('Paid', False)
            
            self.parent.logger.debug(f"EDIT_DIALOG: Current state - Valid={is_valid}, Paid={is_paid}, Weight={weight}, BirthYear={birth_year}")
            
            # For QUARANTINE or when age_group is empty, calculate fallback age group from birth year
            if not age_group and birth_year:
                try:
                    birth_year_int = int(birth_year) if isinstance(birth_year, str) else birth_year
                    current_year = datetime.datetime.now().year
                    calculated_age = current_year - birth_year_int
                    fallback_age_group = get_age_group_with_fallback(calculated_age)
                    if fallback_age_group:
                        age_group = fallback_age_group
                        self.parent.logger.debug(f"EDIT_DIALOG: Calculated age group from birth year {birth_year_int}: {age_group} (age={calculated_age})")
                except (ValueError, TypeError, Exception) as e:
                    self.parent.logger.debug(f"EDIT_DIALOG: Could not calculate age group from birth year: {e}")
            
            if isinstance(weight, (int, float)):
                weight_str = f"{weight:.1f}"
            else:
                weight_str = str(weight)
            
            available_weight_classes = self._get_available_weight_classes(gender, age_group)
            self.parent.logger.debug(f"EDIT_DIALOG: Available weight classes for {gender}|{age_group}: {available_weight_classes}")
            
            # Header with participant name
            header_frame = tk.Frame(self, bg=COLORS['bg_darker'], height=70)
            header_frame.pack(fill=tk.X)
            header_frame.pack_propagate(False)
            
            tk.Frame(header_frame, bg=COLORS['accent_blue'], width=5).pack(side=tk.LEFT, fill=tk.Y)
            
            title_label = tk.Label(header_frame, text=f"Participant: {first_name} {last_name}".strip(), bg=COLORS['bg_darker'], fg=COLORS['text_primary'], font=FONTS['preview_title'])
            title_label.pack(side=tk.LEFT, padx=20, pady=20)
            
            # Main container with better padding
            container = tk.Frame(self, bg=COLORS['bg_dark'])
            container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

            # ── Click anywhere outside entries to deselect ──
            def _focus_window(e):
                """Shift focus to the window when clicking non-entry areas.
                Skip interactive widgets (buttons, checkbuttons, dropdowns)."""
                widget = e.widget
                if isinstance(widget, (tk.Entry, tk.Button, tk.Checkbutton, tk.Listbox)):
                    return
                # Walk up widget hierarchy: skip if any ancestor has cursor='hand2'
                w = widget
                while w and w != self:
                    try:
                        if w.cget('cursor') == 'hand2':
                            return
                    except (tk.TclError, AttributeError):
                        pass
                    try:
                        w = w.master
                    except AttributeError:
                        break
                self.focus_set()
            self.bind('<Button-1>', _focus_window)
            
            # ── Input validation ──────────────────────────────────────
            NAME_PATTERN = re.compile(r'^[A-Za-zÄÖÜäöüß\- ]*$')

            # Field limits
            MAX_NAME_LENGTH = 30
            MAX_WEIGHT_LENGTH = 6
            MAX_BIRTHYEAR_LENGTH = 4
            MAX_CLUB_LENGTH = 50
            MAX_ASSOCIATION_LENGTH = 30

            # Hint texts
            HINT_NAME = "Nur Buchstaben und -, max 30 Zeichen"
            HINT_WEIGHT = "Nur Ziffern, 52.3 oder 52,3"
            HINT_BIRTHYEAR = "Genau 4 Ziffern"
            HINT_CLUB = "Maximal 50 Zeichen"
            HINT_ASSOCIATION = "Maximal 30 Zeichen"


            def _validate_name(action, value_if_allowed):
                """Allow only letters, hyphens, spaces, and umlauts. Max 30 chars.
                Hyphens may not be consecutive, leading, or trailing."""
                if action == '0':  # deletion is always ok
                    return True
                if len(value_if_allowed) > MAX_NAME_LENGTH:
                    return False
                if not NAME_PATTERN.match(value_if_allowed):
                    return False
                # Reject consecutive hyphens (--) and leading hyphen
                if '--' in value_if_allowed or value_if_allowed.startswith('-'):
                    return False
                return True

            def _validate_weight(action, value_if_allowed):
                """Allow digits and one decimal separator (. or ,). Max 6 chars, max 3 digits before sep, max 1 after."""
                if action == '0':
                    return True
                if len(value_if_allowed) > MAX_WEIGHT_LENGTH:
                    return False
                # Normalize comma to dot for checking
                normalized = value_if_allowed.replace(',', '.')
                # Only digits and at most one dot
                if normalized.count('.') > 1:
                    return False
                parts = normalized.split('.')
                # Before decimal: max 3 digits
                if len(parts[0]) > 3:
                    return False
                if not all(c.isdigit() for c in parts[0] if c != ''):
                    return False
                # After decimal (if present): max 1 digit
                if len(parts) == 2:
                    if len(parts[1]) > 1:
                        return False
                    if parts[1] and not parts[1].isdigit():
                        return False
                # Reject any non-digit, non-separator chars
                for c in value_if_allowed:
                    if c not in '0123456789.,':
                        return False
                return True

            def _validate_birthyear(action, value_if_allowed):
                """Allow only digits, max 4 characters."""
                if action == '0':
                    return True
                if len(value_if_allowed) > MAX_BIRTHYEAR_LENGTH:
                    return False
                return value_if_allowed.isdigit()

            def _validate_max_length(max_len):
                """Return a validator that only enforces a max character length."""
                def _validate(action, value_if_allowed):
                    if action == '0':
                        return True
                    return len(value_if_allowed) <= max_len
                return _validate

            # Register validators with Tkinter
            validation_command_name = (self.register(_validate_name), '%d', '%P')
            validation_command_weight = (self.register(_validate_weight), '%d', '%P')
            validation_command_birthyear = (self.register(_validate_birthyear), '%d', '%P')
            validation_command_club = (self.register(_validate_max_length(MAX_CLUB_LENGTH)), '%d', '%P')
            validation_command_association = (self.register(_validate_max_length(MAX_ASSOCIATION_LENGTH)), '%d', '%P')

            # Helper function to create form fields with subtle borders
            def create_field(parent_frame, label_text, entry_var=None, is_readonly=False,
                             validation_command=None, hint_text=None):
                """Create a nicely styled form field with optional validation feedback."""
                field_frame = tk.Frame(parent_frame, bg=COLORS['bg_dark'])
                field_frame.pack(fill=tk.X, pady=(0, 18))
                
                label = tk.Label(field_frame, text=label_text.upper(), bg=COLORS['bg_dark'], fg=COLORS['accent_blue'], font=FONTS['preview_label'])
                label.pack(anchor=tk.W, pady=(0, 6))
                
                # Wrapper for border effect
                border_frame = tk.Frame(field_frame, bg=COLORS['border'], padx=1, pady=1)
                border_frame.pack(fill=tk.X)

                # ── Red flash on invalid input ──
                _flash_timer_id = [None]  # mutable container for after-id

                def _on_invalid():
                    """Flash the border red briefly when validation rejects input."""
                    border_frame.config(bg=COLORS['accent_red'])
                    if _flash_timer_id[0]:
                        self.after_cancel(_flash_timer_id[0])
                    _flash_timer_id[0] = self.after(
                        350, lambda: border_frame.config(bg=COLORS['accent_blue'] if entry == self.focus_get() else COLORS['border'])
                    )

                invalid_input_command = (self.register(lambda: _on_invalid() or False),)
                
                entry_kwargs = dict(
                    bg=COLORS['bg_input'], fg=COLORS['text_primary'],
                    font=FONTS['preview_text'], bd=0, relief=tk.FLAT
                )
                if validation_command:
                    entry_kwargs['validate'] = 'key'
                    entry_kwargs['validatecommand'] = validation_command
                    entry_kwargs['invalidcommand'] = invalid_input_command

                entry = tk.Entry(border_frame, **entry_kwargs)
                entry.pack(fill=tk.X, ipady=10, ipadx=10)
                
                if is_readonly:
                    entry.config(state=tk.DISABLED, fg=COLORS['text_muted'])
                    border_frame.config(bg=COLORS['bg_panel'])

                # ── Hint text below the field ──
                if hint_text:
                    hint_label = tk.Label(field_frame, text=hint_text, bg=COLORS['bg_dark'],
                                          fg=COLORS['text_muted'], font=FONTS['preview_hint'])
                    hint_label.pack(anchor=tk.W, pady=(3, 0))

                # Highlight on focus
                def on_focus_in(e, b=border_frame):
                    if not is_readonly:
                        b.config(bg=COLORS['accent_blue'])

                def on_focus_out(e, b=border_frame):
                    if not is_readonly:
                        b.config(bg=COLORS['border'])
                
                entry.bind("<FocusIn>", on_focus_in)
                entry.bind("<FocusOut>", on_focus_out)
                
                return entry

            def insert_value(entry, value):
                """Insert a value into the entry."""
                if value:
                    entry.insert(0, value)

            # Name fields in a row
            name_row = tk.Frame(container, bg=COLORS['bg_dark'])
            name_row.pack(fill=tk.X)
            
            first_col = tk.Frame(name_row, bg=COLORS['bg_dark'])
            first_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            first_entry = create_field(first_col, "First Name", validation_command=validation_command_name,
                                        hint_text=HINT_NAME)
            insert_value(first_entry, first_name)
            
            last_col = tk.Frame(name_row, bg=COLORS['bg_dark'])
            last_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            last_entry = create_field(last_col, "Last Name", validation_command=validation_command_name,
                                       hint_text=HINT_NAME)
            insert_value(last_entry, last_name)
            
            # Weight and Age in a row
            row_frame = tk.Frame(container, bg=COLORS['bg_dark'])
            row_frame.pack(fill=tk.X)
            
            weight_col = tk.Frame(row_frame, bg=COLORS['bg_dark'])
            weight_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            weight_entry = create_field(weight_col, "Weight (kg)", validation_command=validation_command_weight,
                                         hint_text=HINT_WEIGHT)
            insert_value(weight_entry, weight_str)
            
            # Show detected weight class as user types
            weight_class_hint = tk.Label(weight_col, text="", bg=COLORS['bg_dark'],
                                         fg=COLORS['text_muted'], font=FONTS['preview_hint'])
            
            def _on_weight_changed(e=None):
                """Show auto-detected weight class as user types (uses ConfigRepository.get_weight_class).
                Uses current age_group or fallback age_group if birth year is out of bounds."""
                weight_str_input = weight_entry.get().strip().replace(',', '.')
                birth_year_str = birth_year_entry.get().strip()
                
                if weight_str_input and self.parent.config_repo:
                    try:
                        weight_val = float(weight_str_input)
                        if weight_val > 0:
                            # Determine effective age group for weight class lookup
                            effective_age_group = age_group
                            if birth_year_str and len(birth_year_str) == 4 and birth_year_str.isdigit():
                                try:
                                    birth_year_int = int(birth_year_str)
                                    current_year = datetime.datetime.now().year
                                    calculated_age = current_year - birth_year_int
                                    fallback_ag = get_age_group_with_fallback(calculated_age)
                                    if fallback_ag:
                                        effective_age_group = fallback_ag
                                except (ValueError, Exception):
                                    pass
                            
                            detected = self.parent.config_repo.get_weight_class(weight_val, gender, effective_age_group)
                            if detected and detected != 'unknown':
                                weight_class_hint.config(text=f"→ Auto-class: {detected}")
                                self.parent.logger.debug(f"EDIT_DIALOG: Weight {weight_val}kg detected as {detected} (age_group={effective_age_group})")
                            else:
                                weight_class_hint.config(text="")
                    except (ValueError, Exception):
                        weight_class_hint.config(text="")
            
            weight_entry.bind("<KeyRelease>", _on_weight_changed)
            weight_entry.bind("<FocusOut>", lambda e: weight_class_hint.pack(anchor=tk.W, pady=(3, 0)) if weight_class_hint.cget("text") else None)
            
            age_col = tk.Frame(row_frame, bg=COLORS['bg_dark'])
            age_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            birth_year_entry = create_field(age_col, "Birth Year", validation_command=validation_command_birthyear,
                                             hint_text=HINT_BIRTHYEAR)
            insert_value(birth_year_entry, str(birth_year))
            
            # Auto-detect age group from birth year on focus out
            def _on_birth_year_changed(e):
                """Auto-detect age group when birth year is entered (uses bracket_service.get_age_group WITH fallback)."""
                birth_year_str = birth_year_entry.get().strip()
                if birth_year_str and len(birth_year_str) == 4 and birth_year_str.isdigit():
                    try:
                        birth_year_int = int(birth_year_str)
                        current_year = datetime.datetime.now().year
                        calculated_age = current_year - birth_year_int
                        
                        # Use bracket_service.get_age_group which has fallback for out-of-bounds years
                        auto_age_group = get_age_group_with_fallback(calculated_age)
                        
                        # Also try config_repo for config-defined eligibility if available
                        config_age_group = None
                        all_eligible = []
                        if self.parent.config_repo:
                            config_age_group = self.parent.config_repo.get_age_group(birth_year_int)
                            all_eligible = self.parent.config_repo.get_all_eligible_age_groups(birth_year_int)
                        
                        self.parent.logger.debug(
                            f"EDIT_DIALOG: Birth year {birth_year_int} (age {calculated_age}) → "
                            f"auto_age_group (with fallback) = {auto_age_group}, "
                            f"config_age_group = {config_age_group}, eligible = {all_eligible}"
                        )
                        
                        if auto_age_group and auto_age_group != age_group and not is_young_category:
                            self.parent.logger.debug(f"EDIT_DIALOG: Birth year {birth_year_int} detected age group: {auto_age_group}")
                            # Could auto-update age_group_var here if implementing auto-upgrade feature
                            
                        # Re-calculate weight class hint based on new age group
                        _on_weight_changed()
                    except (ValueError, Exception) as ex:
                        self.parent.logger.debug(f"EDIT_DIALOG: Birth year auto-detect failed: {ex}")
            
            birth_year_entry.bind("<FocusOut>", _on_birth_year_changed)
            
            # Club and Association fields in a row
            club_row = tk.Frame(container, bg=COLORS['bg_dark'])
            club_row.pack(fill=tk.X)
            
            club_col = tk.Frame(club_row, bg=COLORS['bg_dark'])
            club_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            club_entry = create_field(club_col, "Club", validation_command=validation_command_club,
                                       hint_text=HINT_CLUB)
            insert_value(club_entry, club)
            
            association_col = tk.Frame(club_row, bg=COLORS['bg_dark'])
            association_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
            association_entry = create_field(association_col, "Association", validation_command=validation_command_association,
                                        hint_text=HINT_ASSOCIATION)
            insert_value(association_entry, association)
            
            # Weight Class / Age Class section
            is_free_match = str(bracket_key).startswith("FM |")
            is_young_category = age_group in ('U9', 'U11') or str(bracket_key).strip() in ('U9', 'U11')
            is_adult_category = age_group == "18+"
            label_text = "WEIGHT CLASS ASSIGNMENT" if is_adult_category else "AGE CLASS UPGRADE"
            
            weight_class_frame = tk.Frame(container, bg=COLORS['bg_dark'])
            # Only show class assignments for participants outside of QUARANTINE
            if not is_free_match and not is_young_category and not is_quarantine:
                weight_class_frame.pack(fill=tk.X, pady=(0, 14))
                
                weight_class_label = tk.Label(weight_class_frame, text=label_text, bg=COLORS['bg_dark'], fg=COLORS['accent_blue'], font=FONTS['preview_label'])
                weight_class_label.pack(anchor=tk.W, pady=(0, 6))
            
            weight_class_var = tk.StringVar(value=current_weight_class)
            age_class_var = tk.StringVar(value=age_group)
            
            def get_weight_key(weight_class_str):
                """Returns (numeric_value, is_plus) for sorting."""
                num_str = weight_class_str.replace('kg', '').replace('-', '').replace('+', '')
                try:
                    num = float(num_str)
                except ValueError:
                    return (999, 0)
                is_plus = 1 if weight_class_str.startswith('+') else 0
                return (num, is_plus)
            
            current_weight_key = get_weight_key(current_weight_class)
            
            # -- Dropdown Option Variables --
            options_to_show = []
            selected_var = None
            
            if not is_free_match and not is_young_category:
                if is_adult_category:
                    # Determine fighter's NATURAL weight class from actual weight
                    natural_weight_class = None
                    fighter_weight = fighter.get('Weight', 0)
                    if self.parent.config_repo and fighter_weight and fighter_weight > 0:
                        natural_weight_class = self.parent.config_repo.get_weight_class(fighter_weight, gender, age_group)
                    
                    if natural_weight_class and natural_weight_class != 'unknown':
                        natural_key = get_weight_key(natural_weight_class)
                        # Find the ONE class above the natural class (max allowed)
                        heavier_than_natural = [wc for wc in available_weight_classes if get_weight_key(wc) > natural_key]
                        if heavier_than_natural:
                            max_allowed_class = heavier_than_natural[0]  # One class above natural
                            max_allowed_key = get_weight_key(max_allowed_class)
                            
                            if current_weight_key >= max_allowed_key:
                                # Already at or above max allowed → no upgrade possible
                                options_to_show = [current_weight_class]
                            else:
                                # Can still go up to max_allowed_class
                                options_to_show = [current_weight_class, max_allowed_class]
                        else:
                            # Already in highest class → no upgrade possible
                            options_to_show = [current_weight_class]
                    else:
                        # No weight entered or config not available → fallback: show next class up
                        heavier_classes = [wc for wc in available_weight_classes if get_weight_key(wc) > current_weight_key]
                        if heavier_classes:
                            next_class = heavier_classes[0]
                            options_to_show = [current_weight_class, next_class]
                    selected_var = weight_class_var
                else:
                    available_age_classes = self._get_available_age_classes(gender, age_group)
                    if available_age_classes:
                        next_class = available_age_classes[0]
                        options_to_show = [age_group, next_class]
                        self.parent.logger.debug(f"EDIT_DIALOG: Age upgrade available: {age_group} → {next_class}")
                    selected_var = age_class_var
                
            if not is_free_match and not is_young_category and not is_quarantine:
                if options_to_show:
                    # CUSTOM DROPDOWN REPLACEMENT (Using a Frame-based layout to prevent draw collisions)
                    dropdown_border = tk.Frame(weight_class_frame, bg=COLORS['border'], padx=1, pady=1)
                    dropdown_border.pack(fill=tk.X)
                    
                    # The clickable button container
                    dropdown_btn = tk.Frame(dropdown_border, bg=COLORS['bg_input'], cursor='hand2')
                    dropdown_btn.pack(fill=tk.BOTH, expand=True)
                    
                    # Left side: Text label bound to the variable
                    text_label = tk.Label(
                        dropdown_btn, 
                        textvariable=selected_var,
                        bg=COLORS['bg_input'], 
                        fg=COLORS['text_primary'], 
                        font=FONTS['preview_text'],
                        anchor=tk.W,
                        padx=10,
                        pady=8
                    )
                    text_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    
                    # Right side: The arrow symbol
                    arrow_label = tk.Label(
                        dropdown_btn, 
                        text="▼", 
                        bg=COLORS['bg_input'], 
                        fg=COLORS['accent_blue'], 
                        font=FONTS['preview_small'],
                        padx=10
                    )
                    arrow_label.pack(side=tk.RIGHT, fill=tk.Y)
                    
                    def show_dropdown_menu():
                        # Create a custom popup for the dropdown
                        popup = tk.Toplevel(self)
                        popup.withdraw()
                        popup.overrideredirect(True)
                        popup.configure(bg=COLORS['border'])
                        
                        # List container
                        list_frame = tk.Frame(popup, bg=COLORS['bg_input'])
                        list_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
                        
                        scrollbar = None
                        if len(options_to_show) > 8:
                            scrollbar = tk.Scrollbar(list_frame, width=10)
                            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                        
                        lb = tk.Listbox(
                            list_frame, 
                            bg=COLORS['bg_input'], 
                            fg=COLORS['text_primary'],
                            font=FONTS['preview_text'],
                            bd=0,
                            highlightthickness=0,
                            selectbackground=COLORS['accent_blue'],
                            selectforeground=COLORS['text_primary'],
                            activestyle='none',
                            yscrollcommand=scrollbar.set if scrollbar else None,
                            cursor='hand2'
                        )
                        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        if scrollbar:
                            scrollbar.config(command=lb.yview)
                        
                        for opt in options_to_show:
                            lb.insert(tk.END, f"  {opt}")
                            if opt == selected_var.get():
                                lb.selection_set(lb.size()-1)
                                lb.see(lb.size()-1)
                        
                        self.update_idletasks()
                        width = dropdown_btn.winfo_width()
                        
                        max_visible_items = 8
                        visible_items = min(len(options_to_show), max_visible_items)
                        lb.config(height=visible_items)
                        
                        # Update widget geometry properties to accurately fetch reqheight
                        popup.update_idletasks()
                        
                        # Compute pixel-perfect height from Listbox's own font rendering
                        req_height = lb.winfo_reqheight()
                        if req_height > 10:
                            height = req_height + 2  # +2 for list_frame (padx=1, pady=1)
                        else:
                            height = visible_items * 22 + 4  # Safe fallback if window hasn't mapped
                        
                        root_x = dropdown_btn.winfo_rootx()
                        root_y = dropdown_btn.winfo_rooty()
                        btn_height = dropdown_btn.winfo_height()
                        
                        screen_height = self.winfo_screenheight()
                        if root_y + btn_height + height > screen_height - 50:
                            pos_y = root_y - height
                        else:
                            pos_y = root_y + btn_height
                            
                        popup.geometry(f"{width}x{height}+{root_x}+{pos_y}")
                        popup.deiconify()
                        popup.lift()
                        popup.focus_force()
                        
                        def on_select(event):
                            selection = lb.curselection()
                            if selection:
                                selected_var.set(options_to_show[selection[0]].strip())
                                popup.destroy()
                                dropdown_border.config(bg=COLORS['border'])
                                # Ensure the arrow label stays on top when the button is redrawn
                                arrow_label.lift()
                        
                        def on_motion(event):
                            idx = lb.nearest(event.y)
                            lb.selection_clear(0, tk.END)
                            lb.selection_set(idx)
                            lb.activate(idx)
    
                        lb.bind("<ButtonRelease-1>", on_select)
                        lb.bind("<Motion>", on_motion)
                        lb.bind("<FocusOut>", lambda e: popup.destroy())
                        lb.bind("<Escape>", lambda e: popup.destroy())
                        
                        dropdown_border.config(bg=COLORS['accent_blue'])
                    
                    # Bind click events to both labels and the container
                    def handle_click(e):
                        # Force remove hover effect when opening menu
                        on_leave(None)
                        show_dropdown_menu()
                    
                    for widget in (dropdown_btn, text_label, arrow_label):
                        widget.bind("<Button-1>", handle_click)
                    
                    # Hover effects
                    def on_enter(e):
                        if popup and popup.winfo_exists() and popup.winfo_viewable():
                            return
                        dropdown_border.config(bg=COLORS['accent_blue'])
                        dropdown_btn.config(bg=COLORS['bg_panel'])
                        text_label.config(bg=COLORS['bg_panel'])
                        arrow_label.config(bg=COLORS['bg_panel'])
                        
                    def on_leave(e):
                        # Prevent flickering when moving between child widgets of the button
                        if e and e.widget != dropdown_btn and e.widget.winfo_containing(e.x_root, e.y_root) in (dropdown_btn, text_label, arrow_label):
                            return
                        dropdown_border.config(bg=COLORS['border'])
                        dropdown_btn.config(bg=COLORS['bg_input'])
                        text_label.config(bg=COLORS['bg_input'])
                        arrow_label.config(bg=COLORS['bg_input'])
                    
                    # Use a dummy popup variable reference so on_enter can check if menu is open
                    popup = None
                    
                    for widget in (dropdown_btn, text_label, arrow_label):
                        widget.bind("<Enter>", on_enter)
                        widget.bind("<Leave>", on_leave)
                else:
                    status_frame = tk.Frame(weight_class_frame, bg=COLORS['bg_panel'], padx=1, pady=1)
                    status_frame.pack(fill=tk.X)
                    status_text = f"● {current_weight_class} (Highest class)" if is_adult_category else f"● {age_group} (Highest class)"
                    status_label = tk.Label(status_frame, text=status_text, bg=COLORS['bg_input'], fg=COLORS['text_muted'], font=FONTS['preview_text'], anchor=tk.W, padx=10, pady=10)
                    status_label.pack(fill=tk.X)
            
            # Valid and Paid checkboxes
            vp_row = tk.Frame(container, bg=COLORS['bg_dark'])
            vp_row.pack(fill=tk.X, pady=(0, 14))

            valid_var = tk.BooleanVar(value=is_valid)
            valid_cb = tk.Checkbutton(
                vp_row, text="Valid", variable=valid_var,
                bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_dark'],
                activeforeground=COLORS['text_primary'],
                font=FONTS['preview_text'], cursor='hand2',
            )
            valid_cb.pack(side=tk.LEFT, padx=(0, 20))

            paid_var = tk.BooleanVar(value=is_paid)
            paid_cb = tk.Checkbutton(
                vp_row, text="Paid", variable=paid_var,
                bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_dark'],
                activeforeground=COLORS['text_primary'],
                font=FONTS['preview_text'], cursor='hand2',
            )
            paid_cb.pack(side=tk.LEFT)

            # Separator
            tk.Frame(container, bg=COLORS['border'], height=1).pack(fill=tk.X, pady=25)
            
            # Buttons
            button_frame = tk.Frame(container, bg=COLORS['bg_dark'])
            button_frame.pack(fill=tk.X)
            
            # Capture initial states for logging reference inside save()
            old_valid = is_valid
            old_paid = is_paid
            
            def save():
                try:
                    # ── Integrations Used ──
                    # 1. QuarantineService.resort_brackets() - Re-validates and re-assigns QUARANTINE participants
                    # 2. ConfigRepository.get_weight_class() - Auto-detects weight class from entered weight
                    # 3. bracket_service.get_age_group(age) - Gets age group WITH FALLBACK for out-of-bounds birth years
                    # 4. ConfigRepository.get_age_group(birth_year) - Config-based lookup (for reference only)
                    # 5. group_preview_screen._move_participant_to_bracket() - Direct bracket movement (non-quarantine)
                    # 6. Inline validation - Name format, weight bounds, age bounds
                    
                    # ── Minimum length / value validation ──
                    errors = []

                    first_name_val = first_entry.get().strip()
                    last_name_val = last_entry.get().strip()
                    weight_raw = weight_entry.get().strip().replace(',', '.')
                    birth_year_raw = birth_year_entry.get().strip()
                    club_val = club_entry.get().strip()
                    association_val = association_entry.get().strip()

                    if not first_name_val:
                        errors.append("Firstname must not be empty.")
                    if first_name_val and first_name_val.endswith('-'):
                        errors.append("Firstname must not end with a hyphen.")
                    if last_name_val and last_name_val.endswith('-'):
                        errors.append("Lastname must not end with a hyphen.")
                    if not weight_raw or float(weight_raw) <= 0:
                        errors.append("Weight must be greater than 0.")
                    if birth_year_raw and (len(birth_year_raw) != 4 or not birth_year_raw.isdigit()):
                        errors.append("Birth Year must be exactly 4 digits.")
                    if errors:
                        messagebox.showwarning("Validation Error", "\n".join(errors), parent=self)
                        return

                    fighter['Firstname'] = first_name_val
                    fighter['Lastname'] = last_name_val
                    fighter['Weight'] = float(weight_raw)
                    fighter['Club'] = club_val
                    fighter['Association'] = association_val
                    fighter['Birthyear'] = int(birth_year_raw) if birth_year_raw else ''
                    fighter['Age'] = fighter['Birthyear']  # TODO Sync Age property for export compatibility
                    fighter['Valid'] = valid_var.get()
                    fighter['Paid'] = paid_var.get()
                    
                    self.parent.logger.debug(f"EDIT_DIALOG: Updated fighter - Valid: {old_valid}→{fighter['Valid']}, Paid: {old_paid}→{fighter['Paid']}, Weight: {weight}→{float(weight_raw)}")
                    if is_quarantine and not old_valid and fighter['Valid']:
                        self.parent.logger.info(f"QUARANTINE ↔ MAIN: Marked QUARANTINE participant as VALID: {first_name_val} {last_name_val}")
                    
                    # Track which bracket to display after save
                    display_bracket_key = bracket_key
                    
                    if is_quarantine:
                        self.parent.logger.debug("QUARANTINE: Using quarantine service for re-sorting")
                        if self.parent.quarantine_service:
                            self.parent.quarantine_service.resort_brackets(
                                self.parent.brackets, 
                                edited_fighter=fighter,
                                group_preview_screen=self.parent
                            )
                        else:
                            self.parent.logger.error("quarantine_service not available")
                            return
                        
                        # Unless QUARANTINE is now empty, stay in the QUARANTINE view
                        if 'QUARANTINE' in self.parent.brackets:
                            display_bracket_key = 'QUARANTINE'
                        else:
                            # If QUARANTINE is completely empty now, find where this fighter ended up
                            display_bracket_key = None
                            for bracket_key_check, bracket_data in self.parent.brackets.items():
                                if bracket_key_check == 'QUARANTINE':
                                    continue
                                for f in bracket_data.get('fighters', []):
                                    if f.get('ID') == fighter.get('ID'):
                                        display_bracket_key = bracket_key_check
                                        break
                                if display_bracket_key:
                                    break
                    
                    elif not is_free_match and not is_young_category:
                        new_weight = float(weight_entry.get().replace(',', '.'))
                        effective_age = age_group
                        effective_weight_class = current_weight_class
                        
                        # Check if age class was upgraded via dropdown
                        if not is_adult_category:
                            new_ac = age_class_var.get()
                            if new_ac != age_group:
                                effective_age = new_ac
                                # Re-map weight class for the new age group
                                new_age_weight_classes = self._get_available_weight_classes(gender, effective_age)
                                if current_weight_class not in new_age_weight_classes:
                                    # Current weight class doesn't exist in new age group
                                    # Try auto-detect from weight first
                                    if self.parent.config_repo and new_weight and new_weight > 0:
                                        detected_weight_class = self.parent.config_repo.get_weight_class(new_weight, gender, effective_age)
                                        if detected_weight_class and detected_weight_class != 'unknown':
                                            effective_weight_class = detected_weight_class
                                        elif new_age_weight_classes:
                                            effective_weight_class = new_age_weight_classes[0]  # Lowest class
                                    elif new_age_weight_classes:
                                        effective_weight_class = new_age_weight_classes[0]  # Lowest class
                        
                        # Check if weight class was manually changed via dropdown (adults)
                        if is_adult_category:
                            new_weight_class = weight_class_var.get()
                            if new_weight_class != current_weight_class:
                                effective_weight_class = new_weight_class
                        
                        # Auto-detect weight class from new weight (overrides manual if weight changed)
                        if self.parent.config_repo and new_weight != weight:
                            detected_weight_class = self.parent.config_repo.get_weight_class(new_weight, gender, effective_age)
                            if detected_weight_class and detected_weight_class != 'unknown':
                                effective_weight_class = detected_weight_class
                        
                        
                        # Move if anything changed
                        if effective_age != age_group or effective_weight_class != current_weight_class:
                            self.parent.logger.debug(f"EDIT_DIALOG: Moving participant: {bracket_key} → {gender}|{effective_age}|{effective_weight_class}")
                            
                            # Direct movement for non-quarantine brackets (no state sync issue)
                            display_bracket_key = self.parent._move_participant_to_bracket(
                                bracket_key, fighter_idx, gender, effective_age, effective_weight_class
                            )
                    
                    self.parent.logger.info(f"EDIT_DIALOG: Save completed for {first_name_val} {last_name_val}, displaying bracket {display_bracket_key}")
                    self.parent.logger.debug("EDIT_DIALOG: Integrations used - QuarantineService, ConfigRepository, movement logic")
                    self.parent._display_participants(display_bracket_key)
                    self.destroy()
                except ValueError:
                    messagebox.showerror("Error", "Invalid weight or age. Please enter numbers.", parent=self)
                except Exception as e:
                    self.parent.logger.error(f"Save error: {e}")
            
            btn_save = tk.Button(button_frame, text="SAVE CHANGES", command=save, bg=COLORS['accent_green'], fg=COLORS['text_primary'], font=FONTS['heading_sm'], bd=0, relief=tk.FLAT, padx=25, pady=12, cursor='hand2')
            btn_save.pack(side=tk.RIGHT)
            
            btn_cancel = tk.Button(button_frame, text="CANCEL", command=self.destroy, bg=COLORS['bg_panel'], fg=COLORS['text_secondary'], font=FONTS['heading_sm'], bd=0, relief=tk.FLAT, padx=25, pady=12, cursor='hand2')
            btn_cancel.pack(side=tk.RIGHT, padx=10)
            
        except Exception as e:
            self.parent.logger.error(f"EDIT_DIALOG: Fatal error - {e}", exc_info=True)
