# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys

def get_app_root():
    """Get the absolute path to the root of the application.
    Works for both source and PyInstaller bundled mode.
    """
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable
        # sys._MEIPASS is where PyInstaller extracts files
        return sys._MEIPASS
    else:
        # Running from source
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_config_path(filename="bracket_config.xlsx"):
    """Get path to a configuration file."""
    return os.path.join(get_app_root(), "config", filename)

def get_database_path(filename="tournament.db"):
    """Get path to the SQLite database.
    In frozen mode, we want this NEXT TO the executable, not inside the temp folder.
    """
    if getattr(sys, 'frozen', False):
        # Dir where the .exe lives
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, filename)
    else:
        return os.path.join(get_app_root(), filename)
