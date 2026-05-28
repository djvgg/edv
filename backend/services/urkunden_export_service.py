# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Urkunden-Export — Datenquelle für den LibreOffice-Serienbrief.

Erzeugt eine XLSX mit *einer Zeile pro vergebener Platzierung* für eine
ausgewählte Menge fertiger Brackets. Das Rendering (vorgedruckte Urkunde,
Feldpositionen, Druck) lebt bewusst NICHT hier, sondern in einer
hand-positionierten LibreOffice-Vorlage (siehe ``assets/urkunden/``).

Betriebsannahme: läuft mehrfach während des Turniers. Die XLSX hat einen
festen Pfad und wird pro Lauf überschrieben, damit die LO-Vorlage die
Datenquelle nur einmal registrieren muss.

Doppeldruck-Vermeidung erfolgt über einen *weichen* Sidecar-Marker
(``urkunden_printed.json``) — bewusst KEIN DB-Status, damit Nachdruck
jederzeit möglich bleibt (Overlay-Druck staut sich).
"""

import json
import os
from typing import Any, Optional

from openpyxl import Workbook

from utils.logging import get_logger

logger = get_logger('urkunden_export_service')

# Spalten der Datenquelle = Seriendruckfeld-Namen in der LO-Vorlage.
COLUMNS = ['vorname', 'nachname', 'platz', 'klasse', 'verein']

# Feste Pfade relativ zum edv-Projektroot.
EXPORT_DIR = os.path.join('temp', 'exports')
XLSX_PATH = os.path.join(EXPORT_DIR, 'urkunden.xlsx')
SIDECAR_PATH = os.path.join(EXPORT_DIR, 'urkunden_printed.json')

_ORDINAL = {1: '1.', 2: '2.', 3: '3.'}
_GENDER_DE = {'m': 'männlich', 'w': 'weiblich'}
# Gewichtsklassen-Tokens, die "keine echte Klasse" bedeuten → weglassen.
_EMPTY_WEIGHT = {'', 'no-class', 'none', 'null', 'offen'}


def compose_class_label(group_name: str) -> str:
    """``'w | U13 | -40kg'`` → ``'U13 -40kg weiblich'``.

    Robust gegen nicht-kanonische Namen: ist der Name nicht im Schema
    ``gender | age_group | weight_class``, wird er unverändert zurückgegeben
    (kein Crash). Leere/`no-class`-Gewichtsklassen entfallen.
    """
    parts = [p.strip() for p in str(group_name).split('|')]
    if len(parts) != 3:
        return str(group_name).strip()

    gender, age_group, weight_class = parts
    gender_de = _GENDER_DE.get(gender.lower(), gender)
    tokens = [age_group]
    if weight_class.lower() not in _EMPTY_WEIGHT:
        tokens.append(weight_class)
    tokens.append(gender_de)
    return ' '.join(t for t in tokens if t)


def _ordinal(platz: Any) -> str:
    """Platz-Zahl → Ordinaltext ``'1.'``. Unbekanntes als ``'<wert>.'``."""
    try:
        return _ORDINAL.get(int(platz), f'{int(platz)}.')
    except (TypeError, ValueError):
        return str(platz)


class UrkundenExportService:
    """Baut die Urkunden-Datenquelle aus den Bracket-Platzierungen.

    ``db`` ist ein Objekt mit ``get_bracket_placements(key)`` und
    ``get_completed_bracket_keys()`` (Default: der DatabaseService-Singleton).
    Injektion erlaubt Tests ohne echte DB.
    """

    def __init__(self, db: Optional[Any] = None):
        self.logger = logger
        if db is None:
            from backend.services.database_service import (  # noqa: PLC0415
                get_database_service,
            )
            db = get_database_service()
        self.db = db

    # ----- Datenbeschaffung --------------------------------------------

    def completed_bracket_keys(self) -> set:
        """Group-Namen aller Brackets mit ``status='completed'``."""
        return self.db.get_completed_bracket_keys()

    def build_rows(self, bracket_keys) -> list:
        """Eine Zeile pro vergebener Platzierung über die gewählten Keys.

        Sortiert nach (klasse, platz). NULL-Plätze sind in
        ``get_bracket_placements`` bereits übersprungen; Doppelpool liefert
        korrekt vier Zeilen (zwei dritte Plätze).
        """
        rows = []
        for key in bracket_keys:
            klasse = compose_class_label(key)
            for p in self.db.get_bracket_placements(key):
                rows.append({
                    'vorname': p.get('vorname', ''),
                    'nachname': p.get('nachname', ''),
                    'platz': _ordinal(p.get('platz')),
                    'klasse': klasse,
                    'verein': p.get('verein', ''),
                })
        rows.sort(key=lambda r: (r['klasse'], r['platz']))
        return rows

    # ----- XLSX-Ausgabe -------------------------------------------------

    def export(self, bracket_keys, out_path: str = XLSX_PATH) -> dict:
        """Schreibt die Datenquelle und gibt eine Zusammenfassung zurück.

        Returns ``{'rows': int, 'brackets': int, 'path': str}``.
        Die Datei wird überschrieben (re-runnable während des Turniers).
        """
        bracket_keys = list(bracket_keys)
        rows = self.build_rows(bracket_keys)

        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = 'urkunden'
        ws.append(COLUMNS)
        for row in rows:
            ws.append([row[c] for c in COLUMNS])
        wb.save(out_path)

        result = {'rows': len(rows), 'brackets': len(bracket_keys),
                  'path': out_path}
        self.logger.info(f"Urkunden-Export: {result}")
        return result


# ----- Sidecar: weicher "schon exportiert"-Marker ----------------------

def load_exported_keys(path: str = SIDECAR_PATH) -> set:
    """Menge der Bracket-Keys, die bereits exportiert wurden.

    Fehlende/kaputte Datei → leere Menge (Marker ist wegwerfbar).
    """
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        return set(data) if isinstance(data, list) else set()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def mark_exported(bracket_keys, path: str = SIDECAR_PATH) -> set:
    """Fügt Keys zum Sidecar hinzu (Union) und gibt die neue Menge zurück."""
    keys = load_exported_keys(path) | set(bracket_keys)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(sorted(keys), fh, ensure_ascii=False, indent=2)
    return keys
