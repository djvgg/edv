# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""CSV (de)serialization for the contestants exchange.

Sibling format to ``contestants_*.json`` — a 1:1 mirror of the same schema,
read/written by both edv and WeighIn. See the ``contestants_*.csv`` cross-repo
invariant in ``WSP/CLAUDE.md`` (Decision 2026-06-03).

Contract:
- Columns (canonical order, header row mandatory, English JSON keys):
  ``ID;Firstname;Lastname;Birthyear;Club;Association;Weight;Valid;Gender;Paid;Doublestart``
- Delimiter ``;``, encoding UTF-8 **with BOM** (write BOM; read ``utf-8-sig``) —
  German Excel uses ``;`` as the list separator and needs the BOM for UTF-8.
- Write canonically: int ``ID``/``Birthyear``, ``Weight`` with ``.`` decimal,
  ``Valid``/``Paid`` as lowercase ``true``/``false``, ``Gender`` verbatim,
  ``Doublestart`` verbatim wire value.
- Read tolerantly: bool accepts true/false/1/0/ja/nein/yes/no (case-insensitive);
  ``Weight`` accepts ``.`` and ``,``; ``Doublestart`` from column ``Doublestart``
  OR legacy ``mode``; missing optional columns default.

The read path returns dicts with the SAME native types as ``json.load`` would,
so downstream validation/normalization is identical for CSV and JSON inputs.
"""

import csv
from typing import Any, Dict, List

CONTESTANTS_CSV_FIELDS = [
    "ID", "Firstname", "Lastname", "Birthyear", "Club",
    "Association", "Weight", "Valid", "Gender", "Paid", "Doublestart",
]

CSV_DELIMITER = ";"
CSV_ENCODING = "utf-8-sig"  # BOM on write, BOM-tolerant on read

_TRUE_TOKENS = {"true", "1", "ja", "yes", "y", "wahr", "x"}
_FALSE_TOKENS = {"false", "0", "nein", "no", "n", "falsch", ""}


def _parse_bool(value: Any) -> bool:
    """Tolerant bool parse mirroring the JSON path's downstream expectations."""
    if isinstance(value, bool):
        return value
    token = str(value or "").strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    # Unknown token -> treat as False (conservative: an unrecognised "Valid"
    # must not silently pass a fighter as valid).
    return False


def _parse_weight(value: Any):
    """Parse a weight allowing both ``.`` and ``,`` decimals. Returns float on
    success, else the raw value (so the caller's validation can flag it)."""
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return value


def _parse_int(value: Any):
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return value  # leave raw; downstream validation will flag it


def _format_weight(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return repr(value)  # JSON-faithful: 26.3 -> "26.3", 0.0 -> "0.0"
    return str(value)


def read_contestants_csv(path: str) -> List[Dict[str, Any]]:
    """Read a ``contestants_*.csv`` into a list of participant dicts with native
    types (mirrors ``json.load`` output for the same data)."""
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding=CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        for row in reader:
            if row is None:
                continue
            # Skip fully blank rows (trailing newlines, separator-only lines).
            if not any(str(v or "").strip() for v in row.values()):
                continue

            def get(key: str):
                v = row.get(key)
                return v.strip() if isinstance(v, str) else v

            d: Dict[str, Any] = {}

            if str(get("ID") or "").strip():
                d["ID"] = _parse_int(get("ID"))
            for key in ("Firstname", "Lastname", "Club", "Association", "Gender"):
                v = get(key)
                if v is not None:
                    d[key] = v or ""
            if str(get("Birthyear") or "").strip():
                d["Birthyear"] = _parse_int(get("Birthyear"))
            if str(get("Weight") or "").strip():
                d["Weight"] = _parse_weight(get("Weight"))
            for key in ("Valid", "Paid"):
                v = get(key)
                if v is not None and str(v).strip() != "":
                    d[key] = _parse_bool(v)
            # Doublestart from the canonical column OR the legacy `mode` column.
            ds = get("Doublestart") or get("mode")
            if ds:
                d["Doublestart"] = ds

            out.append(d)
    return out


def write_contestants_csv(path: str, contestants: List[Dict[str, Any]]) -> None:
    """Write participant dicts to a ``contestants_*.csv`` in the canonical form."""
    with open(path, "w", encoding=CSV_ENCODING, newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=CONTESTANTS_CSV_FIELDS, delimiter=CSV_DELIMITER,
            extrasaction="ignore", lineterminator="\r\n",
        )
        writer.writeheader()
        for c in contestants:
            row: Dict[str, Any] = {}
            for key in CONTESTANTS_CSV_FIELDS:
                value = c.get(key)
                if key in ("Valid", "Paid"):
                    row[key] = "true" if _parse_bool(value) else "false"
                elif key == "Doublestart":
                    # `mode` first: WeighIn's legacy `mode` is the fresh UI edit
                    # and must win over a stale `Doublestart` carried in from a
                    # prior load; edv-internal dicts never carry `mode`.
                    ds = c.get("mode") or c.get("Doublestart")
                    row[key] = str(ds).strip() if ds else "standard"
                elif key == "Weight":
                    row[key] = _format_weight(value)
                elif value is None:
                    row[key] = ""
                else:
                    row[key] = value
            writer.writerow(row)
