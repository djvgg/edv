# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Log Levels:
#   info    - General application events and status updates.
#   error   - Errors that prevent normal program execution.
#   warning - Recoverable issues or unexpected situations that may need attention.
#   debug   - Detailed diagnostic information for development and troubleshooting.
#
# Usage:
#   logger.info('...')    # For normal events
#   logger.error('...')   # For errors also generally printed to console
#   logger.warning('...') # For warnings also generally printed to console
#   logger.debug('...')   # For debug output (optionally prints to console if debug_verbose=True)

# Example usage:
# logger = Logger('logs')
# logger.info('Application started')
# logger.error('An error occurred')

import os
import sys
import threading
import datetime
import traceback
from .handlers import FileHandler, ConsoleHandler


class Logger:
    LOG_LEVELS = ['info', 'error', 'warning', 'debug']
    LOG_LEVELS_STR = ', '.join(LOG_LEVELS)

    def __init__(self, log_dir='logs', debug_verbose=False):
        self._lock = threading.Lock()  # Thread-safe logging
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        self.info_log = os.path.join(self.log_dir, 'app.info.log')
        self.error_log = os.path.join(self.log_dir, 'app.error.log')
        self.warning_log = os.path.join(self.log_dir, 'app.warning.log')
        self.debug_log = os.path.join(self.log_dir, 'app.debug.log')
        self.all_log = os.path.join(self.log_dir, 'app.all.log')
        self.info_handler = FileHandler(self.info_log)
        self.error_handler = FileHandler(self.error_log)
        self.warning_handler = FileHandler(self.warning_log)
        self.debug_handler = FileHandler(self.debug_log)
        self.all_handler = FileHandler(self.all_log)
        self.console_handler = ConsoleHandler()
        self.debug_verbose = debug_verbose  # Optional, defaults to False

    @staticmethod
    def _format_exc_info(exc_info):
        # Match stdlib logging.Logger semantics: exc_info may be True, an
        # exception instance, or a (type, value, tb) tuple. Anything truthy
        # else is treated as "use current exception".
        if not exc_info:
            return ''
        if isinstance(exc_info, BaseException):
            tb_lines = traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)
        elif isinstance(exc_info, tuple) and len(exc_info) == 3:
            tb_lines = traceback.format_exception(*exc_info)
        else:
            current = sys.exc_info()
            if current[0] is None:
                return ''
            tb_lines = traceback.format_exception(*current)
        return '\n' + ''.join(tb_lines).rstrip()

    def _write(self, level, message, args=(), exc_info=False):
        with self._lock:  # Thread-safe write
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # stdlib-compatible: msg % args when args provided. Best-effort:
            # if formatting fails (mismatched specifiers), fall back to repr.
            if args:
                try:
                    message = message % args
                except (TypeError, ValueError):
                    message = f'{message} {args!r}'
            log_entry = f'[{timestamp}] [{level.upper()}] {message}{self._format_exc_info(exc_info)}\n'
            # Write to all-level log
            self.all_handler.emit(log_entry)
            # Write to level-specific log
            if level == 'info':
                self.info_handler.emit(log_entry)
            elif level == 'error':
                self.error_handler.emit(log_entry)
                self.console_handler.emit(log_entry)
            elif level == 'warning':
                self.warning_handler.emit(log_entry)
                self.console_handler.emit(log_entry)
            elif level == 'debug':
                self.debug_handler.emit(log_entry)
                if self.debug_verbose:
                    self.console_handler.emit(log_entry)


    def info(self, message, *args, exc_info=False, **_kwargs):
        self._write('info', message, args, exc_info)

    def error(self, message, *args, exc_info=False, **_kwargs):
        self._write('error', message, args, exc_info)

    def warning(self, message, *args, exc_info=False, **_kwargs):
        self._write('warning', message, args, exc_info)

    def debug(self, message, *args, exc_info=False, **_kwargs):
        self._write('debug', message, args, exc_info)
    
    def close(self):
        """Close all file handlers."""
        with self._lock:  # Thread-safe close
            self.info_handler.close()
            self.error_handler.close()
            self.warning_handler.close()
            self.debug_handler.close()
            self.all_handler.close()


# Simple factory / singleton accessor for easy use across projects
_LOGGERS = {}

def get_logger(name='app', log_dir=None, debug_verbose=False):
        """Return a Logger instance with the given name.

        - `name` is used as a key for reusing logger instances.
        - `log_dir` if provided will be used as the directory for log files;
            otherwise the Logger default ('logs') is used.
        - `debug_verbose` controls whether debug logs also print to console.
        """
        key = (name, log_dir, debug_verbose)
        if key in _LOGGERS:
                return _LOGGERS[key]
        # Create a log directory per logger name if log_dir not provided
        dir_to_use = log_dir if log_dir is not None else os.path.join('logs', name)
        logger = Logger(log_dir=dir_to_use, debug_verbose=debug_verbose)
        _LOGGERS[key] = logger
        return logger