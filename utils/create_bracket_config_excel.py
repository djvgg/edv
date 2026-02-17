import pandas as pd

# Data for AgeEligibility sheet
age_eligibility = [
    # Add younger birth years and a U11 column to include 6-year-olds (born 2020)
    {'BirthYear': 2020, 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2019, 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2018, 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2017, 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2016, 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2015, 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2014, 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2013, 'U11': '', 'U13': 'X', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2012, 'U11': '', 'U13': 'X', 'U15': 'X', 'U18': '', '18+': ''},
    {'BirthYear': 2011, 'U11': '', 'U13': '', 'U15': 'X', 'U18': '', '18+': ''},
    {'BirthYear': 2010, 'U11': '', 'U13': '', 'U15': 'X', 'U18': 'X', '18+': ''},
    {'BirthYear': 2009, 'U11': '', 'U13': '', 'U15': '', 'U18': 'X', '18+': ''},
    {'BirthYear': 2008, 'U11': '', 'U13': '', 'U15': '', 'U18': 'X', '18+': 'X'},
    {'BirthYear': 2007, 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
    {'BirthYear': 2006, 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
    {'BirthYear': 2005, 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
]

# Data for Options sheet
options = [
    {'OptionName': 'allow_double_age_bracket', 'Value': 'TRUE'},
    {'OptionName': 'event_year', 'Value': '2026'},
]

# Data for WeightClasses sheet
weight_classes = [
    {'Gender': 'm', 'MinWeight': 0, 'MaxWeight': 60, 'Label': 'under 60kg'},
    {'Gender': 'm', 'MinWeight': 60, 'MaxWeight': 66, 'Label': '60-66kg'},
    {'Gender': 'm', 'MinWeight': 66, 'MaxWeight': 73, 'Label': '66-73kg'},
    {'Gender': 'm', 'MinWeight': 73, 'MaxWeight': 81, 'Label': '73-81kg'},
    {'Gender': 'm', 'MinWeight': 81, 'MaxWeight': 90, 'Label': '81-90kg'},
    {'Gender': 'm', 'MinWeight': 90, 'MaxWeight': 100, 'Label': '90-100kg'},
    {'Gender': 'm', 'MinWeight': 100, 'MaxWeight': 999, 'Label': 'over 100kg'},
    {'Gender': 'w', 'MinWeight': 0, 'MaxWeight': 48, 'Label': 'under 48kg'},
    {'Gender': 'w', 'MinWeight': 48, 'MaxWeight': 52, 'Label': '48-52kg'},
    {'Gender': 'w', 'MinWeight': 52, 'MaxWeight': 57, 'Label': '52-57kg'},
    {'Gender': 'w', 'MinWeight': 57, 'MaxWeight': 63, 'Label': '57-63kg'},
    {'Gender': 'w', 'MinWeight': 63, 'MaxWeight': 70, 'Label': '63-70kg'},
    {'Gender': 'w', 'MinWeight': 70, 'MaxWeight': 78, 'Label': '70-78kg'},
    {'Gender': 'w', 'MinWeight': 78, 'MaxWeight': 999, 'Label': 'over 78kg'},
]

def create_bracket_config_excel(filename='bracket_config.xlsx'):
    with pd.ExcelWriter(filename) as writer:
        pd.DataFrame(age_eligibility).to_excel(writer, sheet_name='AgeEligibility', index=False)
        pd.DataFrame(options).to_excel(writer, sheet_name='Options', index=False)
        pd.DataFrame(weight_classes).to_excel(writer, sheet_name='WeightClasses', index=False)
    print(f"Excel file '{filename}' created successfully.")

if __name__ == '__main__':
    create_bracket_config_excel()
