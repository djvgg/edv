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

    # ===== DUPLICATE DETECTION LOGIC =====
    
    def _check_is_duplicate(self, candidate: dict, existing: dict) -> bool:
        """Check if candidate participant matches existing participant by natural key.
        
        Pure logic method - independent of cache/DB. Used by both in-memory and DB duplicate detection.
        
        Natural key comparison:
        - first_name (required)
        - last_name (required)
        - gender (required)
        - birth_date (optional - only compared if present in both)
        - club (optional - only compared if present in both)
        - association (optional - only compared if present in both)
        
        Args:
            candidate: Participant dict (may have 'first_name'/'last_name' or 'Firstname'/'Lastname')
            existing: Participant dict (same format as candidate)
        
        Returns:
            True if candidate matches existing (duplicate), False otherwise
        """
        # Normalize field names (handle both dict formats: lowercase DB and uppercase JSON)
        def get_field(p, *field_names):
            for name in field_names:
                if name in p and p[name] is not None:
                    return str(p[name]).strip().lower() if isinstance(p[name], str) else p[name]
            return None
        
        # Natural key: first_name + last_name + gender (always required)
        cand_first = get_field(candidate, 'first_name', 'Firstname', 'firstname')
        cand_last = get_field(candidate, 'last_name', 'Lastname', 'lastname')
        cand_gender = get_field(candidate, 'gender', 'Gender')
        
        exist_first = get_field(existing, 'first_name', 'Firstname', 'firstname')
        exist_last = get_field(existing, 'last_name', 'Lastname', 'lastname')
        exist_gender = get_field(existing, 'gender', 'Gender')
        
        # All three required fields must match
        if not (cand_first and cand_last and cand_gender):
            return False
        if not (exist_first and exist_last and exist_gender):
            return False
        
        if cand_first != exist_first or cand_last != exist_last or cand_gender != exist_gender:
            return False
        
        # Optional field comparisons (only if present in both)
        cand_birth = candidate.get('birth_date') or candidate.get('Birthyear')
        exist_birth = existing.get('birth_date') or existing.get('Birthyear')
        if cand_birth and exist_birth and cand_birth != exist_birth:
            return False
        
        cand_club = get_field(candidate, 'club', 'Club')
        exist_club = get_field(existing, 'club', 'Club')
        if cand_club and exist_club and cand_club != exist_club:
            return False
        
        cand_assoc = get_field(candidate, 'association', 'Association')
        exist_assoc = get_field(existing, 'association', 'Association')
        if cand_assoc and exist_assoc and cand_assoc != exist_assoc:
            return False
        
        return True

    def _extract_participants_from_brackets(self, brackets: dict) -> list:
        """Extract all unique participants from brackets dict for cache duplicate detection.
        
        Args:
            brackets: Dict of brackets (each bracket has 'participants' list)
        
        Returns:
            List of unique participant dicts
        """
        seen_keys = set()
        participants = []
        
        for bracket_key, bracket_data in brackets.items():
            if not isinstance(bracket_data, dict) or 'participants' not in bracket_data:
                continue
            
            for p in bracket_data.get('participants', []):
                # Use natural key to avoid duplicates across brackets
                p_key = (
                    str(p.get('first_name', p.get('Firstname', ''))).strip().lower(),
                    str(p.get('last_name', p.get('Lastname', ''))).strip().lower(),
                    str(p.get('gender', p.get('Gender', ''))).strip().lower()
                )
                
                if p_key not in seen_keys:
                    seen_keys.add(p_key)
                    participants.append(p)
        
        return participants

    def _find_duplicates_in_cache(self, new_participants: list, existing_brackets: dict = None) -> tuple:
        """Find duplicates between new participants and cached brackets.
        
        Args:
            new_participants: List of new participant dicts to check
            existing_brackets: Current brackets dict (may be None or empty for fresh import)
        
        Returns:
            Tuple of (unique_participants, duplicates_list) where:
            - unique_participants: New participants not in cache
            - duplicates_list: Participants that were skipped (already in cache)
        """
        if not existing_brackets:
            return new_participants, []
        
        cached_participants = self._extract_participants_from_brackets(existing_brackets)
        if not cached_participants:
            return new_participants, []
        
        unique = []
        duplicates = []
        
        for new_p in new_participants:
            is_dup = False
            for cached_p in cached_participants:
                if self._check_is_duplicate(new_p, cached_p):
                    duplicates.append(new_p)
                    is_dup = True
                    break
            
            if not is_dup:
                unique.append(new_p)
        
        return unique, duplicates

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

    def load_json_and_generate(self, filepaths, callbacks, existing_brackets=None):
        """Load participants from 2 JSON files (male/female) and generate brackets.
        
        Smart mode: if existing_brackets is None/empty → fresh import (replace)
                  if existing_brackets has data → append mode (deduplicate + merge)
        
        Args:
            filepaths: Tuple of 2 JSON file paths
            callbacks: Dict with 'on_success' callback function
            existing_brackets: Current brackets dict for append mode detection (None = fresh import)
        """
        if self.ui_feedback:
            mode = "Appending to" if existing_brackets else "Loading and generating"
            self.ui_feedback.show_loading_progress(f"{mode} brackets from JSON...")
        
        self.task_runner.submit_task(
            'load_json',
            fn=lambda on_progress=None: self._load_json_and_generate_thread(filepaths, callbacks, existing_brackets),
            on_error=self._handle_load_error
        )

    def _load_json_and_generate_thread(self, filepaths, callbacks, existing_brackets=None):
        """Background task for loading JSON files and generating brackets.
        
        Implements smart append/replace logic:
        - Fresh import: No existing brackets → replace mode
        - Append mode: Has existing brackets → deduplicate + merge
        - Always updates cache first (working copy)
        - DB save is soft-fail (continues if down)
        - If DB succeeds, fetches authoritative data and resyncs cache
        """
        is_append_mode = bool(existing_brackets)
        db_save_succeeded = False
        
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

            # APPEND MODE: Deduplicate against cache if existing brackets present
            duplicates_skipped = []
            if is_append_mode:
                all_participants, duplicates_skipped = self._find_duplicates_in_cache(
                    all_participants, existing_brackets
                )
                if duplicates_skipped:
                    self.logger.info(
                        f"[APPEND MODE] Skipped {len(duplicates_skipped)} duplicate participant(s) "
                        f"already in cache"
                    )
                
                if not all_participants:
                    if self.ui_feedback:
                        self.ui_feedback.hide_loading_progress()
                        self.ui_feedback.set_status(
                            f"No new unique participants (all {len(duplicates_skipped)} are duplicates)", 
                            '#999999'
                        )
                    return

            if self.ui_feedback:
                self.ui_feedback.update_progress(62)

            # ===== SAVE TO DATABASE (SOFT-FAIL) =====
            # Wrap in try-except so app continues if DB is down
            try:
                if self.db_service:
                    self.db_service.save_participants(all_participants)
                    self.db_service.initialize_all_groups()
                    db_save_succeeded = True
                    self.logger.info("[DB] Save succeeded - cache will be synced from DB")
            except Exception as db_error:
                db_save_succeeded = False
                self.logger.warning(
                    f"[DB SOFT-FAIL] Could not save to database: {db_error}. "
                    f"Working offline with cache only."
                )
                if self.ui_feedback:
                    self.ui_feedback.set_status(
                        f"DB unavailable - working offline ({len(all_participants)} new)",
                        '#999999'
                    )

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

            # ===== BRACKET GENERATION WITH DB RESYNC =====
            # If DB save succeeded: fetch authoritative data and regenerate all
            # If DB failed: use cache data only
            participants_for_brackets = all_participants
            resync_note = ""
            
            if db_save_succeeded and self.db_service:
                try:
                    all_db_participants = self.db_service.fetch_participants()
                    if all_db_participants:
                        participants_for_brackets = all_db_participants
                        resync_note = " (resynced from DB)"
                        self.logger.info(
                            f"[DB RESYNC] Fetched {len(all_db_participants)} total participants from DB"
                        )
                except Exception as resync_error:
                    self.logger.warning(f"[DB RESYNC] Could not resync from DB: {resync_error}. Using cache.")
                    resync_note = " (cache used, DB sync failed)"

            # Generate brackets
            new_brackets = {}
            new_brackets.update(export_all_brackets(participants_for_brackets))
            
            # APPEND MODE: Merge with existing brackets (don't replace)
            if is_append_mode and existing_brackets:
                existing_brackets.update(new_brackets)
                brackets = existing_brackets
                merge_summary = (
                    f"Merged {len(new_brackets)} brackets. "
                    f"Added {len(all_participants)} participants, "
                    f"skipped {len(duplicates_skipped)} duplicates."
                )
                self.logger.info(f"[APPEND] {merge_summary}{resync_note}")
            else:
                # Fresh import mode
                brackets = new_brackets
                merge_summary = f"Fresh import: {len(all_participants)} participants."
                self.logger.info(f"[FRESH] {merge_summary}{resync_note}")
            
            if self.ui_feedback:
                self.ui_feedback.update_progress(95)
            
            status_msg = (
                f"Success! Generated {len(brackets)} brackets. {merge_summary}"
                if merge_summary else f"Success! Generated {len(brackets)} brackets from JSON files."
            )
            if self.ui_feedback:
                self.ui_feedback.set_status(status_msg, '#00cc00')
                self.ui_feedback.update_progress(100)
                self.ui_feedback.hide_loading_progress()

            # Call success callback with brackets, rejection info, and load mode
            if 'on_success' in callbacks and callable(callbacks['on_success']):
                callbacks['on_success'](
                    brackets=brackets,
                    rejected_participants=all_rejected,
                    load_mode='append' if is_append_mode else 'fresh',
                    duplicates_skipped=len(duplicates_skipped),
                    db_available=db_save_succeeded
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