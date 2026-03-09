# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Dialog for pairing two lone fighters into a friendly match bracket."""

import tkinter as tk
from tkinter import messagebox
from typing import Callable

from ..styles import COLORS, FONTS


class FriendlyMatchDialog(tk.Toplevel):
    """Modal dialog for creating a friendly match between two eligible fighters.

    Eligible fighters come from brackets that have exactly 1 or 2 participants
    and are not already a friendly-match bracket (key does not start with 'FM |').

    Args:
        parent:      Root or Toplevel window to attach to (transient + grab).
        brackets:    The shared brackets dict — mutated in-place on confirm.
        on_success:  Called with no arguments after the match is created
                     (typically refreshes the group list in the caller).
    """

    def __init__(self, parent: tk.Misc, brackets: dict, on_success: Callable):
        super().__init__(parent)
        self._brackets = brackets
        self._on_success = on_success
        self._eligible: list[tuple[str, dict]] = []  # (bracket_key, fighter_dict)

        self.title("Friendly Match")
        self.geometry("600x450")
        self.configure(bg=COLORS['bg_dark'])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._populate_list()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        tk.Label(
            self, text="Create Friendly Match",
            bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
            font=FONTS['preview_title'],
        ).pack(pady=15)

        tk.Label(
            self, text="Select exactly 2 fighters from groups with 1-2 participants:",
            bg=COLORS['bg_dark'], fg=COLORS['text_secondary'],
            font=FONTS['preview_info'],
        ).pack(pady=(0, 10))

        list_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._listbox = tk.Listbox(
            list_frame,
            bg=COLORS['bg_input'],
            fg=COLORS['text_primary'],
            font=FONTS['list_ui'],
            selectmode=tk.MULTIPLE,
            yscrollcommand=scrollbar.set,
            bd=0, highlightthickness=1, highlightbackground=COLORS['border'],
            selectbackground=COLORS['accent_blue'],
            selectforeground=COLORS['text_primary'],
            exportselection=False,
            activestyle='none',
        )
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self._listbox.yview)

        btn_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Button(
            btn_frame, text="Create Match", command=self._on_confirm,
            bg=COLORS['accent_green'], fg=COLORS['text_primary'],
            font=FONTS['body_md'], bd=0, padx=15, pady=8, cursor='hand2',
        ).pack(side=tk.RIGHT)

        tk.Button(
            btn_frame, text="Cancel", command=self.destroy,
            bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
            font=FONTS['body_md'], bd=0, padx=15, pady=8, cursor='hand2',
        ).pack(side=tk.RIGHT, padx=10)

    def _populate_list(self):
        for b_key in sorted(self._brackets.keys()):
            fighters = self._brackets[b_key].get('fighters', [])
            if len(fighters) not in (1, 2) or b_key.startswith("FM |"):
                continue
            for f in fighters:
                self._eligible.append((b_key, f))
                name = (
                    f"{f.get('Firstname', '')} {f.get('Lastname', '')}".strip()
                    or f.get('Name', 'Unknown')
                )
                weight = f.get('Weight', 'N/A')
                birth = f.get('Birthyear', f.get('age', 'N/A'))
                club = f.get('Club', f.get('Verein', 'N/A'))
                self._listbox.insert(tk.END, f"{b_key}:   {name} ({weight}kg, {birth}yrs, {club})")

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _on_confirm(self):
        selections = self._listbox.curselection()
        if len(selections) != 2:
            messagebox.showwarning("Warning", "Please select exactly 2 fighters.", parent=self)
            return

        idx1, idx2 = selections
        b_key1, f1 = self._eligible[idx1]
        b_key2, f2 = self._eligible[idx2]

        name1 = (
            f"{f1.get('Firstname', '')} {f1.get('Lastname', '')}".strip()
            or f1.get('Name', 'Unknown')
        )
        name2 = (
            f"{f2.get('Firstname', '')} {f2.get('Lastname', '')}".strip()
            or f2.get('Name', 'Unknown')
        )
        new_key = f"FM | {name1} vs {name2}"

        if new_key not in self._brackets:
            self._brackets[new_key] = {'fighters': [], 'bracket': []}

        for b_key, fighter in ((b_key1, f1), (b_key2, f2)):
            try:
                self._brackets[b_key]['fighters'].remove(fighter)
                self._brackets[new_key]['fighters'].append(fighter)
            except ValueError:
                pass

        messagebox.showinfo(
            "Success",
            f"Friendly match created:\n{f1['Name']} vs {f2['Name']}",
            parent=self,
        )
        self._on_success()
        self.destroy()
