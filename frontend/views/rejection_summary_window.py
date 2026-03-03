"""Window to display detailed summary of rejected participants."""

import tkinter as tk
from tkinter import ttk

from ..styles import COLORS, FONTS, apply_label_style


class RejectionSummaryWindow(tk.Toplevel):
    """Displays detailed information about rejected participants in a blocking modal dialog.
    
    This window blocks the calling thread (similar to messagebox) until the user closes it.
    This prevents the UI from advancing until the rejections have been reviewed.
    
    Shows:
    - Name and reason for rejection (reason in red)
    - Age information for age-related rejections
    """
    
    def __init__(self, parent, rejected_participants):
        """
        Args:
            parent: Parent window
            rejected_participants: List of dicts with rejection_reason and participant data
        """
        super().__init__(parent)
        self.title("Rejected Participants")
        self.geometry("900x550")
        self.minsize(600, 300)
        self.result = None
        
        # Configure style using app theme
        self.configure(bg=COLORS['bg_dark'])
        
        # Header with title and button
        header_frame = tk.Frame(self, bg=COLORS['bg_dark'], highlightthickness=0)
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_label = tk.Label(
            header_frame,
            text=f"Rejected Participants ({len(rejected_participants)})",
            font=FONTS['heading_lg'],
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary']
        )
        apply_label_style(title_label, 'heading_md')
        title_label.pack(side=tk.LEFT)
        
        # Continue button in header (right side)
        continue_btn = tk.Button(
            header_frame,
            text="Continue",
            command=self._on_close,
            bg=COLORS['accent_green'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=8,
            font=FONTS['body_md'],
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=COLORS['accent_green'],
            activeforeground=COLORS['text_primary'],
            borderwidth=0
        )
        continue_btn.pack(side=tk.RIGHT)
        
        # Main content with tree view
        main_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Create treeview with scrollbar
        tree_frame = tk.Frame(main_frame, bg=COLORS['bg_dark'])
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview columns
        columns = ('Name', 'Age', 'Reason')
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            height=20,
            yscrollcommand=scrollbar.set,
            selectmode='none'
        )
        scrollbar.config(command=self.tree.yview)
        
        # Define column headings and widths
        self.tree.column('#0', width=0, stretch=tk.NO)
        self.tree.column('Name', anchor=tk.W, width=280)
        self.tree.column('Age', anchor=tk.CENTER, width=100)
        self.tree.column('Reason', anchor=tk.W, width=450)
        
        self.tree.heading('#0', text='', anchor=tk.W)
        self.tree.heading('Name', text='Name', anchor=tk.W)
        self.tree.heading('Age', text='Age', anchor=tk.CENTER)
        self.tree.heading('Reason', text='Rejection Reason', anchor=tk.W)
        
        # Configure styling
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'Treeview',
            background=COLORS['bg_input'],
            foreground=COLORS['accent_red'],
            fieldbackground=COLORS['bg_input'],
            rowheight=28,
            font=FONTS['body_sm'],
            borderwidth=0
        )
        style.configure(
            'Treeview.Heading',
            background=COLORS['bg_panel'],
            foreground=COLORS['text_secondary'],
            font=FONTS['heading_sm'],
            borderwidth=0
        )
        style.map('Treeview', background=[('selected', COLORS['bg_panel'])])
        
        # Populate tree with rejected participants
        for idx, participant in enumerate(rejected_participants):
            name = self._get_name(participant)
            age = self._get_age_display(participant)
            reason = self._get_reason_display(participant)
            
            # Alternate row colors
            tag = 'oddrow' if idx % 2 == 0 else 'evenrow'
            self.tree.insert('', 'end', text='', values=(name, age, reason), tags=(tag,))
        
        # Configure row colors with red text for emphasis on rejections
        self.tree.tag_configure('oddrow', background=COLORS['bg_input'], foreground=COLORS['accent_red'])
        self.tree.tag_configure('evenrow', background=COLORS['bg_darker'], foreground=COLORS['accent_red'])
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Make window modal and keep focus
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        
        # Bring to front
        self.lift()
        self.attributes('-topmost', True)
        self.after_idle(self.attributes, '-topmost', False)
        
        # Handle window close button (X)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Close button handler - unblock the waiting thread."""
        self.result = 'closed'
        self.destroy()
    
    def wait_for_close(self):
        """Block until the window is closed (mimics messagebox blocking behavior).
        
        This allows the calling thread to wait for user interaction before continuing.
        """
        self.wait_window()
        
    def _get_name(self, participant):
        """Extract full name from participant dict."""
        firstname = participant.get('Firstname', participant.get('Vorname', '')).strip()
        lastname = participant.get('Lastname', participant.get('Nachname', '')).strip()
        name = f"{firstname} {lastname}".strip()
        return name or participant.get('Name', 'Unknown')
    
    def _get_age_display(self, participant):
        """Format age display with birthyear if available."""
        age = participant.get('age', participant.get('Age'))
        if age is None:
            return '—'
        
        # If it's likely a birthyear (4-digit number > 100), show as age
        try:
            age_val = int(age)
            if age_val > 100:  # Likely a birthyear
                return f"(b. {age_val})"
            else:  # Likely an age
                return str(age_val)
        except (ValueError, TypeError):
            return str(age)
    
    def _get_reason_display(self, participant):
        """Format rejection reason for display."""
        reason = participant.get('rejection_reason', 'Unknown reason')
        
        # Format common reasons nicely
        reason_map = {
            'unpaid': '❌ Not paid',
            'age_too_young': '❌ Too young (< 6 years)',
            'age_too_old': '❌ Too old (> 120 years)',
            'invalid_birthyear': '❌ Invalid birth year'
        }
        
        return reason_map.get(reason, f"❌ {reason}")
