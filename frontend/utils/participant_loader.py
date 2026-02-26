# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Participant loading and normalization from spreadsheet files."""

from utils.logging import get_logger


def load_participants_from_xlsx(file_path):
    """Load participants from XLSX file using pandas.

    Args:
        file_path: Path to XLSX file

    Returns:
        List of participant dicts with Name, Gender, Weight, Age, etc.

    Raises:
        ImportError: If pandas is not available
        Exception: If file cannot be parsed
    """
    logger = get_logger('participant_loader', debug_verbose=True)
    
    try:
        import pandas as pd
        import re
        logger.debug('Loading XLSX file with pandas')
        
        # Try reading with headers in row 2 (tournament format) first
        try:
            df = pd.read_excel(file_path, header=1)
        except Exception:
            # Fall back to row 1 if row 2 doesn't work
            df = pd.read_excel(file_path, header=0)
        
        df = df.dropna(how='all')  # Remove completely empty rows
        df = df.reset_index(drop=True)
        
        # Clean up column names - remove HTML tags, newlines, extra spaces
        df.columns = [re.sub(r'<[^>]+>', '', col)  # Remove HTML tags
                     .replace('\n', ' ')  # Replace newlines with space
                     .replace('\r', '')  # Remove carriage returns
                     .strip()  # Strip leading/trailing spaces
                     for col in df.columns]
        
        logger.debug(f"XLSX columns (cleaned): {list(df.columns)}")
        logger.debug(f"Total rows: {len(df)}")
        if len(df) > 0:
            logger.debug(f"First row: {df.iloc[0].to_dict()}")
        
        participants = []
        
        for idx, row in df.iterrows():
            # Extract first name and last name
            vorname = ''
            nachname = ''
            
            for col in df.columns:
                col_lower = col.lower()
                if 'vorname' in col_lower and not vorname:
                    if pd.notna(row[col]):
                        vorname = str(row[col]).strip()
                elif ('name' in col_lower and 'nachname' not in col_lower and 'email' not in col_lower 
                      and 'kampfer' not in col_lower and not nachname):
                    if pd.notna(row[col]):
                        nachname = str(row[col]).strip()
            
            # Construct full name
            full_name = ''
            if vorname and nachname:
                full_name = f"{vorname} {nachname}"
            elif vorname:
                full_name = vorname
            elif nachname:
                full_name = nachname
            
            if not full_name:
                logger.debug(f"Row {idx}: Skipping - no name found. Vorname='{vorname}', Name/Nachname='{nachname}'")
                continue
            
            # Extract gender (look for column containing männlich/weiblich)
            gender = ''
            for col in df.columns:
                col_lower = col.lower()
                if ('männlich' in col_lower or 'weiblich' in col_lower or 'geschlecht' in col_lower):
                    if pd.notna(row[col]):
                        gender_val = str(row[col]).strip().lower()
                        # Take first character: m, w, f, etc.
                        if gender_val:
                            gender = gender_val[0]
                        if gender:
                            break
            
            # Extract weight (look for columns containing "gewicht" or "weight")
            weight = None
            weight_source_col = None
            for col in df.columns:
                col_lower = col.lower()
                if 'gewicht' in col_lower or 'weight' in col_lower:
                    if pd.notna(row[col]):
                        try:
                            weight_str = str(row[col]).strip()
                            # Handle weight class format like "-43kg" or "+100kg"
                            if weight_str.startswith('-') or weight_str.startswith('+'):
                                weight_str = re.sub(r'[+-]', '', weight_str)
                            weight_str = re.sub(r'kg.*', '', weight_str).strip()
                            weight = float(weight_str)
                            if weight > 0:
                                weight_source_col = col
                                break
                        except (ValueError, TypeError):
                            pass
            
            # Extract birth year / age (look for jahrgang or age)
            age = None
            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ['jahrgang', 'birthyear', 'birth year', 'age', 'alter']:
                    if pd.notna(row[col]):
                        try:
                            age = int(float(row[col]))
                            break
                        except (ValueError, TypeError):
                            pass
            
            # Extract club
            club = ''
            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ['verein', 'club']:
                    if pd.notna(row[col]):
                        club = str(row[col]).strip()
                        if club:
                            break
            
            # Extract association
            association = ''
            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ['verband', 'association']:
                    if pd.notna(row[col]):
                        association = str(row[col]).strip()
                        if association:
                            break
            
            # Build participant record
            participant = {
                'Name': full_name,
                'Gender': gender,
                'Weight': weight if weight is not None else 0.0,
                'Age': age,
                'Club': club,
                'Association': association,
            }
            
            participants.append(participant)
            logger.debug(f"Row {idx}: Loaded '{full_name}' (gender: {gender}, weight: {weight} from '{weight_source_col}', age: {age})")
        
        logger.info(f"Successfully loaded {len(participants)} participants from XLSX")
        return participants
        
    except ImportError as e:
        raise ImportError("pandas is required for XLSX parsing") from e
    except Exception as e:
        logger.error(f"Error loading XLSX: {e}")
        raise


def normalize_participants(raw_participants):
    """Normalize participant data to standardized format.
    
    Ensures all required fields are present and properly typed.
    
    Args:
        raw_participants: List of dicts from XLSX
    
    Returns:
        List of normalized dicts with Name, Gender, Weight, Age, Club, Association, Paid
    
    Raises:
        ValueError: If no valid participants found
    """
    normalized = []
    logger = get_logger('participant_loader', debug_verbose=True)
    
    for i, row in enumerate(raw_participants):
        if not isinstance(row, dict):
            logger.warning(f"Row {i}: Not a dict, skipping")
            continue
        
        # Validate required fields
        name = row.get('Name', '').strip() if isinstance(row.get('Name'), str) else ''
        
        if not name:
            logger.warning(f"Row {i}: Missing name, skipping")
            continue
        
        # Extract and validate gender
        gender = row.get('Gender', '').strip().lower() if isinstance(row.get('Gender'), str) else ''
        if gender and gender[0] in ['m', 'f', 'w']:
            gender = gender[0]
        else:
            gender = ''
        
        # Extract and validate weight
        try:
            weight = float(row.get('Weight', 0.0))
        except (ValueError, TypeError):
            weight = 0.0
        
        # Extract age
        age = row.get('Age')
        
        # Extract and validate paid status
        paid_str = str(row.get('Paid', row.get('Bezahlt', ''))).strip().lower()
        paid = paid_str in ['true', 'ja', 'yes', '1', 'y']
        
        # Build normalized record
        normalized_row = {
            'Name': name,
            'Gender': gender,
            'Weight': weight,
            'Age': age,
            'Club': str(row.get('Club', '')).strip(),
            'Association': str(row.get('Association', '')).strip(),
            'Paid': paid,
        }
        
        normalized.append(normalized_row)
        logger.debug(f"Normalized row {i}: {name} ({gender}, {weight}kg, age {age})")
    
    if not normalized:
        raise ValueError("No valid participants found in file")
    
    logger.info(f"Normalized {len(normalized)} participants")
    return normalized
