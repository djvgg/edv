# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
File Loader Screen - Load participant data from XLSX, JSON, or Database

Provides multiple options for importing participant data:
- Load XLSX file and generate brackets
- Load from database
- Load M/W JSON files
- Split M/W contestants
"""

import tkinter as tk
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger
from ..styles import (
    COLORS, FONTS,
    apply_button_style,
    apply_label_style,
    create_dark_frame,
)

logger = get_logger('file_loader_screen')


class FileLoaderScreen(tk.Frame):
    """
    Initial file loading screen for importing participant data.
    
    Displays multiple options for data import:
    - XLSX files (with automatic bracket generation)
    - Database (with automatic bracket generation)
    - JSON files (M/W split)
    - Gender split utility (XLSX → JSON)
    """

    # Debug flag - set to True for verbose logging
    DEBUG = False

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger

        # Callbacks - will be set by main window
        self.on_load_xlsx = None
        self.on_load_database = None
        self.on_load_json = None
        self.on_split_gender = None

        # UI state
        self.info_var = tk.StringVar(value="[Waiting for data source...]")
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = None

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        # Header
        title = tk.Label(
            self,
            text="Tournament Bracket Manager",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            font=FONTS['heading_xl'],
        )
        apply_label_style(title, 'heading_xl')
        title.pack(pady=(20, 5))

        subtitle = tk.Label(
            self,
            text="Bracket Generator & Viewer",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_secondary'],
            font=FONTS['body_md'],
        )
        apply_label_style(subtitle, 'subtitle')
        subtitle.pack(pady=(0, 5))

        # Info label
        info_label = tk.Label(self, textvariable=self.info_var)
        apply_label_style(info_label, 'info')
        info_label.pack(pady=(0, 20))

        # Status label (bottom)
        self.status_label = tk.Label(self, textvariable=self.status_var, wraplength=480)
        apply_label_style(self.status_label, 'status_success')
        self.status_label.pack(side="bottom", pady=15)

        # Main buttons
        load_xlsx_btn = tk.Button(
            self,
            text="Load Participant List (XLSX) & Generate Brackets",
            command=self.on_load_xlsx_click,
        )
        apply_button_style(load_xlsx_btn, 'primary')
        load_xlsx_btn.pack(pady=8, fill="x", padx=40)

        # Database load button
        db_btn = tk.Button(
            self,
            text="Load from Database & Generate Brackets",
            command=self.on_load_database_click,
        )
        apply_button_style(db_btn, 'primary')
        db_btn.pack(pady=8, fill="x", padx=40)

        # Load JSON files button
        json_btn = tk.Button(
            self,
            text="Load M/W JSON Files & Generate Brackets",
            command=self.on_load_json_click,
        )
        apply_button_style(json_btn, 'primary')
        json_btn.pack(pady=8, fill="x", padx=40)

        # Split M/W button
        split_btn = tk.Button(
            self,
            text="Split M/W Contestants (XLSX → JSON)",
            command=self.on_split_gender_click,
        )
        apply_button_style(split_btn, 'secondary')
        split_btn.pack(pady=8, fill="x", padx=40)

        self.logger.debug("File loader UI initialized")

    def on_load_xlsx_click(self):
        """Handle XLSX load button click."""
        self.logger.info("User clicked: Load XLSX")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_load_xlsx callback")
        if self.on_load_xlsx:
            self.on_load_xlsx()

    def on_load_database_click(self):
        """Handle database load button click."""
        self.logger.info("User clicked: Load from Database")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_load_database callback")
        if self.on_load_database:
            self.on_load_database()

    def on_load_json_click(self):
        """Handle JSON load button click."""
        self.logger.info("User clicked: Load JSON")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_load_json callback")
        if self.on_load_json:
            self.on_load_json()

    def on_split_gender_click(self):
        """Handle gender split button click."""
        self.logger.info("User clicked: Split M/W")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_split_gender callback")
        if self.on_split_gender:
            self.on_split_gender()

    def set_info_text(self, text):
        """Update the info label text."""
        self.info_var.set(text)
        self.logger.debug(f"Info updated: {text}")

    def set_status_text(self, text, style='status_success'):
        """Update the status label text and style."""
        self.status_var.set(text)
        if self.status_label:
            apply_label_style(self.status_label, style)
        self.logger.debug(f"Status updated: {text}")
