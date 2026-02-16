
import os
from libraries.logging import get_logger
from .utils.bracket_utils import set_bracket_config, export_all_brackets

# Set up logger
debug_logger = get_logger('bracket_test')

def main():
    # Set config path (adjust if needed) — use edv_backend/bracket_config.xlsx
    set_bracket_config(os.path.abspath(os.path.join(os.path.dirname(__file__), 'bracket_config.xlsx')))

    # Sample participants (adjust fields as needed)
    participants = [
        {'Name': 'Alice', 'Gender': 'w', 'Age': 14, 'Weight': 52, 'Club': 'Judo Club A'},
        {'Name': 'Bob', 'Gender': 'm', 'Age': 15, 'Weight': 66, 'Club': 'Judo Club B'},
        {'Name': 'Charlie', 'Gender': 'm', 'Age': 17, 'Weight': 81, 'Club': 'Judo Club C'},
        {'Name': 'Diana', 'Gender': 'w', 'Age': 13, 'Weight': 48, 'Club': 'Judo Club D'},
        {'Name': 'Eve', 'Gender': 'w', 'Age': 18, 'Weight': 70, 'Club': 'Judo Club E'},
        {'Name': 'Frank', 'Gender': 'm', 'Age': 18, 'Weight': 100, 'Club': 'Judo Club F'},
    ]

    debug_logger.info('Testing export_all_brackets with sample participants...')
    brackets = export_all_brackets(participants)
    for bracket_key, data in brackets.items():
        debug_logger.info(f"Bracket: {bracket_key}")
        debug_logger.info(f"Fighters: {[p['Name'] for p in data['fighters']]}")
        debug_logger.info(f"Bracket matches: {data['bracket']}")

if __name__ == '__main__':
    main()
