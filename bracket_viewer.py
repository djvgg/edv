import tkinter as tk
from tkinter import ttk
import pandas as pd
import random

# --- Config ---
inputFile = r'C:\UNI\TOP\libraries\wichtigedocs\teilnehmer_judo_700.xlsx'

# --- Helper functions ---
def getWeightClass(weight):
    # Use global gender context if set
    if hasattr(getWeightClass, 'currentGender') and getWeightClass.currentGender == 'Female':
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

def getAgeGroup(age):
    return 'under 18' if age < 18 else '18+'

def loadPools():
    df = pd.read_excel(inputFile)
    df['ageGroup'] = df['Alter'].apply(getAgeGroup)
    # Combine first and last name for display
    df['Name'] = df['Vorname'].astype(str) + ' ' + df['Nachname'].astype(str)
    pools = {}
    for (gender, ageGroup), group in df.groupby(['Geschlecht', 'ageGroup']):
        genderLabel = 'Female' if str(gender).lower().startswith('w') else 'Male'
        # Set gender context for weight class assignment
        getWeightClass.currentGender = genderLabel
        group = group.copy()
        group['weightClass'] = group['Gewicht'].apply(getWeightClass)
        for weightClass, subGroup in group.groupby('weightClass'):
            # Limit to 64 per bracket
            records = subGroup[['Name', 'Verein']].to_dict('records')[:64]
            pools[f'{genderLabel} | {ageGroup} | {weightClass}'] = records
    # Clean up
    if hasattr(getWeightClass, 'currentGender'):
        del getWeightClass.currentGender
    return pools

