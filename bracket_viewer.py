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
            records = subGroup[['Name', 'Verein']].to_dict('records')
            # Split into brackets of max 64
            for i in range(0, len(records), 64):
                bracketNum = i // 64 + 1
                suffix = f'_{bracketNum}' if bracketNum > 1 else ''
                pools[f'{genderLabel} | {ageGroup} | {weightClass}{suffix}'] = records[i:i+64]
    # Clean up
    if hasattr(getWeightClass, 'currentGender'):
        del getWeightClass.currentGender
    return pools

def makeBracket(participants):
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
        self.createWidgets()

    def createWidgets(self):
        # Search bar
        searchFrame = tk.Frame(self)
        searchFrame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        tk.Label(searchFrame, text='Search Bracket:').pack(side=tk.LEFT)
        self.searchVar = tk.StringVar()
        self.searchVar.trace('w', self.updateFilter)
        searchEntry = tk.Entry(searchFrame, textvariable=self.searchVar)
        searchEntry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Bracket list
        listFrame = tk.Frame(self)
        listFrame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        self.poolList = tk.Listbox(listFrame, width=30)
        self.poolList.pack(fill=tk.Y, expand=True)
        self.poolList.bind('<<ListboxSelect>>', self.onPoolSelect)
        self.updatePoolList()

        # Bracket display with scrollbars
        self.bracketFrame = tk.Frame(self)
        self.bracketFrame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.bracketCanvas = tk.Canvas(self.bracketFrame, bg='white', scrollregion=(-100, -100, 2000, 2000))
        xScroll = tk.Scrollbar(self.bracketFrame, orient=tk.HORIZONTAL, command=self.bracketCanvas.xview)
        yScroll = tk.Scrollbar(self.bracketFrame, orient=tk.VERTICAL, command=self.bracketCanvas.yview)
        self.bracketCanvas.configure(xscrollcommand=xScroll.set, yscrollcommand=yScroll.set)
        self.bracketCanvas.grid(row=0, column=0, sticky='nsew')
        xScroll.grid(row=1, column=0, sticky='ew')
        yScroll.grid(row=0, column=1, sticky='ns')
        self.bracketFrame.grid_rowconfigure(0, weight=1)
        self.bracketFrame.grid_columnconfigure(0, weight=1)

    def updateFilter(self, *args):
        search = self.searchVar.get().lower()
        self.filteredPools = [k for k in self.pools if search in k.lower()]
        self.updatePoolList()

    def updatePoolList(self):
        self.poolList.delete(0, tk.END)
        for pool in self.filteredPools:
            self.poolList.insert(tk.END, pool)

    def onPoolSelect(self, event):
        selection = self.poolList.curselection()
        if not selection:
            return
        poolName = self.poolList.get(selection[0])
        participants = self.pools[poolName]
        bracket = makeBracket(participants)
        self.renderBracket(bracket)

    def renderBracket(self, bracket):
        self.bracketCanvas.delete('all')
        width = self.bracketCanvas.winfo_width() or 800
        height = self.bracketCanvas.winfo_height() or 500
        boxWidth = 120
        boxHeight = 40
        xGap = 80
        yGap = 30
        rounds = []
        # Build rounds for a single-elimination tree
        current = [(p1, p2) for p1, p2 in bracket]
        rounds.append(current)
        while len(current) > 1:
            nextRound = []
            for i in range(0, len(current), 2):
                # Winner of match i vs winner of match i+1
                p1 = f"Winner {i+1}"
                p2 = f"Winner {i+2}" if i+1 < len(current) else 'BYE'
                nextRound.append((p1, p2))
            current = nextRound
            rounds.append(current)

        # Calculate vertical positions for each match in each round, centering next round between previous matches
        positions = {}  # (round, match) -> (x, y)
        yOffsets = {}   # (round, match) -> y center
        # First round: evenly spaced
        firstTotal = len(rounds[0])
        for m in range(firstTotal):
            x = 60
            y = 60 + m * (boxHeight + yGap)
            positions[(0, m)] = (x, y)
            yOffsets[(0, m)] = y + boxHeight // 2
        # Next rounds: center between previous matches
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

        # Draw the tree
        for r, matches in enumerate(rounds):
            for m, (p1, p2) in enumerate(matches):
                x, y = positions[(r, m)]
                # Draw box with both names, separated by a line and 'vs'
                self.bracketCanvas.create_rectangle(x, y, x + boxWidth, y + boxHeight, outline='black', width=2)
                self.bracketCanvas.create_line(x, y + boxHeight // 2, x + boxWidth, y + boxHeight // 2, fill='gray', dash=(2, 2))
                self.bracketCanvas.create_text(x + boxWidth // 2, y + boxHeight // 4, text=p1, anchor='c')
                self.bracketCanvas.create_text(x + boxWidth // 2, y + 3 * boxHeight // 4, text=p2, anchor='c')
                self.bracketCanvas.create_text(x + boxWidth // 2, y + boxHeight // 2, text='vs', anchor='c', font=('Arial', 10, 'bold'), fill='blue')
                # Draw connection to next round (from right center of this box to left center of next box)
                if r < len(rounds) - 1:
                    nextMatchIdx = m // 2
                    nx, ny = positions[(r + 1, nextMatchIdx)]
                    self.bracketCanvas.create_line(
                        x + boxWidth, y + boxHeight // 2,
                        nx, ny + boxHeight // 2,
                        arrow=tk.LAST, width=2
                    )

if __name__ == '__main__':
    app = BracketViewerApp()
    app.mainloop()
