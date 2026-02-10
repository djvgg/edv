import pandas as pd

# Define weight classes for adults (using men's classes for now)
weightClasses = [
    (0, 60),    # under 60kg
    (60, 66),   # 60-66kg
    (66, 73),   # 66-73kg
    (73, 81),   # 73-81kg
    (81, 90),   # 81-90kg
    (90, 100),  # 90-100kg
    (100, float('inf')) # over 100kg
]

# Labels for each weight class
weightLabels = [
    'under 60kg',
    '60-66kg',
    '66-73kg',
    '73-81kg',
    '81-90kg',
    '90-100kg',
    'over 100kg'
]

def getWeightClass(weight):
    """Return the weight class label for a given weight."""
    for i, (low, high) in enumerate(weightClasses):
        if low <= weight < high:
            return weightLabels[i]
    return 'unknown'

def getAgeGroup(age):
    """Return the age group label for a given age."""
    return 'under 18' if age < 18 else '18+'

# Read Excel file with participant data
inputFile = r'C:\UNI\TOP\libraries\wichtigedocs\teilnehmer_judo_mock.xlsx'
dataFrame = pd.read_excel(inputFile)

# Assign age group and weight class to each participant
# Column names: 'Name', 'Alter', 'Gewicht (kg)'
dataFrame['ageGroup'] = dataFrame['Alter'].apply(getAgeGroup)
dataFrame['weightClass'] = dataFrame['Gewicht (kg)'].apply(getWeightClass)

# Group by age group and weight class, collect names
pools = dataFrame.groupby(['ageGroup', 'weightClass'])['Name'].apply(list)

# Write pools to text file, one pool per line (only names)
outputFile = r'C:\UNI\TOP\edv_backend\judo_pools.txt'
with open(outputFile, 'w', encoding='utf-8') as file:
    for (ageGroup, weightClass), names in pools.items():
        line = f"{ageGroup} | {weightClass}: {', '.join(names)}\n"
        file.write(line)

print(f"Pools written to {outputFile}")
