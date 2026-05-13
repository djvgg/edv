# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service for managing quarantine brackets (rejected participants for manual review)."""


from utils.logging import get_logger
from utils.helpers import age_group_from_bracket_key, bracket_key_matches_age_lock
from backend.services.bracket_service import export_all_brackets, validate_age_from_birthyear



class QuarantineService:
    """Handles creation and management of quarantine brackets for rejected participants."""
    
    MIN_PARTICIPANT_AGE = 6
    MAX_PARTICIPANT_AGE = 120
    
    def __init__(self, task_runner=None):
        """Initialize the quarantine service.
        
        Args:
            task_runner: Optional TaskRunner for background DB operations
        """
        self.logger = get_logger(__name__, debug_verbose=True)
        self.quarantine_brackets = {}  # Preserved quarantine brackets dict: {reason: bracket_data}
        self.locked_brackets = {}      # Preserved locked brackets dict: {bracket_key: bracket_data}
        self.task_runner = task_runner  # For threaded DB saves
    
    def extract_quarantine(self, brackets):
        """Extract and preserve all QUARANTINE_* brackets from workflow.
        
        Call this when transitioning from group preview to generation method.
        Removes QUARANTINE_* brackets from brackets dict and preserves them for later restoration.
        
        Args:
            brackets (dict): The brackets dictionary
            
        Returns:
            dict: The preserved quarantine brackets {reason: bracket_data} (or empty dict if none present)
        """
        extracted = {}
        keys_to_remove = [k for k in brackets.keys() if k.startswith('QUARANTINE_')]
        
        for key in keys_to_remove:
            extracted[key] = brackets.pop(key)
            reason = key.replace('QUARANTINE_', '')
            self.logger.info(f"QUARANTINE_{reason} bracket extracted and preserved ({len(extracted[key].get('fighters', []))} participants)")
        
        if extracted:
            self.quarantine_brackets = extracted
        
        return extracted
    
    def restore_quarantine(self, brackets):
        """Restore preserved QUARANTINE_* brackets to brackets dict.
        
        Call this when showing group preview screen.
        Adds all preserved QUARANTINE_* brackets back to brackets.
        
        Args:
            brackets (dict): The brackets dictionary to update
            
        Returns:
            bool: True if any quarantine brackets were restored, False if none to restore
        """
        if not self.quarantine_brackets:
            return False
        
        for reason, bracket_data in self.quarantine_brackets.items():
            brackets[reason] = bracket_data
            fighters_count = len(bracket_data.get('fighters', []))
            self.logger.debug(f"{reason} bracket restored ({fighters_count} participants)")
        
        return True

    def extract_locked(self, brackets, bracket_table_assignment):
        """Extract and preserve locked brackets (assigned to mats) from workflow.
        
        Call this before generation_method to prevent editing of locked participants.
        Moves brackets with mat assignments to a separate cache.
        
        Args:
            brackets (dict): The brackets dictionary
            bracket_table_assignment (dict): {bracket_key: mat_id} mapping
            
        Returns:
            dict: The extracted locked brackets {bracket_key: bracket_data}
        """
        extracted = {}
        locked_keys = [k for k in bracket_table_assignment.keys() 
                      if bracket_table_assignment[k] is not None and k in brackets]
        
        for key in locked_keys:
            extracted[key] = brackets.pop(key)
            mat_num = bracket_table_assignment[key]
            fighters = len(extracted[key].get('fighters', []))
            self.logger.info(f"LOCKED bracket '{key}' extracted (Matte {mat_num}, {fighters} participants)")
        
        if extracted:
            self.locked_brackets = extracted
        
        return extracted
    
    def restore_locked(self, brackets):
        """Restore locked brackets to brackets dict.
        
        Call this when showing fight_monitoring screen.
        Adds all preserved locked brackets back for viewing/monitoring.
        
        Args:
            brackets (dict): The brackets dictionary to update
            
        Returns:
            bool: True if any locked brackets were restored, False if none to restore
        """
        if not self.locked_brackets:
            return False
        
        for bracket_key, bracket_data in self.locked_brackets.items():
            brackets[bracket_key] = bracket_data
            fighters_count = len(bracket_data.get('fighters', []))
            self.logger.debug(f"LOCKED bracket '{bracket_key}' restored ({fighters_count} participants)")
        
        return True
    
    def create_quarantine_bracket(self, brackets, invalid_participants):
        """Create separate QUARANTINE_* brackets per rejection reason.
        
        Args:
            brackets (dict): The brackets dictionary to update with quarantine brackets
            invalid_participants (list): List of full participant dicts with 'rejection_reason' 
                                        and 'calculated_age' added
        
        Returns:
            dict: Dict mapping rejection reasons to created fighter lists {reason: fighters}
        """
        if not invalid_participants:
            return {}
        
        # Group participants by rejection reason
        grouped_by_reason = {}
        for invalid_p in invalid_participants:
            reason = invalid_p.get('rejection_reason', 'unknown')
            if reason not in grouped_by_reason:
                grouped_by_reason[reason] = []
            grouped_by_reason[reason].append(invalid_p)
        
        # Create separate bracket for each rejection reason
        result = {}
        for reason, participants in grouped_by_reason.items():
            fighters = []
            for i, invalid_p in enumerate(participants, 1):
                # Copy all original fields from the participant
                fighter = dict(invalid_p)
                
                # Add rejection tracking fields
                fighter['ID'] = invalid_p.get('ID', f"QUARANTINE_{reason}_{i}")
                fighter['RejectionReason'] = invalid_p.get('rejection_reason', 'Unknown reason')
                
                # Ensure Age field contains the original age/birthyear value
                # (calculated_age is the computed age, Age is the original field)
                if 'Age' not in fighter or fighter.get('Age') is None:
                    # If Age is missing, try Birthyear
                    if 'Birthyear' in invalid_p:
                        fighter['Age'] = invalid_p['Birthyear']
                
                fighters.append(fighter)
            
            # Create bracket key like QUARANTINE_unpaid, QUARANTINE_age_too_young, etc.
            bracket_key = f'QUARANTINE_{reason}'
            
            if bracket_key not in brackets:
                brackets[bracket_key] = {
                    'fighters': fighters,
                    'bracket': [],  # No bracket structure; people manually reviewed here
                    'pool_size': None,
                    'is_quarantine': True,  # Flag to identify as quarantine
                    'rejection_reason': reason,  # Track the reason
                }
            else:
                # Append to existing quarantine if it exists
                brackets[bracket_key]['fighters'].extend(fighters)
            
            result[reason] = fighters
            self.logger.info(f"Created QUARANTINE_{reason} bracket with {len(fighters)} rejected participant(s)")
        
        # Update preserved quarantine brackets
        self.quarantine_brackets = {f'QUARANTINE_{r}': brackets[f'QUARANTINE_{r}'] for r in grouped_by_reason.keys()}
        
        return result

    def evaluate_participant(self, fighter):
        """Evaluate a single participant to determine why they might be in QUARANTINE.
        
        Args:
            fighter (dict): The fighter dictionary to evaluate.
            
        Returns:
            list: A list of issue strings (e.g., ["Unpaid", "Invalid Age: too young (4 years)"]).
                  Returns an empty list if the participant is perfectly valid.
        """
        issues = []
        
        # 1. Payment check
        if not fighter.get('Paid', False):
            issues.append("Unpaid")
            
        # 2. Age check
        birthyear = fighter.get('Birthyear') or fighter.get('Age')
        _, calculated_age, age_is_valid, age_rejection_reason = validate_age_from_birthyear(birthyear)
        
        if not age_is_valid:
            if birthyear in (None, ''):
                issues.append("Missing Age/Birthyear")
            else:
                issues.append(f"Invalid Age: {age_rejection_reason}")

        # 3. Validation check (manual flag)
        if not fighter.get('Valid', True):
            issues.append("Invalid")
                
        return issues

    def resort_brackets(self, brackets, edited_fighter=None, group_preview_screen=None,
                        db_service=None, bracket_table_assignment=None, locked_age_classes=None):
        """Re-sort brackets after changes in any QUARANTINE_* bracket.

        Args:
            brackets (dict): The brackets dictionary to update.
            edited_fighter (dict, optional): The fighter that was just edited.
                If provided, only that fighter is re-validated.
                If None, all QUARANTINE fighters are checked.
            group_preview_screen (object, optional): Reference to group preview
                screen — refreshed after the sort if provided.
            db_service (optional): Database service to persist changes after successful resort.
            bracket_table_assignment (dict, optional): {bracket_key: mat_id} - mat-locked brackets to avoid merging
            locked_age_classes (set, optional): age-class lock scopes to avoid merging
        """
        self.logger.debug("RESORT: resort_brackets() called")

        quarantine_keys = [k for k in brackets if k.startswith('QUARANTINE_')]
        if not quarantine_keys:
            self.logger.debug("RESORT: No QUARANTINE_* brackets found, returning early")
            return

        valid_from_quarantine = self._extract_valid_from_quarantine(
            brackets, quarantine_keys, edited_fighter)

        if valid_from_quarantine:
            self._merge_valid_into_brackets(
                brackets, valid_from_quarantine, bracket_table_assignment, locked_age_classes
            )

        self.quarantine_brackets = {k: v for k, v in brackets.items() if k.startswith('QUARANTINE_')}

        if group_preview_screen and group_preview_screen.winfo_exists():
            current_selection = getattr(group_preview_screen, 'current_bracket_key', None)
            group_preview_screen.load_data(brackets)
            if current_selection and current_selection in brackets:
                group_preview_screen._display_participants(current_selection)
                self.logger.info(f"Group preview refreshed, selection restored to {current_selection}")
            else:
                self.logger.info("Group preview refreshed after resort")
        else:
            self.logger.debug("RESORT: No group_preview_screen to refresh")
        
        # Save changes to database in background thread if db_service provided
        if db_service and valid_from_quarantine:
            if self.task_runner:
                # Run in background thread
                self.task_runner.submit_task(
                    'resort_save_participants',
                    fn=lambda: self._save_participants_bg(db_service, valid_from_quarantine),
                    on_error=lambda e: self.logger.error(f"RESORT: Background save failed: {e}")
                )
            else:
                # Fallback to synchronous update if no task_runner
                try:
                    db_service.update_participants(valid_from_quarantine)
                    self.logger.info(f"RESORT: Updated {len(valid_from_quarantine)} participant(s) in database after resort")
                except Exception as db_error:
                    self.logger.error(f"RESORT: Failed to update participants in database: {db_error}")
    
    def _save_participants_bg(self, db_service, participants):
        """Background thread task to update participants in database."""
        try:
            db_service.update_participants(participants)
            self.logger.info(f"RESORT: [BG] Updated {len(participants)} participant(s) in database after resort")
        except Exception as db_error:
            self.logger.error(f"RESORT: [BG] Failed to update participants: {db_error}")
            raise

    def _extract_valid_from_quarantine(self, brackets, quarantine_keys, edited_fighter):
        """Validate fighters in each quarantine bracket; separate valid from still-invalid.

        Mutates brackets in-place (updates fighter lists inside each quarantine bracket).
        Returns list of fighters that are now valid and should be re-placed in normal brackets.

        Also handles fighters whose rejection reason changed (e.g. age_out_of_bounds → unpaid):
        those are migrated to the correct QUARANTINE_* bucket rather than left in the wrong one.
        """
        valid_fighters = []
        migrating = []  # [(fighter, new_reason)] — collected and applied after the main loop

        for quarantine_key in quarantine_keys:
            current_reason = quarantine_key.replace('QUARANTINE_', '')
            quarantine_fighters = brackets[quarantine_key].get('fighters', [])
            self.logger.debug(f"RESORT: Found {len(quarantine_fighters)} fighters in {quarantine_key}")

            if not quarantine_fighters:
                self.logger.debug(f"RESORT: {quarantine_key} bracket is empty")
                continue

            still_invalid = []
            for base_fighter in quarantine_fighters:
                # When only one fighter was edited, skip all others unchanged
                if edited_fighter is not None and base_fighter is not edited_fighter:
                    still_invalid.append(base_fighter)
                    continue

                fighter_name = base_fighter.get('Name', f"Unknown ({base_fighter.get('ID', '?')})")
                is_valid, reason = self._evaluate_fighter_validity(base_fighter, brackets)

                if is_valid:
                    valid_fighters.append(base_fighter)
                    self.logger.info(f"RESORT: ✓ {fighter_name} now valid (fixed)")
                elif reason != current_reason:
                    # Rejection reason changed — migrate to the correct quarantine bucket
                    base_fighter['RejectionReason'] = reason
                    base_fighter['rejection_reason'] = reason
                    migrating.append((base_fighter, reason))
                    self.logger.info(f"RESORT: ↔ {fighter_name} moved {quarantine_key} → QUARANTINE_{reason}")
                else:
                    still_invalid.append(base_fighter)
                    self.logger.info(f"RESORT: ✗ {fighter_name} remains invalid ({reason})")

            # Keep the bracket even if empty so it persists in the UI
            brackets[quarantine_key]['fighters'] = still_invalid
            moved = len(quarantine_fighters) - len(still_invalid)
            if still_invalid:
                self.logger.info(f"Re-sorted from {quarantine_key}: {moved} now valid/migrated, {len(still_invalid)} remain")
            else:
                self.logger.info(f"Re-sorted all {len(quarantine_fighters)} from {quarantine_key} (bracket now empty but preserved)")

        # Apply migrations after the main loop so we don't interfere with ongoing iteration
        for fighter, new_reason in migrating:
            new_key = f'QUARANTINE_{new_reason}'
            if new_key not in brackets:
                brackets[new_key] = {
                    'fighters': [],
                    'bracket': [],
                    'pool_size': None,
                    'is_quarantine': True,
                    'rejection_reason': new_reason,
                }
            brackets[new_key]['fighters'].append(fighter)

        return valid_fighters

    def _evaluate_fighter_validity(self, fighter, brackets):
        """Check if a single fighter passes all validity criteria.

        Returns (is_valid: bool, reason: str | None).
        Checks in order: payment → manual flag → age → duplicate.
        """
        fighter_name = fighter.get('Name', f"Unknown ({fighter.get('ID', '?')})")
        self.logger.debug(f"RESORT: Validating {fighter_name} (ID: {fighter.get('ID', '?')})")

        if not fighter.get('Paid', False):
            self.logger.debug("RESORT:   Paid: False → INVALID: unpaid")
            return False, "unpaid"

        if not fighter.get('Valid', True):
            self.logger.debug("RESORT:   Manual Valid Flag: False → INVALID: marked_invalid")
            return False, "marked_invalid"

        birthyear = fighter.get('Birthyear') or fighter.get('Age')
        age_group, calculated_age, age_is_valid, age_rejection_reason = validate_age_from_birthyear(birthyear)
        self.logger.debug(
            f"RESORT:   Age validation: birthyear={birthyear}, calculated_age={calculated_age}, "
            f"valid={age_is_valid}, reason={age_rejection_reason}"
        )
        if not age_is_valid:
            self.logger.debug(f"RESORT:   → INVALID: {age_rejection_reason}")
            return False, age_rejection_reason

        # Check for duplicates against valid fighters in brackets
        if self._is_duplicate_in_brackets(fighter, brackets):
            self.logger.debug("RESORT:   Duplicate: Already exists in valid brackets → INVALID: duplicate")
            return False, "duplicate"

        self.logger.debug(f"RESORT:   Age bounds OK, age group {age_group} - VALID")
        return True, None

    def _is_duplicate_in_brackets(self, candidate, brackets):
        """Check if candidate fighter is a duplicate of anyone in valid (non-quarantine) brackets.
        
        NOTE: Legitimate doublestart copies (same person in multiple age groups) are exempt
        from the duplicate check. If both candidate and existing fighter are marked as 
        is_doublestart_copy, they represent the same person in different age groups and
        should NOT be blocked.
        
        Returns True if duplicate found, False otherwise.
        """
        for bracket_key, bracket_data in brackets.items():
            # Skip quarantine brackets
            if bracket_key.startswith('QUARANTINE_'):
                continue
            
            if not isinstance(bracket_data, dict):
                continue
            
            fighter_list = bracket_data.get('participants') or bracket_data.get('fighters', [])
            
            for existing_fighter in fighter_list:
                if self._check_is_duplicate(candidate, existing_fighter):
                    # Both are doublestart copies - this is legitimate doublestart, not an error duplicate
                    if candidate.get('is_doublestart_copy') and existing_fighter.get('is_doublestart_copy'):
                        self.logger.debug(f"RESORT:   Found legitimate doublestart copy in {bracket_key} (same person, different age group)")
                        continue
                    
                    existing_name = f"{existing_fighter.get('Firstname', '')} {existing_fighter.get('Lastname', '')}".strip()
                    self.logger.debug(f"RESORT:   Found duplicate of {candidate.get('Name', candidate.get('ID'))} in {bracket_key}: {existing_name}")
                    return True
        
        return False

    def _check_is_duplicate(self, candidate: dict, existing: dict) -> bool:
        """Check if candidate participant matches existing participant by natural key.
        
        Natural key comparison:
        - first_name (required)
        - last_name (required)  
        - gender (required)
        - birth_date (optional - only compared if present in both)
        - club (optional - only compared if present in both)
        """
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
        
        return True

    def _merge_valid_into_brackets(
        self, brackets, valid_fighters, bracket_table_assignment=None, locked_age_classes=None
    ):
        """Generate brackets for newly-valid fighters and merge into existing brackets.

        Quarantine brackets are preserved throughout the operation.
        Brackets that are assigned to mats are protected from merging.
        """
        bracket_table_assignment = bracket_table_assignment or {}
        locked_age_classes = set(locked_age_classes or [])
        temp_brackets = {k: v for k, v in brackets.items() if not k.startswith('QUARANTINE_')}
        quarantine_to_preserve = {k: v for k, v in brackets.items() if k.startswith('QUARANTINE_')}
        age_lock_blocked = []

        new_brackets = export_all_brackets(valid_fighters)

        brackets.clear()
        brackets.update(temp_brackets)

        for key, new_data in new_brackets.items():
            # Check if this bracket is locked (assigned to a mat)
            if key in bracket_table_assignment and bracket_table_assignment[key] is not None:
                mat_num = bracket_table_assignment[key]
                locked_fighters = new_data.get('fighters', [])
                self.logger.warning(f"RESORT: Cannot merge {len(locked_fighters)} fighter(s) into '{key}' - bracket is assigned to Matte {mat_num}. Keeping in quarantine.")
                # Skip this bracket and let fighters stay in quarantine
                continue

            if bracket_key_matches_age_lock(key, locked_age_classes):
                age_group = age_group_from_bracket_key(key)
                locked_fighters = new_data.get('fighters', [])
                for fighter in locked_fighters:
                    fighter['rejection_reason'] = 'age_class_locked'
                    fighter['locked_age_classes'] = age_group
                age_lock_blocked.extend(locked_fighters)
                self.logger.warning(
                    f"RESORT: Cannot merge {len(locked_fighters)} fighter(s) into '{key}' "
                    f"- age class {age_group} is locked. Keeping in quarantine."
                )
                continue
            
            if key in brackets:
                brackets[key]['fighters'].extend(new_data.get('fighters', []))
                brackets[key]['bracket'] = []  # reset fight tree — regenerated on demand
                self.logger.debug(f"RESORT: Merged {len(new_data.get('fighters', []))} fighter(s) into existing bracket {key}")
            else:
                brackets[key] = new_data
                self.logger.debug(f"RESORT: Created new bracket {key} with {len(new_data.get('fighters', []))} fighter(s)")

        if age_lock_blocked:
            quarantine_to_preserve.setdefault('QUARANTINE_age_class_locked', {
                'fighters': [],
                'bracket': [],
                'pool_size': None,
                'is_quarantine': True,
                'rejection_reason': 'age_class_locked',
            })
            quarantine_to_preserve['QUARANTINE_age_class_locked']['fighters'].extend(age_lock_blocked)

        brackets.update(quarantine_to_preserve)
        self.logger.debug(f"RESORT: Restored {len(quarantine_to_preserve)} quarantine bracket(s)")

        # Log final placement of each re-sorted fighter
        for fighter in valid_fighters:
            fighter_id = fighter.get('ID')
            fighter_name = fighter.get('Name', f"Unknown ({fighter_id})")
            placed_in = next(
                (bk for bk, bd in brackets.items()
                 if not bk.startswith('QUARANTINE_')
                 and any(f.get('ID') == fighter_id for f in bd.get('fighters', []))),
                None
            )
            if placed_in:
                self.logger.debug(f"RESORT: {fighter_name} → {placed_in}")
            else:
                self.logger.warning(f"RESORT: {fighter_name} could not find assigned bracket after re-sort")
