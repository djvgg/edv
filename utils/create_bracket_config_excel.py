import pandas as pd
import os

# Data for AgeEligibility sheet
# According to AllgemeineInfos.md (Tunier Juni 2026)
age_eligibility = [
    # U9: Jahrgänge 2018, 2019
    {'BirthYear': 2020, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2019, 'U9': 'X', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2018, 'U9': 'X', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    # U11: Jahrgänge 2016, 2017
    {'BirthYear': 2017, 'U9': '', 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2016, 'U9': '', 'U11': 'X', 'U13': '', 'U15': '', 'U18': '', '18+': ''},
    # U13: Jahrgänge 2014, 2015
    {'BirthYear': 2015, 'U9': '', 'U11': '', 'U13': 'X', 'U15': '', 'U18': '', '18+': ''},
    {'BirthYear': 2014, 'U9': '', 'U11': '', 'U13': 'X', 'U15': 'X', 'U18': '', '18+': ''},  # Double start
    # U15: Jahrgänge 2012, 2013, 2014
    {'BirthYear': 2013, 'U9': '', 'U11': '', 'U13': '', 'U15': 'X', 'U18': '', '18+': ''},
    {'BirthYear': 2012, 'U9': '', 'U11': '', 'U13': '', 'U15': 'X', 'U18': 'X', '18+': ''},  # Double start
    # U18: Jahrgänge 2009, 2010, 2011, 2012
    {'BirthYear': 2011, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': 'X', '18+': ''},
    {'BirthYear': 2010, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': 'X', '18+': ''},
    {'BirthYear': 2009, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': 'X', '18+': 'X'},  # Double start
    # 18+: Jahrgänge < 2009
    {'BirthYear': 2008, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
    {'BirthYear': 2007, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
    {'BirthYear': 2006, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
    {'BirthYear': 2005, 'U9': '', 'U11': '', 'U13': '', 'U15': '', 'U18': '', '18+': 'X'},
]

# Data for Options sheet
options = [
    {'OptionName': 'allow_double_age_bracket', 'Value': 'TRUE'},
    {'OptionName': 'event_year', 'Value': '2026'},
    {'OptionName': 'U9_pool_size', 'Value': '3'},
    {'OptionName': 'U11_pool_size', 'Value': '4'},
]

# Data for WeightClasses sheet
# Note: U9 and U11 have no fixed weight classes (configurable pool size)
# Only U13, U15, U18, and 18+ have defined weight classes
weight_classes = [
    # U13 Men
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 0, 'MaxWeight': 28, 'Label': '-28kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 28, 'MaxWeight': 31, 'Label': '-31kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 31, 'MaxWeight': 34, 'Label': '-34kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 34, 'MaxWeight': 37, 'Label': '-37kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 37, 'MaxWeight': 40, 'Label': '-40kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 40, 'MaxWeight': 43, 'Label': '-43kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 43, 'MaxWeight': 46, 'Label': '-46kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 46, 'MaxWeight': 50, 'Label': '-50kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 50, 'MaxWeight': 55, 'Label': '-55kg'},
    {'Gender': 'm', 'AgeGroup': 'U13', 'MinWeight': 55, 'MaxWeight': 999, 'Label': '+55kg'},
    
    # U15 Men
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 0, 'MaxWeight': 34, 'Label': '-34kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 34, 'MaxWeight': 37, 'Label': '-37kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 37, 'MaxWeight': 40, 'Label': '-40kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 40, 'MaxWeight': 43, 'Label': '-43kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 43, 'MaxWeight': 46, 'Label': '-46kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 46, 'MaxWeight': 50, 'Label': '-50kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 50, 'MaxWeight': 55, 'Label': '-55kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 55, 'MaxWeight': 60, 'Label': '-60kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 60, 'MaxWeight': 66, 'Label': '-66kg'},
    {'Gender': 'm', 'AgeGroup': 'U15', 'MinWeight': 66, 'MaxWeight': 999, 'Label': '+66kg'},
    
    # U18 Men
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 0, 'MaxWeight': 46, 'Label': '-46kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 46, 'MaxWeight': 50, 'Label': '-50kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 50, 'MaxWeight': 55, 'Label': '-55kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 55, 'MaxWeight': 60, 'Label': '-60kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 60, 'MaxWeight': 66, 'Label': '-66kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 66, 'MaxWeight': 73, 'Label': '-73kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 73, 'MaxWeight': 81, 'Label': '-81kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 81, 'MaxWeight': 90, 'Label': '-90kg'},
    {'Gender': 'm', 'AgeGroup': 'U18', 'MinWeight': 90, 'MaxWeight': 999, 'Label': '+90kg'},
    
    # 18+ Men
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 0, 'MaxWeight': 60, 'Label': '-60kg'},
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 60, 'MaxWeight': 66, 'Label': '-66kg'},
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 66, 'MaxWeight': 73, 'Label': '-73kg'},
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 73, 'MaxWeight': 81, 'Label': '-81kg'},
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 81, 'MaxWeight': 90, 'Label': '-90kg'},
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 90, 'MaxWeight': 100, 'Label': '-100kg'},
    {'Gender': 'm', 'AgeGroup': '18+', 'MinWeight': 100, 'MaxWeight': 999, 'Label': '+100kg'},
    
    # U13 Women
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 0, 'MaxWeight': 27, 'Label': '-27kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 27, 'MaxWeight': 30, 'Label': '-30kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 30, 'MaxWeight': 33, 'Label': '-33kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 33, 'MaxWeight': 36, 'Label': '-36kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 36, 'MaxWeight': 40, 'Label': '-40kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 40, 'MaxWeight': 44, 'Label': '-44kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 44, 'MaxWeight': 48, 'Label': '-48kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 48, 'MaxWeight': 52, 'Label': '-52kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 52, 'MaxWeight': 57, 'Label': '-57kg'},
    {'Gender': 'w', 'AgeGroup': 'U13', 'MinWeight': 57, 'MaxWeight': 999, 'Label': '+57kg'},
    
    # U15 Women
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 0, 'MaxWeight': 33, 'Label': '-33kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 33, 'MaxWeight': 36, 'Label': '-36kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 36, 'MaxWeight': 40, 'Label': '-40kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 40, 'MaxWeight': 44, 'Label': '-44kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 44, 'MaxWeight': 48, 'Label': '-48kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 48, 'MaxWeight': 52, 'Label': '-52kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 52, 'MaxWeight': 57, 'Label': '-57kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 57, 'MaxWeight': 63, 'Label': '-63kg'},
    {'Gender': 'w', 'AgeGroup': 'U15', 'MinWeight': 63, 'MaxWeight': 999, 'Label': '+63kg'},
    
    # U18 Women
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 0, 'MaxWeight': 40, 'Label': '-40kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 40, 'MaxWeight': 44, 'Label': '-44kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 44, 'MaxWeight': 48, 'Label': '-48kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 48, 'MaxWeight': 52, 'Label': '-52kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 52, 'MaxWeight': 57, 'Label': '-57kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 57, 'MaxWeight': 63, 'Label': '-63kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 63, 'MaxWeight': 70, 'Label': '-70kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 70, 'MaxWeight': 78, 'Label': '-78kg'},
    {'Gender': 'w', 'AgeGroup': 'U18', 'MinWeight': 78, 'MaxWeight': 999, 'Label': '+78kg'},
    
    # 18+ Women
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 0, 'MaxWeight': 48, 'Label': '-48kg'},
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 48, 'MaxWeight': 52, 'Label': '-52kg'},
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 52, 'MaxWeight': 57, 'Label': '-57kg'},
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 57, 'MaxWeight': 63, 'Label': '-63kg'},
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 63, 'MaxWeight': 70, 'Label': '-70kg'},
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 70, 'MaxWeight': 78, 'Label': '-78kg'},
    {'Gender': 'w', 'AgeGroup': '18+', 'MinWeight': 78, 'MaxWeight': 999, 'Label': '+78kg'},
]