def makeBracket(participants):
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
        self.pools = loadPools()
        self.filteredPools = list(self.pools.keys())
        self.bracket_table_assignment = {k: None for k in self.pools}
        self.createWidgets()

    def createWidgets(self):
        # Main layout: left for unassigned, right for tables/bracket view
        mainFrame = tk.Frame(self)
        mainFrame.pack(fill=tk.BOTH, expand=True)

        # Bind Escape key to return to tables
        self.bind('<Escape>', lambda event: self.showTables())

        # Left: Unassigned brackets with search
        leftFrame = tk.Frame(mainFrame)
        leftFrame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        tk.Label(leftFrame, text='Unassigned Brackets', font=('Arial', 12, 'bold')).pack(pady=(0,5))
        searchFrame = tk.Frame(leftFrame)
        searchFrame.pack(fill=tk.X, pady=(0,5))
        tk.Label(searchFrame, text='Search:').pack(side=tk.LEFT)
        self.searchVar = tk.StringVar()
        self.searchVar.trace('w', self.updateFilter)
        searchEntry = tk.Entry(searchFrame, textvariable=self.searchVar)
        searchEntry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.poolList = tk.Listbox(leftFrame, width=32, height=22)
        self.poolList.pack(fill=tk.Y, expand=True)
        self.poolList.bind('<<ListboxSelect>>', self.onPoolSelect)
        self.poolList.bind('<Double-Button-1>', self.onPoolDoubleClick)
        self.updatePoolList()

        # Right: Container for table panels or bracket view
        self.rightFrame = tk.Frame(mainFrame)
        self.rightFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Bracket view (hidden by default)
        self.bracketFrame = tk.Frame(self.rightFrame)
        self.bracketCanvas = tk.Canvas(self.bracketFrame, bg='white', height=220, scrollregion=(-100, -100, 2000, 2000))
        xScroll = tk.Scrollbar(self.bracketFrame, orient=tk.HORIZONTAL, command=self.bracketCanvas.xview)
        yScroll = tk.Scrollbar(self.bracketFrame, orient=tk.VERTICAL, command=self.bracketCanvas.yview)
        self.bracketCanvas.configure(xscrollcommand=xScroll.set, yscrollcommand=yScroll.set)
        self.bracketCanvas.grid(row=0, column=0, sticky='nsew')
        xScroll.grid(row=1, column=0, sticky='ew')
        yScroll.grid(row=0, column=1, sticky='ns')
        self.bracketFrame.grid_rowconfigure(0, weight=1)
        self.bracketFrame.grid_columnconfigure(0, weight=1)
        self.backBtn = tk.Button(self.bracketFrame, text='Back to Tables', command=self.showTables)
        self.backBtn.grid(row=2, column=0, columnspan=2, pady=10)

        # Table panels (shown by default)
        self.tablesFrame = tk.Frame(self.rightFrame)
        self.tablesFrame.pack(fill=tk.BOTH, expand=True)
        self.tablePanels = {}
        for i, (row, col) in enumerate([(0,0), (0,1), (1,0), (1,1)]):
            tableNum = i+1
            panel = tk.LabelFrame(self.tablesFrame, text=f'Table {tableNum}', font=('Arial', 12, 'bold'), width=180, height=120, labelanchor='n')
            panel.grid(row=row, column=col, padx=18, pady=18, sticky='nsew')
            panel.grid_propagate(False)
            self.tablePanels[tableNum] = panel
        self.tablesFrame.grid_rowconfigure(0, weight=1)
        self.tablesFrame.grid_rowconfigure(1, weight=1)
        self.tablesFrame.grid_columnconfigure(0, weight=1)
        self.tablesFrame.grid_columnconfigure(1, weight=1)

        # Assignment state is now initialized in __init__

        # Assign to table buttons
        assignBtnFrame = tk.Frame(leftFrame)
        assignBtnFrame.pack(pady=8)
        tk.Label(assignBtnFrame, text='Assign to Table:').pack(side=tk.LEFT)
        for t in range(1, 5):
            btn = tk.Button(assignBtnFrame, text=str(t), width=3, command=lambda t=t: self.assignToTable(t))
            btn.pack(side=tk.LEFT, padx=2)

        self.showTables()
        self.updateTablePanels()
        self.updatePoolList()
    def assignToTable(self, tableNum):
        selection = self.poolList.curselection()
        if not selection:
            return
        poolName = self.poolList.get(selection[0])
        # Only allow max 2 brackets per table
        assigned = [k for k, v in self.bracket_table_assignment.items() if v == tableNum]
        if len(assigned) >= 2:
            tk.messagebox.showwarning('Table Full', f'Table {tableNum} already has 2 brackets assigned.')
            return
        self.bracket_table_assignment[poolName] = tableNum
        self.updatePoolList()
        self.updateTablePanels()

    def updateTablePanels(self):
        # Clear and repopulate each table panel
        for t in range(1, 5):
            panel = self.tablePanels[t]
            for widget in panel.winfo_children():
                widget.destroy()
            assigned = [k for k, v in self.bracket_table_assignment.items() if v == t]
            for i, pool in enumerate(assigned):
                rowFrame = tk.Frame(panel)
                rowFrame.pack(fill=tk.X, pady=4, padx=4)
                label = tk.Label(rowFrame, text=pool, wraplength=120, justify='left', anchor='w')
                label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                unassignBtn = tk.Button(rowFrame, text='Unassign', width=8, command=lambda p=pool: self.unassignBracket(p))
                unassignBtn.pack(side=tk.RIGHT, padx=2)

    def unassignBracket(self, poolName):
        self.bracket_table_assignment[poolName] = None
        self.updatePoolList()
        self.updateTablePanels()

    def showBracketView(self, bracketKey):
        self.tablesFrame.pack_forget()
        self.bracketFrame.pack(fill=tk.BOTH, expand=True)
        self.renderBracket(bracketKey)

    def showTables(self):
        self.bracketFrame.pack_forget()
        self.tablesFrame.pack(fill=tk.BOTH, expand=True)

    def updateFilter(self, *args):
        search = self.searchVar.get().lower()
        self.filteredPools = [k for k in self.pools if search in k.lower()]
        self.updatePoolList()

    def updatePoolList(self):
        self.poolList.delete(0, tk.END)
        # Only show unassigned brackets
        for pool in self.filteredPools:
            if not self.bracket_table_assignment.get(pool):
                self.poolList.insert(tk.END, pool)

    def onPoolSelect(self, event):
        selection = self.poolList.curselection()
        if not selection:
            return
        poolName = self.poolList.get(selection[0])
        self.renderBracket(poolName)

    def onPoolDoubleClick(self, event):
        selection = self.poolList.curselection()
        if selection:
            poolName = self.poolList.get(selection[0])
            self.showBracketView(poolName)

    def renderBracket(self, bracketKey):
        try:
            self.bracketCanvas.delete('all')
            participants = self.pools[bracketKey]
            bracket = makeBracket(participants)
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
                    self.bracketCanvas.create_rectangle(x, y, x + boxWidth, y + boxHeight, outline='black', width=2)
                    self.bracketCanvas.create_line(x, y + boxHeight // 2, x + boxWidth, y + boxHeight // 2, fill='gray', dash=(2, 2))
                    self.bracketCanvas.create_text(x + boxWidth // 2, y + boxHeight // 4, text=p1, anchor='c')
                    self.bracketCanvas.create_text(x + boxWidth // 2, y + 3 * boxHeight // 4, text=p2, anchor='c')
                    self.bracketCanvas.create_text(x + boxWidth // 2, y + boxHeight // 2, text='vs', anchor='c', font=('Arial', 10, 'bold'), fill='blue')
                    if r < len(rounds) - 1:
                        nextMatchIdx = m // 2
                        nx, ny = positions[(r + 1, nextMatchIdx)]
                        self.bracketCanvas.create_line(
                            x + boxWidth, y + boxHeight // 2,
                            nx, ny + boxHeight // 2,
                            arrow=tk.LAST, width=2
                        )
        except Exception as e:
            print(f"Exception in renderBracket: {e}")

if __name__ == '__main__':
    app = BracketViewerApp()
    app.mainloop()
