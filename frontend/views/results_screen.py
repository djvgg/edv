# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fertige Kampflisten — shows completed brackets and their placements."""

import os
import sys

import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger  # noqa: E402
from ..styles import (  # noqa: E402
    COLORS, FONTS,
    apply_button_style,
    apply_entry_style,
    apply_label_style,
    apply_listbox_style,
    create_dark_frame,
)
from ..utils.search_utils import filter_items  # noqa: E402


class ResultsScreen(tk.Frame):
    """Screen that lists completed brackets and shows their placements."""

    _POLL_INTERVAL_MS = 15_000

    def __init__(self, parent, main_window=None):
        super().__init__(parent, bg=COLORS['bg_dark'])
        self.logger = get_logger('results_screen')
        self.main_window = main_window
        self._listbox_map = {}   # display_text → bracket_key
        self._poll_job = None
        self._build_ui()
        self.logger.debug("ResultsScreen initialized")

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               bg=COLORS['bg_dark'], sashwidth=4,
                               sashrelief=tk.FLAT, showhandle=False)
        paned.pack(fill=tk.BOTH, expand=True)

        # ── Left panel ────────────────────────────────────────────────────
        left = create_dark_frame(paned)
        paned.add(left, width=250, minsize=200)

        title_lbl = tk.Label(left, text='Fertige Kampflisten')
        apply_label_style(title_lbl, 'heading_md')
        title_lbl.pack(anchor=tk.W, pady=(0, 5))

        search_frame = create_dark_frame(left)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        search_lbl = tk.Label(search_frame, text='Search:')
        apply_label_style(search_lbl, 'info')
        search_lbl.pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace('w', self._refresh_list)
        search_entry = tk.Entry(search_frame, textvariable=self._search_var)
        apply_entry_style(search_entry)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self._listbox = tk.Listbox(left, width=26, height=20)
        apply_listbox_style(self._listbox)
        self._listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self._listbox.bind('<ButtonRelease-1>', self._on_select)

        # ── Right panel ───────────────────────────────────────────────────
        right = create_dark_frame(paned)
        paned.add(right, minsize=400)

        # Title bar
        top_bar = create_dark_frame(right)
        top_bar.pack(fill=tk.X, pady=(0, 5), padx=5)

        self._title_var = tk.StringVar(value='')
        title = tk.Label(top_bar, textvariable=self._title_var)
        apply_label_style(title, 'heading_md')
        title.pack(side=tk.LEFT)

        # Content area (cleared + rebuilt on each selection)
        self._content = create_dark_frame(right)
        self._content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self._show_hint()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _show_hint(self):
        for w in self._content.winfo_children():
            w.destroy()
        hint = tk.Label(self._content, text='Kampfliste auswählen',
                        bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                        font=FONTS['body_md'])
        hint.pack(pady=40)

    def _refresh_list(self, *_):
        self._listbox.delete(0, tk.END)
        self._listbox_map.clear()

        if not self.main_window:
            return

        completed = sorted(self.main_window.db_service.get_completed_bracket_keys())
        filtered, _, _ = filter_items(completed, self._search_var.get())

        for key in filtered:
            self._listbox.insert(tk.END, key)
            self._listbox_map[key] = key

    def _on_select(self, _event):
        sel = self._listbox.curselection()
        if not sel:
            return
        display = self._listbox.get(sel[0])
        bracket_key = self._listbox_map.get(display)
        if bracket_key:
            self._show_results(bracket_key)

    def _show_results(self, bracket_key):
        self._title_var.set(bracket_key)
        for w in self._content.winfo_children():
            w.destroy()

        rows = self.main_window.db_service.get_bracket_placements(bracket_key)

        headers = ['Platz', 'Vorname', 'Nachname', 'Verein']
        col_widths = [6, 18, 18, 30]

        for col, (hdr, width) in enumerate(zip(headers, col_widths)):
            lbl = tk.Label(self._content, text=hdr, width=width, anchor='w',
                           bg=COLORS['bg_panel'], fg=COLORS['accent_orange'],
                           font=FONTS['heading_sm'])
            lbl.grid(row=0, column=col, padx=6, pady=(4, 2), sticky='w')

        sep = tk.Frame(self._content, height=1, bg=COLORS['border'])
        sep.grid(row=1, column=0, columnspan=4, sticky='ew', padx=4, pady=2)

        if not rows:
            no_data = tk.Label(self._content, text='Keine Platzierungen vorhanden.',
                               bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                               font=FONTS['body_md'])
            no_data.grid(row=2, column=0, columnspan=4, pady=20, sticky='w', padx=6)
            return

        platz_labels = {1: '1.', 2: '2.', 3: '3.'}
        for i, row in enumerate(rows):
            values = [platz_labels.get(row['platz'], f"{row['platz']}."),
                      row['vorname'], row['nachname'], row['verein']]
            for col, (val, width) in enumerate(zip(values, col_widths)):
                lbl = tk.Label(self._content, text=val, width=width, anchor='w',
                               bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                               font=FONTS['body_md'])
                lbl.grid(row=i + 2, column=col, padx=6, pady=3, sticky='w')

    # ── Polling ───────────────────────────────────────────────────────────

    def _start_poll(self):
        self._stop_poll()
        self._poll_job = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    def _stop_poll(self):
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None

    def _poll_tick(self):
        self._poll_job = None
        self._refresh_list()
        self._poll_job = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def on_show(self, force_reload=False):
        self._refresh_list()
        self._show_hint()
        self._title_var.set('')
        self._start_poll()

    def on_close_screen(self):
        self._stop_poll()
