# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tolerance configuration mixin for GroupPreviewScreen."""

import tkinter as tk
from tkinter import ttk
from ..styles import COLORS, FONTS, apply_button_style, apply_label_style, create_dark_frame


class _ToleranceMixin:
    """Mixin providing weight tolerance configuration UI for GroupPreviewScreen."""

    def _fmt_tolerance(self, val):
        """Format tolerance to maintain 4 decimal places internally but show cleanly (e.g. 0.0 or 0.05)."""
        formatted = f"{float(val):.4f}".rstrip('0')
        if formatted.endswith('.'):
            formatted += '0'
        return formatted

    def _create_custom_spinbox(self, parent, var, callback=None):
        """Create a custom spinbox replacement using an Entry and two up/down buttons."""
        frame = tk.Frame(parent, bg=COLORS['bg_input'], highlightthickness=1, highlightbackground=COLORS['border'])

        def validate_float(P):
            if P == "":
                return True
            try:
                float(P)
                return True
            except ValueError:
                return False
        vcmd = (parent.register(validate_float), '%P')

        entry = tk.Entry(
            frame, textvariable=var, width=6, bg=COLORS['bg_input'],
            fg=COLORS['text_primary'], font=FONTS['list_mono'], bd=0,
            validate="key", validatecommand=vcmd, insertbackground=COLORS['text_primary']
        )
        entry.pack(side=tk.LEFT, fill=tk.Y, ipady=2, padx=4)

        btn_frame = tk.Frame(frame, bg=COLORS['bg_panel'])
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        def increment(amount):
            try:
                val = float(var.get() or 0)
            except ValueError:
                val = 0.0
            val += amount
            val = max(0.0, round(val, 4))
            var.set(self._fmt_tolerance(val))
            if callback:
                callback()

        btn_up = tk.Button(btn_frame, text="▲", font=FONTS['preview_hint'], bg=COLORS['bg_panel'], fg=COLORS['text_primary'], bd=0, padx=2, pady=0, command=lambda: increment(0.1))
        btn_up.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        btn_down = tk.Button(btn_frame, text="▼", font=FONTS['preview_hint'], bg=COLORS['bg_panel'], fg=COLORS['text_primary'], bd=0, padx=2, pady=0, command=lambda: increment(-0.1))
        btn_down.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        return frame

    def _create_tolerance_bar(self, parent, gender=None, age_group=None):
        """Create the tolerance control bar above the participant table."""
        if not gender or not age_group:
            return  # Hide the tolerance bar completely for QUARANTINE or Friendly Matches

        bar = create_dark_frame(parent)
        bar.pack(fill=tk.X, pady=(0, 5))

        # Context-aware label
        if gender and age_group:
            label_text = f'⚖ Tolerance for {gender} {age_group}:'
        else:
            label_text = '⚖ Tolerance:'

        lbl = tk.Label(bar, text=label_text)
        apply_label_style(lbl, 'info')
        lbl.pack(side=tk.LEFT)

        # Load current tolerance for this group
        group_key = (gender, age_group) if gender and age_group else None
        current_val = self.tolerances.get(group_key, 0.0) if group_key else 0.0

        self._tolerance_var = tk.StringVar(value=self._fmt_tolerance(current_val))
        self._tolerance_group_key = group_key
        spinbox = self._create_custom_spinbox(bar, self._tolerance_var, self._on_tolerance_changed)
        spinbox.pack(side=tk.LEFT, padx=5, pady=2)

        kg_lbl = tk.Label(bar, text='kg')
        apply_label_style(kg_lbl, 'info')
        kg_lbl.pack(side=tk.LEFT)

        apply_btn = tk.Button(bar, text='Apply', command=self._on_tolerance_changed)
        apply_button_style(apply_btn, 'secondary')
        apply_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Configure All button
        config_all_btn = tk.Button(bar, text='⚙ Configure All', command=self._open_tolerance_config_dialog)
        apply_button_style(config_all_btn, 'secondary')
        config_all_btn.pack(side=tk.LEFT, padx=(10, 0))

    def _on_tolerance_changed(self):
        """Save tolerance for the current group and re-render."""
        try:
            new_val = round(float(self._tolerance_var.get()), 4)
            new_val = max(0.0, new_val)
        except (ValueError, TypeError):
            new_val = 0.0

        if self._tolerance_group_key:
            self.tolerances[self._tolerance_group_key] = new_val
            self.logger.debug(f"Tolerance for {self._tolerance_group_key} set to {new_val} kg")
        if self.current_bracket_key:
            self._display_participants(self.current_bracket_key)

    def _open_tolerance_config_dialog(self):
        """Open dialog to configure tolerances for all age-group/gender combos."""
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title("Configure Weight Tolerances")
        dialog.geometry("450x400")
        dialog.configure(bg=COLORS['bg_dark'])
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        title_lbl = tk.Label(dialog, text="Weight Tolerances per Group",
                             bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                             font=FONTS['preview_title'])
        title_lbl.pack(pady=10)

        info_lbl = tk.Label(dialog, text="Set clothing tolerance (0.0–2.0 kg, 100g steps) for each group:",
                            bg=COLORS['bg_dark'], fg=COLORS['text_secondary'],
                            font=FONTS['preview_info'])
        info_lbl.pack(pady=(0, 10))

        # Scrollable frame for the table
        scroll_container = tk.Frame(dialog, bg=COLORS['bg_dark'])
        scroll_container.pack(fill=tk.BOTH, expand=True, padx=20)

        canvas = tk.Canvas(scroll_container, bg=COLORS['bg_dark'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=canvas.yview,
                                  style='Dark.Vertical.TScrollbar')
        table_frame = tk.Frame(canvas, bg=COLORS['bg_dark'])

        def _update_scrollregion(event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        table_frame.bind('<Configure>', _update_scrollregion)
        canvas.create_window((0, 0), window=table_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Enter>", _bind_mousewheel)
        dialog.bind("<Leave>", _unbind_mousewheel)
        dialog.bind("<Destroy>", _unbind_mousewheel)

        # Collect unique (gender, age_group) combos from brackets
        group_keys = set()
        for bk in self.brackets.keys():
            g, ag, _ = self._parse_bracket_key(bk)
            if g and ag:
                group_keys.add((g, ag))

        # Sort: gender then age_group
        sorted_groups = sorted(group_keys, key=lambda x: (x[0], x[1]))

        # Header
        hdr_group = tk.Label(table_frame, text="Group", width=20, anchor='w',
                             bg=COLORS['bg_dark'], fg=COLORS['accent_blue'],
                             font=FONTS['list_mono_bold'])
        hdr_group.grid(row=0, column=0, padx=5, pady=2)
        hdr_tol = tk.Label(table_frame, text="Tolerance (kg)", width=15, anchor='w',
                           bg=COLORS['bg_dark'], fg=COLORS['accent_blue'],
                           font=FONTS['list_mono_bold'])
        hdr_tol.grid(row=0, column=1, padx=5, pady=2)

        spinbox_vars = {}  # {(gender, age_group): StringVar}

        for i, (g, ag) in enumerate(sorted_groups, 1):
            current_val = self.tolerances.get((g, ag), 0.0)

            lbl = tk.Label(table_frame, text=f"{g} | {ag}", anchor='w', width=20,
                           bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                           font=FONTS['list_mono'])
            lbl.grid(row=i, column=0, padx=5, pady=2)

            var = tk.StringVar(value=self._fmt_tolerance(current_val))
            spinbox_vars[(g, ag)] = var

            sb = self._create_custom_spinbox(table_frame, var)
            sb.grid(row=i, column=1, padx=5, pady=2)

        # Buttons
        btn_frame = tk.Frame(dialog, bg=COLORS['bg_dark'])
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        def save_all():
            for key, var in spinbox_vars.items():
                try:
                    val = round(float(var.get()), 4)
                    val = max(0.0, val)
                except (ValueError, TypeError):
                    val = 0.0
                self.tolerances[key] = val
            self.logger.info(f"Saved tolerances: {self.tolerances}")
            dialog.destroy()
            if self.current_bracket_key:
                self._display_participants(self.current_bracket_key)

        ok_btn = tk.Button(btn_frame, text='Save', command=save_all,
                           bg=COLORS['accent_green'], fg=COLORS['text_primary'],
                           font=FONTS['body_md'], bd=0, padx=15, pady=8, cursor='hand2')
        ok_btn.pack(side=tk.RIGHT)

        cancel_btn = tk.Button(btn_frame, text='Cancel', command=dialog.destroy,
                               bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                               font=FONTS['body_md'], bd=0, padx=15, pady=8, cursor='hand2')
        cancel_btn.pack(side=tk.RIGHT, padx=10)
