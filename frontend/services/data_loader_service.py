# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""DataLoaderService - Handles all data loading and filtering operations.

Extracted from main_window.py:
- Loading participants from XLSX, database, and JSON
- Filtering unpaid and invalid-age participants
- Creating quarantine brackets
- Splitting participants by gender to JSON
"""

import datetime
import json
import os
import threading
import traceback
from tkinter import filedialog, messagebox

from utils.logging import get_logger
from backend.services.bracket_service import export_all_brackets, validate_age_from_birthyear
from frontend.utils import (
    load_participants_from_xlsx,
    normalize_participants,
)


class DataLoaderService:
    """Handles all participant data loading and filtering operations."""

    def __init__(self, ui_feedback=None, quarantine_service=None, db_service=None):
        """Initialize the DataLoaderService.
        
        Args:
            ui_feedback: UIFeedbackService instance for progress updates
            quarantine_service: QuarantineService instance for rejected participants
            db_service: DatabaseService instance for database operations
        """
        self.logger = get_logger('data_loader_service', debug_verbose=True)
        self.ui_feedback = ui_feedback
        self.quarantine_service = quarantine_service
        self.db_service = db_service

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
                invalid_entry['rejection_reason'] = rejection_reason
                invalid_entry['age'] = calculated_age
                invalid_entry['age_group'] = age_group
                invalid_participants.append(invalid_entry)
        
        if invalid_participants:
            invalid_names = ['{} {}'.format(
                p.get('Firstname', p.get('Vorname', '')),
                p.get('Lastname', p.get('Nachname', ''))
            ).strip() or p.get('Name', 'Unknown') for p in invalid_participants]
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
            invalid_names = ['{} {}'.format(
                p.get('Firstname', p.get('Vorname', '')),
                p.get('Lastname', p.get('Nachname', ''))
            ).strip() or p.get('Name', 'Unknown') for p in invalid_participants]
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
        
        # Run loading in background thread
        thread = threading.Thread(
            target=self._load_and_generate_thread,
            args=(filepath, callbacks),
            daemon=True
        )
        thread.start()

    def _load_and_generate_thread(self, filepath, callbacks):
        """Background thread for loading XLSX and generating brackets."""
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
        
        # Run loading in background thread
        thread = threading.Thread(
            target=self._load_from_database_thread,
            args=(callbacks,),
            daemon=True
        )
        thread.start()

    def _load_from_database_thread(self, callbacks):
        """Background thread for loading from database and generating brackets."""
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
                messagebox.showwarning("No Data", "No participants found in database.")
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
                messagebox.showwarning("No Data", "No valid participants found in database.")
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
            messagebox.showerror("Database Error", f"Failed to load from database:\n{str(e)}")

    def load_json_and_generate(self, filepaths, callbacks):
        """Load participants from 2 JSON files (male/female) and generate brackets.
        
        Args:
            filepaths: Tuple of 2 JSON file paths
            callbacks: Dict with 'on_success' callback function
        """
        if self.ui_feedback:
            self.ui_feedback.show_loading_progress("Loading and generating brackets from JSON...")
        
        thread = threading.Thread(target=self._load_json_and_generate_thread, args=(filepaths, callbacks), daemon=True)
        thread.start()

    def _load_json_and_generate_thread(self, filepaths, callbacks):
        """Background thread for loading JSON files and generating brackets."""
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
                    messagebox.showerror("Invalid JSON Format", error_msg)
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
                        messagebox.showerror("Invalid Participant", error_msg)
                        return

                    # Check for required core fields
                    missing_fields = [field for field in required_core_fields if field not in participant]
                    if missing_fields:
                        error_msg = f"Participant {idx} is missing required fields: {', '.join(missing_fields)}\nFile: {filename}"
                        self.logger.error(error_msg)
                        if self.ui_feedback:
                            self.ui_feedback.hide_loading_progress()
                            self.ui_feedback.set_status(error_msg, '#cc0000')
                        messagebox.showerror("Missing Required Fields", error_msg)
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
                        messagebox.showerror("Validation Error", error_msg)
                        return

                    # Construct Name field from Firstname + Lastname if not present
                    if 'Name' not in participant:
                        participant['Name'] = f"{participant['Firstname']} {participant['Lastname']}".strip()
                    
                    # Ensure Age field exists (use Birthyear)
                    if 'Age' not in participant:
                        participant['Age'] = participant.get('Birthyear')

                    self.logger.debug(f"[File {file_idx}] Participant {idx}: {participant['Name']} (Age: {participant.get('Birthyear')}, Weight: {participant.get('Weight', 0.0)}kg, Gender: {gender})")
                    
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
            messagebox.showerror("JSON Error", f"Failed to parse JSON file:\n{str(e)}")
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self.logger.error(error_msg)
            if self.ui_feedback:
                self.ui_feedback.set_status(error_msg, '#cc0000')
                self.ui_feedback.hide_loading_progress()
            messagebox.showerror("File Error", f"Could not find file:\n{str(e)}")
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.logger.error(error_msg, exc_info=True)
            if self.ui_feedback:
                self.ui_feedback.set_status(error_msg, '#cc0000')
                self.ui_feedback.hide_loading_progress()
            messagebox.showerror("Error", f"Failed to load JSON files:\n{str(e)}")
