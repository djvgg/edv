# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service for managing UI feedback (progress dialogs, status messages, etc.)."""

import tkinter as tk
from tkinter import ttk, messagebox
from utils.logging import get_logger
from ..styles import COLORS, apply_label_style


class UIFeedbackService:
    """Handles all UI feedback operations (progress dialogs, status updates, info text)."""
    
    def __init__(self, root_window):
        """Initialize the UI feedback service.
        
        Args:
            root_window: The root tkinter window to attach dialogs to
        """
        self.logger = get_logger(__name__)
        self.root = root_window
        self.loading_window = None
        self.progress_var = None
        self.progress_label = None
        self.status_var = None
        self.status_label = None
        self.info_var = None
    
    def set_status_label_reference(self, status_label, status_var):
        """Register the status label and variable for updates.
        
        Args:
            status_label: The tk.Label widget for status display
            status_var: The tk.StringVar for status text
        """
        self.status_label = status_label
        self.status_var = status_var
    
    def set_info_var_reference(self, info_var):
        """Register the info variable for updates.
        
        Args:
            info_var: The tk.StringVar for info text
        """
        self.info_var = info_var
    
    def set_file_loader_screen_reference(self, file_loader_screen):
        """Register the file loader screen for cascading updates.
        
        Args:
            file_loader_screen: The FileLoaderScreen instance
        """
        self.file_loader_screen = file_loader_screen
    
    def show_loading_progress(self, message):
        """Show a loading progress dialog.
        
        Args:
            message (str): The message to display in the loading dialog
        """
        # Create a loading window
        self.loading_window = tk.Toplevel(self.root)
        self.loading_window.title("Loading...")
        self.loading_window.geometry("400x150")
        self.loading_window.configure(bg=COLORS['bg_dark'])
        self.loading_window.resizable(False, False)
        
        # Make it modal
        self.loading_window.transient(self.root)
        self.loading_window.grab_set()
        
        # Center on parent window
        self.loading_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 150) // 2
        self.loading_window.geometry(f"+{x}+{y}")
        
        # Message label
        msg_label = tk.Label(self.loading_window, text=message)
        apply_label_style(msg_label, 'heading_md')
        msg_label.pack(pady=(20, 10))
        
        # Progress bar
        self.progress_var = tk.IntVar(value=0)
        progress_bar = ttk.Progressbar(self.loading_window, variable=self.progress_var,
                                       maximum=100, length=350, mode='determinate')
        progress_bar.pack(pady=10, padx=20)
        
        # Percentage label
        self.progress_label = tk.Label(self.loading_window, text="0%")
        apply_label_style(self.progress_label, 'info')
        self.progress_label.pack(pady=(0, 10))
        
        self.loading_window.update_idletasks()
    
    def update_progress(self, value):
        """Update the progress bar.
        
        Args:
            value (int): Progress percentage (0-100)
        """
        if self.progress_var and self.loading_window:
            self.progress_var.set(value)
            self.progress_label.config(text=f"{value}%")
            self.loading_window.update_idletasks()
    
    def hide_loading_progress(self):
        """Hide the loading progress dialog."""
        if self.loading_window and self.loading_window.winfo_exists():
            self.loading_window.destroy()
            self.loading_window = None
            self.progress_var = None
            self.progress_label = None
    
    def set_status(self, msg, color=None, update_file_loader=True):
        """Update status label.
        
        Args:
            msg (str): Status message
            color (str, optional): Text color (hex or named color)
            update_file_loader (bool): Whether to cascade update to file loader screen
        """
        if self.status_var:
            self.status_var.set(msg)
            if color and self.status_label:
                self.status_label.config(fg=color)
            self.root.update_idletasks()
        
        # Also update file loader screen if it exists and is displayed
        if update_file_loader and hasattr(self, 'file_loader_screen') and \
           self.file_loader_screen and self.file_loader_screen.winfo_exists():
            style = 'status_success'
            if color and color == COLORS['accent_red']:
                style = 'status_error'
            elif color and color == COLORS['text_secondary']:
                style = 'info'
            self.file_loader_screen.set_status_text(msg, style)
    
    def set_info_text(self, text):
        """Update info text on file loader screen if available.

        Args:
            text (str): Info text to display
        """
        if self.info_var:
            self.info_var.set(text)
        if hasattr(self, 'file_loader_screen') and self.file_loader_screen and \
           self.file_loader_screen.winfo_exists():
            self.file_loader_screen.set_info_text(text)

    def show_error(self, title: str, message: str):
        """Show an error dialog safely from any thread.

        Uses root.after(0, ...) to post the dialog onto the main thread's
        event loop, avoiding the tkinter thread-safety violation that occurs
        when messagebox is called directly from a background thread.
        """
        self.root.after(0, lambda: messagebox.showerror(title, message, parent=self.root))

    def show_warning(self, title: str, message: str):
        """Show a warning dialog safely from any thread.

        Uses root.after(0, ...) to post the dialog onto the main thread's
        event loop, avoiding the tkinter thread-safety violation that occurs
        when messagebox is called directly from a background thread.
        """
        self.root.after(0, lambda: messagebox.showwarning(title, message, parent=self.root))
