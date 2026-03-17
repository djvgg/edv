# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Printing Service - Orchestrates bracket PDF generation and printing.

Coordinates:
- PDF generation via BracketPDFGenerator
- Printer operations via PrinterService
- Temporary file management
"""

import os
import sys
import tempfile
from datetime import datetime
from typing import Optional, List

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from .bracket_pdf_generator import BracketPDFGenerator  # noqa: E402
from .printer_service import PrinterService  # noqa: E402

logger = get_logger('printing_service')


class PrintingService:
    """Orchestrate bracket printing workflow."""

    def __init__(self, db=None, temp_dir: Optional[str] = None):
        """
        Initialize printing service.
        
        Args:
            db: SQLAlchemy database session
            temp_dir: Directory for temporary PDF files
        """
        self.db = db
        self.temp_dir = temp_dir or os.path.join(
            os.path.dirname(__file__), '..', '..', 'temp'
        )
        self.pdf_generator = BracketPDFGenerator(db)
        self.printer_service = PrinterService()
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info(f"PrintingService initialized with temp_dir: {self.temp_dir}")

    def print_bracket(self, bracket_id: int, printer_name: Optional[str] = None,
                     copies: int = 1) -> bool:
        """
        Print a bracket (main entry point).
        
        Args:
            bracket_id: ID of bracket to print
            printer_name: Target printer (None = system default)
            copies: Number of copies
        
        Returns:
            True if print succeeded, False otherwise
        """
        try:
            logger.info(f"Starting bracket print: id={bracket_id}, printer={printer_name}, copies={copies}")
            
            # Generate PDF
            pdf_path = self._generate_bracket_pdf(bracket_id)
            if not pdf_path or not os.path.exists(pdf_path):
                logger.error(f"PDF generation failed for bracket {bracket_id}")
                return False
            
            logger.info(f"PDF generated: {pdf_path}")
            
            # Send to printer
            success = self.printer_service.print_file(pdf_path, printer_name, copies)
            
            if success:
                logger.info(f"Bracket {bracket_id} printed successfully")
            else:
                logger.error(f"Failed to print bracket {bracket_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"Print bracket error: {e}")
            return False

    def print_bracket_dialog(self, bracket_id: int) -> tuple:
        """
        Prepare data for print dialog (UI layer).
        
        Returns:
            Tuple of (bracket_info_dict, available_printers_list)
        """
        try:
            # TODO: Retrieve bracket info from database
            bracket_info = {
                'id': bracket_id,
                'type': 'ko',  # or 'pool'
                'age_group': 'U13',
                'weight_class': '45kg',
                'mat_number': 5,
            }
            
            printers = self.get_available_printers()
            
            logger.info(f"Print dialog prepared for bracket {bracket_id}: {len(printers)} printers available")
            return bracket_info, printers
        
        except Exception as e:
            logger.error(f"Print dialog error: {e}")
            return {}, []

    def save_bracket_as_pdf(self, bracket_id: int, output_path: str) -> bool:
        """
        Save bracket as PDF without printing.
        
        Args:
            bracket_id: Bracket ID
            output_path: Where to save the PDF file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Saving bracket {bracket_id} to: {output_path}")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            
            # TODO: Determine bracket type (KO vs Pool) from database
            pdf_path = self.pdf_generator.generate_bracket_pdf(bracket_id, output_path)
            
            if os.path.exists(pdf_path):
                logger.info(f"Bracket PDF saved: {pdf_path}")
                return True
            else:
                logger.error(f"PDF file not created: {pdf_path}")
                return False
        
        except Exception as e:
            logger.error(f"Save PDF error: {e}")
            return False

    def get_available_printers(self) -> List[str]:
        """
        Get list of available printers.
        
        Returns:
            List of printer names
        """
        try:
            printers = self.printer_service.get_available_printers()
            logger.debug(f"Found {len(printers)} available printer(s)")
            return printers
        except Exception as e:
            logger.error(f"Failed to get printers: {e}")
            return []

    def get_default_printer(self) -> Optional[str]:
        """
        Get system default printer.
        
        Returns:
            Default printer name or None
        """
        try:
            printer = self.printer_service.get_default_printer()
            if printer:
                logger.debug(f"Default printer: {printer}")
            else:
                logger.debug("No default printer configured")
            return printer
        except Exception as e:
            logger.error(f"Failed to get default printer: {e}")
            return None

    # ===== Private Methods =====

    def _generate_bracket_pdf(self, bracket_id: int) -> str:
        """
        Generate a bracket PDF in temp directory.
        
        Returns:
            Path to generated PDF file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"bracket_{bracket_id}_{timestamp}.pdf"
        pdf_path = os.path.join(self.temp_dir, pdf_filename)
        
        # TODO: Determine bracket type from database
        bracket_type = 'ko'  # or 'pool'
        
        if bracket_type == 'ko':
            return self.pdf_generator.generate_bracket_pdf(bracket_id, pdf_path)
        else:
            return self.pdf_generator.generate_pool_pdf(bracket_id, pdf_path)

    def cleanup_temp_files(self, max_age_hours: int = 1) -> int:
        """
        Clean up old temporary PDF files.
        
        Args:
            max_age_hours: Delete files older than this many hours
        
        Returns:
            Number of files deleted
        """
        import time
        
        deleted = 0
        try:
            if not os.path.exists(self.temp_dir):
                return 0
            
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                
                if not filename.startswith('bracket_') or not filename.endswith('.pdf'):
                    continue
                
                file_age = now - os.path.getmtime(filepath)
                
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        deleted += 1
                        logger.debug(f"Removed old temp file: {filename}")
                    except OSError as e:
                        logger.warning(f"Failed to delete temp file {filename}: {e}")
            
            logger.info(f"Cleaned up {deleted} old temp file(s)")
            return deleted
        
        except Exception as e:
            logger.error(f"Temp file cleanup error: {e}")
            return 0
