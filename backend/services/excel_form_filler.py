# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Fill the official German tournament forms (Poolsystem / Doppel-KO-System) by
writing participant names into pre-formatted .xls templates.

Rationale: the score sheets and double-KO diagrams are fixed printed forms whose
layout (merged cells, borders, the bracket diagram drawn entirely from cell
borders) cannot be faithfully re-created cell-by-cell in openpyxl. Instead we open
the original .xls template, write the names into the known slot cells while
cloning each cell's original style so borders/fonts survive, and save .xls.

Templates live in ``backend/services/templates/`` and were captured 1:1 from the
example files in ``Beispieldateien/``:

  - pool_listen.xls : sheet "Einfach" (single pool) + "2 Pools" (double pool)
  - ko_8.xls / ko_16.xls : sheet "Wettkampfliste" (Doppel-KO 8 / 16)
  - ko_32.xls : sheet "Liste" (Doppel-KO 32)

The "Wiegeliste" sheet present in the KO templates is intentionally left blank.
"""

import os
from typing import List, Dict, Any, Optional

import xlrd
import xlwt
from xlutils.copy import copy as xl_copy

from utils.logging import get_logger

logger = get_logger('excel_form_filler')

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

# --- Slot maps (derived from the templates, see module docstring) ------------

# KO layouts: read the Los number from ``los_col`` of each name row and place the
# fighter seeded to that Los into ``name_col``. ``heading`` is the prominent title
# cell we append the age/weight class to; ``kg`` is the "kg" box (8/16 only).
_KO_LAYOUTS = {
    8:  {'template': 'ko_8.xls',  'sheet': 1, 'rows': range(11, 19), 'los_col': 0, 'name_col': 1, 'style': 'name',        'heading': (0, 1), 'kg': (2, 2)},
    16: {'template': 'ko_16.xls', 'sheet': 1, 'rows': range(11, 27), 'los_col': 0, 'name_col': 1, 'style': 'name',        'heading': (0, 1), 'kg': (2, 2)},
    32: {'template': 'ko_32.xls', 'sheet': 0, 'rows': range(9, 41),  'los_col': 2, 'name_col': 3, 'style': 'name_verein', 'heading': (0, 3), 'kg': None},
}

# Pool layouts: sequential name rows (Start-Nr. is pre-printed), no Los lookup.
# ``heading`` = "Poolsystem" title cell, ``altersklasse`` = the labelled header
# field, ``pool_labels`` = the pre-printed "Pool A"/"Pool B" cells (double only).
# ``header_rows`` holds, per block, the row carrying the pre-printed Kampfnummer
# cells (one entry per ``blocks`` entry); used to renumber shortened pools.
_POOL_TEMPLATE = 'pool_listen.xls'
_POOL_SINGLE = {'sheet': 0, 'blocks': [range(7, 12)], 'name_col': 2, 'header_rows': [6],
                'heading': (0, 1), 'altersklasse': (2, 22), 'pool_labels': []}
_POOL_DOUBLE = {'sheet': 1, 'blocks': [range(7, 12), range(18, 23)], 'name_col': 2,
                'header_rows': [6, 17],
                'heading': (0, 1), 'altersklasse': (2, 22), 'pool_labels': [(4, 1), (15, 1)]}

# The pool score grid is a fixed DJB 5-slot / 10-fight form. Each fight occupies
# two columns (score + Unter-bewertung); the score column is the key here and the
# Ubw column is always ``score_col + 1``. The grid shading hard-codes which two
# (1-indexed) slots fight in each column — this mapping is a function of the
# column position and is identical on both the "Einfach" and "2 Pools" sheets.
# Captured 1:1 from the template; see the module docstring.
_POOL_COL_PAIRS = {
    5:  (1, 4), 7:  (2, 5), 9:  (1, 3), 11: (2, 4), 13: (3, 5),
    15: (1, 2), 17: (3, 4), 19: (1, 5), 21: (2, 3), 23: (4, 5),
}

# Canonical DJB fight order per pool size (1-indexed slot pairs), mirroring
# bracket_reconstruction_service._generate_fight_schedule. Used to renumber the
# shortened pools so a fighter doesn't fight in consecutive bouts where the
# round-robin allows it. A 4er pool can't fully avoid it (2 repeats are
# unavoidable for 6 bouts among 4 fighters) — this is the established minimum.
# The full 5er form keeps the template's own order, which is already conflict-free.
_POOL_FIGHT_ORDER = {
    3: [(1, 3), (2, 3), (1, 2)],
    4: [(1, 4), (2, 3), (1, 3), (2, 4), (1, 2), (3, 4)],
}


def _class_label(title: Optional[str]) -> tuple[str, str, str]:
    """Parse a bracket key ('m | U13 | -50kg') into (age, weight, gender).

    Returns ('', '', '') when the title is empty or not in the 3-part format.
    """
    if not title:
        return '', '', ''
    try:
        from utils.helpers import parse_bracket_key
        gender, age, weight = parse_bracket_key(title)
        return age.strip(), weight.strip(), gender.strip()
    except Exception:
        return '', '', ''


def _class_str(title: Optional[str]) -> str:
    """Human heading fragment: 'U13 -50kg' (falls back to the raw title)."""
    age, weight, _ = _class_label(title)
    parts = [p for p in (age, weight) if p]
    return ' '.join(parts) if parts else str(title or '').strip()


# --- style cloning -----------------------------------------------------------

def _clone_style(rb: xlrd.Book, xf_index: int) -> xlwt.XFStyle:
    """Build an xlwt style replicating an xlrd cell's font, borders, alignment
    and solid fill, so overwriting a templated cell preserves its look."""
    xf = rb.xf_list[xf_index]
    fnt = rb.font_list[xf.font_index]

    st = xlwt.XFStyle()

    f = xlwt.Font()
    f.name = fnt.name
    f.bold = bool(fnt.bold)
    f.height = fnt.height
    f.italic = bool(fnt.italic)
    f.colour_index = fnt.colour_index
    st.font = f

    # xlrd line-style codes share the BIFF numbering used by xlwt borders.
    b = xlwt.Borders()
    b.left = xf.border.left_line_style
    b.right = xf.border.right_line_style
    b.top = xf.border.top_line_style
    b.bottom = xf.border.bottom_line_style
    st.borders = b

    al = xlwt.Alignment()
    al.horz = xf.alignment.hor_align
    al.vert = xf.alignment.vert_align
    al.wrap = xf.alignment.text_wrapped
    st.alignment = al

    if xf.background.fill_pattern == 1:  # solid
        pat = xlwt.Pattern()
        pat.pattern = xlwt.Pattern.SOLID_PATTERN
        pat.pattern_fore_colour = xf.background.pattern_colour_index
        st.pattern = pat

    return st


class _FormWriter:
    """Wraps an xlutils copy and writes into cells while preserving their style."""

    def __init__(self, template_path: str):
        self._rb = xlrd.open_workbook(template_path, formatting_info=True)
        self._wb = xl_copy(self._rb)
        self._style_cache: Dict[int, xlwt.XFStyle] = {}

    def write(self, sheet_index: int, row: int, col: int, value: Any) -> None:
        rsheet = self._rb.sheet_by_index(sheet_index)
        xf_index = rsheet.cell_xf_index(row, col)
        style = self._style_cache.get(xf_index)
        if style is None:
            style = _clone_style(self._rb, xf_index)
            self._style_cache[xf_index] = style
        self._wb.get_sheet(sheet_index).write(row, col, value, style)

    def read(self, sheet_index: int, row: int, col: int) -> Any:
        return self._rb.sheet_by_index(sheet_index).cell_value(row, col)

    def restyle(self, sheet_index: int, dst_row: int, dst_col: int,
                src_row: int, src_col: int, value: Any = '') -> None:
        """Write ``value`` into a cell using the style cloned from another cell.

        Used to re-open a natively shaded score cell by copying an open cell's
        style (white fill, full borders), e.g. for a 2-person best-of-three.
        """
        rsheet = self._rb.sheet_by_index(sheet_index)
        xf_index = rsheet.cell_xf_index(src_row, src_col)
        style = self._style_cache.get(xf_index)
        if style is None:
            style = _clone_style(self._rb, xf_index)
            self._style_cache[xf_index] = style
        self._wb.get_sheet(sheet_index).write(dst_row, dst_col, value, style)

    def hide_col(self, sheet_index: int, col: int) -> None:
        # xlutils preserves the source column width on the copy; toggling
        # ``hidden`` keeps it, so the kept columns stay at their printed width.
        self._wb.get_sheet(sheet_index).col(col).hidden = True

    def hide_row(self, sheet_index: int, row: int) -> None:
        self._wb.get_sheet(sheet_index).row(row).hidden = True

    def save(self, output_path: str) -> None:
        self._wb.save(output_path)


# --- name formatting ---------------------------------------------------------

def _name_parts(fighter: Any) -> tuple[str, str]:
    """Return (display_name, verein) for a fighter dict/tuple/str.

    ``Name`` upstream is "Vorname Nachname"; the forms want "Nachname, Vorname".
    """
    if isinstance(fighter, dict):
        raw = fighter.get('Name') or fighter.get('name') or ''
        verein = fighter.get('Verein') or fighter.get('Club') or fighter.get('club') or ''
    elif isinstance(fighter, (list, tuple)):
        raw = fighter[0] if fighter else ''
        verein = fighter[1] if len(fighter) > 1 else ''
    else:
        raw = str(fighter or '')
        verein = ''

    raw = str(raw).strip()
    if not raw:
        return '', str(verein or '').strip()
    if ',' in raw:                       # already "Nachname, Vorname"
        return raw, str(verein or '').strip()
    parts = raw.split()
    if len(parts) == 1:
        return raw, str(verein or '').strip()
    first, last = parts[0], ' '.join(parts[1:])
    return f"{last}, {first}", str(verein or '').strip()


def _format_name(fighter: Any, style: str) -> str:
    display, verein = _name_parts(fighter)
    if not display:
        return ''
    if style == 'name_verein' and verein:
        return f"{display}, {verein}"
    return display


# --- public API --------------------------------------------------------------

# Score columns reused for the three best-of-three bouts (left-most three).
_BO3_SCORE_COLS = (5, 7, 9)


def _render_best_of_three(writer: '_FormWriter', sheet: int, layout: Dict[str, Any]) -> None:
    """Turn the single-pool sheet into a 2-fighter best-of-three card.

    Shows three bouts of fighter 1 vs fighter 2. Only one template column is
    natively the (1,2) pairing, so the other two bout columns are re-opened by
    copying that column's open (white, fully bordered) cell style onto slots 1
    and 2 of both sub-columns (score + Unter-bewertung). All remaining fight
    columns and the empty slot rows 3-5 are hidden.
    """
    rows = list(layout['blocks'][0])      # slot rows; slot 1 = rows[0], slot 2 = rows[1]
    slot1, slot2 = rows[0], rows[1]
    header_row = layout['header_rows'][0]
    src = next(c for c, pair in _POOL_COL_PAIRS.items() if set(pair) == {1, 2})  # col 15

    for number, score_col in enumerate(_BO3_SCORE_COLS, start=1):
        for sub in (0, 1):               # score sub-col + Unter-bewertung sub-col
            for slot_row in (slot1, slot2):
                writer.restyle(sheet, slot_row, score_col + sub, slot_row, src + sub)
        writer.write(sheet, header_row, score_col, number)

    # Hide every fight column not used by the three bouts.
    kept = set(_BO3_SCORE_COLS) | {c + 1 for c in _BO3_SCORE_COLS}
    for col in range(5, 25):
        if col not in kept:
            writer.hide_col(sheet, col)

    # Hide the empty slot rows (3-5).
    for slot_row in rows[2:]:
        writer.hide_row(sheet, slot_row)


def _shorten_pool_grid(writer: '_FormWriter', sheet: int, layout: Dict[str, Any],
                       block_sizes: List[int]) -> None:
    """Trim the 5-slot grid down to the fights a smaller pool actually needs.

    Hides the empty slot rows of each under-filled block, and — when *every*
    populated block agrees a fight column is unused (its pairing references a
    slot beyond the pool) — hides that fight's two columns so the printed form
    is physically narrower. Surviving fights are renumbered 1..k.

    The both-columns-shared "2 Pools" sheet means a column can only be hidden if
    neither pool needs it; a mixed 4/5 double pool therefore keeps the full grid
    (a deliberate, accepted limitation — slot-5 columns are still needed by the
    5-pool). Row hiding is per-block and always applies.
    """
    populated = [s for s in block_sizes if s > 0]
    if not populated or min(populated) >= 5:
        return  # nothing under-filled -> leave the full form untouched

    # A lone 2-fighter pool is run best-of-three (see pool_renderer's fight
    # schedule). Only on the single-pool sheet — a 2-person "double pool" is
    # nonsensical and would clash with the other block over the shared columns.
    if len(layout['blocks']) == 1 and block_sizes[0] == 2:
        _render_best_of_three(writer, sheet, layout)
        return

    # Hide the empty trailing slot rows of each block.
    for block_idx, rows in enumerate(layout['blocks']):
        size = block_sizes[block_idx] if block_idx < len(block_sizes) else 0
        for slot, row in enumerate(rows):
            if slot + 1 > size:
                writer.hide_row(sheet, row)

    # A column is needed if any populated pool fields both its slots.
    hidden_cols = set()
    for score_col, (a, b) in _POOL_COL_PAIRS.items():
        needed = any(max(a, b) <= size for size in populated)
        if not needed:
            writer.hide_col(sheet, score_col)
            writer.hide_col(sheet, score_col + 1)
            hidden_cols.add(score_col)

    if not hidden_cols:
        return  # mixed sizes on a shared-column sheet -> keep original numbering

    # Renumber the surviving fights in the canonical rest-aware order, 1..k across
    # blocks. The fight number drives the run order; the column drives the pairing
    # (fixed by the grid shading), so numbering out of left-to-right order is fine.
    col_by_pair = {frozenset(pair): col for col, pair in _POOL_COL_PAIRS.items()}
    num = 1
    for block_idx, header_row in enumerate(layout['header_rows']):
        size = block_sizes[block_idx] if block_idx < len(block_sizes) else 0
        for pair in _POOL_FIGHT_ORDER.get(size, []):
            col = col_by_pair.get(frozenset(pair))
            if col is None or col in hidden_cols:
                continue
            writer.write(sheet, header_row, col, num)
            num += 1


def fill_pool_form(output_path: str,
                   pools_data: List[Dict[str, Any]],
                   age_class: Optional[str] = None) -> bool:
    """Fill the Poolsystem score sheet (single or double pool) from a template.

    Args:
        output_path: target .xls path (extension is normalised to .xls)
        pools_data: list of {'pool_name', 'fighters'}; 1 pool -> "Einfach",
            2 pools -> "2 Pools". Each pool holds up to 5 fighters.
        age_class: optional label written into the "Altersklasse" header field.
    """
    try:
        output_path = os.path.splitext(output_path)[0] + '.xls'
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        layout = _POOL_DOUBLE if len(pools_data) >= 2 else _POOL_SINGLE
        sheet = layout['sheet']
        name_col = layout['name_col']

        writer = _FormWriter(os.path.join(_TEMPLATE_DIR, _POOL_TEMPLATE))

        block_sizes = []
        for block_idx, rows in enumerate(layout['blocks']):
            fighters = pools_data[block_idx].get('fighters', []) if block_idx < len(pools_data) else []
            block_sizes.append(len(fighters))
            for slot, row in enumerate(rows):
                name = _format_name(fighters[slot], 'name') if slot < len(fighters) else ''
                if name:
                    writer.write(sheet, row, name_col, name)

        # Trim the grid to a 3er/4er pool's actual fights (hide unused columns/rows).
        _shorten_pool_grid(writer, sheet, layout, block_sizes)

        age, weight, gender = _class_label(age_class)
        cls = _class_str(age_class)

        # Heading cell: "Poolsystem  —  U13 -50kg"
        if cls:
            base = str(writer.read(sheet, *layout['heading']) or '').strip()
            _write_header_field(writer, sheet, *layout['heading'],
                                f"{base}  —  {cls}" if base else cls)

        # Labelled header field: "Altersklasse: U13   Gewicht: -50kg"
        if age or weight:
            field = "Altersklasse:"
            if age:
                field += f" {age}"
            if weight:
                field += f"   Gewicht: {weight}"
            _write_header_field(writer, sheet, *layout['altersklasse'], field)

        # Pre-printed "Pool A"/"Pool B" cells -> add the group number (double only).
        for block_idx, cell in enumerate(layout['pool_labels']):
            base = str(writer.read(sheet, *cell) or '').strip()
            if base:
                _write_header_field(writer, sheet, *cell, f"{base}  (Gr. {block_idx + 1})")

        writer.save(output_path)
        logger.info(f"✓ Pool form created: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error filling pool form: {e}", exc_info=True)
        return False


def fill_ko_form(output_path: str,
                 fighters: List[Any],
                 age_class: Optional[str] = None) -> bool:
    """Fill the Doppel-KO-System diagram from the 8/16/32 template.

    The participant count is rounded up to the next template size (8/16/32);
    empty seeds become "Freilos". Counts > 32 are not supported by a template.

    Args:
        output_path: target .xls path (extension normalised to .xls)
        fighters: seeded list; fighter at index i is placed at Los i+1.
        age_class: optional label written into the "kg" header field.
    """
    try:
        output_path = os.path.splitext(output_path)[0] + '.xls'
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        n = len(fighters)
        size = next((s for s in (8, 16, 32) if n <= s), None)
        if size is None:
            logger.error(f"KO form: {n} fighters exceeds largest template (32)")
            return False

        layout = _KO_LAYOUTS[size]
        sheet = layout['sheet']
        writer = _FormWriter(os.path.join(_TEMPLATE_DIR, layout['template']))

        # Map Los number -> fighter (seeded order); missing slots become Freilos.
        los_to_name = {}
        for i in range(size):
            los = i + 1
            los_to_name[los] = _format_name(fighters[i], layout['style']) if i < n else 'Freilos'

        for row in layout['rows']:
            los_val = writer.read(sheet, row, layout['los_col'])
            try:
                los = int(los_val)
            except (TypeError, ValueError):
                continue
            name = los_to_name.get(los, '')
            if name:
                writer.write(sheet, row, layout['name_col'], name)

        age, weight, gender = _class_label(age_class)
        cls = _class_str(age_class)

        # Heading cell: "Doppel-KO-System / N Teilnehmer  —  U13 -50kg"
        if cls:
            base = str(writer.read(sheet, *layout['heading']) or '').strip()
            _write_header_field(writer, sheet, *layout['heading'],
                                f"{base}  —  {cls}" if base else cls)

        # "kg" box (8/16 only) -> the weight class; the 32 "Liste" has no kg box.
        if layout['kg'] and weight:
            _write_header_field(writer, sheet, *layout['kg'], weight)

        writer.save(output_path)
        logger.info(f"✓ KO form created ({size}er): {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error filling KO form: {e}", exc_info=True)
        return False


def _write_header_field(writer: _FormWriter, sheet: int, row: int, col: int, text: str) -> None:
    """Best-effort header label; never fail the whole export over a header."""
    try:
        writer.write(sheet, row, col, text)
    except Exception as e:
        logger.debug(f"Header field ({row},{col}) skipped: {e}")
