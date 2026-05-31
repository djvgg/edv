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

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger, DEBUG_VERBOSE  # noqa: E402
from ..styles import (  # noqa: E402
    COLORS, FONTS, SPACING,
    apply_button_style,
    apply_label_style,
    create_dark_frame,
)

logger = get_logger('file_loader_screen', debug_verbose=DEBUG_VERBOSE)


class FileLoaderScreen(tk.Frame):
    """
    Initial file loading screen for importing participant data.
    
    Displays multiple options for data import:
    - XLSX files (with automatic bracket generation)
    - Database (with automatic bracket generation)
    - JSON files (M/W split)
    - Gender split utility (XLSX → JSON)
    """

    DEBUG = DEBUG_VERBOSE

    def __init__(self, parent, main_window=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=COLORS['bg_dark'])
        self.logger = logger
        self.main_window = main_window

        # Callbacks - will be set by main window
        self.on_load_database = None
        self.on_load_json_initial = None   # fresh import: wipes existing data
        self.on_load_json_append = None    # append/update import: merges into current data
        self.on_split_gender = None
        self.on_flush_database = None

        # UI state
        self.info_var = tk.StringVar(value="[Warte auf Datenquelle...]")
        self.status_var = tk.StringVar(value="Bereit.")
        self.status_label = None
        self.ui_initialized = False  # Track if UI has been built

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface. Only build once."""
        if self.ui_initialized:
            self.logger.debug("UI already initialized, skipping rebuild")
            return
        
        # Header
        title = tk.Label(
            self,
            text="Turnier-Management-System",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            font=FONTS['heading_xl'],
        )
        apply_label_style(title, 'heading_xl')
        title.pack(pady=(SPACING['xl'], SPACING['sm']))

        subtitle = tk.Label(
            self,
            text="Listen-Generator & Ansicht",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_secondary'],
        )
        apply_label_style(subtitle, 'subtitle')
        subtitle.pack(pady=(0, SPACING['sm']))

        # Info label
        info_label = tk.Label(self, textvariable=self.info_var)
        apply_label_style(info_label, 'info')
        info_label.pack(pady=(0, SPACING['lg']))

        # Bottom section — packed with side="bottom" in reverse order
        # (Tkinter bottom-packing: first packed = lowest)
        self.status_label = tk.Label(self, textvariable=self.status_var, wraplength=480)
        apply_label_style(self.status_label, 'status_success')
        self.status_label.pack(side="bottom", pady=SPACING['md'])


        # Main buttons container
        main_controls = create_dark_frame(self)
        main_controls.pack(pady=SPACING['md'], fill="x", expand=True)

        # Database load button
        db_btn = tk.Button(
            main_controls,
            text="Aus Datenbank laden & Listen generieren",
            command=self.on_load_database_click,
        )
        apply_button_style(db_btn, 'primary')
        db_btn.pack(pady=SPACING['sm'], fill="x", padx=SPACING['xl'])

        # Initial JSON import (replaces all existing data)
        json_initial_btn = tk.Button(
            main_controls,
            text="Initialer Import (ersetzt alle Daten)",
            command=self.on_load_json_initial_click,
        )
        apply_button_style(json_initial_btn, 'primary')
        json_initial_btn.pack(pady=SPACING['sm'], fill="x", padx=SPACING['xl'])

        # Append/update JSON import (merges into current data, e.g. add the 2nd
        # gender list or re-import a corrected list — matched by name+gender+...)
        json_append_btn = tk.Button(
            main_controls,
            text="Import anfügen / aktualisieren",
            command=self.on_load_json_append_click,
        )
        apply_button_style(json_append_btn, 'primary')
        json_append_btn.pack(pady=SPACING['sm'], fill="x", padx=SPACING['xl'])

        # Split M/W button
        split_btn = tk.Button(
            main_controls,
            text="Teilnehmer nach Geschlecht trennen (Excel → JSON)",
            command=self.on_split_gender_click,
        )
        apply_button_style(split_btn, 'secondary')
        split_btn.pack(pady=SPACING['sm'], fill="x", padx=SPACING['xl'])

        # Flush Database button (moved into main stack for consistent layout)
        flush_btn = tk.Button(
            main_controls,
            text="Datenbank leeren (Alle Daten löschen)",
            command=self.on_flush_database_click,
        )
        apply_button_style(flush_btn, 'secondary')
        flush_btn.configure(fg=COLORS['accent_red'])
        flush_btn.pack(side="bottom", pady=(10, 0), fill="x", padx=40)

        self.logger.debug("File loader UI initialized")
        self.ui_initialized = True

    def on_load_database_click(self):
        """Handle database load button click."""
        self.logger.info("User clicked: Load from Database")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_load_database callback")
        if self.on_load_database:
            self.on_load_database()

    def on_load_json_initial_click(self):
        """Handle initial (replace) JSON import button click."""
        self.logger.info("User clicked: Initial JSON import (replace)")
        if self.on_load_json_initial:
            try:
                self.on_load_json_initial()
            except Exception as e:
                self.logger.error(f"[FILE_LOADER] Error in on_load_json_initial: {e}", exc_info=True)
        else:
            self.logger.warning("[FILE_LOADER] on_load_json_initial callback is NOT set!")

    def on_load_json_append_click(self):
        """Handle append/update JSON import button click."""
        self.logger.info("User clicked: Append/update JSON import")
        if self.on_load_json_append:
            try:
                self.on_load_json_append()
            except Exception as e:
                self.logger.error(f"[FILE_LOADER] Error in on_load_json_append: {e}", exc_info=True)
        else:
            self.logger.warning("[FILE_LOADER] on_load_json_append callback is NOT set!")

    def on_split_gender_click(self):
        """Handle gender split button click."""
        self.logger.info("User clicked: Split M/W")
        if self.DEBUG:
            self.logger.debug("DEBUG: Executing on_split_gender callback")
        if self.on_split_gender:
            self.on_split_gender()

    def on_flush_database_click(self):
        """Handle flush database button click with confirmation dialog."""
        from tkinter import messagebox
        self.logger.info("User clicked: Flush Database")
        if messagebox.askyesno(
            "Flush Database",
            "This will permanently delete ALL tournament data.\n\nAre you sure?",
            icon='warning',
        ):
            if self.on_flush_database:
                self.on_flush_database()

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

    def on_show(self, force_reload=False):
        """Lifecycle hook called when screen is displayed."""
        # FileLoaderScreen is the entry point, no reload needed
        self.logger.debug(f"[LIFECYCLE] FileLoaderScreen.on_show(force_reload={force_reload})")

    def on_close_screen(self):
        """Cleanup when screen is hidden."""
        pass

