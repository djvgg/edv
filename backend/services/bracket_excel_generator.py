# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Double-KO bracket export.

Produces the official German "Doppel-KO-System" sheet by filling the
pre-formatted 8/16/32 .xls template (see
:mod:`backend.services.excel_form_filler`). The participant count is rounded up
to the next template size; empty seeds become "Freilos". The previous
algorithmic openpyxl tree has been replaced by template filling so the output
matches the printed diagrams 1:1.
"""

import os
from typing import List, Dict, Tuple

from utils.logging import get_logger
from backend.services.excel_form_filler import fill_ko_form

logger = get_logger('bracket_excel_generator')


class BracketExcelGenerator:
    """Generate the Doppel-KO-System sheet from a template."""

    def __init__(self):
        self.logger = logger

    def generate_bracket_excel(self,
                               output_path: str,
                               fighters: List[Dict],
                               bracket_type: str = 'double',
                               title: str = "Tournament Bracket") -> bool:
        """Fill the KO template (rounded up to 8/16/32, extra seeds = Freilos).

        ``bracket_type`` is retained for call-site compatibility; the template is
        always the double-KO form.
        """
        return fill_ko_form(output_path, fighters, age_class=title)

    def generate_bracket_with_pdf(self,
                                  output_excel_path: str,
                                  output_pdf_path: str,
                                  fighters: List[Dict],
                                  bracket_type: str = 'double',
                                  title: str = "Tournament Bracket") -> Tuple[bool, bool]:
        """Generate the .xls form and, where Excel COM is available (Windows),
        a PDF export."""
        excel_ok = self.generate_bracket_excel(output_excel_path, fighters, bracket_type, title)
        xls_path = os.path.splitext(output_excel_path)[0] + '.xls'

        pdf_ok = False
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            wb = excel.Workbooks.Open(os.path.abspath(xls_path))
            wb.ExportAsFixedFormat(0, os.path.abspath(output_pdf_path))  # 0 = PDF
            wb.Close()
            excel.Quit()
            self.logger.info(f"✓ Bracket PDF created: {output_pdf_path}")
            pdf_ok = True
        except ImportError:
            self.logger.warning("pywin32 not available, skipping PDF export")
        except Exception as e:
            self.logger.warning(f"PDF export failed: {e}")

        return excel_ok, pdf_ok


# Convenience functions
def create_bracket_excel(output_path: str,
                         fighters: List[Dict],
                         bracket_type: str = 'double',
                         title: str = "Tournament Bracket") -> bool:
    """Create the Doppel-KO-System .xls form."""
    return BracketExcelGenerator().generate_bracket_excel(output_path, fighters, bracket_type, title)


def create_bracket_excel_and_pdf(excel_path: str,
                                 pdf_path: str,
                                 fighters: List[Dict],
                                 bracket_type: str = 'double',
                                 title: str = "Tournament Bracket") -> Tuple[bool, bool]:
    """Create the .xls form and (Windows COM) a PDF."""
    return BracketExcelGenerator().generate_bracket_with_pdf(excel_path, pdf_path, fighters, bracket_type, title)
