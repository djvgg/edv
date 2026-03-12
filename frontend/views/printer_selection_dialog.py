# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Printer selection dialog for bracket printing."""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger  # noqa: E402
from ..styles import (  # noqa: E402
    COLORS, FONTS,
    apply_button_style,
    apply_label_style,
    create_dark_frame,
)

logger = get_logger('printer_selection_dialog')


class PrinterSelectionDialog(tk.Toplevel):
    """Dialog for selecting printer and print options."""

    def __init__(self, parent, bracket_info: dict, available_printers: list):
        """
        Initialize printer selection dialog.
        
        Args:
            parent: Parent window
            bracket_info: Info about bracket being printed
            available_printers: List of available printer names
        """
        super().__init__(parent)
        self.title("Print Bracket")
        self.resizable(False, False)
        
        self.bracket_info = bracket_info
        self.available_printers = available_printers or ["System Default"]
        
        self.result = None  # Will be set to (printer_name, copies) or None
        
        logger.debug(f"Creating print dialog for bracket {bracket_info.get('id')}")
        self._build_ui()
        
        # Center on parent
        self.transient(parent)
        self.grab_set()
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Build dialog UI."""
        self.configure(bg=COLORS['bg_dark'])
        
        # Main frame with padding
        main_frame = create_dark_frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="Print Bracket", bg=COLORS['bg_dark'])
        apply_label_style(title_label, 'heading_md')
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Bracket info
        info_text = f"{self.bracket_info.get('age_group', 'N/A')} | "
        info_text += f"{self.bracket_info.get('weight_class', 'N/A')} | "
        info_text += f"Mat {self.bracket_info.get('mat_number', 'N/A')}"
        
        info_label = tk.Label(main_frame, text=info_text, bg=COLORS['bg_dark'])
        apply_label_style(info_label, 'info')
        info_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Printer selection
        printer_label = tk.Label(main_frame, text="Select Printer:", bg=COLORS['bg_dark'])
        apply_label_style(printer_label, 'label')
        printer_label.pack(anchor=tk.W, pady=(10, 5))
        
        self.printer_var = tk.StringVar(
            value=self.available_printers[0] if self.available_printers else ""
        )
        
        printer_frame = create_dark_frame(main_frame)
        printer_frame.pack(fill=tk.X, pady=(0, 15))
        
        for printer in self.available_printers:
            radio = tk.Radiobutton(
                printer_frame,
                text=printer,
                variable=self.printer_var,
                value=printer,
                bg=COLORS['bg_dark'],
                fg=COLORS['text_primary'],
                selectcolor=COLORS['accent_red'],
                activebackground=COLORS['bg_dark'],
                activeforeground=COLORS['accent_red']
            )
            radio.pack(anchor=tk.W, pady=3)
        
        # Copies
        copies_label = tk.Label(main_frame, text="Copies:", bg=COLORS['bg_dark'])
        apply_label_style(copies_label, 'label')
        copies_label.pack(anchor=tk.W, pady=(10, 5))
        
        copies_frame = create_dark_frame(main_frame)
        copies_frame.pack(anchor=tk.W, pady=(0, 20))
        
        self.copies_var = tk.StringVar(value="1")
        copies_spinbox = tk.Spinbox(
            copies_frame,
            from_=1,
            to=10,
            textvariable=self.copies_var,
            width=5,
            bg=COLORS['bg_darker'],
            fg=COLORS['text_primary'],
            insertbackground=COLORS['text_primary']
        )
        copies_spinbox.pack(side=tk.LEFT)
        
        # Buttons
        button_frame = create_dark_frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        cancel_btn = tk.Button(button_frame, text="Cancel", command=self._on_cancel)
        apply_button_style(cancel_btn, 'secondary')
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        print_btn = tk.Button(button_frame, text="Print", command=self._on_print)
        apply_button_style(print_btn, 'primary')
        print_btn.pack(side=tk.RIGHT)

    def _on_print(self):
        """Handle print button click."""
        try:
            printer = self.printer_var.get()
            copies = int(self.copies_var.get())
            
            if copies < 1 or copies > 10:
                messagebox.showwarning("Invalid Copies", "Copies must be between 1 and 10")
                return
            
            self.result = (printer, copies)
            logger.info(f"Print dialog result: printer={printer}, copies={copies}")
            self.destroy()
        
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for copies")

    def _on_cancel(self):
        """Handle cancel button click."""
        logger.debug("Print dialog cancelled")
        self.result = None
        self.destroy()

    def show_dialog(self):
        """Show dialog and wait for result."""
        self.wait_window()
        return self.result