def create_bracket_config_excel(filename='bracket_config.xlsx'):
    # Determine the config folder path
    utils_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(utils_dir, '..', 'config')
    config_dir = os.path.abspath(config_dir)
    
    # Ensure config directory exists
    os.makedirs(config_dir, exist_ok=True)
    
    # Full path to the config file
    filepath = os.path.join(config_dir, filename)
    
    # Create DataFrames with explicit column order
    df_age = pd.DataFrame(age_eligibility)
    # Ensure columns are in correct order
    age_columns = ['BirthYear', 'U9', 'U11', 'U13', 'U15', 'U18', '18+']
    df_age = df_age[age_columns]
    
    # Fill empty strings with NaN for consistency
    df_age = df_age.replace('', pd.NA)
    
    df_options = pd.DataFrame(options)
    df_weight = pd.DataFrame(weight_classes)
    
    # Write to Excel
    with pd.ExcelWriter(filepath) as writer:
        df_age.to_excel(writer, sheet_name='AgeEligibility', index=False)
        df_options.to_excel(writer, sheet_name='Options', index=False)
        df_weight.to_excel(writer, sheet_name='WeightClasses', index=False)
    print(f"Excel file '{filepath}' created successfully.")

if __name__ == '__main__':
    create_bracket_config_excel()
