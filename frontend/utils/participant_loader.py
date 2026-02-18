# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Participant loading and normalization from spreadsheet files."""

import logging
import os
import sys


def load_participants_from_xlsx(file_path):
    """Load participants from XLSX file.
    
    Tries judgefrontend first, then pandas as fallback.
    
    Args:
        file_path: Path to XLSX file
    
    Returns:
        List of participant dicts with Name, Verein, and other fields
    
    Raises:
        ImportError: If neither judgefrontend nor pandas available
        Exception: If file cannot be parsed
    """
    logger = logging.getLogger(__name__)
    
    # Try judgefrontend's flexible handler first
    try:
        judgefrontend_path = os.path.join(os.path.dirname(file_path), '..', '..', '..', 'judgefrontend')
        if os.path.exists(judgefrontend_path):
            sys.path.insert(0, judgefrontend_path)
        
        from src.xlsxHandler import processXlsx
        logger.debug('Using judgefrontend xlsx handler')
        groups = processXlsx(file_path)
        
        # Convert groups to participants format
        participants = []
        for group in groups:
            for fighter in group.get('fighters', []):
                participants.append({
                    'Name': fighter.get('name', fighter.get('Name', '')),
                    'Gender': fighter.get('geschlecht', fighter.get('Gender', fighter.get('gender', ''))),
                    'Age': fighter.get('alter', fighter.get('Age', fighter.get('age'))),
                    'Weight': fighter.get('gewicht', fighter.get('Weight', fighter.get('weight'))),
                    'Verein': fighter.get('verein', fighter.get('Club', fighter.get('club', '')))
                })
        return participants
    except ImportError:
        pass
    
    # Fallback to pandas
    try:
        import pandas as pd
        logger.debug('Using pandas fallback for xlsx reading')
        df = pd.read_excel(file_path)
        
        # Build name from Vorname + Nachname if needed
        if 'Name' not in df.columns and 'Vorname' in df.columns and 'Nachname' in df.columns:
            df['Name'] = df['Vorname'].astype(str) + ' ' + df['Nachname'].astype(str)
        
        participants = []
        for _, row in df.iterrows():
            participants.append({
                'Name': row.get('Name', ''),
                'Gender': row.get('Geschlecht', row.get('Gender', '')),
                'Age': row.get('Alter', row.get('Age')),
                'Weight': row.get('Gewicht', row.get('Weight')),
                'Verein': row.get('Verein', row.get('Club', ''))
            })
        return participants
    except ImportError as e:
        raise ImportError(
            "Neither judgefrontend nor pandas available for XLSX parsing"
        ) from e


def normalize_participants(raw_participants):
    """Normalize participant data to standardized format.
    
    Preserves all original fields while standardizing key field names.
    This allows backend services to access any field they need.
    
    Args:
        raw_participants: List of dicts from XLSX
    
    Returns:
        List of dicts with standardized field names (Name, Verein, Gender, Age, Weight)
        plus all original fields preserved
    
    Raises:
        ValueError: If critical fields missing from all rows
    """
    normalized = []
    logger = logging.getLogger(__name__)
    
    for i, row in enumerate(raw_participants):
        if not isinstance(row, dict):
            logger.warning(f"Row {i} is not a dict, skipping: {row}")
            continue
        
        # Start with all original fields
        row_dict = dict(row)
        
        # Normalize/standardize key field names (case-insensitive mapping)
        # These become the canonical names that backend expects
        for key in list(row_dict.keys()):
            key_lower = str(key).lower()
            
            # Map to standardized names
            if key_lower in ['name', 'kampfer', 'fighter'] and key != 'Name':
                row_dict['Name'] = row_dict.get(key, '')
            elif key_lower in ['verein', 'club', 'verband'] and key != 'Verein':
                row_dict['Verein'] = row_dict.get(key, '')
            elif key_lower in ['geschlecht', 'gender'] and key != 'Gender':
                row_dict['Gender'] = row_dict.get(key, '')
            elif key_lower in ['alter', 'age'] and key != 'Age':
                row_dict['Age'] = row_dict.get(key, '')
            elif key_lower in ['gewicht', 'weight'] and key != 'Weight':
                row_dict['Weight'] = row_dict.get(key, '')
        
        # Validate required Name field
        if not row_dict.get('Name'):
            logger.warning(f"Row {i} missing Name field, skipping")
            continue
        
        # Ensure key fields exist (set to empty string if missing)
        for field in ['Name', 'Verein', 'Gender', 'Age', 'Weight']:
            if field not in row_dict:
                row_dict[field] = ''
        
        normalized.append(row_dict)
    
    if not normalized:
        raise ValueError("No valid participants found in file")
    
    logger.info(f"Loaded and normalized {len(normalized)} participants")
    return normalized
