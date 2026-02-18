# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Example usage:
# log_entry = '[2026-02-11 12:00:00] [INFO] Application started\n'
# console = ConsoleHandler()
# console.emit(log_entry)
# file = FileHandler('logs/app.info.log')
# file.emit(log_entry)

class ConsoleHandler:
    def emit(self, log_entry):
        print(log_entry)

class FileHandler:
    def __init__(self, file_path):
        self.file_path = file_path
    def emit(self, log_entry):
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)

