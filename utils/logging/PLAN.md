# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
#
# SPDX-License-Identifier: CC0-1.0

# Logging Framework Plan

## Purpose
Create a reusable logging library for error handling, log file creation, and logging data/events for all backend scripts.

## Structure
- `logging/`
  - `logger.py`: Main logger class and functions
  - `handlers.py`: File and console log handlers
  - `config.py`: Logging configuration (log levels, file paths)
  - `README.md`: Usage instructions and examples

## Features
- Easy-to-use logger interface
- Log file creation and rotation
- Error and exception logging
- Custom log levels (info, warning, error, debug)
- Console and file output
- Timestamped log entries
- Optional: log formatting, context info
- **Optional Tkinter Automation:**
  - Decorator/context manager for event handlers to auto-capture errors
  - Automatic sending of logs from Tkinter frontend to backend
  - Integration with Tkinter global error handling (optional)

## Steps
1. Implement `logger.py` with basic logging methods
2. Add file and console handlers in `handlers.py`
3. Provide configuration options in `config.py`
4. Implement frontend logging subservice (API endpoint, storage)
5. [Optional] Add Tkinter automation features for frontend logging
6. Document usage in `README.md`

## Example Usage
```python
from logging.logger import Logger
logger = Logger()
logger.info('App started')
logger.error('Something went wrong')
# Frontend log example
logger.frontend_log.error('UI error: button not responding', user_id='123')
# Optional Tkinter automation
@logger.auto_log
def on_button_click():
    ...
```

## Integration
- Import logger in backend scripts for consistent logging
- Extend for advanced error handling as needed
- Frontend can POST error logs/messages to backend logging API
- Tkinter frontend can use automation features for error/event logging
