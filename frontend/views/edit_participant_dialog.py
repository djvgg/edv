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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.logging import get_logger  # noqa: E402
from backend.services.bracket_service import get_age_group as get_age_group_with_fallback  # noqa: E402
from backend.services.bracket_service import validate_age_from_birthyear  # noqa: E402

from ..styles import COLORS, FONTS

# ===== DEBUG CONFIGURATION =====
DEBUG = True
# ==============================

logger = get_logger('edit_participant_dialog', debug_verbose=DEBUG)

NAME_PATTERN = re.compile(r'^[A-Za-zÄÖÜäöüß\- ]*$')
MAX_WEIGHT_LENGTH = 8
MAX_BIRTHYEAR_LENGTH = 4
HINT_NAME = "Nur Buchstaben und -"
HINT_WEIGHT = "Nur Ziffern, z.B. 52.3500 oder 52,3"
HINT_BIRTHYEAR = "Genau 4 Ziffern"

class Edit_Participants(tk.Toplevel):
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
        
        # Initialize UI variables
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

    def _build_ui(self):
        self._build_header()
        
        self.container = tk.Frame(self, bg=COLORS['bg_dark'])
        self.container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        self.bind('<Button-1>', self._focus_window)
        
        self._build_name_fields()
        self._build_weight_age_fields()
        self._build_club_assoc_fields()
        self._build_class_assignment()
        self._build_status_fields()
        
        tk.Frame(self.container, bg=COLORS['border'], height=1).pack(fill=tk.X, pady=25)
        
        self._build_buttons()

    def _build_header(self):
        header_frame = tk.Frame(self, bg=COLORS['bg_darker'], height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Frame(header_frame, bg=COLORS['accent_blue'], width=5).pack(side=tk.LEFT, fill=tk.Y)
        
        title_label = tk.Label(header_frame, text=f"Participant: {self.first_name} {self.last_name}".strip(), 
                               bg=COLORS['bg_darker'], fg=COLORS['text_primary'], font=FONTS['preview_title'])
        title_label.pack(side=tk.LEFT, padx=20, pady=20)
        
        # Warnings
        if self.is_quarantine and self.parent.quarantine_service:
            qs = self.parent.quarantine_service
            if hasattr(qs, 'evaluate_participant'):
                issues = qs.evaluate_participant(self.fighter)
                if issues:
                    warning_frame = tk.Frame(self, bg=COLORS['accent_orange'])
                    warning_frame.pack(fill=tk.X)
                    warning_text = "⚠️ " + " | ".join(issues)
                    tk.Label(warning_frame, text=warning_text, bg=COLORS['accent_orange'], 
                             fg=COLORS['bg_darker'], font=FONTS['preview_label']).pack(pady=5)

    def _build_name_fields(self):
        name_row = tk.Frame(self.container, bg=COLORS['bg_dark'])
        name_row.pack(fill=tk.X)
        
        first_col = tk.Frame(name_row, bg=COLORS['bg_dark'])
        first_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.first_entry = self._create_field(first_col, "First Name", 
                                              validation_command=self.validation_command_name, hint_text=HINT_NAME)
        self._insert_value(self.first_entry, self.first_name)
        
        last_col = tk.Frame(name_row, bg=COLORS['bg_dark'])
        last_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.last_entry = self._create_field(last_col, "Last Name", 
                                             validation_command=self.validation_command_name, hint_text=HINT_NAME)
        self._insert_value(self.last_entry, self.last_name)

    def _build_weight_age_fields(self):
        row_frame = tk.Frame(self.container, bg=COLORS['bg_dark'])
        row_frame.pack(fill=tk.X)
        
        weight_col = tk.Frame(row_frame, bg=COLORS['bg_dark'])
        weight_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.weight_entry = self._create_field(weight_col, "Weight (kg)", 
                                               validation_command=self.validation_command_weight, hint_text=HINT_WEIGHT)
        self._insert_value(self.weight_entry, self.weight_str)
        
        self.weight_popup = tk.Label(weight_col, text="", bg=COLORS['accent_green'], fg=COLORS['bg_panel'], 
                                     font=FONTS['preview_hint'], padx=5, pady=2, bd=1, relief=tk.RAISED)
        self.weight_popup_timer = [None]
        self.weight_entry.bind("<KeyRelease>", self._on_weight_changed)
        
        age_col = tk.Frame(row_frame, bg=COLORS['bg_dark'])
        age_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.birth_year_entry = self._create_field(age_col, "Birth Year", 
                                                   validation_command=self.validation_command_birthyear, hint_text=HINT_BIRTHYEAR)
        self._insert_value(self.birth_year_entry, str(self.birth_year))
        
        self.age_popup = tk.Label(age_col, text="", bg=COLORS['accent_green'], fg=COLORS['bg_panel'], 
                                  font=FONTS['preview_hint'], padx=5, pady=2, bd=1, relief=tk.RAISED)
        self.age_popup_timer = [None]
        self.birth_year_entry.bind("<KeyRelease>", self._on_birth_year_changed)
        self.birth_year_entry.bind("<FocusOut>", lambda e: self._on_birth_year_changed(e, show_popup=False), add='+')

    def _build_club_assoc_fields(self):
        club_row = tk.Frame(self.container, bg=COLORS['bg_dark'])
        club_row.pack(fill=tk.X)
        
        club_col = tk.Frame(club_row, bg=COLORS['bg_dark'])
        club_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.club_entry = self._create_field(club_col, "Club")
        self._insert_value(self.club_entry, self.club)
        
        assoc_col = tk.Frame(club_row, bg=COLORS['bg_dark'])
        assoc_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.association_entry = self._create_field(assoc_col, "Association")
        self._insert_value(self.association_entry, self.association)

    def _build_class_assignment(self):
        label_text = "WEIGHT CLASS ASSIGNMENT" if self.is_adult_category else "AGE CLASS UPGRADE"
        weight_class_slot = tk.Frame(self.container, bg=COLORS['bg_dark'])
        if not self.is_free_match and not self.is_young_category and not self.is_quarantine:
            weight_class_slot.pack(fill=tk.X)
            
        self.weight_class_frame = tk.Frame(weight_class_slot, bg=COLORS['bg_dark'])
        if not self.is_free_match and not self.is_young_category and not self.is_quarantine:
            self.weight_class_frame.pack(fill=tk.X, pady=(0, 14))
            tk.Label(self.weight_class_frame, text=label_text, bg=COLORS['bg_dark'], 
                     fg=COLORS['accent_blue'], font=FONTS['preview_label']).pack(anchor=tk.W, pady=(0, 6))
            
        current_weight_key = self._get_weight_key(self.current_weight_class)
        
        if not self.is_free_match and not self.is_young_category:
            if self.is_adult_category:
                natural_weight_class = None
                fighter_weight = self.fighter.get('Weight', 0)
                if self.parent.config_repo and fighter_weight and fighter_weight > 0:
                    natural_weight_class = self.parent.config_repo.get_weight_class(fighter_weight - self._group_tolerance, self.gender, self.age_group)
                
                if natural_weight_class and natural_weight_class != 'unknown':
                    natural_key = self._get_weight_key(natural_weight_class)
                    allowed = [natural_weight_class]
                    heavier = [wc for wc in self.available_weight_classes if self._get_weight_key(wc) > natural_key]
                    if heavier:
                        allowed.append(heavier[0])
                    if self.current_weight_class not in allowed:
                        allowed.append(self.current_weight_class)
                    allowed.sort(key=self._get_weight_key)
                    self.options_to_show = allowed
                else:
                    heavier_classes = [wc for wc in self.available_weight_classes if self._get_weight_key(wc) > current_weight_key]
                    if heavier_classes:
                        self.options_to_show = [self.current_weight_class, heavier_classes[0]]
                self.selected_var = self.weight_class_var
            else:
                available_age_classes = self._get_available_age_classes(self.gender, self.age_group)
                if available_age_classes:
                    self.options_to_show = [self.age_group, available_age_classes[0]]
                self.selected_var = self.age_class_var
                
        if not self.is_free_match and not self.is_young_category and not self.is_quarantine:
            if self.options_to_show:
                self._build_dropdown_widget()
            else:
                status_frame = tk.Frame(self.weight_class_frame, bg=COLORS['bg_panel'], padx=1, pady=1)
                status_frame.pack(fill=tk.X)
                status_text = f"● {self.current_weight_class} (Highest class)" if self.is_adult_category else f"● {self.age_group} (Highest class)"
                tk.Label(status_frame, text=status_text, bg=COLORS['bg_input'], fg=COLORS['text_muted'], 
                         font=FONTS['preview_text'], anchor=tk.W, padx=10, pady=10).pack(fill=tk.X)

    def _build_dropdown_widget(self):
        self.dropdown_border = tk.Frame(self.weight_class_frame, bg=COLORS['border'], padx=1, pady=1)
        self.dropdown_border.pack(fill=tk.X)
        self.dropdown_btn = tk.Frame(self.dropdown_border, bg=COLORS['bg_input'], cursor='hand2')
        self.dropdown_btn.pack(fill=tk.BOTH, expand=True)
        
        self.text_label = tk.Label(self.dropdown_btn, textvariable=self.selected_var, bg=COLORS['bg_input'], 
                                   fg=COLORS['text_primary'], font=FONTS['preview_text'], anchor=tk.W, padx=10, pady=8)
        self.text_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.arrow_label = tk.Label(self.dropdown_btn, text="▼", bg=COLORS['bg_input'], 
                                    fg=COLORS['accent_blue'], font=FONTS['preview_small'], padx=10)
        self.arrow_label.pack(side=tk.RIGHT, fill=tk.Y)
        
        for widget in (self.dropdown_btn, self.text_label, self.arrow_label):
            widget.bind("<Button-1>", self._handle_dropdown_click)
            widget.bind("<Enter>", self._on_dropdown_enter)
            widget.bind("<Leave>", self._on_dropdown_leave)
            
        self.dropdown_info_label = tk.Label(self.weight_class_frame, text="", bg=COLORS['bg_dark'], 
                                            fg=COLORS['accent_red'], font=FONTS['preview_hint'])

    def _build_status_fields(self):
        vp_row = tk.Frame(self.container, bg=COLORS['bg_dark'])
        vp_row.pack(fill=tk.X, pady=(0, 14))

        self.valid_var = tk.BooleanVar(value=self.is_valid)
        tk.Checkbutton(vp_row, text="Valid", variable=self.valid_var, bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                       selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_dark'], 
                       activeforeground=COLORS['text_primary'], font=FONTS['preview_text'], cursor='hand2').pack(side=tk.LEFT, padx=(0, 20))

        self.paid_var = tk.BooleanVar(value=self.is_paid)
        tk.Checkbutton(vp_row, text="Paid", variable=self.paid_var, bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                       selectcolor=COLORS['bg_input'], activebackground=COLORS['bg_dark'], 
                       activeforeground=COLORS['text_primary'], font=FONTS['preview_text'], cursor='hand2').pack(side=tk.LEFT)

    def _build_buttons(self):
        button_frame = tk.Frame(self.container, bg=COLORS['bg_dark'])
        button_frame.pack(fill=tk.X)
        
        tk.Button(button_frame, text="SAVE CHANGES", command=self._save_changes, bg=COLORS['accent_green'], 
                  fg=COLORS['text_primary'], font=FONTS['heading_sm'], bd=0, relief=tk.FLAT, padx=25, pady=12, cursor='hand2').pack(side=tk.RIGHT)
        
        tk.Button(button_frame, text="CANCEL", command=self.destroy, bg=COLORS['bg_panel'], 
                  fg=COLORS['text_secondary'], font=FONTS['heading_sm'], bd=0, relief=tk.FLAT, padx=25, pady=12, cursor='hand2').pack(side=tk.RIGHT, padx=10)

    # --- UI Interactions & Events ---
    
    def _focus_window(self, e):
        widget = e.widget
        if isinstance(widget, (tk.Entry, tk.Button, tk.Checkbutton, tk.Listbox)):
            return
        w = widget
        while w and w != self:
            try:
                if w.cget('cursor') == 'hand2': return
            except (tk.TclError, AttributeError): pass
            try:
                w = w.master
            except AttributeError: break
        self.focus_set()

    def _on_weight_changed(self, e=None, show_popup=True):
        if self.weight_popup_timer[0]: self.after_cancel(self.weight_popup_timer[0])
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
                            if fallback_ag: effective_age_group = fallback_ag
                        except Exception: pass
                    
                    detected = self.parent.config_repo.get_weight_class(weight_val - self._group_tolerance, self.gender, effective_age_group)
                    if detected and detected != 'unknown':
                        self.logger.debug(f"Weight class detected: {detected} (weight={weight_val:.3f}, age_group={effective_age_group}, gender={self.gender})")
                        if show_popup:
                            self.weight_popup.config(text=f"Auto-class: {detected}")
                            self.weight_popup.place(rely=1.0, relx=0.0, y=-22) 
                            self.weight_popup.lift()
                            self.weight_popup_timer[0] = self.after(2500, self.weight_popup.place_forget)
                        
                        if self.is_adult_category and not self.is_quarantine and effective_age_group == '18+':
                            effective_weight_classes = self._get_available_weight_classes(self.gender, effective_age_group) if effective_age_group != self.age_group else self.available_weight_classes
                            detected_natural_key = self._get_weight_key(detected)
                            allowed_weight_classes = [detected]
                            heavier = [wc for wc in effective_weight_classes if self._get_weight_key(wc) > detected_natural_key]
                            if heavier: allowed_weight_classes.append(heavier[0])
                            allowed_weight_classes.sort(key=self._get_weight_key)
                            self.options_to_show.clear()
                            self.options_to_show.extend(allowed_weight_classes)
                            self.weight_class_var.set(detected)
            except Exception: pass

    def _on_birth_year_changed(self, e=None, show_popup=True):
        if self.age_popup_timer[0]: self.after_cancel(self.age_popup_timer[0])
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
                        if self.is_adult_category:
                            if auto_age_group == '18+':
                                self.dropdown_enabled[0] = True
                                if self.dropdown_info_label: self.dropdown_info_label.pack_forget()
                                self.dropdown_btn.config(cursor='hand2')
                                self.text_label.config(fg=COLORS['text_primary'])
                                self.arrow_label.config(fg=COLORS['accent_blue'])
                            else:
                                self.dropdown_enabled[0] = False
                                self.dropdown_btn.config(cursor='')
                                self.text_label.config(fg=COLORS['text_muted'])
                                self.arrow_label.config(fg=COLORS['text_muted'])
                                self.weight_class_var.set("N/A")
                                if self.dropdown_info_label:
                                    self.dropdown_info_label.config(text=f"→ Person is now {auto_age_group} (Only 18+ have manual weight classes)")
                                    self.dropdown_info_label.pack(anchor=tk.W, pady=(4, 0))
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
                                if self.dropdown_info_label: self.dropdown_info_label.pack_forget()
                                self.dropdown_btn.config(cursor='hand2')
                                self.text_label.config(fg=COLORS['text_primary'])
                                self.arrow_label.config(fg=COLORS['accent_blue'])
                    
                    self._on_weight_changed(show_popup=False)
            except Exception: pass

    # --- Dropdown Logic ---
    
    def _handle_dropdown_click(self, e):
        if not self.dropdown_enabled[0]: return
        self._on_dropdown_leave(None)
        self._show_dropdown_menu()

    def _on_dropdown_enter(self, e):
        if not self.dropdown_enabled[0]: return
        p = self.popup_ref[0]
        if p and p.winfo_exists() and p.winfo_viewable(): return
        self.dropdown_border.config(bg=COLORS['accent_blue'])
        self.dropdown_btn.config(bg=COLORS['bg_panel'])
        self.text_label.config(bg=COLORS['bg_panel'])
        self.arrow_label.config(bg=COLORS['bg_panel'])
        
    def _on_dropdown_leave(self, e):
        if e and e.widget != self.dropdown_btn and e.widget.winfo_containing(e.x_root, e.y_root) in (self.dropdown_btn, self.text_label, self.arrow_label): return
        p = self.popup_ref[0]
        if p and p.winfo_exists() and p.winfo_viewable(): return
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
        if scrollbar: scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        lb = tk.Listbox(list_frame, bg=COLORS['bg_input'], fg=COLORS['text_primary'], font=FONTS['preview_text'], 
                        bd=0, highlightthickness=0, selectbackground=COLORS['accent_blue'], selectforeground=COLORS['text_primary'], 
                        activestyle='none', yscrollcommand=scrollbar.set if scrollbar else None, cursor='hand2')
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        if scrollbar: scrollbar.config(command=lb.yview)
        
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
        if action == '0': return True
        if not NAME_PATTERN.match(value_if_allowed): return False
        if '--' in value_if_allowed or value_if_allowed.startswith('-'): return False
        return True

    def _validate_weight(self, action, value_if_allowed):
        if action == '0': return True
        if len(value_if_allowed) > MAX_WEIGHT_LENGTH: return False
        normalized = value_if_allowed.replace(',', '.')
        if normalized.count('.') > 1: return False
        parts = normalized.split('.')
        if len(parts[0]) > 3: return False
        if not all(c.isdigit() for c in parts[0] if c != ''): return False
        if len(parts) == 2:
            if len(parts[1]) > 4: return False
            if parts[1] and not parts[1].isdigit(): return False
        for c in value_if_allowed:
            if c not in '0123456789.,': return False
        return True

    def _validate_birthyear(self, action, value_if_allowed):
        if action == '0': return True
        if len(value_if_allowed) > MAX_BIRTHYEAR_LENGTH: return False
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
            if _flash_timer_id[0]: self.after_cancel(_flash_timer_id[0])
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

        if not hasattr(self, '_all_borders'): self._all_borders = []
        self._all_borders.append(border_frame)

        def on_focus_in(e, b=border_frame):
            if not is_readonly:
                for ob in getattr(self, '_all_borders', []): ob.config(bg=COLORS['border'])
                b.config(bg=COLORS['accent_blue'])

        def on_focus_out(e, b=border_frame):
            if not is_readonly: b.config(bg=COLORS['border'])
        
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return entry

    def _insert_value(self, entry, value):
        if value: entry.insert(0, value)

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
        elif not self.is_free_match and not self.is_young_category:
            self.logger.debug("Save path: normal participant — checking for bracket/weight class movement")
            return self._handle_normal_routing()
        return self.bracket_key, None

    def _handle_quarantine_resort(self) -> tuple:
        """Participant was in quarantine — re-sort them into the correct bracket."""
        if not self.parent.quarantine_service:
            return False, False  # abort: no service to perform the re-sort

        tracking_id = str(uuid.uuid4())
        self.fighter['_tracking_id'] = tracking_id
        self.parent.quarantine_service.resort_brackets(
            self.parent.brackets, edited_fighter=self.fighter, group_preview_screen=self.parent
        )

        target_key = None
        for bk, bd in self.parent.brackets.items():
            if bk.startswith('QUARANTINE_'):
                continue
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

        # 1. Non-adult: user manually upgraded age class via dropdown
        if not self.is_adult_category:
            new_ac = self.age_class_var.get()
            if new_ac != self.age_group:
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

        # 2. Adult: user manually selected a different weight class via dropdown
        manual_override = False
        if self.is_adult_category:
            dropdown_selection = self.weight_class_var.get()
            auto_detected = None
            if self.parent.config_repo and new_weight > 0:
                auto_detected = self.parent.config_repo.get_weight_class(
                    new_weight - self._group_tolerance, self.gender, effective_age
                )
            if (auto_detected and dropdown_selection != auto_detected) \
                    or dropdown_selection != self.current_weight_class:
                effective_weight_class = dropdown_selection
                manual_override = True

        # 3. Auto-detect weight class from changed weight (no manual override)
        if not manual_override and self.parent.config_repo and new_weight != self.weight:
            detected = self.parent.config_repo.get_weight_class(
                new_weight - self._group_tolerance, self.gender, effective_age
            )
            if detected and detected != 'unknown':
                effective_weight_class = detected

        # 4. Birth year changed → re-detect age group → re-detect weight class for new age
        birth_year_val = self.birth_year_entry.get().strip()
        if birth_year_val and len(birth_year_val) == 4 and birth_year_val.isdigit():
            calculated_age     = datetime.datetime.now().year - int(birth_year_val)
            detected_age_group = get_age_group_with_fallback(calculated_age)
            if detected_age_group and detected_age_group != effective_age:
                effective_age = detected_age_group
                if self.parent.config_repo and new_weight > 0:
                    detected_wc = self.parent.config_repo.get_weight_class(
                        new_weight - self._group_tolerance, self.gender, effective_age
                    )
                    if detected_wc and detected_wc != 'unknown':
                        effective_weight_class = detected_wc

        return effective_age, effective_weight_class

    def _finalize(self, values: dict, display_key, target_key):
        """Persist to DB, refresh the parent UI, and close the dialog."""
        db_svc = getattr(self.parent, 'db_service', None)
        if db_svc:
            db_svc.update_participant(self.fighter, display_key or 'QUARANTINE')

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
        except ValueError: return []

    @staticmethod
    def _get_weight_key(weight_class_str):
        if weight_class_str == 'no-class': return (0, 0)
        num_str = weight_class_str.replace('kg', '').replace('-', '').replace('+', '')
        try: num = float(num_str)
        except ValueError: return (999, 0)
        return (num, 1 if weight_class_str.startswith('+') else 0)

    def _get_available_weight_classes(self, gender, age_group):
        available_classes = []
        used_fallback = False
        if self.parent.config_repo:
            try:
                gender_norm = str(gender).lower().strip()
                if gender_norm in ('m', 'male', 'maennlich', 'männlich'): gender_norm = 'm'
                elif gender_norm in ('w', 'f', 'female', 'weiblich', 'frau'): gender_norm = 'w'
                df = self.parent.config_repo.weight_classes
                filtered = df[(df['Gender'] == gender_norm) & (df['AgeGroup'] == age_group)]
                available_classes = filtered['Label'].tolist()
            except Exception: pass
        if not available_classes:
            used_fallback = True
            for bracket_key in self.parent.brackets.keys():
                parts = [p.strip() for p in bracket_key.split('|')]
                if len(parts) >= 3 and parts[0] == gender and parts[1] == age_group:
                    if parts[2] not in available_classes: available_classes.append(parts[2])
        if used_fallback: available_classes.sort(key=self._get_weight_key)
        return available_classes
