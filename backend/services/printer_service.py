# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Printer Service - Cross-platform printer control using native OS commands.

Provides printer detection and file printing via:
- Windows: 'print' command
- Linux: 'lp' command (CUPS)
- macOS: 'lp' command (CUPS)
"""

import os
import sys
import subprocess
import platform
from typing import List, Optional

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402

logger = get_logger('printer_service')


class PrinterService:
    """Cross-platform printer control via native OS commands."""

    @staticmethod
    def get_available_printers() -> List[str]:
        """
        Get list of available printers.
        
        Returns:
            List of printer names. May include 'System Default' or OS-specific names.
        """
        system = platform.system()
        
        if system == 'Windows':
            return PrinterService._get_printers_windows()
        elif system == 'Linux':
            return PrinterService._get_printers_linux()
        elif system == 'Darwin':  # macOS
            return PrinterService._get_printers_macos()
        else:
            logger.warning(f"Unknown OS: {system}, no printer detection available")
            return []

    @staticmethod
    def get_default_printer() -> Optional[str]:
        """
        Get the system default printer name.
        
        Returns:
            Default printer name or None if not available.
        """
        system = platform.system()
        
        if system == 'Windows':
            # Windows: get default from registry/system
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 
                     '(Get-WmiObject -Class Win32_Printer -Filter "Default=True").Name'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get Windows default printer: {e}")
            return None
        
        elif system in ('Linux', 'Darwin'):
            # Linux/macOS: use lpstat
            try:
                result = subprocess.run(
                    ['lpstat', '-d'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    # Output format: "system default output for class 'printer': printer-name"
                    parts = result.stdout.strip().split(':')
                    if len(parts) > 1:
                        return parts[-1].strip()
            except Exception as e:
                logger.debug(f"Failed to get Unix default printer: {e}")
            return None
        
        return None

    @staticmethod
    def print_file(file_path: str, printer_name: Optional[str] = None, 
                   copies: int = 1) -> bool:
        """
        Print a file using native OS commands.
        
        Args:
            file_path: Path to file to print (e.g., PDF)
            printer_name: Target printer name. If None, uses system default
            copies: Number of copies to print
        
        Returns:
            True if print command succeeded, False otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        system = platform.system()
        
        try:
            if system == 'Windows':
                return PrinterService._print_windows(file_path, printer_name, copies)
            elif system == 'Linux':
                return PrinterService._print_linux(file_path, printer_name, copies)
            elif system == 'Darwin':  # macOS
                return PrinterService._print_macos(file_path, printer_name, copies)
            else:
                logger.error(f"Printing not supported on OS: {system}")
                return False
        
        except Exception as e:
            logger.error(f"Print error: {e}")
            return False

    # ===== Windows Printing =====

    @staticmethod
    def _get_printers_windows() -> List[str]:
        """Get list of printers on Windows."""
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 'Get-WmiObject Win32_Printer | Select-Object -ExpandProperty Name'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                printers = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
                logger.info(f"Found {len(printers)} Windows printer(s)")
                return printers
        except Exception as e:
            logger.warning(f"Failed to enumerate Windows printers: {e}")
        
        return []

    @staticmethod
    def _print_windows(file_path: str, printer_name: Optional[str], copies: int) -> bool:
        """Print on Windows using 'print' command."""
        file_path = os.path.abspath(file_path)
        
        # Build command
        cmd = ['print']
        
        if printer_name:
            cmd.extend(['/D:' + printer_name])
        
        cmd.append(file_path)
        
        # Handle copies (Windows print command; may need to print multiple times)
        for _ in range(copies):
            logger.info(f"Printing to Windows printer: {printer_name or 'default'}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"Windows print failed: {result.stderr}")
                return False
        
        logger.info("Windows print command completed successfully")
        return True

    # ===== Linux Printing (CUPS) =====

    @staticmethod
    def _get_printers_linux() -> List[str]:
        """Get list of printers on Linux (CUPS)."""
        try:
            result = subprocess.run(
                ['lpstat', '-p', '-d'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse output: "printer printer-name is idle..."
                printers = []
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('printer '):
                        parts = line.split()
                        if len(parts) >= 2:
                            printer_name = parts[1]
                            printers.append(printer_name)
                logger.info(f"Found {len(printers)} Linux printer(s)")
                return printers
        except Exception as e:
            logger.warning(f"Failed to enumerate Linux printers: {e}")
        
        return []

    @staticmethod
    def _print_linux(file_path: str, printer_name: Optional[str], copies: int) -> bool:
        """Print on Linux using 'lp' command (CUPS)."""
        file_path = os.path.abspath(file_path)
        
        cmd = ['lp']
        
        if printer_name:
            cmd.extend(['-d', printer_name])
        
        if copies > 1:
            cmd.extend(['-n', str(copies)])
        
        cmd.append(file_path)
        
        logger.info(f"Printing to Linux printer: {printer_name or 'default'}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"Linux print failed: {result.stderr}")
            return False
        
        logger.info("Linux print command completed successfully")
        return True

    # ===== macOS Printing (CUPS) =====

    @staticmethod
    def _get_printers_macos() -> List[str]:
        """Get list of printers on macOS (CUPS)."""
        try:
            result = subprocess.run(
                ['lpstat', '-p', '-d'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse output: "printer printer-name is idle..."
                printers = []
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('printer '):
                        parts = line.split()
                        if len(parts) >= 2:
                            printer_name = parts[1]
                            printers.append(printer_name)
                logger.info(f"Found {len(printers)} macOS printer(s)")
                return printers
        except Exception as e:
            logger.warning(f"Failed to enumerate macOS printers: {e}")
        
        return []

    @staticmethod
    def _print_macos(file_path: str, printer_name: Optional[str], copies: int) -> bool:
        """Print on macOS using 'lp' command (CUPS)."""
        file_path = os.path.abspath(file_path)
        
        cmd = ['lp']
        
        if printer_name:
            cmd.extend(['-d', printer_name])
        
        if copies > 1:
            cmd.extend(['-n', str(copies)])
        
        cmd.append(file_path)
        
        logger.info(f"Printing to macOS printer: {printer_name or 'default'}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"macOS print failed: {result.stderr}")
            return False
        
        logger.info("macOS print command completed successfully")
        return True
