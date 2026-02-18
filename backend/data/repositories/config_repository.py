# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

# Moved from utils/bracket_config_loader.py

import pandas as pd

class ConfigRepository:
    def __init__(self, excel_path):
        self.excel_path = excel_path
        self.age_eligibility = None
        self.options = None
        self.weight_classes = None
        self._load_config()

    def _load_config(self):
        self.age_eligibility = pd.read_excel(self.excel_path, sheet_name='AgeEligibility')
        self.options = pd.read_excel(self.excel_path, sheet_name='Options')
        self.weight_classes = pd.read_excel(self.excel_path, sheet_name='WeightClasses')

    def get_event_year(self):
        row = self.options[self.options['OptionName'] == 'event_year']
        if not row.empty:
            return int(row.iloc[0]['Value'])
        return None

    def get_pool_size(self, age_group):
        """
        Get the pool size configuration for U9 and U11 age groups.
        
        Args:
            age_group: The age group (e.g., 'U9', 'U11')
        
        Returns:
            The pool size as integer, or None if not configured
        """
        if age_group not in ('U9', 'U11'):
            return None
        
        option_name = f'{age_group}_pool_size'
        row = self.options[self.options['OptionName'] == option_name]
        if not row.empty:
            try:
                return int(row.iloc[0]['Value'])
            except (ValueError, TypeError):
                return None
        return None

    def get_age_group(self, birth_year):
        # Returns the first age group (U13, U15, etc.) for which the cell is 'X'
        row = self.age_eligibility[self.age_eligibility['BirthYear'] == birth_year]
        if row.empty:
            return None
        for col in self.age_eligibility.columns[1:]:
            if row.iloc[0][col] == 'X':
                return col
        return None

    def get_weight_class(self, weight, gender, age_group=None):
        """
        Get weight class for a participant.
        
        Args:
            weight: The participant's weight in kg
            gender: The participant's gender ('m', 'w', 'M', 'W', 'Male', 'Female', 'F', etc.)
            age_group: Optional age group (e.g., 'U13', 'U15', 'U18', '18+')
                      If provided, returns age-group-specific weight class
                      If not provided or age_group is U9/U11, returns 'no-class' since those age groups
                      have no fixed weight classes (configurable pool size)
        
        Returns:
            The weight class label string, or 'unknown' if not found
        """
        # U9 and U11 have no fixed weight classes
        if age_group in ('U9', 'U11'):
            return 'no-class'
        
        # Normalize gender: m/M/Male -> 'm', w/W/Female/F -> 'w'
        gender_str = str(gender).lower().strip()
        if gender_str in ('m', 'male'):
            gender = 'm'
        elif gender_str in ('w', 'f', 'female', 'frau'):
            gender = 'w'
        else:
            # Fallback: take first character
            gender = gender_str[0] if gender_str else 'm'
        
        # If age_group is provided, use it to filter weight classes
        if age_group:
            df = self.weight_classes[
                (self.weight_classes['Gender'] == gender) & 
                (self.weight_classes['AgeGroup'] == age_group)
            ]
        else:
            # Fallback to gender only (for backward compatibility)
            df = self.weight_classes[self.weight_classes['Gender'] == gender]
            # Exclude age-group-specific rows if no age_group is specified
            if 'AgeGroup' in df.columns:
                df = df[df['AgeGroup'].isna()]
        
        for _, row in df.iterrows():
            if row['MinWeight'] <= weight < row['MaxWeight']:
                return row['Label']
        return 'unknown'

# Example usage:
# config = ConfigRepository('bracket_config.xlsx')
# print(config.get_age_group(2012))
# print(config.get_weight_class(66, 'm'))

# Backward compatibility alias
BracketConfig = ConfigRepository
