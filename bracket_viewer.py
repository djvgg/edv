import os
#SPDX-FileCopyrightText: 2026 TOP Team Combat Control

#SPDX-License-Identifier: GPL-3.0-or-later

import tkinter as tk
from tkinter import ttk
import pandas as pd
import random
from libraries.logging import get_logger
from .utils.bracket_utils import set_bracket_config, export_all_brackets

# --- Config ---
input_file = r'C:\UNI\TOP\libraries\wichtigedocs\teilnehmer_judo_700.xlsx'

# Load bracket config (excel) from local folder
DEFAULT_CONFIG = os.path.abspath(os.path.join(os.path.dirname(__file__), 'bracket_config.xlsx'))
try:
    set_bracket_config(DEFAULT_CONFIG)
except Exception:
    # Will try to load later when needed; keep app running
    pass

# Logger
logger = get_logger('bracket_viewer')

# --- Helper functions ---
def get_weight_class(weight):
    # Use global gender context if set
    if hasattr(get_weight_class, 'current_gender') and get_weight_class.current_gender == 'Female':
        weightClasses = [
            (0, 48), (48, 52), (52, 57), (57, 63), (63, 70), (70, 78), (78, float('inf'))
        ]
        weightLabels = [
            'under 48kg', '48-52kg', '52-57kg', '57-63kg', '63-70kg', '70-78kg', 'over 78kg'
        ]
    else:
        weightClasses = [
            (0, 60), (60, 66), (66, 73), (73, 81), (81, 90), (90, 100), (100, float('inf'))
        ]
        weightLabels = [
            'under 60kg', '60-66kg', '66-73kg', '73-81kg', '81-90kg', '90-100kg', 'over 100kg'
        ]
    for i, (low, high) in enumerate(weightClasses):
        if low <= weight < high:
            return weightLabels[i]
    return 'unknown'

def get_age_group(age):
    return 'under 18' if age < 18 else '18+'

def load_pools():
    # Read participants and transform to unified participant dicts
    df = pd.read_excel(input_file)
    # Combine first and last name for display if columns exist
    if 'Vorname' in df.columns and 'Nachname' in df.columns:
        df['Name'] = df['Vorname'].astype(str) + ' ' + df['Nachname'].astype(str)
    # Fallback: use 'Name' column if present
    if 'Name' not in df.columns:
        df['Name'] = df.index.astype(str)

    participants = []
    for _, row in df.iterrows():
        gender = row.get('Geschlecht') or row.get('Gender') or ''
        # keep gender short (m/w) if possible
        gender_val = str(gender).strip()
        participants.append({
            'Name': row.get('Name'),
            'Gender': gender_val,
            'Age': row.get('Alter') if 'Alter' in row else row.get('Age'),
            'Weight': row.get('Gewicht') if 'Gewicht' in row else row.get('Weight'),
            'Verein': row.get('Verein') if 'Verein' in row else row.get('Club')
        })

    try:
        brackets = export_all_brackets(participants)
    except Exception as e:
        logger.error(f"Failed to export brackets from config: {e}")
        # Fallback to empty pools
        return {}

    pools = {}
    for key, data in brackets.items():
        # data['fighters'] is a list of participant dicts
        records = []
        for p in data.get('fighters', [])[:64]:
            records.append({'Name': p.get('Name'), 'Verein': p.get('Verein')})
        pools[key] = records
    return pools

def make_bracket(participants):
    # --- Same club avoidance logic (commented out) ---
    # random.shuffle(participants)
    # bracket = []
    # used = set()
    # pool = participants[:]
    # while len(pool) > 1:
    #     found = False
    #     for i, p1 in enumerate(pool):
    #         for j, p2 in enumerate(pool):
    #             if i != j and p1['Verein'] != p2['Verein']:
    #                 bracket.append((p1['Name'], p2['Name']))
    #                 used.update([i, j])
    #                 pool.pop(max(i, j))
    #                 pool.pop(min(i, j))
    #                 found = True
    #                 break
    #         if found:
    #             break
    #     if not found:
    #         bracket.append((pool[0]['Name'], pool[1]['Name']))
    #         pool = pool[2:]
    # if pool:
    #     bracket.append((pool[0]['Name'], 'BYE'))
    # return bracket

    # --- Current simple random pairing ---
    random.shuffle(participants)
    bracket = []
    pool = participants[:]
    while len(pool) > 1:
        bracket.append((pool[0]['Name'], pool[1]['Name']))
        pool = pool[2:]
    if pool:
        bracket.append((pool[0]['Name'], 'BYE'))
    return bracket

