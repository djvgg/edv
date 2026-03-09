# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""DataLoaderService - Handles all data loading and filtering operations.

Extracted from main_window.py:
- Loading participants from XLSX, database, and JSON
- Filtering unpaid and invalid-age participants
- Creating quarantine brackets
- Splitting participants by gender to JSON
"""

import json
import os
from tkinter import filedialog

from utils.logging import get_logger
from utils.task_runner import TaskRunner
from backend.services.bracket_service import export_all_brackets, validate_age_from_birthyear
from frontend.utils import (
    load_participants_from_xlsx,
    normalize_participants,
)


class DataLoaderService:
    """Handles all participant data loading and filtering operations."""

    def __init__(self, ui_feedback=None, quarantine_service=None, db_service=None, task_runner=None):
        """Initialize the DataLoaderService.
        
        Args:
            ui_feedback: UIFeedbackService instance for progress updates
            quarantine_service: QuarantineService instance for rejected participants
            db_service: DatabaseService instance for database operations
            task_runner: TaskRunner instance for background operations (optional, created if not provided)
        """
        self.logger = get_logger('data_loader_service', debug_verbose=True)
        self.ui_feedback = ui_feedback
        self.quarantine_service = quarantine_service
        self.db_service = db_service
        self.task_runner = task_runner or TaskRunner(num_workers=2)

    def filter_unpaid_participants(self, all_participants):
        """Filter out unpaid participants and show a popup if any are found.
        
        Args:
            all_participants: List of participant dicts with 'Paid' field
        
        Returns:
            Tuple of (paid_participants, unpaid_list) where unpaid_list contains full
            participant dicts with 'rejection_reason' field added
        """
        paid_participants = []
        unpaid_participants = []
        
        for p in all_participants:
            # Check if paid field exists and is truthy
            is_paid = p.get('Paid', False)
            
            if is_paid:
                paid_participants.append(p)
            else:
                # Add full participant data with rejection reason
                unpaid_entry = dict(p)
                unpaid_entry['rejection_reason'] = 'unpaid'
                unpaid_participants.append(unpaid_entry)
        
        if unpaid_participants:
            unpaid_names = ['{} {}'.format(
                p.get('Firstname', p.get('Vorname', '')),
                p.get('Lastname', p.get('Nachname', ''))
            ).strip() or p.get('Name', 'Unknown') for p in unpaid_participants]
            self.logger.info(f"Filtered out {len(unpaid_participants)} unpaid participant(s): {', '.join(unpaid_names)}")
        
        return paid_participants, unpaid_participants

    def filter_invalid_ages(self, all_participants, min_age=6, max_age=120):
        """Filter out participants with invalid ages.
        
        Uses unified validate_age_from_birthyear() for consistent validation across the app.
        
        Args:
            all_participants: List of participant dicts with Birthyear or Age fields
            min_age: Minimum valid age (configurable, default 6)
            max_age: Maximum valid age (configurable, default 120)
        
        Returns:
            Tuple of (valid_participants, invalid_list) where invalid_list contains dicts 
            with name, age, and rejection reason
        """
        valid_participants = []
        invalid_participants = []
        
        for p in all_participants:
            # Try Birthyear first, fall back to Age field (both can contain birthyear)
            birthyear = p.get('Birthyear') or p.get('Age')
            
            # Use unified validation function (SINGLE SOURCE OF TRUTH)
            age_group, calculated_age, is_valid, rejection_reason = validate_age_from_birthyear(
                birthyear, min_age=min_age, max_age=max_age
            )
            
            if is_valid:
                valid_participants.append(p)
            else:
                # Add rejection info to participant data
                invalid_entry = dict(p)
                # Normalize all age-related rejections to "age_out_of_bounds" category
                # (too old, too young, missing age all go to same quarantine)
                if rejection_reason and ('too old' in rejection_reason or 'too young' in rejection_reason or 'Missing' in str(rejection_reason)):
                    invalid_entry['rejection_reason'] = 'age_out_of_bounds'
                else:
                    invalid_entry['rejection_reason'] = rejection_reason
                invalid_entry['age'] = calculated_age
                invalid_entry['age_group'] = age_group
                invalid_participants.append(invalid_entry)
        
        if invalid_participants:
            self.logger.info(f"Filtered out {len(invalid_participants)} participants with invalid ages")
        
        return valid_participants, invalid_participants

    def filter_invalid_valid(self, all_participants):
        """Filter out participants with Valid field set to False.
        
        Some data sources (JSON) include a Valid field that marks whether
        a participant should be included. This filters based on that field.
        
        Args:
            all_participants: List of participant dicts with optional 'Valid' field
        
        Returns:
            Tuple of (valid_participants, invalid_list) where invalid_list contains dicts
            with participants that have Valid=False
        """
        valid_participants = []
        invalid_participants = []
        
        for p in all_participants:
            # Check Valid field (default to True if not present)
            is_valid = p.get('Valid', True)
            
            if is_valid:
                valid_participants.append(p)
            else:
                # Add rejection info
                invalid_entry = dict(p)
                invalid_entry['rejection_reason'] = 'marked_invalid'
                invalid_participants.append(invalid_entry)
        
        if invalid_participants:
            self.logger.info(f"Filtered out {len(invalid_participants)} participant(s) marked as invalid")
        
        return valid_participants, invalid_participants

    def load_and_generate(self, callbacks):
        """Load participants from XLSX file and generate brackets.
        
        Args:
            callbacks: Dict with 'on_success' function to call when complete
        """
        filepath = filedialog.askopenfilename(
            title="Select Participant XLSX File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not filepath:
            return

        # Show loading progress dialog
        if self.ui_feedback:
            self.ui_feedback.show_loading_progress("Loading and generating brackets...")
        
        # Run loading in background thread via task runner
        self.task_runner.submit_task(
            'load_xlsx',
            fn=lambda on_progress=None: self._load_and_generate_thread(filepath, callbacks),
            on_error=self._handle_load_error
        )

    def _load_and_generate_thread(self, filepath, callbacks):
        """Background task for loading XLSX and generating brackets."""
        try:
            if self.ui_feedback:
                self.ui_feedback.set_status("Reading XLSX file...", '#999999')  # text_secondary
                self.ui_feedback.update_progress(10)

            # Load and normalize participants from XLSX
            raw_participants = load_participants_from_xlsx(filepath)
            if self.ui_feedback:
                self.ui_feedback.update_progress(30)
            
            participants = normalize_participants(raw_participants)
            if self.ui_feedback:
                self.ui_feedback.update_progress(40)
            if self.db_service:
                self.db_service.save_participants(participants)
                self.db_service.initialize_all_groups()

            # Filter out unpaid participants
            participants, unpaid = self.filter_unpaid_participants(participants)

            # Filter out participants marked as invalid (Valid field)
            participants, invalid_valid = self.filter_invalid_valid(participants)

            # Filter out participants with invalid ages
            participants, invalid_ages = self.filter_invalid_ages(participants)
            
            # Create QUARANTINE bracket with all rejected participants
            all_rejected = unpaid + invalid_valid + invalid_ages
            brackets = {}
            if all_rejected and self.quarantine_service:
                self.quarantine_service.create_quarantine_bracket(brackets, all_rejected)

            if not participants:
                if self.ui_feedback:
                    self.ui_feedback.set_status("Error: No valid participants found.", '#cc0000')  # accent_red
                    self.ui_feedback.hide_loading_progress()
                return

            total_fighters = len(participants)
            if self.ui_feedback:
                self.ui_feedback.set_info_text(f"✓ {total_fighters} participants loaded")
                self.ui_feedback.update_progress(50)
                self.ui_feedback.set_status("Generating brackets...", '#999999')

            # Generate brackets using backend service
            brackets.update(export_all_brackets(participants))
            if self.ui_feedback:
                self.ui_feedback.update_progress(80)

            if self.ui_feedback:
                self.ui_feedback.set_status(f"Success! Generated {len(brackets)} brackets.", '#00cc00')  # accent_green
                self.ui_feedback.update_progress(100)
                self.ui_feedback.hide_loading_progress()

            # Call success callback with brackets and rejection info
            if 'on_success' in callbacks and callable(callbacks['on_success']):
                callbacks['on_success'](
                    brackets=brackets,
                    rejected_participants=all_rejected
                )

        except Exception as e:
            self.logger.error(f"Error during load and generate: {e}")
            if self.ui_feedback:
                self.ui_feedback.set_status(f"Error: {e}", '#cc0000')
                self.ui_feedback.hide_loading_progress()

    def load_from_database(self, callbacks):
        """Load participants from PostgreSQL database and generate brackets.
        
        Args:
            callbacks: Dict with 'on_success' function to call when complete
        """
        # Show loading progress dialog
        if self.ui_feedback:
            self.ui_feedback.show_loading_progress("Loading from database...")
        
        # Run loading in background thread via task runner
        self.task_runner.submit_task(
            'load_database',
            fn=lambda on_progress=None: self._load_from_database_thread(callbacks),
            on_error=self._handle_load_error
        )

    def _load_from_database_thread(self, callbacks):
        """Background task for loading from database and generating brackets."""
        try:
            if self.ui_feedback:
                self.ui_feedback.set_status("Connecting to database...", '#999999')
                self.ui_feedback.update_progress(10)

            # Fetch participants from database
            if not self.db_service:
                raise RuntimeError("Database service not available")
            
            participants = self.db_service.fetch_participants()
            if self.ui_feedback:
                self.ui_feedback.update_progress(30)

            if not participants:
                if self.ui_feedback:
                    self.ui_feedback.set_status("Error: No participants found in database.", '#cc0000')
                    self.ui_feedback.hide_loading_progress()
                    self.ui_feedback.show_warning("No Data", "No participants found in database.")
                return

            # Filter out unpaid participants
            participants, unpaid = self.filter_unpaid_participants(participants)

            # Filter out participants marked as invalid (Valid field)
            participants, invalid_valid = self.filter_invalid_valid(participants)

            # Filter out participants with invalid ages
            participants, invalid_ages = self.filter_invalid_ages(participants)
            
            # Create QUARANTINE bracket with all rejected participants
            all_rejected = unpaid + invalid_valid + invalid_ages
            brackets = {}
            if all_rejected and self.quarantine_service:
                self.quarantine_service.create_quarantine_bracket(brackets, all_rejected)

            if not participants:
                if self.ui_feedback:
                    self.ui_feedback.set_status("Error: No valid participants found in database.", '#cc0000')
                    self.ui_feedback.hide_loading_progress()
                    self.ui_feedback.show_warning("No Data", "No valid participants found in database.")
                return

            total_fighters = len(participants)
            if self.ui_feedback:
                self.ui_feedback.set_info_text(f"✓ {total_fighters} participants loaded from database")
                self.ui_feedback.update_progress(50)
                self.ui_feedback.set_status("Generating brackets...", '#999999')

            # Generate brackets using backend service
            brackets.update(export_all_brackets(participants))
            if self.ui_feedback:
                self.ui_feedback.update_progress(80)

            if self.ui_feedback:
                self.ui_feedback.set_status(f"Success! Generated {len(brackets)} brackets from database.", '#00cc00')
                self.ui_feedback.update_progress(100)
                self.ui_feedback.hide_loading_progress()

            # Call success callback with brackets and rejection info
            if 'on_success' in callbacks and callable(callbacks['on_success']):
                callbacks['on_success'](
                    brackets=brackets,
                    rejected_participants=all_rejected
                )

        except Exception as e:
            self.logger.error(f"Database error during load: {e}")
            if self.ui_feedback:
                self.ui_feedback.set_status(f"Database Error: {e}", '#cc0000')
                self.ui_feedback.hide_loading_progress()
                self.ui_feedback.show_error("Database Error", f"Failed to load from database:\n{str(e)}")

    def load_json_and_generate(self, filepaths, callbacks):
        """Load participants from 2 JSON files (male/female) and generate brackets.
        
        Args:
            filepaths: Tuple of 2 JSON file paths
            callbacks: Dict with 'on_success' callback function
        """
        if self.ui_feedback:
            self.ui_feedback.show_loading_progress("Loading and generating brackets from JSON...")
        
        self.task_runner.submit_task(
            'load_json',
            fn=lambda on_progress=None: self._load_json_and_generate_thread(filepaths, callbacks),
            on_error=self._handle_load_error
        )

    def _load_json_and_generate_thread(self, filepaths, callbacks):
        """Background task for loading JSON files and generating brackets."""
        try:
            if self.ui_feedback:
                self.ui_feedback.set_status("Reading JSON files...", '#888888')
                self.ui_feedback.update_progress(10)
            self.logger.info(f"Loading {len(filepaths)} JSON files")

            all_participants = []
            required_core_fields = ['Firstname', 'Lastname', 'Birthyear', 'Weight', 'Gender']

            # Load both JSON files
            for file_idx, filepath in enumerate(filepaths, 1):
                filename = os.path.basename(filepath)
                self.logger.info(f"[File {file_idx}] Loading: {filename}")
                
                progress = 20 + (file_idx - 1) * 30
                if self.ui_feedback:
                    self.ui_feedback.update_progress(progress)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate that data is a list
                if not isinstance(data, list):
                    error_msg = f"File must contain a JSON array.\nFile: {filename}\nGot: {type(data).__name__}"
                    self.logger.error(error_msg)
                    if self.ui_feedback:
                        self.ui_feedback.hide_loading_progress()
                        self.ui_feedback.set_status(error_msg, '#cc0000')
                        self.ui_feedback.show_error("Invalid JSON Format", error_msg)
                    return

                self.logger.debug(f"[File {file_idx}] Found {len(data)} entries")
                valid_count = 0

                # Validate each participant
                for idx, participant in enumerate(data, 1):
                    if not isinstance(participant, dict):
                        error_msg = f"Participant {idx} is not a valid object (got {type(participant).__name__}).\nFile: {filename}"
                        self.logger.error(error_msg)
                        if self.ui_feedback:
                            self.ui_feedback.hide_loading_progress()
                            self.ui_feedback.set_status(error_msg, '#cc0000')
                            self.ui_feedback.show_error("Invalid Participant", error_msg)
                        return

                    # Check for required core fields
                    missing_fields = [field for field in required_core_fields if field not in participant]
                    if missing_fields:
                        error_msg = f"Participant {idx} is missing required fields: {', '.join(missing_fields)}\nFile: {filename}"
                        self.logger.error(error_msg)
                        if self.ui_feedback:
                            self.ui_feedback.hide_loading_progress()
                            self.ui_feedback.set_status(error_msg, '#cc0000')
                            self.ui_feedback.show_error("Missing Required Fields", error_msg)
                        return

                    # Validate field types and values
                    validation_errors = []
                    
                    if not isinstance(participant.get('Firstname'), str) or not participant.get('Firstname', '').strip():
                        validation_errors.append("Firstname must be non-empty string")
                    if not isinstance(participant.get('Lastname'), str) or not participant.get('Lastname', '').strip():
                        validation_errors.append("Lastname must be non-empty string")
                    
                    birthyear = participant.get('Birthyear')
                    if birthyear is not None and not isinstance(birthyear, int):
                        try:
                            participant['Birthyear'] = int(birthyear)
                        except (ValueError, TypeError):
                            validation_errors.append(f"Birthyear must be integer, got: {birthyear}")
                    
                    weight = participant.get('Weight')
                    if weight is not None:
                        try:
                            participant['Weight'] = float(weight)
                        except (ValueError, TypeError):
                            validation_errors.append(f"Weight must be number, got: {weight}")
                    
                    gender = str(participant.get('Gender', '')).strip().lower()
                    if gender in ['m', 'male', 'maennlich', 'männlich']:
                        participant['Gender'] = 'male'
                    elif gender in ['w', 'f', 'female', 'weiblich', 'frau']:
                        participant['Gender'] = 'female'
                    else:
                        validation_errors.append(f"Gender must be male/female/männlich/weiblich, got: {gender}")
                    
                    if validation_errors:
                        error_msg = f"Participant {idx} validation failed:\n" + "\n".join(f"  • {err}" for err in validation_errors) + f"\nFile: {filename}"
                        self.logger.error(error_msg)
                        if self.ui_feedback:
                            self.ui_feedback.hide_loading_progress()
                            self.ui_feedback.set_status(error_msg, '#cc0000')
                            self.ui_feedback.show_error("Validation Error", error_msg)
                        return

                    # Construct Name field from Firstname + Lastname if not present
                    if 'Name' not in participant:
                        participant['Name'] = f"{participant['Firstname']} {participant['Lastname']}".strip()
                    
                    # Ensure Age field exists (use Birthyear)
                    if 'Age' not in participant:
                        participant['Age'] = participant.get('Birthyear')
                    
                    valid_count += 1
                    all_participants.append(participant)

                self.logger.info(f"[File {file_idx}] Successfully validated {valid_count} participants")

            if self.ui_feedback:
                self.ui_feedback.update_progress(60)

            if not all_participants:
                error_msg = "No valid participants found in JSON files."
                self.logger.error(error_msg)
                if self.ui_feedback:
                    self.ui_feedback.hide_loading_progress()
                    self.ui_feedback.set_status(error_msg, '#cc0000')
                return

            if self.db_service:
                self.db_service.save_participants(all_participants)
                self.db_service.initialize_all_groups()

            if self.ui_feedback:
                self.ui_feedback.set_status("Filtering participants...", '#888888')
                self.ui_feedback.update_progress(65)

            # Filter out unpaid participants
            all_participants, unpaid = self.filter_unpaid_participants(all_participants)

            if self.ui_feedback:
                self.ui_feedback.update_progress(70)

            # Filter out participants marked as invalid (Valid field)
            all_participants, invalid_valid = self.filter_invalid_valid(all_participants)

            if self.ui_feedback:
                self.ui_feedback.update_progress(72)

            # Filter out participants with invalid ages
            all_participants, invalid_ages = self.filter_invalid_ages(all_participants)
            
            if self.ui_feedback:
                self.ui_feedback.update_progress(75)

            # Create QUARANTINE bracket with all rejected participants
            all_rejected = unpaid + invalid_valid + invalid_ages
            brackets = {}
            if all_rejected and self.quarantine_service:
                self.quarantine_service.create_quarantine_bracket(brackets, all_rejected)

            if not all_participants:
                error_msg = "No valid participants found in JSON files."
                self.logger.error(error_msg)
                if self.ui_feedback:
                    self.ui_feedback.hide_loading_progress()
                    self.ui_feedback.set_status(error_msg, '#cc0000')
                return

            total_fighters = len(all_participants)
            self.logger.info(f"Total valid participants loaded: {total_fighters}")
            if self.ui_feedback:
                self.ui_feedback.set_info_text(f"✓ {total_fighters} valid participants loaded from JSON files")
                self.ui_feedback.set_status("Generating brackets...", '#888888')
                self.ui_feedback.update_progress(85)
            self.logger.info("Starting bracket generation...")

            # Generate brackets
            brackets.update(export_all_brackets(all_participants))
            if self.ui_feedback:
                self.ui_feedback.update_progress(95)
            
            if self.ui_feedback:
                self.ui_feedback.set_status(f"Success! Generated {len(brackets)} brackets from JSON files.", '#00cc00')
                self.ui_feedback.update_progress(100)
                self.ui_feedback.hide_loading_progress()

            # Call success callback with brackets and rejection info
            if 'on_success' in callbacks and callable(callbacks['on_success']):
                callbacks['on_success'](
                    brackets=brackets,
                    rejected_participants=all_rejected
                )

        except json.JSONDecodeError as e:
            error_msg = f"JSON Parse Error: {e}"
            self.logger.error(error_msg)
            if self.ui_feedback:
                self.ui_feedback.set_status(error_msg, '#cc0000')
                self.ui_feedback.hide_loading_progress()
                self.ui_feedback.show_error("JSON Error", f"Failed to parse JSON file:\n{str(e)}")
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self.logger.error(error_msg)
            if self.ui_feedback:
                self.ui_feedback.set_status(error_msg, '#cc0000')
                self.ui_feedback.hide_loading_progress()
                self.ui_feedback.show_error("File Error", f"Could not find file:\n{str(e)}")
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.logger.error(error_msg)
            if self.ui_feedback:
                self.ui_feedback.set_status(error_msg, '#cc0000')
                self.ui_feedback.hide_loading_progress()
                self.ui_feedback.show_error("Error", f"Failed to load JSON files:\n{str(e)}")
    def split_gender_to_json_with_tolerances(self, input_file, save_dir, configured_tolerances=None):
        """Split tournament registration XLSX by gender and save with tolerance configuration.
        
        Reads tournament registration XLSX, splits participants by gender (M/W),
        and saves:
        - contestants_male.json
        - contestants_female.json
        - tolerance_settings.json (if tolerances provided)
        
        Args:
            input_file: Path to tournament registration XLSX file
            save_dir: Directory to save the split JSON files
            configured_tolerances: Dict mapping (gender, age_group) -> tolerance_value
                                  Obtained from ToleranceConfigDialog.show() in main_window
                                  If None, only contestant files are saved without tolerances
        
        Args:
            input_file: Path to tournament registration XLSX file
            save_dir: Directory to save the split JSON files
            tolerance_dialog_class: ToleranceConfigDialog class from frontend.views
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if self.ui_feedback:
                self.ui_feedback.set_status("Reading tournament XLSX file...", '#999999')
            
            # Load participants using the tournament format parser
            raw_participants = load_participants_from_xlsx(input_file)
            
            if not raw_participants:
                return False, "No participants found in the file."
            
            self.logger.debug(f"Loaded {len(raw_participants)} raw participants from {input_file}")
            
            if self.ui_feedback:
                self.ui_feedback.set_status("Splitting by gender and converting to English format...", '#999999')
            
            # Split by gender and convert to English field names
            male_contestants = []
            female_contestants = []
            skipped_participants = []
            
            for idx, p in enumerate(raw_participants, 1):
                # Extract gender
                gender = str(p.get('Gender', '')).strip().lower()
                
                # Try alternative gender field names
                if not gender:
                    for gender_field in ['Geschlecht', 'gender']:
                        if gender_field in p and p[gender_field]:
                            gender = str(p[gender_field]).strip().lower()
                            break
                
                # Normalize gender
                if gender in ['m', 'male', 'männlich', 'maennlich']:
                    gender_normalized = 'male'
                elif gender in ['w', 'female', 'weiblich', 'f']:
                    gender_normalized = 'female'
                else:
                    # Skip participants with missing gender
                    participant_name = p.get('Name', f"ID {idx}")
                    skipped_participants.append({
                        'name': participant_name,
                        'gender': gender if gender else '(empty)',
                        'id': idx
                    })
                    self.logger.warning(f"Skipping participant with missing/invalid gender '{gender}': {participant_name}")
                    continue
                
                # Split full name
                full_name = p.get('Name', '')
                name_parts = full_name.split(' ', 1)
                firstname = name_parts[0] if len(name_parts) > 0 else ''
                lastname = name_parts[1] if len(name_parts) > 1 else ''
                
                # Extract birthyear
                birthyear = None
                for year_field in ['BirthYear', 'Jahrgang', 'Age']:
                    if year_field in p and p[year_field]:
                        try:
                            birthyear = int(p[year_field])
                            break
                        except (ValueError, TypeError):
                            pass
                
                # Extract other fields
                club = p.get('Verein', p.get('Club', ''))
                association = p.get('Verband', p.get('Association', ''))
                weight = 0.0  # Will be filled during weighing
                
                # Extract paid status
                paid_str = str(p.get('Bezahlt', p.get('Paid', ''))).strip().lower()
                paid = paid_str in ['true', 'ja', 'yes', '1', 'y']
                
                # Create contestant record
                contestant = {
                    'ID': idx,
                    'Firstname': firstname,
                    'Lastname': lastname,
                    'Name': f"{firstname} {lastname}".strip(),
                    'Birthyear': birthyear,
                    'Club': club,
                    'Association': association,
                    'Weight': weight,
                    'Valid': False,
                    'Gender': gender_normalized,
                    'Paid': paid
                }
                
                if gender_normalized == 'male':
                    male_contestants.append(contestant)
                else:
                    female_contestants.append(contestant)
            
            male_count = len(male_contestants)
            female_count = len(female_contestants)
            
            if male_count == 0 and female_count == 0:
                return False, "No valid contestants found with recognized gender."
            
            if self.ui_feedback:
                self.ui_feedback.set_status("Saving JSON files...", '#999999')
            
            # Ensure save directory exists
            os.makedirs(save_dir, exist_ok=True)
            
            # Save male contestants
            if male_count > 0:
                male_file = os.path.join(save_dir, 'contestants_male.json')
                with open(male_file, 'w', encoding='utf-8') as f:
                    json.dump(male_contestants, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Saved {male_count} male contestants to: {male_file}")
            
            # Save female contestants
            if female_count > 0:
                female_file = os.path.join(save_dir, 'contestants_female.json')
                with open(female_file, 'w', encoding='utf-8') as f:
                    json.dump(female_contestants, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Saved {female_count} female contestants to: {female_file}")
            
            # Save tolerance settings with proper structure
            if configured_tolerances:
                tolerance_settings = {
                    "ageRange": {
                        "minAge": 6,
                        "maxAge": 35
                    },
                    "ageClassTolerance": {
                        "mixed": {},
                        "male": {},
                        "female": {}
                    }
                }
                
                for (gender, age_group), tolerance_value in configured_tolerances.items():
                    # Map age group: '18+' -> 'Senior'
                    mapped_age_group = 'Senior' if age_group == '18+' else age_group
                    
                    if gender == 'mixed':
                        # Mixed categories (U9, U11)
                        tolerance_settings["ageClassTolerance"]["mixed"][mapped_age_group] = int(tolerance_value)
                    else:
                        # Gender-specific categories (U13+)
                        if gender == 'm':
                            tolerance_settings["ageClassTolerance"]["male"][mapped_age_group] = int(tolerance_value)
                        elif gender == 'w':
                            tolerance_settings["ageClassTolerance"]["female"][mapped_age_group] = int(tolerance_value)
                
                tolerances_file = os.path.join(save_dir, 'tolerance_settings.json')
                with open(tolerances_file, 'w', encoding='utf-8') as f:
                    json.dump(tolerance_settings, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Saved tolerance configuration to: {tolerances_file}")
            
            if self.ui_feedback:
                self.ui_feedback.set_status("Split complete! Files ready for weighing.", '#00cc00')
            
            success_msg = "Successfully saved split files:\n"
            if male_count > 0:
                success_msg += f"• contestants_male.json ({male_count} entries)\n"
            if female_count > 0:
                success_msg += f"• contestants_female.json ({female_count} entries)\n"
            success_msg += "• tolerance_settings.json (weight tolerance configuration)\n"
            
            return True, success_msg
        
        except Exception as e:
            error_msg = f"Failed to split participants: {str(e)}"
            self.logger.exception(error_msg)
            if self.ui_feedback:
                self.ui_feedback.set_status(error_msg, '#cc0000')
            return False, error_msg

    def _handle_load_error(self, error: Exception):
        """Handle errors from background loading tasks."""
        self.logger.error(f"Background task error: {error}", exc_info=True)
        if self.ui_feedback:
            self.ui_feedback.set_status(f"Error: {error}", '#cc0000')
            self.ui_feedback.hide_loading_progress()