# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Reusable Weight Tolerance Configuration Dialog

Used by both group preview screen and split gender workflow to configure
per-gender/age-group weight tolerances (clothing adjustments).
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from ..styles import (COLORS, FONTS)  # noqa: E402

logger = get_logger('tolerance_config_dialog', debug_verbose=False)


class ToleranceConfigDialog:
    """
    Reusable dialog for configuring weight tolerances per gender/age-group.
    
    Usage:
        dialog = ToleranceConfigDialog(parent, group_keys=[('m', 'U9'), ('w', 'U11'), ...])
        tolerances = dialog.show()  # Blocks until user saves or cancels
        # tolerances is a dict like {('m', 'U9'): 0.1, ('w', 'U11'): 0.05, ...}
    """

    def __init__(self, parent, group_keys=None, existing_tolerances=None):
        """
        Initialize the tolerance configuration dialog.
        
        Args:
            parent: Parent window (for modality and positioning)
            group_keys: List of (gender, age_group) tuples to configure
            existing_tolerances: Dict of {(gender, age_group): float} with current values
        """
        self.parent = parent
        self.group_keys = group_keys or []
        self.existing_tolerances = existing_tolerances or {}
        self.result = None  # Will hold the configured tolerances after show()
        
        self.dialog = None
        self.spinbox_vars = {}

    def _fmt_tolerance(self, val):
        """Format tolerance to maintain 4 decimal places internally but show cleanly."""
        formatted = f"{float(val):.4f}".rstrip('0')
        if formatted.endswith('.'):
            formatted += '0'
        return formatted

    def _create_custom_spinbox(self, parent, var, callback=None):
        """Create a custom spinbox replacement using an Entry and two up/down buttons."""
        frame = tk.Frame(parent, bg=COLORS['bg_input'], highlightthickness=1, 
                        highlightbackground=COLORS['border'])
        
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
            validate="key", validatecommand=vcmd, 
            insertbackground=COLORS['text_primary']
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
        
        btn_up = tk.Button(btn_frame, text="▲", font=FONTS['preview_hint'], 
                          bg=COLORS['bg_panel'], fg=COLORS['text_primary'], 
                          bd=0, padx=2, pady=0, 
                          command=lambda: increment(0.1))
        btn_up.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        btn_down = tk.Button(btn_frame, text="▼", font=FONTS['preview_hint'], 
                            bg=COLORS['bg_panel'], fg=COLORS['text_primary'], 
                            bd=0, padx=2, pady=0, 
                            command=lambda: increment(-0.1))
        btn_down.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        return frame

    def show(self):
        """
        Display the tolerance configuration dialog and return configured tolerances.
        
        Blocks until user clicks Save or Cancel.
        
        Returns:
            Dict of {(gender, age_group): float} with configured tolerances,
            or None if user cancelled.
        """
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configure Weight Tolerances")
        self.dialog.geometry("450x400")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Title
        title_lbl = tk.Label(self.dialog, text="Weight Tolerances per Group",
                             bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                             font=FONTS['preview_title'])
        title_lbl.pack(pady=10)
        
        # Info
        info_lbl = tk.Label(
            self.dialog, 
            text="Set clothing tolerance (0.0–2.0 kg, 100g steps) for each group:",
            bg=COLORS['bg_dark'], fg=COLORS['text_secondary'],
            font=FONTS['preview_info']
        )
        info_lbl.pack(pady=(0, 10))
        
        # Scrollable frame for the table
        scroll_container = tk.Frame(self.dialog, bg=COLORS['bg_dark'])
        scroll_container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        canvas = tk.Canvas(scroll_container, bg=COLORS['bg_dark'], 
                          highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient=tk.VERTICAL, 
                                 command=canvas.yview,
                                 style='Dark.Vertical.TScrollbar')
        table_frame = tk.Frame(canvas, bg=COLORS['bg_dark'])
        
        table_frame.bind('<Configure>', 
                        lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=table_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Sort the group keys
        sorted_groups = sorted(self.group_keys, key=lambda x: (x[0], x[1]))
        
        # Header
        hdr_group = tk.Label(table_frame, text="Group", width=20, anchor='w',
                             bg=COLORS['bg_dark'], fg=COLORS['accent_blue'],
                             font=FONTS['list_mono_bold'])
        hdr_group.grid(row=0, column=0, padx=5, pady=2)
        
        hdr_tol = tk.Label(table_frame, text="Tolerance (kg)", width=15, 
                          anchor='w', bg=COLORS['bg_dark'], 
                          fg=COLORS['accent_blue'],
                          font=FONTS['list_mono_bold'])
        hdr_tol.grid(row=0, column=1, padx=5, pady=2)
        
        # Create spinboxes for each group
        for i, (g, ag) in enumerate(sorted_groups, 1):
            current_val = self.existing_tolerances.get((g, ag), 0.0)
            
            # Format label: show 'Mixed' for mixed categories, 'Male'/'Female' for gender-specific
            if g == 'mixed':
                label_text = f"{ag} (Mixed)"
            else:
                gender_text = 'Male' if g == 'm' else 'Female'
                label_text = f"{ag} {gender_text}"
            
            lbl = tk.Label(table_frame, text=label_text, anchor='w', width=20,
                          bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
                          font=FONTS['list_mono'])
            lbl.grid(row=i, column=0, padx=5, pady=2)
            
            var = tk.StringVar(value=self._fmt_tolerance(current_val))
            self.spinbox_vars[(g, ag)] = var
            
            sb = self._create_custom_spinbox(table_frame, var)
            sb.grid(row=i, column=1, padx=5, pady=2)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg=COLORS['bg_dark'])
        btn_frame.pack(fill=tk.X, padx=20, pady=15)
        
        def save_all():
            self.result = {}
            for key, var in self.spinbox_vars.items():
                try:
                    val = round(float(var.get()), 4)
                    val = max(0.0, val)
                except (ValueError, TypeError):
                    val = 0.0
                self.result[key] = val
            logger.info(f"Saved tolerances: {self.result}")
            self.dialog.destroy()
        
        ok_btn = tk.Button(btn_frame, text='Save', command=save_all,
                          bg=COLORS['accent_green'], fg=COLORS['text_primary'],
                          font=FONTS['body_md'], bd=0, padx=15, pady=8, 
                          cursor='hand2')
        ok_btn.pack(side=tk.RIGHT)
        
        cancel_btn = tk.Button(btn_frame, text='Cancel', 
                              command=lambda: self.dialog.destroy(),
                              bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                              font=FONTS['body_md'], bd=0, padx=15, pady=8, 
                              cursor='hand2')
        cancel_btn.pack(side=tk.RIGHT, padx=10)
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        
        return self.result
