# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import uuid
import datetime
import traceback
import tkinter as tk
from tkinter import messagebox

import sys
import os
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)
from utils.logging import get_logger, DEBUG_VERBOSE  # noqa: E402
from utils.helpers import normalize_gender  # noqa: E402
from backend.services.bracket_service import get_age_group as get_age_group_with_fallback  # noqa: E402
from backend.services.bracket_service import validate_age_from_birthyear  # noqa: E402

from ..styles import COLORS, FONTS  # noqa: E402
from ._edit_participant_ui import _UIBuilderMixin  # noqa: E402

logger = get_logger('edit_participant_dialog', debug_verbose=DEBUG_VERBOSE)

NAME_PATTERN = re.compile(r'^[A-Za-zÄÖÜäöüß\- ]*$')
MAX_WEIGHT_LENGTH = 8
MAX_BIRTHYEAR_LENGTH = 4
HINT_NAME = "Nur Buchstaben und -"
HINT_WEIGHT = "Nur Ziffern, z.B. 52.3500 oder 52,3"
HINT_BIRTHYEAR = "Genau 4 Ziffern"

class Edit_Participants(_UIBuilderMixin, tk.Toplevel):
    def __init__(self, parent, bracket_key, fighter_idx):
        # We need parent.master as the master for Toplevel so it stays within the app context
        super().__init__(parent.master)
        self.logger = logger
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
        
        # Initialize participant state
        if not self._init_participant_data():
            self.destroy()
            return
            
        self._register_validators()
        self._build_ui()

    def _init_participant_data(self):
        self.is_quarantine = self.bracket_key.startswith('QUARANTINE_')
        self.logger.debug(f"Opening dialog for bracket={self.bracket_key}, fighter_idx={self.fighter_idx}, is_quarantine={self.is_quarantine}")
        
        fighters = self.parent.brackets.get(self.bracket_key, {}).get('fighters', [])
        if not (0 <= self.fighter_idx < len(fighters)):
            self.logger.error(f"Invalid fighter_idx {self.fighter_idx} for bracket {self.bracket_key}")
            return False
            
        self.fighter = fighters[self.fighter_idx]
        self.original_fighter = self.fighter.copy()
        self.logger.debug(f"Editing {self.fighter.get('Firstname', '')} {self.fighter.get('Lastname', '')} (ID: {self.fighter.get('ID', '?')})")
        
        gender, age_group, current_weight_class = self.parent._parse_bracket_key(self.bracket_key)
        self.gender = gender if gender else ""
        self.age_group = age_group if age_group else ""
        self.current_weight_class = current_weight_class if current_weight_class else ""
        
        if not self.gender and self.fighter.get('Gender'):
            g = str(self.fighter.get('Gender')).strip().lower()
            if g:
                self.gender = g[0]
                self.logger.debug(f"Using fighter's Gender field: {self.gender}")
                
        self.first_name = self.fighter.get('Firstname', self.fighter.get('name', ''))
        self.last_name = self.fighter.get('Lastname', '')
        self.weight = self.fighter.get('Weight', self.fighter.get('weight', ''))
        self.club = self.fighter.get('Club', self.fighter.get('Verein', self.fighter.get('verein', self.fighter.get('club', ''))))
        self.association = self.fighter.get('Association', '')
        self.birth_year = self.fighter.get('Birthyear', self.fighter.get('BirthYear', self.fighter.get('birthyear', self.fighter.get('age', ''))))
        self.is_valid = self.fighter.get('Valid', True)
        self.is_paid = self.fighter.get('Paid', False)
        self.old_valid = self.is_valid
        self.old_paid = self.is_paid
        
        if not self.age_group and self.birth_year:
            try:
                birth_year_int = int(self.birth_year) if isinstance(self.birth_year, str) else self.birth_year
                current_year = datetime.datetime.now().year
                calculated_age = current_year - birth_year_int
                fallback_age_group = get_age_group_with_fallback(calculated_age)
                if fallback_age_group:
                    self.age_group = fallback_age_group
            except (ValueError, TypeError, Exception):
                pass
                
        if isinstance(self.weight, (int, float)):
            self.weight_str = f"{self.weight:.4f}".rstrip('0')
            if self.weight_str.endswith('.'):
                self.weight_str += '0'
        else:
            self.weight_str = str(self.weight)
            
        self.available_weight_classes = self._get_available_weight_classes(self.gender, self.age_group)
        
        self._group_tolerance = 0.0
        if hasattr(self.parent, 'tolerances') and self.gender and self.age_group:
            self._group_tolerance = self.parent.tolerances.get((self.gender, self.age_group), 0.0)
            
        self.is_free_match = str(self.bracket_key).startswith("FM |")
        self.is_young_category = self.age_group in ('U9', 'U11') or str(self.bracket_key).strip() in ('U9', 'U11')
        self.is_adult_category = self.age_group == "18+"
        
        # Initialize Doublestart status based on birth year and config
        self.has_doppelstart = False
        self.base_age_group = None
        if self.parent.config_repo and self.birth_year:
            try:
                birth_year_int = int(float(self.birth_year))
                
                # Check eligibility
                eligible_groups = self.parent.config_repo.get_all_eligible_age_groups(birth_year_int)
                if len(eligible_groups) > 1:
                    self.has_doppelstart = True
                
                # Calculate base age group
                event_year = self.parent.config_repo.get_event_year() if self.parent.config_repo else datetime.datetime.now().year
                if not event_year:
                    event_year = datetime.datetime.now().year
                calc_age = event_year - birth_year_int
                from backend.services.bracket_service import get_age_group as get_age_group_service
                self.base_age_group = get_age_group_service(calc_age, event_year)
            except (ValueError, TypeError, Exception):
                pass
                
        self.already_upgraded = False
        if self.has_doppelstart and self.base_age_group and self.age_group == self.base_age_group:
            my_full   = (f"{self.fighter.get('Firstname','')} {self.fighter.get('Lastname','')}".strip() or self.fighter.get('Name','')).strip()
            my_club   = (self.fighter.get('Verein') or self.fighter.get('Club') or "").strip()
            my_birth  = str(self.birth_year).strip()
            my_norm_g = normalize_gender(self.gender)
            
            AGE_CLASS_ORDER = ['U9', 'U11', 'U13', 'U15', 'U18', '18+']
            try:
                base_idx = AGE_CLASS_ORDER.index(self.base_age_group)
                for bk, bd in self.parent.brackets.items():
                    g, ag, wc = self.parent._parse_bracket_key(bk)
                    if g and normalize_gender(g) == my_norm_g and ag in AGE_CLASS_ORDER and AGE_CLASS_ORDER.index(ag) > base_idx:
                        for f in bd.get('fighters', []):
                            f_f     = (f"{f.get('Firstname','')} {f.get('Lastname','')}".strip() or f.get('Name','')).strip()
                            f_club  = (f.get('Verein') or f.get('Club') or "").strip()
                            f_birth = str(f.get('Birthyear', f.get('BirthYear', f.get('Age', "")))).strip()
                            
                            # Match by Name + Club + Birthyear
                            if f_f == my_full and f_club == my_club and f_birth == my_birth:
                                self.already_upgraded = True
                                break
                    if self.already_upgraded:
                        break
            except ValueError:
                pass
        
        self.logger.debug(f"Doublestart status based on config (birth_year={self.birth_year}) -> has_doppelstart={self.has_doppelstart}, already_upgraded={self.already_upgraded}")
        
        # Initialize UI variables
        self.target_is_copy = False
        self.weight_class_var = tk.StringVar(value=self.current_weight_class)
        self.age_class_var = tk.StringVar(value=self.age_group)
        self.dropdown_enabled = [True]
        self.dropdown_info_label = None
        self.popup_ref = [None]
        self.options_to_show = []
        self.selected_var = None
        
        return True

    def _register_validators(self):
        self.validation_command_name = (self.register(self._validate_name), '%d', '%P')
        self.validation_command_weight = (self.register(self._validate_weight), '%d', '%P')
        self.validation_command_birthyear = (self.register(self._validate_birthyear), '%d', '%P')

    # --- UI Interactions & Events ---
    
    def _focus_window(self, e):
        widget = e.widget
        if isinstance(widget, (tk.Entry, tk.Button, tk.Checkbutton, tk.Listbox)):
            return
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

    def _on_weight_changed(self, e=None, show_popup=True):
        if self.weight_popup_timer[0]:
            self.after_cancel(self.weight_popup_timer[0])
        self.weight_popup.place_forget()
            
        weight_str_input = self.weight_entry.get().strip().replace(',', '.')
        birth_year_str = self.birth_year_entry.get().strip()
        
        if weight_str_input and self.parent.config_repo:
            try:
                weight_val = float(weight_str_input)
                if weight_val > 0:
                    effective_age_group = self.age_group
                    if birth_year_str and len(birth_year_str) == 4 and birth_year_str.isdigit():
                        try:
                            birth_year_int = int(birth_year_str)
                            calculated_age = datetime.datetime.now().year - birth_year_int
                            fallback_ag = get_age_group_with_fallback(calculated_age)
                            if fallback_ag:
                                effective_age_group = fallback_ag
                        except Exception:
                            pass
                    
                    detected = self.parent.config_repo.get_weight_class(weight_val - self._group_tolerance, self.gender, effective_age_group)
                    if detected and detected != 'unknown':
                        self.logger.debug(f"Weight class detected: {detected} (weight={weight_val:.3f}, age_group={effective_age_group}, gender={self.gender})")
                        if show_popup:
                            self.weight_popup.config(text=f"Auto-class: {detected}")
                            self.weight_popup.place(rely=1.0, relx=0.0, y=-22) 
                            self.weight_popup.lift()
                            self.weight_popup_timer[0] = self.after(2500, self.weight_popup.place_forget)
                        
                        if self.is_adult_category and not self.is_quarantine:
                            # Use '18+' as the reference for weight classes even if birthyear says U18
                            target_ag = '18+'
                            effective_weight_classes = self._get_available_weight_classes(self.gender, target_ag)
                            
                            detected_natural_key = self._get_weight_key(detected)
                            allowed_weight_classes = [detected]
                            heavier = [wc for wc in effective_weight_classes if self._get_weight_key(wc) > detected_natural_key]
                            if heavier:
                                allowed_weight_classes.append(heavier[0])
                            
                            # Add Undo Upgrade if applicable
                            base = getattr(self, 'base_age_group', target_ag)
                            if base and target_ag != base:
                                allowed_weight_classes.append(f"{base} (Undo Upgrade)")
                                
                            allowed_weight_classes.sort(key=lambda wc: self._get_weight_key(wc.replace(" (Undo Upgrade)", "")))
                            self.options_to_show.clear()
                            self.options_to_show.extend(allowed_weight_classes)
                            
                            # Automatically snap to the detected class
                            self.weight_class_var.set(detected)
            except Exception:
                pass

    def _on_birth_year_changed(self, e=None, show_popup=True):
        if self.age_popup_timer[0]:
            self.after_cancel(self.age_popup_timer[0])
        self.age_popup.place_forget()
        
        birth_year_str = self.birth_year_entry.get().strip()
        if birth_year_str and len(birth_year_str) == 4 and birth_year_str.isdigit():
            try:
                birth_year_int = int(birth_year_str)
                auto_age_group, calculated_age, is_valid, rejection_reason = validate_age_from_birthyear(birth_year_int)
                self.logger.debug(f"Birth year {birth_year_int} → age_group={auto_age_group}, age={calculated_age}, valid={is_valid}")

                if auto_age_group:
                    if show_popup:
                        self.age_popup.config(text=f"Auto-class: {auto_age_group}")
                        self.age_popup.place(rely=1.0, relx=0.0, y=-22)
                        self.age_popup.lift()
                        self.age_popup_timer[0] = self.after(2500, self.age_popup.place_forget)
                    
                    if not self.is_free_match and not self.is_young_category and not self.is_quarantine:
                        if auto_age_group in ('U9', 'U11'):
                            self.dropdown_enabled[0] = False
                            self.dropdown_btn.config(cursor='')
                            self.text_label.config(fg=COLORS['text_muted'])
                            self.arrow_label.config(fg=COLORS['text_muted'])
                            self.age_class_var.set("U9/U11 (No upgrade)")
                            if self.dropdown_info_label:
                                self.dropdown_info_label.config(text=f"→ Group {auto_age_group} has no manual upgrades.")
                                self.dropdown_info_label.pack(anchor=tk.W, pady=(4, 0))
                        elif self.is_adult_category:
                            # If they are in the adult category, stay enabled regardless of whether 
                            # the birth year detected U18 etc (since they are playing as adult).
                            self.dropdown_enabled[0] = True
                            if self.dropdown_info_label:
                                self.dropdown_info_label.pack_forget()
                            self.dropdown_btn.config(cursor='hand2')
                            self.text_label.config(fg=COLORS['text_primary'])
                            self.arrow_label.config(fg=COLORS['accent_blue'])
                        else:
                            if auto_age_group == '18+':
                                self.dropdown_enabled[0] = False
                                self.dropdown_btn.config(cursor='')
                                self.text_label.config(fg=COLORS['text_muted'])
                                self.arrow_label.config(fg=COLORS['text_muted'])
                                self.age_class_var.set("N/A")
                                if self.dropdown_info_label:
                                    self.dropdown_info_label.config(text="→ Person is now 18+ (Please save and reopen to assign weight class)")
                                    self.dropdown_info_label.pack(anchor=tk.W, pady=(4, 0))
                            else:
                                self.dropdown_enabled[0] = True
                                if self.dropdown_info_label:
                                    self.dropdown_info_label.pack_forget()
                                self.dropdown_btn.config(cursor='hand2')
                                self.text_label.config(fg=COLORS['text_primary'])
                                self.arrow_label.config(fg=COLORS['accent_blue'])
                                
                                # Automatically update the age class dropdown if it's a valid option
                                if auto_age_group in self.options_to_show:
                                    self.age_class_var.set(auto_age_group)
                                elif f"{auto_age_group} (Undo Upgrade)" in self.options_to_show:
                                    self.age_class_var.set(f"{auto_age_group} (Undo Upgrade)")
                    
                    self._on_weight_changed(show_popup=False)
            except Exception:
                pass

    # --- Dropdown Logic ---
    
    def _handle_dropdown_click(self, e):
        if not self.dropdown_enabled[0]:
            return
        self._on_dropdown_leave(None)
        self._show_dropdown_menu()

    def _on_dropdown_enter(self, e):
        if not self.dropdown_enabled[0]:
            return
        p = self.popup_ref[0]
        if p and p.winfo_exists() and p.winfo_viewable():
            return
        self.dropdown_border.config(bg=COLORS['accent_blue'])
        self.dropdown_btn.config(bg=COLORS['bg_panel'])
        self.text_label.config(bg=COLORS['bg_panel'])
        self.arrow_label.config(bg=COLORS['bg_panel'])
        
    def _on_dropdown_leave(self, e):
        if e and e.widget != self.dropdown_btn and e.widget.winfo_containing(e.x_root, e.y_root) in (self.dropdown_btn, self.text_label, self.arrow_label):
            return
        p = self.popup_ref[0]
        if p and p.winfo_exists() and p.winfo_viewable():
            return
        self.dropdown_border.config(bg=COLORS['border'])
        self.dropdown_btn.config(bg=COLORS['bg_input'])
        self.text_label.config(bg=COLORS['bg_input'])
        self.arrow_label.config(bg=COLORS['bg_input'])

    def _show_dropdown_menu(self):
        popup = tk.Toplevel(self)
        self.popup_ref[0] = popup
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(bg=COLORS['border'])
        
        list_frame = tk.Frame(popup, bg=COLORS['bg_input'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        scrollbar = tk.Scrollbar(list_frame, width=10) if len(self.options_to_show) > 8 else None
        if scrollbar:
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        lb = tk.Listbox(list_frame, bg=COLORS['bg_input'], fg=COLORS['text_primary'], font=FONTS['preview_text'], 
                        bd=0, highlightthickness=0, selectbackground=COLORS['accent_blue'], selectforeground=COLORS['text_primary'], 
                        activestyle='none', yscrollcommand=scrollbar.set if scrollbar else None, cursor='hand2')
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        if scrollbar:
            scrollbar.config(command=lb.yview)
        
        for opt in self.options_to_show:
            lb.insert(tk.END, f"  {opt}")
            if opt == self.selected_var.get():
                lb.selection_set(lb.size()-1)
                lb.see(lb.size()-1)
        
        self.update_idletasks()
        width = self.dropdown_btn.winfo_width()
        visible_items = min(len(self.options_to_show), 8)
        lb.config(height=visible_items)
        popup.update_idletasks()
        
        req_height = lb.winfo_reqheight()
        height = req_height + 2 if req_height > 10 else visible_items * 22 + 4
        
        root_x = self.dropdown_btn.winfo_rootx()
        root_y = self.dropdown_btn.winfo_rooty()
        btn_height = self.dropdown_btn.winfo_height()
        
        pos_y = root_y - height if root_y + btn_height + height > self.winfo_screenheight() - 50 else root_y + btn_height
        popup.geometry(f"{width}x{height}+{root_x}+{pos_y}")
        popup.deiconify()
        popup.lift()
        popup.focus_force()
        
        def close_popup(e=None):
            if self.popup_ref[0]:
                self.popup_ref[0].destroy()
                self.popup_ref[0] = None
            self._on_dropdown_leave(None)

        def on_select(event):
            selection = lb.curselection()
            if selection:
                self.selected_var.set(self.options_to_show[selection[0]].strip())
                close_popup()
        
        def on_motion(event):
            idx = lb.nearest(event.y)
            lb.selection_clear(0, tk.END)
            lb.selection_set(idx)
            lb.activate(idx)

        lb.bind("<ButtonRelease-1>", on_select)
        lb.bind("<Motion>", on_motion)
        lb.bind("<FocusOut>", close_popup)
        lb.bind("<Escape>", close_popup)
        self.dropdown_border.config(bg=COLORS['accent_blue'])

    # --- Validation ---
    
    def _validate_name(self, action, value_if_allowed):
        if action == '0':
            return True
        if not NAME_PATTERN.match(value_if_allowed):
            return False
        if '--' in value_if_allowed or value_if_allowed.startswith('-'):
            return False
        return True

    def _validate_weight(self, action, value_if_allowed):
        if action == '0':
            return True
        if len(value_if_allowed) > MAX_WEIGHT_LENGTH:
            return False
        normalized = value_if_allowed.replace(',', '.')
        if normalized.count('.') > 1:
            return False
        parts = normalized.split('.')
        if len(parts[0]) > 3:
            return False
        if not all(c.isdigit() for c in parts[0] if c != ''):
            return False
        if len(parts) == 2:
            if len(parts[1]) > 4:
                return False
            if parts[1] and not parts[1].isdigit():
                return False
        for c in value_if_allowed:
            if c not in '0123456789.,':
                return False
        return True

    def _validate_birthyear(self, action, value_if_allowed):
        if action == '0':
            return True
        if len(value_if_allowed) > MAX_BIRTHYEAR_LENGTH:
            return False
        return value_if_allowed.isdigit()

    def _create_field(self, parent_frame, label_text, entry_var=None, is_readonly=False, validation_command=None, hint_text=None):
        field_frame = tk.Frame(parent_frame, bg=COLORS['bg_dark'])
        field_frame.pack(fill=tk.X, pady=(0, 18))
        
        tk.Label(field_frame, text=label_text.upper(), bg=COLORS['bg_dark'], fg=COLORS['accent_blue'], 
                 font=FONTS['preview_label']).pack(anchor=tk.W, pady=(0, 6))
        
        border_frame = tk.Frame(field_frame, bg=COLORS['border'], padx=1, pady=1)
        border_frame.pack(fill=tk.X)

        _flash_timer_id = [None]
        def _on_invalid():
            border_frame.config(bg=COLORS['accent_red'])
            if _flash_timer_id[0]:
                self.after_cancel(_flash_timer_id[0])
            _flash_timer_id[0] = self.after(350, lambda: border_frame.config(bg=COLORS['accent_blue'] if entry == self.focus_get() else COLORS['border']))

        invalid_input_command = (self.register(lambda: _on_invalid() or False),)
        
        entry_kwargs = dict(bg=COLORS['bg_input'], fg=COLORS['text_primary'], font=FONTS['preview_text'], bd=0, relief=tk.FLAT)
        if validation_command:
            entry_kwargs['validate'] = 'key'
            entry_kwargs['validatecommand'] = validation_command
            entry_kwargs['invalidcommand'] = invalid_input_command

        entry = tk.Entry(border_frame, **entry_kwargs)
        entry.pack(fill=tk.X, ipady=10, ipadx=10)
        
        if is_readonly:
            entry.config(state=tk.DISABLED, fg=COLORS['text_muted'])
            border_frame.config(bg=COLORS['bg_panel'])

        if hint_text:
            tk.Label(field_frame, text=hint_text, bg=COLORS['bg_dark'], fg=COLORS['text_muted'], 
                     font=FONTS['preview_hint']).pack(anchor=tk.W, pady=(3, 0))

        if not hasattr(self, '_all_borders'):
            self._all_borders = []
        self._all_borders.append(border_frame)

        def on_focus_in(e, b=border_frame):
            if not is_readonly:
                for ob in getattr(self, '_all_borders', []):
                    ob.config(bg=COLORS['border'])
                b.config(bg=COLORS['accent_blue'])

        def on_focus_out(e, b=border_frame):
            if not is_readonly:
                b.config(bg=COLORS['border'])
        
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return entry

    def _insert_value(self, entry, value):
        if value:
            entry.insert(0, value)

    # --- Save orchestration ---

    def _save_changes(self):
        try:
            self.logger.debug(f"Saving changes: bracket={self.bracket_key}, idx={self.fighter_idx}, is_quarantine={self.is_quarantine}")
            values = self._collect_form_values()

            errors = self._validate(values)
            if errors:
                self.logger.debug(f"Validation failed: {errors}")
                messagebox.showwarning("Validation Error", "\n".join(errors), parent=self)
                return

            self._apply_to_fighter(values)

            display_key, target_key = self._resolve_routing()
            if display_key is False:  # abort sentinel: no quarantine_service available
                return

            self._finalize(values, display_key, target_key)
        except ValueError:
            messagebox.showerror("Error", "Invalid weight or age. Please enter numbers.", parent=self)
        except Exception:
            self.logger.error(f"Unexpected error in _save_changes:\n{traceback.format_exc()}")

    def _collect_form_values(self) -> dict:
        return {
            'first_name':    self.first_entry.get().strip(),
            'last_name':     self.last_entry.get().strip(),
            'weight_raw':    self.weight_entry.get().strip().replace(',', '.'),
            'birth_year_raw': self.birth_year_entry.get().strip(),
            'club':          self.club_entry.get().strip(),
            'association':   self.association_entry.get().strip(),
        }

    def _validate(self, values: dict) -> list:
        errors = []
        first_name    = values['first_name']
        last_name     = values['last_name']
        weight_raw    = values['weight_raw']
        birth_year_raw = values['birth_year_raw']

        if not first_name:
            errors.append("Firstname must not be empty.")
        if first_name and first_name.endswith('-'):
            errors.append("Firstname must not end with a hyphen.")
        if last_name and last_name.endswith('-'):
            errors.append("Lastname must not end with a hyphen.")
        if not weight_raw or float(weight_raw) <= 0:
            errors.append("Weight must be greater than 0.")
        if birth_year_raw and (len(birth_year_raw) != 4 or not birth_year_raw.isdigit()):
            errors.append("Birth Year must be exactly 4 digits.")
        elif birth_year_raw and birth_year_raw.isdigit():
            _, _, age_is_valid, age_rejection_reason = validate_age_from_birthyear(birth_year_raw)
            if not age_is_valid:
                errors.append(f"Invalid Age: {age_rejection_reason}")
        return errors

    def _apply_to_fighter(self, values: dict):
        birth_year_raw = values['birth_year_raw']
        self.fighter['Firstname']  = values['first_name']
        self.fighter['Lastname']   = values['last_name']
        self.fighter['Weight']     = float(values['weight_raw'])
        self.fighter['Club']       = values['club']
        self.fighter['Association'] = values['association']
        self.fighter['Birthyear']  = int(birth_year_raw) if birth_year_raw else ''
        self.fighter['Age']        = self.fighter['Birthyear']
        self.fighter['Valid']      = self.valid_var.get()
        self.fighter['Paid']       = self.paid_var.get()

    def _resolve_routing(self) -> tuple:
        """Route the save to the correct handler and return (display_key, target_key).

        Returns (False, False) as a sentinel when the save must be silently aborted.
        """
        issues = []
        if self.parent.quarantine_service:
            issues = self.parent.quarantine_service.evaluate_participant(self.fighter)

        if self.is_quarantine:
            self.logger.debug("Save path: quarantine participant → re-sorting")
            return self._handle_quarantine_resort()
        elif issues:
            self.logger.debug(f"Save path: participant now quarantined (issues={issues})")
            return self._handle_move_to_quarantine()
        elif not self.is_free_match:
            self.logger.debug("Save path: normal participant — checking for movement")
            return self._handle_normal_routing()
        return self.bracket_key, None

    def _handle_quarantine_resort(self) -> tuple:
        """Participant was in quarantine — re-sort them into the correct bracket."""
        if not self.parent.quarantine_service:
            return False, False  # abort: no service to perform the re-sort

        tracking_id = str(uuid.uuid4())
        self.fighter['_tracking_id'] = tracking_id
        self.parent.quarantine_service.resort_brackets(
            self.parent.brackets, edited_fighter=self.fighter, group_preview_screen=self.parent,
            db_service=self.parent.db_service
        )

        target_key = None
        for bk, bd in self.parent.brackets.items():
            for f in bd.get('fighters', []):
                if f.get('_tracking_id') == tracking_id:
                    target_key = bk
                    break
            if target_key:
                break

        for bd in self.parent.brackets.values():
            for f in bd.get('fighters', []):
                f.pop('_tracking_id', None)

        self.logger.debug(f"Re-sort result: target_key={target_key}")

        still_in_quarantine = (
            self.bracket_key in self.parent.brackets
            and self.parent.brackets[self.bracket_key].get('fighters', [])
        )
        display_key = self.bracket_key if still_in_quarantine else target_key
        return display_key, target_key

    def _handle_move_to_quarantine(self) -> tuple:
        """Participant was normal — they now fail validation and must be quarantined."""
        old_fighters = self.parent.brackets[self.bracket_key].get('fighters', [])
        if not (0 <= self.fighter_idx < len(old_fighters)):
            return None, None

        moved_fighter = old_fighters.pop(self.fighter_idx)
        self.parent.brackets[self.bracket_key]['bracket'] = []

        # Explicitly set rejection_reason so create_quarantine_bracket places the
        # fighter in the correct QUARANTINE_* bucket instead of falling back to 'unknown'.
        # self.fighter is already updated by _apply_to_fighter at this point.
        if not moved_fighter.get('Paid', False):
            moved_fighter['rejection_reason'] = 'unpaid'
        elif not moved_fighter.get('Valid', True):
            moved_fighter['rejection_reason'] = 'marked_invalid'
        else:
            birthyear = moved_fighter.get('Birthyear') or moved_fighter.get('Age')
            _, _, _, reason = validate_age_from_birthyear(birthyear)
            moved_fighter['rejection_reason'] = reason

        display_key = None
        if self.parent.quarantine_service:
            quarantine_result = self.parent.quarantine_service.create_quarantine_bracket(
                self.parent.brackets, [moved_fighter]
            )
            if quarantine_result:
                first_reason = list(quarantine_result.keys())[0]
                display_key = f'QUARANTINE_{first_reason}'

        self.parent._populate_group_list()
        return display_key, None

    def _handle_normal_routing(self) -> tuple:
        """Normal participant — detect if age/weight class changed and move if needed."""
        new_weight = float(self.weight_entry.get().replace(',', '.'))
        effective_age, effective_weight_class = self._resolve_effective_class(new_weight)

        if effective_age == self.age_group and effective_weight_class == self.current_weight_class:
            return self.bracket_key, None

        AGE_CLASS_ORDER = ['U9', 'U11', 'U13', 'U15', 'U18', '18+']
        try:
            old_idx = AGE_CLASS_ORDER.index(self.age_group)
            new_idx = AGE_CLASS_ORDER.index(effective_age)
        except ValueError:
            old_idx = new_idx = 0

        # Logic for duplication (Copy) or Move
        if effective_age != self.age_group:
            if new_idx > old_idx:
                # Upgrade path
                if not self.is_adult_category and self.has_doppelstart:
                    self.logger.debug(f"Upgrading participant: age {self.age_group}→{effective_age}")
                    new_bracket_key = self.parent._copy_participant_to_bracket(
                        self.bracket_key, self.fighter, self.gender, effective_age, effective_weight_class
                    )
                    self.target_is_copy = True
                    return self.bracket_key, new_bracket_key
            elif new_idx < old_idx:
                # Downgrade path (Undo)
                # If they are currently in a higher class, we perform an Undo.
                # If they were a 'doppel' start, they are already in the target; 
                # if they were a 'höher' start, they are ONLY here and must be MOVED back.
                target_base_bk = f"{self.gender} | {effective_age} | {effective_weight_class}"
                if effective_age in ('U9', 'U11'):
                    target_base_bk = effective_age
                
                # Check if they exist in any lower bracket already
                exists_in_base = False
                my_full = (f"{self.fighter.get('Firstname','')} {self.fighter.get('Lastname','')}".strip() or self.fighter.get('Name','')).strip()
                my_club = (self.fighter.get('Verein') or self.fighter.get('Club') or "").strip()
                my_birth = str(self.fighter.get('Birthyear', self.fighter.get('BirthYear', ''))).strip()
                
                if target_base_bk in self.parent.brackets:
                    for f in self.parent.brackets[target_base_bk].get('fighters', []):
                        f_f = (f"{f.get('Firstname','')} {f.get('Lastname','')}".strip() or f.get('Name','')).strip()
                        f_club = (f.get('Verein') or f.get('Club') or "").strip()
                        f_birth = str(f.get('Birthyear', f.get('BirthYear', ''))).strip()
                        if f_f == my_full and f_club == my_club and f_birth == my_birth:
                            exists_in_base = True
                            break
                
                if exists_in_base:
                    self.logger.debug(f"Undoing upgrade (Delete): age {self.age_group}→{effective_age}")
                    self.parent._remove_participant_from_bracket(self.bracket_key, self.fighter_idx)
                    if getattr(self.parent, 'db_service', None):
                        self.parent.db_service.remove_participant_from_group(self.fighter, self.bracket_key)
                else:
                    self.logger.debug(f"Undoing upgrade (Move back): age {self.age_group}→{effective_age}")
                    # Move also handles the UI removal and DB update
                    self.parent._move_participant_to_bracket(self.bracket_key, self.fighter_idx, self.gender, effective_age, effective_weight_class)

                # Check if any fighters are left in the current bracket
                remaining = 0
                if self.bracket_key in self.parent.brackets:
                    remaining = len(self.parent.brackets[self.bracket_key].get('fighters', []))
                
                if remaining > 0:
                    return self.bracket_key, target_base_bk
                else:
                    return target_base_bk, target_base_bk

        self.logger.debug(f"Moving participant: age {self.age_group}→{effective_age}, weight_class {self.current_weight_class}→{effective_weight_class}")
        new_bracket_key = self.parent._move_participant_to_bracket(
            self.bracket_key, self.fighter_idx, self.gender, effective_age, effective_weight_class
        )
        self.logger.debug(f"Participant moved to bracket: {new_bracket_key}")

        old_bracket = self.parent.brackets.get(self.bracket_key, {})
        display_key = self.bracket_key if old_bracket.get('fighters') else new_bracket_key
        return display_key, new_bracket_key

    def _resolve_effective_class(self, new_weight: float) -> tuple:
        """Determine the effective (age_group, weight_class) after all edits.

        Checks in priority order:
          1. Manual age class upgrade via dropdown (non-adult)
          2. Manual weight class override via dropdown (adult)
          3. Auto-detect weight class from changed weight
          4. Birth year changed → re-detect age group → re-detect weight class

        Returns:
            (effective_age, effective_weight_class)
        """
        effective_age         = self.age_group
        effective_weight_class = self.current_weight_class

        # 1. Birth year changed → re-detect age group → re-detect weight class for new age
        birth_year_val = self.birth_year_entry.get().strip()
        if birth_year_val and len(birth_year_val) == 4 and birth_year_val.isdigit():
            calculated_age     = datetime.datetime.now().year - int(birth_year_val)
            detected_age_group = get_age_group_with_fallback(calculated_age)
            if detected_age_group and detected_age_group != effective_age:
                effective_age = detected_age_group
        
        # ── Fresh Start Policy: Force weight class re-detection if moving between category systems ──
        # If moving FROM U9/U11 (no weight class) TO U13+ (fixed weight class), 
        # we MUST find a valid weight class for the target age group.
        needs_fixed_wc = (effective_age not in ('U9', 'U11', None))
        currently_has_no_wc = (effective_weight_class in ('', 'no-class', None))
        
        if needs_fixed_wc and currently_has_no_wc:
            if self.parent.config_repo and new_weight > 0:
                detected_wc = self.parent.config_repo.get_weight_class(
                    new_weight - self._group_tolerance, self.gender, effective_age
                )
                if detected_wc and detected_wc != 'unknown':
                    effective_weight_class = detected_wc
                else:
                    # Last resort fallback: find any valid weight class for this category
                    wcs = self._get_available_weight_classes(self.gender, effective_age)
                    if wcs:
                        effective_weight_class = wcs[0]

        # 2. Non-adult: user manually upgraded age class via dropdown (Manual override)
        # FRESH START POLICY: If birthyear was changed, we ignore any manual dropdown override
        # and strictly follow the age group detected from the new birth year.
        old_birth_start = str(self.original_fighter.get('Birthyear', self.original_fighter.get('Age', ''))).strip()
        birthyear_changed_locally = (birth_year_val != old_birth_start)

        if not birthyear_changed_locally and not (self.age_group == '18+' and effective_age == '18+'):
            new_ac = self.age_class_var.get()
            if new_ac.endswith(" (Undo Upgrade)"):
                new_ac = new_ac.replace(" (Undo Upgrade)", "")
            if new_ac != effective_age and new_ac != "": # If dropdown selection differs from detected/current
                effective_age = new_ac
                new_age_wcs = self._get_available_weight_classes(self.gender, effective_age)
                if self.current_weight_class not in new_age_wcs:
                    if self.parent.config_repo and new_weight > 0:
                        detected = self.parent.config_repo.get_weight_class(
                            new_weight - self._group_tolerance, self.gender, effective_age
                        )
                        effective_weight_class = (
                            detected if detected and detected != 'unknown'
                            else (new_age_wcs[0] if new_age_wcs else effective_weight_class)
                        )
                    elif new_age_wcs:
                        effective_weight_class = new_age_wcs[0]

        # 3. Adult: user manually selected a different weight class via dropdown
        manual_override = False
        if effective_age == "18+":
            dropdown_selection = self.weight_class_var.get()
            
            # SPECIAL: Handle "Undo Upgrade" selected from weight class dropdown
            if dropdown_selection.endswith(" (Undo Upgrade)"):
                undo_age = dropdown_selection.replace(" (Undo Upgrade)", "")
                effective_age = undo_age
                # Detect natural weight class for the restored age group
                if self.parent.config_repo and new_weight > 0:
                    detected = self.parent.config_repo.get_weight_class(
                        new_weight - self._group_tolerance, self.gender, effective_age
                    )
                    if detected and detected != 'unknown':
                        effective_weight_class = detected
                manual_override = True
            else:
                auto_detected = None
                if self.parent.config_repo and new_weight > 0:
                    auto_detected = self.parent.config_repo.get_weight_class(
                        new_weight - self._group_tolerance, self.gender, effective_age
                    )
                if (auto_detected and dropdown_selection != auto_detected) \
                        or dropdown_selection != self.current_weight_class:
                    effective_weight_class = dropdown_selection
                    manual_override = True

        # 4. Auto-detect weight class from changed weight (no manual override)
        if not manual_override and self.parent.config_repo and new_weight != self.weight:
            detected = self.parent.config_repo.get_weight_class(
                new_weight - self._group_tolerance, self.gender, effective_age
            )
            if detected and detected != 'unknown':
                effective_weight_class = detected
        return effective_age, effective_weight_class

    def _get_available_weight_classes(self, gender, age_group):
        """Helper to get weight classes from config repo."""
        if self.parent.config_repo:
            return self.parent.config_repo.get_weight_classes(gender, age_group)
        return []

    def _finalize(self, values: dict, display_key, target_key):
        """Persist to DB, refresh the parent UI, and close the dialog."""
        db_svc = getattr(self.parent, 'db_service', None)
        if db_svc:
            if getattr(self, 'target_is_copy', False):
                # Upgrade/Duplication path:
                # 1. Update the original participant's details (weight, etc. - affects all classes anyway)
                #    using their CURRENT bracket key so it doesn't move.
                db_svc.update_participant(self.fighter, self.bracket_key, self.bracket_key)
                # 2. ADD them to the NEW bracket.
                db_svc.add_participant_to_group(self.fighter, target_key)
            else:
                # Normal move/save path
                db_svc.update_participant(self.fighter, self.bracket_key, target_key or display_key or 'QUARANTINE')

        # ── Fresh start logic for in-memory brackets ──
        old_birth = str(self.original_fighter.get('Birthyear', self.original_fighter.get('Age', ''))).strip()
        new_birth = str(self.fighter.get('Birthyear', '')).strip()
        
        if old_birth != new_birth:
             # Identify current fighter by their unique ID (fallback to Name+Club)
             my_id   = self.original_fighter.get('ID', self.original_fighter.get('id'))
             my_full = (f"{self.original_fighter.get('Firstname','')} {self.original_fighter.get('Lastname','')}".strip() or self.original_fighter.get('Name','')).strip()
             my_club = (self.original_fighter.get('Verein') or self.original_fighter.get('Club') or "").strip()
             
             # Remove from ALL brackets except the new one
             exempt_bk = target_key or display_key
             for bk, bd in list(self.parent.brackets.items()):
                 if bk == exempt_bk: continue
                 # Remove matching fighter from this in-memory list
                 fighters = bd.get('fighters', [])
                 to_remove = []
                 for idx, f in enumerate(fighters):
                     f_id    = f.get('ID', f.get('id'))
                     f_f     = (f"{f.get('Firstname','')} {f.get('Lastname','')}".strip() or f.get('Name','')).strip()
                     f_club  = (f.get('Verein') or f.get('Club') or "").strip()
                     f_birth = str(f.get('Birthyear', f.get('BirthYear', f.get('Age', "")))).strip()
                     
                     matched = False
                     if my_id and f_id:
                         matched = (str(my_id) == str(f_id))
                     else:
                         matched = (f_f == my_full and f_club == my_club and f_birth == old_birth)
                     
                     if matched:
                         to_remove.append(idx)
                 
                 # Perform removals in reverse to keep indices valid
                 for idx in reversed(to_remove):
                     fighters.pop(idx)
                 
                 # CLEANUP: If bracket is now empty, delete it
                 if not fighters and bk not in ('U9', 'U11', 'QUARANTINE'):
                     if bk in self.parent.brackets:
                         del self.parent.brackets[bk]
             
             # Force list refresh to remove empty tabs
             if hasattr(self.parent, '_populate_group_list'):
                 self.parent._populate_group_list()

        self.fighter['Name'] = f"{values['first_name']} {values['last_name']}".strip()
        self.parent._display_participants(display_key)
        if hasattr(self.parent, 'flash_bracket'):
            flash_key = target_key if target_key else display_key
            if flash_key:
                self.parent.flash_bracket(flash_key)
        self.destroy()

    def _get_available_age_classes(self, gender, current_age_group):
        AGE_CLASS_ORDER = ['U9', 'U11', 'U13', 'U15', 'U18', '18+']
        try:
            current_idx = AGE_CLASS_ORDER.index(current_age_group)
            return AGE_CLASS_ORDER[current_idx + 1:]
        except ValueError:
            return []

    @staticmethod
    def _get_weight_key(weight_class_str):
        if weight_class_str == 'no-class':
            return (0, 0)
        num_str = weight_class_str.replace('kg', '').replace('-', '').replace('+', '')
        try:
            num = float(num_str)
        except ValueError:
            return (999, 0)
        return (num, 1 if weight_class_str.startswith('+') else 0)

    def _get_available_weight_classes(self, gender, age_group):
        available_classes = []
        used_fallback = False
        if self.parent.config_repo:
            try:
                gender_norm = normalize_gender(gender)
                df = self.parent.config_repo.weight_classes
                filtered = df[(df['Gender'] == gender_norm) & (df['AgeGroup'] == age_group)]
                available_classes = filtered['Label'].tolist()
            except Exception:
                pass
        if not available_classes:
            used_fallback = True
            for bracket_key in self.parent.brackets.keys():
                parts = [p.strip() for p in bracket_key.split('|')]
                if len(parts) >= 3 and parts[0] == gender and parts[1] == age_group:
                    if parts[2] not in available_classes:
                        available_classes.append(parts[2])
        if used_fallback:
            available_classes.sort(key=self._get_weight_key)
        return available_classes
