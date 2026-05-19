# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tournament configuration screen.

Centralizes age-class locks and weight tolerances that used to be split
across inline controls in Gruppenvorschau and Wettkampfsystem.

Two sections:
    1) Altersklassen-Sperren — lock / unlock per age group
       (writes through to db_service.lock_age_class / unlock_age_class
        and mirrors main_window.locked_age_classes)
    2) Gewichtstoleranzen — per (gender × age group) spinbox
       (mutates main_window.tolerances; consumers read from there)

Both sections refresh on every show so the screen always reflects the
current state, even when a lock was toggled elsewhere.
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

# Setup sys.path for utils import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.logging import get_logger  # noqa: E402
from utils.helpers import parse_bracket_key  # noqa: E402
from backend.data.repositories.config_repository import ConfigRepository  # noqa: E402

from ..styles import (  # noqa: E402
    COLORS, FONTS, SPACING,
    apply_button_style, apply_label_style, create_dark_frame,
)


# Canonical order, mirrors what AGE_CLASS_ORDER uses elsewhere in the app.
_AGE_GROUPS = ['U9', 'U11', 'U13', 'U15', 'U18', '18+']
_GENDERS = [('m', 'männlich'), ('w', 'weiblich')]


class TournamentConfigScreen(tk.Frame):
    """6th tab — central place to manage age-class locks and tolerances."""

    def __init__(self, parent, main_window=None, **kwargs):
        super().__init__(parent, bg=COLORS['bg_dark'])
        self.logger = get_logger('tournament_config_screen')
        self.main_window = main_window

        # State containers — rebuilt on every on_show().
        self._lock_widgets = {}        # age_group -> {'btn': Button, 'status': Label}
        self._tolerance_vars = {}      # (gender, age_group) -> tk.StringVar

        self._build_ui()

    # ----- Lifecycle hooks --------------------------------------------------

    def on_show(self, force_reload=False):
        """Refresh both sections from the current main_window state."""
        self._refresh_lock_section()
        self._refresh_tolerance_section()

    def on_hide(self):
        """Persist tolerances back into main_window before leaving."""
        self._save_tolerances()

    # ----- UI scaffold ------------------------------------------------------

    def _build_ui(self):
        # Title
        title = tk.Label(
            self, text="Turnier-Konfiguration",
            bg=COLORS['bg_dark'], fg=COLORS['text_primary'],
            font=FONTS['heading_lg'],
        )
        title.pack(anchor='w', padx=SPACING['lg'], pady=(SPACING['lg'], SPACING['sm']))

        subtitle = tk.Label(
            self,
            text="Altersklassen-Sperren und Gewichtstoleranzen — zentral verwaltet.",
            bg=COLORS['bg_dark'], fg=COLORS['text_muted'],
            font=FONTS['body_sm'],
        )
        subtitle.pack(anchor='w', padx=SPACING['lg'], pady=(0, SPACING['md']))

        # Two columns: locks (left) + tolerances (right)
        container = create_dark_frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=SPACING['lg'], pady=SPACING['md'])

        # Lock section
        self._lock_section = create_dark_frame(container)
        self._lock_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, SPACING['md']))

        # Tolerance section
        self._tolerance_section = create_dark_frame(container)
        self._tolerance_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(SPACING['md'], 0))

    # ----- Lock section -----------------------------------------------------

    def _refresh_lock_section(self):
        for widget in self._lock_section.winfo_children():
            widget.destroy()
        self._lock_widgets.clear()

        heading = tk.Label(
            self._lock_section, text="🔒 Altersklassen-Sperren",
            bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
            font=FONTS['heading_md'],
        )
        heading.pack(anchor='w', pady=(SPACING['sm'], SPACING['sm']), padx=SPACING['sm'])

        info = tk.Label(
            self._lock_section,
            text=("Gesperrte Altersklassen sind beim Re-Import geschützt —\n"
                  "die Teilnehmer-Liste wird nicht überschrieben.\n"
                  "Matten-Zuweisung, Kämpfen und Ergebnisse bleiben möglich."),
            bg=COLORS['bg_panel'], fg=COLORS['text_muted'],
            font=FONTS['body_sm'], justify='left',
        )
        info.pack(anchor='w', padx=SPACING['sm'], pady=(0, SPACING['md']))

        locks = self._current_locks()
        for age in _AGE_GROUPS:
            self._build_lock_row(self._lock_section, age, age in locks)

    def _build_lock_row(self, parent, age_group: str, currently_locked: bool):
        row = create_dark_frame(parent)
        row.pack(fill=tk.X, pady=SPACING['xs'], padx=SPACING['sm'])

        label = tk.Label(
            row, text=age_group, width=8, anchor='w',
            bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
            font=FONTS['body_md'],
        )
        label.pack(side=tk.LEFT)

        status_label = tk.Label(
            row,
            text="gesperrt" if currently_locked else "frei",
            width=10, anchor='w',
            bg=COLORS['bg_panel'],
            fg=COLORS['accent_red'] if currently_locked else COLORS['text_muted'],
            font=FONTS['body_sm'],
        )
        status_label.pack(side=tk.LEFT, padx=SPACING['sm'])

        btn_text = "Entsperren" if currently_locked else "Sperren"
        btn = tk.Button(
            row, text=btn_text,
            command=lambda ag=age_group, l=currently_locked: self._toggle_lock(ag, l),
        )
        apply_button_style(btn, 'secondary')
        btn.pack(side=tk.RIGHT)

        self._lock_widgets[age_group] = {'btn': btn, 'status': status_label}

    def _toggle_lock(self, age_group: str, currently_locked: bool):
        db_service = getattr(self.main_window, 'db_service', None)
        if not db_service:
            messagebox.showerror("Fehler", "Datenbank-Service nicht verfügbar.")
            return

        if currently_locked:
            # Optional confirm when fights already exist.
            activity = db_service.get_age_class_activity(age_group) or {}
            if activity.get('fight_count', 0) or activity.get('completed_fight_count', 0):
                ok = messagebox.askyesno(
                    "Altersklasse entsperren",
                    f"In {age_group} existieren bereits {activity.get('fight_count', 0)} Kämpfe "
                    f"({activity.get('completed_fight_count', 0)} mit Ergebnis).\n\n"
                    "Sperre wirklich aufheben?",
                )
                if not ok:
                    return

            if db_service.unlock_age_class(age_group):
                self._mirror_unlock(age_group)
                self.logger.info(f"Unlocked age class: {age_group}")
            else:
                messagebox.showerror("Fehler", f"Sperre für {age_group} konnte nicht aufgehoben werden.")
        else:
            if db_service.lock_age_class(age_group, reason='manual'):
                self._mirror_lock(age_group)
                self.logger.info(f"Locked age class: {age_group}")
            else:
                messagebox.showerror("Fehler", f"{age_group} konnte nicht gesperrt werden.")

        # Mark all downstream screens stale so they pick up the new lock state.
        sm = getattr(self.main_window, 'screen_manager', None)
        if sm:
            for screen in ('group_preview', 'generation_method', 'bracket_viewer'):
                sm.mark_screen_stale(screen)

        # Rebuild this section to reflect the new state.
        self._refresh_lock_section()

    def _mirror_lock(self, age_group: str):
        locks = getattr(self.main_window, 'locked_age_classes', set())
        locks.add(age_group)
        self.main_window.locked_age_classes = locks

    def _mirror_unlock(self, age_group: str):
        locks = getattr(self.main_window, 'locked_age_classes', set())
        locks.discard(age_group)
        # Also discard gender-scoped variants like 'm|U18'
        for scope in list(locks):
            if scope.endswith(f"|{age_group}"):
                locks.discard(scope)
        self.main_window.locked_age_classes = locks

    def _current_locks(self) -> set:
        """Return the set of currently-locked age groups (gender-stripped)."""
        raw = getattr(self.main_window, 'locked_age_classes', set()) or set()
        result = set()
        for scope in raw:
            if '|' in scope:
                result.add(scope.split('|', 1)[1])
            else:
                result.add(scope)
        return result

    # ----- Tolerance section ------------------------------------------------

    def _refresh_tolerance_section(self):
        for widget in self._tolerance_section.winfo_children():
            widget.destroy()
        self._tolerance_vars.clear()

        heading = tk.Label(
            self._tolerance_section, text="⚖ Gewichtstoleranzen",
            bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
            font=FONTS['heading_md'],
        )
        heading.pack(anchor='w', pady=(SPACING['sm'], SPACING['sm']), padx=SPACING['sm'])

        info = tk.Label(
            self._tolerance_section,
            text=("Kleider-Abzug pro Geschlecht und Altersgruppe (kg).\n"
                  "Wird beim Berechnen der Gewichtsklasse abgezogen."),
            bg=COLORS['bg_panel'], fg=COLORS['text_muted'],
            font=FONTS['body_sm'], justify='left',
        )
        info.pack(anchor='w', padx=SPACING['sm'], pady=(0, SPACING['md']))

        # Header row
        header_row = create_dark_frame(self._tolerance_section)
        header_row.pack(fill=tk.X, pady=(0, SPACING['xs']), padx=SPACING['sm'])
        tk.Label(header_row, text="", width=8, bg=COLORS['bg_panel']).pack(side=tk.LEFT)
        for gender_code, gender_label in _GENDERS:
            lbl = tk.Label(
                header_row, text=gender_label, width=12, anchor='center',
                bg=COLORS['bg_panel'], fg=COLORS['text_secondary'],
                font=FONTS['body_sm'],
            )
            lbl.pack(side=tk.LEFT, padx=SPACING['xs'])

        # Rows
        current = self._current_tolerances()
        for age in _AGE_GROUPS:
            row = create_dark_frame(self._tolerance_section)
            row.pack(fill=tk.X, pady=SPACING['xs'], padx=SPACING['sm'])

            tk.Label(
                row, text=age, width=8, anchor='w',
                bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                font=FONTS['body_md'],
            ).pack(side=tk.LEFT)

            for gender_code, _label in _GENDERS:
                key = (gender_code, age)
                val = current.get(key, 0.0)
                var = tk.StringVar(value=self._fmt(val))
                self._tolerance_vars[key] = var
                self._build_tolerance_cell(row, var)

        # Apply button
        apply_row = create_dark_frame(self._tolerance_section)
        apply_row.pack(fill=tk.X, pady=SPACING['md'], padx=SPACING['sm'])
        btn = tk.Button(apply_row, text="Toleranzen anwenden", command=self._save_tolerances)
        apply_button_style(btn, 'primary')
        btn.pack(side=tk.RIGHT)

    def _build_tolerance_cell(self, parent, var: tk.StringVar):
        frame = tk.Frame(
            parent, bg=COLORS['bg_input'],
            highlightthickness=1, highlightbackground=COLORS['border'],
        )
        frame.pack(side=tk.LEFT, padx=SPACING['xs'])

        def validate(p):
            if p == "":
                return True
            try:
                float(p); return True
            except ValueError:
                return False
        vcmd = (parent.register(validate), '%P')

        entry = tk.Entry(
            frame, textvariable=var, width=6,
            bg=COLORS['bg_input'], fg=COLORS['text_primary'],
            font=FONTS['list_mono'], bd=0,
            validate="key", validatecommand=vcmd,
            insertbackground=COLORS['text_primary'],
        )
        entry.pack(side=tk.LEFT, fill=tk.Y, ipady=2, padx=4)

        btn_frame = tk.Frame(frame, bg=COLORS['bg_panel'])
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        def step(amount):
            try:
                v = float(var.get() or 0)
            except ValueError:
                v = 0.0
            v = max(0.0, round(v + amount, 4))
            var.set(self._fmt(v))

        up = tk.Button(btn_frame, text="▲", font=FONTS['preview_hint'],
                       bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                       bd=0, padx=2, pady=0, command=lambda: step(0.1))
        up.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        down = tk.Button(btn_frame, text="▼", font=FONTS['preview_hint'],
                         bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                         bd=0, padx=2, pady=0, command=lambda: step(-0.1))
        down.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _save_tolerances(self):
        store = getattr(self.main_window, 'tolerances', None)
        if store is None:
            store = {}
            self.main_window.tolerances = store

        changed = 0
        for key, var in self._tolerance_vars.items():
            try:
                val = max(0.0, round(float(var.get() or 0), 4))
            except ValueError:
                val = 0.0
            if store.get(key, 0.0) != val:
                store[key] = val
                changed += 1

        if not changed:
            return

        self.logger.info(f"Saved {changed} tolerance changes from config screen")

        # Actually re-bucket the participants — without this step the
        # tolerance is just stored but nothing moves into the lower class.
        moved = self._apply_tolerances_to_existing_brackets()

        # Refresh any open downstream screens so they recompute.
        sm = getattr(self.main_window, 'screen_manager', None)
        if sm:
            sm.mark_screen_stale('group_preview')
            sm.mark_screen_stale('generation_method')
            sm.mark_screen_stale('bracket_viewer')

        if moved:
            messagebox.showinfo(
                "Toleranzen angewendet",
                f"{moved} Teilnehmer wurde(n) in eine andere Gewichtsklasse verschoben.",
            )

    def _apply_tolerances_to_existing_brackets(self) -> int:
        """For every participant in main_window.brackets, recompute the
        weight class with the (possibly new) per-group tolerance subtracted
        from the weight. If a participant ends up in a different class,
        move them to that bracket (locked age classes are skipped).

        Returns the number of participants moved.
        """
        if not self.main_window or not getattr(self.main_window, 'brackets', None):
            return 0

        # Load a fresh ConfigRepository — same path as group_preview_screen
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'config', 'bracket_config.xlsx'
            )
            config_repo = ConfigRepository(config_path)
        except Exception as exc:
            self.logger.warning(f"Could not load ConfigRepository for tolerance re-apply: {exc}")
            return 0

        tolerances = getattr(self.main_window, 'tolerances', {}) or {}
        brackets = self.main_window.brackets
        locked_full = getattr(self.main_window, 'locked_age_classes', set()) or set()
        locked_ages = {scope.split('|', 1)[1] if '|' in scope else scope for scope in locked_full}

        # Collect planned moves first to avoid mutating the dict mid-iteration.
        planned = []  # list of (old_key, fighter_idx, new_key)
        for bracket_key, bracket_data in list(brackets.items()):
            if bracket_key.startswith('QUARANTINE_'):
                continue
            try:
                gender, age_group, _wc = parse_bracket_key(bracket_key)
            except ValueError:
                continue
            if age_group in locked_ages:
                continue

            tol = float(tolerances.get((gender, age_group), 0.0) or 0.0)
            if tol <= 0:
                continue

            # Some bracket dicts store the list under 'fighters', some under
            # 'participants' (quarantine + import paths differ). Read both,
            # and remember which key the bracket uses so we can write back.
            list_key = 'fighters' if 'fighters' in bracket_data else 'participants'
            fighters = list(bracket_data.get(list_key, []))
            self.logger.debug(
                f"[TOLERANCE] {bracket_key}: tol={tol}, {len(fighters)} fighter(s), list_key={list_key}"
            )
            for idx, fighter in enumerate(fighters):
                raw_w = fighter.get('Weight', fighter.get('weight'))
                try:
                    weight = float(raw_w) if raw_w is not None else 0.0
                except (TypeError, ValueError):
                    self.logger.debug(f"[TOLERANCE]   skip {fighter.get('Lastname','?')}: bad weight {raw_w!r}")
                    continue
                if weight <= 0:
                    continue
                try:
                    new_wc = config_repo.get_weight_class(weight - tol, gender, age_group)
                except Exception as exc:
                    self.logger.debug(f"[TOLERANCE]   skip {fighter.get('Lastname','?')}: get_weight_class failed: {exc}")
                    continue
                if not new_wc or new_wc == 'unknown' or new_wc == _wc:
                    continue

                new_key = f"{gender} | {age_group} | {new_wc}"
                self.logger.info(
                    f"[TOLERANCE] move {fighter.get('Firstname','')} {fighter.get('Lastname','?')} "
                    f"({weight}kg - {tol}kg = {weight - tol}kg) {bracket_key} → {new_key}"
                )
                planned.append((bracket_key, idx, new_key, fighter, list_key))

        if not planned:
            return 0

        # Execute moves — pop from the back of each source bracket so earlier
        # indices stay valid. Group planned by (old_key) and process from
        # highest idx down.
        from collections import defaultdict
        by_src = defaultdict(list)
        for old_key, idx, new_key, fighter, list_key in planned:
            by_src[old_key].append((idx, new_key, fighter, list_key))

        moved = 0
        for old_key, items in by_src.items():
            for idx, new_key, fighter, list_key in sorted(items, key=lambda t: -t[0]):
                old_list = brackets[old_key].get(list_key, [])
                if 0 <= idx < len(old_list):
                    old_list.pop(idx)
                # Destination uses the same list_key as source for symmetry.
                if new_key not in brackets:
                    brackets[new_key] = {list_key: [], 'bracket': []}
                brackets[new_key].setdefault(list_key, []).append(fighter)
                brackets[new_key]['bracket'] = []  # invalidate seeding/pairings
                moved += 1
            # Invalidate the source seeding too — class composition changed
            brackets[old_key]['bracket'] = []

        self.logger.info(f"[TOLERANCE] Re-bucketed {moved} participant(s) after tolerance change")
        return moved

    def _current_tolerances(self) -> dict:
        """Read tolerances from main_window — single source of truth."""
        return getattr(self.main_window, 'tolerances', {}) or {}

    @staticmethod
    def _fmt(val) -> str:
        formatted = f"{float(val):.4f}".rstrip('0')
        if formatted.endswith('.'):
            formatted += '0'
        return formatted
