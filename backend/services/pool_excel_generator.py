# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Pool score-sheet export.

Produces the official German "Poolsystem" Wertungsbogen by filling the
pre-formatted .xls template (see :mod:`backend.services.excel_form_filler`).
The previous hand-built openpyxl layout has been replaced by template filling so
the output matches the printed forms 1:1.
"""

from typing import List, Dict, Any

from utils.logging import get_logger
from backend.services.excel_form_filler import fill_pool_form

logger = get_logger('pool_excel_generator')


class PoolExcelGenerator:
    """Generate the Poolsystem score sheet (single or double pool)."""

    def __init__(self):
        self.logger = logger

    def generate_pools_excel(self,
                             output_path: str,
                             pools_data: List[Dict[str, Any]],
                             title: str = "Tournament Pools",
                             include_finale: bool = True) -> bool:
        """Fill the pool template. 1 pool -> "Einfach", 2 pools -> "2 Pools"
        (the finale cascade is pre-printed in the template).

        ``include_finale`` is retained for call-site compatibility but no longer
        controls drawing — the template determines the layout.
        """
        return fill_pool_form(output_path, pools_data, age_class=title)