# --- GUI ---
class BracketViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Judo Bracket Viewer')
        self.geometry('800x500')
        self.pools = load_pools()
        self.filtered_pools = list(self.pools.keys())
        self.bracket_table_assignment = {k: None for k in self.pools}
        self.create_widgets()

    def create_widgets(self):
        # Main layout: left for unassigned, right for tables/bracket view
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Bind Escape key to return to tables
        self.bind('<Escape>', lambda event: self.show_tables())

        # Left: Unassigned brackets with search
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        tk.Label(left_frame, text='Unassigned Brackets', font=('Arial', 12, 'bold')).pack(pady=(0,5))
        search_frame = tk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0,5))
        tk.Label(search_frame, text='Search:').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.update_filter)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.pool_list = tk.Listbox(left_frame, width=32, height=22)
        self.pool_list.pack(fill=tk.Y, expand=True)
        self.pool_list.bind('<<ListboxSelect>>', self.on_pool_select)
        self.pool_list.bind('<Double-Button-1>', self.on_pool_double_click)
        self.update_pool_list()

        # Right: Container for table panels or bracket view
        self.right_frame = tk.Frame(main_frame)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Bracket view (hidden by default)
        self.bracket_frame = tk.Frame(self.right_frame)
        self.bracket_canvas = tk.Canvas(self.bracket_frame, bg='white', height=220, scrollregion=(-100, -100, 2000, 2000))
        x_scroll = tk.Scrollbar(self.bracket_frame, orient=tk.HORIZONTAL, command=self.bracket_canvas.xview)
        y_scroll = tk.Scrollbar(self.bracket_frame, orient=tk.VERTICAL, command=self.bracket_canvas.yview)
        self.bracket_canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.bracket_canvas.grid(row=0, column=0, sticky='nsew')
        x_scroll.grid(row=1, column=0, sticky='ew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        self.bracket_frame.grid_rowconfigure(0, weight=1)
        self.bracket_frame.grid_columnconfigure(0, weight=1)
        self.back_btn = tk.Button(self.bracket_frame, text='Back to Tables', command=self.show_tables)
        self.back_btn.grid(row=2, column=0, columnspan=2, pady=10)

        # Table panels (shown by default)
        self.tables_frame = tk.Frame(self.right_frame)
        self.tables_frame.pack(fill=tk.BOTH, expand=True)
        self.table_panels = {}
        for i, (row, col) in enumerate([(0,0), (0,1), (1,0), (1,1)]):
            table_num = i+1
            panel = tk.LabelFrame(self.tables_frame, text=f'Table {table_num}', font=('Arial', 12, 'bold'), width=180, height=120, labelanchor='n')
            panel.grid(row=row, column=col, padx=18, pady=18, sticky='nsew')
            panel.grid_propagate(False)
            self.table_panels[table_num] = panel
        self.tables_frame.grid_rowconfigure(0, weight=1)
        self.tables_frame.grid_rowconfigure(1, weight=1)
        self.tables_frame.grid_columnconfigure(0, weight=1)
        self.tables_frame.grid_columnconfigure(1, weight=1)

        # Assignment state is now initialized in __init__

        # Assign to table buttons
        assign_btn_frame = tk.Frame(left_frame)
        assign_btn_frame.pack(pady=8)
        tk.Label(assign_btn_frame, text='Assign to Table:').pack(side=tk.LEFT)
        for t in range(1, 5):
            btn = tk.Button(assign_btn_frame, text=str(t), width=3, command=lambda t=t: self.assign_to_table(t))
            btn.pack(side=tk.LEFT, padx=2)
        # Auto-assign button: distribute unassigned brackets across tables
        auto_btn = tk.Button(assign_btn_frame, text='Auto-assign', command=self.auto_assign_tables)
        auto_btn.pack(side=tk.LEFT, padx=6)

        self.show_tables()
        self.update_table_panels()
        self.update_pool_list()
    def assign_to_table(self, table_num):
        selection = self.pool_list.curselection()
        if not selection:
            return
        pool_name = self.pool_list.get(selection[0])
        # Only allow max 2 brackets per table
        assigned = [k for k, v in self.bracket_table_assignment.items() if v == table_num]
        if len(assigned) >= 2:
            tk.messagebox.showwarning('Table Full', f'Table {table_num} already has 2 brackets assigned.')
            return
        self.bracket_table_assignment[pool_name] = table_num
        self.update_pool_list()
        self.update_table_panels()

    def auto_assign_tables(self):
        """Automatically distribute unassigned brackets across tables (max 2 per table)."""
        # Collect all currently unassigned pools (ignore search filter)
        unassigned = [p for p in self.pools.keys() if not self.bracket_table_assignment.get(p)]
        if not unassigned:
            tk.messagebox.showinfo('Auto-assign', 'No unassigned brackets to assign.')
            return

        # Count current assignments per table
        assigned_count = {t: len([k for k, v in self.bracket_table_assignment.items() if v == t]) for t in range(1, 5)}
        table = 1
        for pool in unassigned:
            # Find next table with space
            found = False
            for _ in range(4):
                if assigned_count[table] < 2:
                    self.bracket_table_assignment[pool] = table
                    assigned_count[table] += 1
                    found = True
                    # move to next table for next allocation
                    table = table % 4 + 1
                    break
                table = table % 4 + 1
            if not found:
                # No available table with free slot
                logger.info('Auto-assign stopped: all tables full (2 per table).')
                break

        self.update_pool_list()
        self.update_table_panels()

    def update_table_panels(self):
        # Clear and repopulate each table panel
        for t in range(1, 5):
            panel = self.table_panels[t]
            for widget in panel.winfo_children():
                widget.destroy()
            assigned = [k for k, v in self.bracket_table_assignment.items() if v == t]
            for i, pool in enumerate(assigned):
                row_frame = tk.Frame(panel)
                row_frame.pack(fill=tk.X, pady=4, padx=4)
                label = tk.Label(row_frame, text=pool, wraplength=120, justify='left', anchor='w', cursor='hand2')
                label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                # Clicking the label shows the bracket view for that pool
                label.bind('<Button-1>', lambda e, p=pool: self.show_bracket_view(p))
                unassign_btn = tk.Button(row_frame, text='Unassign', width=8, command=lambda p=pool: self.unassign_bracket(p))
                unassign_btn.pack(side=tk.RIGHT, padx=2)

    def unassign_bracket(self, pool_name):
        self.bracket_table_assignment[pool_name] = None
        self.update_pool_list()
        self.update_table_panels()

    def show_bracket_view(self, bracket_key):
        self.tables_frame.pack_forget()
        self.bracket_frame.pack(fill=tk.BOTH, expand=True)
        self.render_bracket(bracket_key)

    def show_tables(self):
        self.bracket_frame.pack_forget()
        self.tables_frame.pack(fill=tk.BOTH, expand=True)

    def update_filter(self, *args):
        search = self.search_var.get().lower()
        self.filtered_pools = [k for k in self.pools if search in k.lower()]
        self.update_pool_list()

    def update_pool_list(self):
        self.pool_list.delete(0, tk.END)
        # Only show unassigned brackets
        for pool in self.filtered_pools:
            if not self.bracket_table_assignment.get(pool):
                self.pool_list.insert(tk.END, pool)

    def on_pool_select(self, event):
        selection = self.pool_list.curselection()
        if not selection:
            return
        pool_name = self.pool_list.get(selection[0])
        self.render_bracket(pool_name)

    def on_pool_double_click(self, event):
        selection = self.pool_list.curselection()
        if selection:
            pool_name = self.pool_list.get(selection[0])
            self.show_bracket_view(pool_name)

    def render_bracket(self, bracket_key):
        try:
            self.bracket_canvas.delete('all')
            participants = self.pools[bracket_key]
            bracket = make_bracket(participants)
            # Build rounds for a single-elimination tree
            rounds = []
            current = [(p1, p2) for p1, p2 in bracket]
            rounds.append(current)
            while len(current) > 1:
                nextRound = []
                for i in range(0, len(current), 2):
                    p1 = f"Winner {i+1}"
                    p2 = f"Winner {i+2}" if i+1 < len(current) else 'BYE'
                    nextRound.append((p1, p2))
                current = nextRound
                rounds.append(current)

            boxWidth = 120
            boxHeight = 40
            xGap = 80
            yGap = 30
            positions = {}
            yOffsets = {}
            firstTotal = len(rounds[0])
            for m in range(firstTotal):
                x = 60
                y = 60 + m * (boxHeight + yGap)
                positions[(0, m)] = (x, y)
                yOffsets[(0, m)] = y + boxHeight // 2
            for r in range(1, len(rounds)):
                matches = rounds[r]
                x = 60 + r * (boxWidth + xGap)
                for m in range(len(matches)):
                    prev1 = (r-1, m*2)
                    prev2 = (r-1, m*2+1)
                    y1 = yOffsets.get(prev1, 60)
                    y2 = yOffsets.get(prev2, y1)
                    y = (y1 + y2) // 2 - boxHeight // 2
                    positions[(r, m)] = (x, y)
                    yOffsets[(r, m)] = y + boxHeight // 2
            for r, matches in enumerate(rounds):
                for m, (p1, p2) in enumerate(matches):
                    x, y = positions[(r, m)]
                    self.bracket_canvas.create_rectangle(x, y, x + boxWidth, y + boxHeight, outline='black', width=2)
                    self.bracket_canvas.create_line(x, y + boxHeight // 2, x + boxWidth, y + boxHeight // 2, fill='gray', dash=(2, 2))
                    self.bracket_canvas.create_text(x + boxWidth // 2, y + boxHeight // 4, text=p1, anchor='c')
                    self.bracket_canvas.create_text(x + boxWidth // 2, y + 3 * boxHeight // 4, text=p2, anchor='c')
                    self.bracket_canvas.create_text(x + boxWidth // 2, y + boxHeight // 2, text='vs', anchor='c', font=('Arial', 10, 'bold'), fill='blue')
                    if r < len(rounds) - 1:
                        next_match_idx = m // 2
                        nx, ny = positions[(r + 1, next_match_idx)]
                        self.bracket_canvas.create_line(
                            x + boxWidth, y + boxHeight // 2,
                            nx, ny + boxHeight // 2,
                            arrow=tk.LAST, width=2
                        )
        except Exception as e:
            print(f"Exception in render_bracket: {e}")

def main():
    app = BracketViewerApp()
    app.mainloop()

    
if __name__ == '__main__':
    main()
