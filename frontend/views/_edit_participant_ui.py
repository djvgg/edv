# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""UI builder mixin for Edit_Participants dialog."""

import tkinter as tk
from ..styles import COLORS, FONTS
import os
import sys
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

HINT_NAME = "Nur Buchstaben und -"
HINT_WEIGHT = "Nur Ziffern, z.B. 52.3500 oder 52,3"
HINT_BIRTHYEAR = "Genau 4 Ziffern"


class _UIBuilderMixin:
    """Mixin providing all UI construction methods for Edit_Participants."""

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
        
        # Only show for adults (weight class) or non-adults with double start (age class)
        show_assignment = self.is_adult_category or getattr(self, 'has_doppelstart', False)
        
        if not self.is_free_match and not self.is_young_category and not self.is_quarantine and show_assignment:
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
                
                # SPECIAL: If this is an 18+ participant who is naturally younger, add Undo option
                base = getattr(self, 'base_age_group', self.age_group)
                if base and self.age_group != base:
                    self.options_to_show.append(f"{base} (Undo Upgrade)")
                
                self.selected_var = self.weight_class_var
            else:
                base = getattr(self, 'base_age_group', self.age_group)
                # If they have doppelstart eligibility OR they are already in an upgraded/moved class (Undo needed)
                if getattr(self, 'has_doppelstart', False) or (base and self.age_group != base):
                    if getattr(self, 'already_upgraded', False):
                        self.options_to_show = [self.age_group]
                        self.dropdown_enabled[0] = False
                        
                        # Initialize info label if not already done
                        if not hasattr(self, 'dropdown_info_label') or not self.dropdown_info_label:
                             self.dropdown_info_label = tk.Label(self.weight_class_frame, bg=COLORS['bg_dark'], font=FONTS['preview_hint'])
                        
                        self.dropdown_info_label.config(text="Already upgraded to higher age class.", fg=COLORS['text_muted'])
                        self.dropdown_info_label.pack(anchor=tk.W, pady=(4, 0))
                    else:
                        if base and self.age_group != base:
                            self.options_to_show = [self.age_group, f"{base} (Undo Upgrade)"]
                        else:
                            # They are in their base class and haven't upgraded yet
                            avail = self._get_available_age_classes(self.gender, self.age_group)
                            if avail:
                                avail_filtered = [ag for ag in avail if ag != self.age_group]
                                if avail_filtered:
                                     self.options_to_show = [self.age_group, avail_filtered[0]]
                        
                        # FINAL SAFETY: If already upgraded, strip ALL other options except the current group
                        if getattr(self, 'already_upgraded', False):
                            self.options_to_show = [self.age_group]
                            self.dropdown_enabled[0] = False
                            self.logger.debug(f"[GEN_OPTIONS] REINFORCING LOCK: Participant ALREADY UPGRADED. Options set to {self.options_to_show}")
                else:
                    self.options_to_show = [self.age_group]
                    self.dropdown_enabled[0] = False
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
        
        is_enabled = self.dropdown_enabled[0]
        bg_color = COLORS['bg_input'] if is_enabled else COLORS['bg_panel']
        cursor = 'hand2' if is_enabled else ''
        
        self.dropdown_btn = tk.Frame(self.dropdown_border, bg=bg_color, cursor=cursor)
        self.dropdown_btn.pack(fill=tk.BOTH, expand=True)

        self.text_label = tk.Label(self.dropdown_btn, textvariable=self.selected_var, bg=bg_color,
                                   fg=COLORS['text_primary'] if is_enabled else COLORS['text_muted'],
                                   font=FONTS['preview_text'], anchor=tk.W, padx=10, pady=8)
        self.text_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if is_enabled:
            self.arrow_label = tk.Label(self.dropdown_btn, text="▼", bg=bg_color,
                                        fg=COLORS['accent_blue'], font=FONTS['preview_small'], padx=10)
            self.arrow_label.pack(side=tk.RIGHT, fill=tk.Y)

            for widget in (self.dropdown_btn, self.text_label, self.arrow_label):
                widget.bind("<Button-1>", self._handle_dropdown_click)
                widget.bind("<Enter>", self._on_dropdown_enter)
                widget.bind("<Leave>", self._on_dropdown_leave)
        else:
            tag_text = "(Base Class)"
            if getattr(self, 'already_upgraded', False):
                tag_text = "(Upgraded)"
            
            tk.Label(self.dropdown_btn, text=tag_text, bg=bg_color,
                     fg=COLORS['accent_blue'] if getattr(self, 'already_upgraded', False) else COLORS['text_muted'],
                     font=FONTS['preview_small'], padx=10).pack(side=tk.RIGHT)

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
