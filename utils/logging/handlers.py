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
        self.file = open(file_path, 'a', encoding='utf-8', buffering=1)  # Line-buffered
    
    def emit(self, log_entry):
        self.file.write(log_entry)
    
    def close(self):
        if self.file and not self.file.closed:
            self.file.close()

