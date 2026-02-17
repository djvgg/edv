import pandas as pd

class BracketConfig:
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

    def get_age_group(self, birth_year):
        # Returns the first age group (U13, U15, etc.) for which the cell is 'X'
        row = self.age_eligibility[self.age_eligibility['BirthYear'] == birth_year]
        if row.empty:
            return None
        for col in self.age_eligibility.columns[1:]:
            if row.iloc[0][col] == 'X':
                return col
        return None

    def get_weight_class(self, weight, gender):
        gender = gender.lower()[0]  # 'm' or 'w'
        df = self.weight_classes[self.weight_classes['Gender'] == gender]
        for _, row in df.iterrows():
            if row['MinWeight'] <= weight < row['MaxWeight']:
                return row['Label']
        return 'unknown'

# Example usage:
# config = BracketConfig('bracket_config.xlsx')
# print(config.get_age_group(2012))
# print(config.get_weight_class(66, 'm'))
