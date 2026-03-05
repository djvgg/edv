# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Service for managing quarantine brackets (rejected participants for manual review)."""


from utils.logging import get_logger
from backend.services.bracket_service import export_all_brackets, validate_age_from_birthyear



class QuarantineService:
    """Handles creation and management of quarantine brackets for rejected participants."""
    
    MIN_PARTICIPANT_AGE = 6
    MAX_PARTICIPANT_AGE = 120
    
    def __init__(self):
        """Initialize the quarantine service."""
        self.logger = get_logger(__name__, debug_verbose=True)
        self.quarantine_brackets = {}  # Preserved quarantine brackets dict: {reason: bracket_data}
    
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

    def resort_brackets(self, brackets, edited_fighter=None, group_preview_screen=None):
        """Re-sort brackets after changes in any QUARANTINE_* bracket.
        
        Args:
            brackets (dict): The brackets dictionary to update
            edited_fighter (dict, optional): The fighter that was just edited.
                                           If provided, only that fighter is checked for re-sorting.
                                           If None, all QUARANTINE fighters are checked.
            group_preview_screen (object, optional): Reference to group preview screen to refresh
        
        This method:
        1. Extracts valid participants from each QUARANTINE_* bracket
        2. Removes them from their reason-specific quarantine
        3. Re-generates brackets with all valid participants
        4. Updates the group preview display
        """
        self.logger.debug("RESORT: resort_brackets() called")
        
        # Find all quarantine brackets (QUARANTINE_*)
        quarantine_keys = [k for k in brackets.keys() if k.startswith('QUARANTINE_')]
        
        if not quarantine_keys:
            self.logger.debug("RESORT: No QUARANTINE_* brackets found in brackets, returning early")
            return
        
        valid_from_quarantine = []
        brackets_to_remove = []
        
        # Process each quarantine bracket by reason
        for quarantine_key in quarantine_keys:
            quarantine_fighters = brackets[quarantine_key].get('fighters', [])
            self.logger.debug(f"RESORT: Found {len(quarantine_fighters)} fighters in {quarantine_key}")
            
            if not quarantine_fighters:
                self.logger.debug(f"RESORT: {quarantine_key} bracket is empty")
                continue
            
            # Separate valid and still-invalid participants while PRESERVING original list order
            still_invalid = []
            
            # We iterate over the ORIGINAL quarantine list, so anyone remaining invalid keeps their exact spot
            for base_fighter in quarantine_fighters:
                
                # If we're only checking one edited fighter, skip all others
                if edited_fighter is not None and base_fighter is not edited_fighter:
                    still_invalid.append(base_fighter)
                    continue
                    
                fighter = base_fighter
                fighter_id = fighter.get('ID')
                fighter_name = fighter.get('Name', f"Unknown ({fighter_id})")
                is_valid = True
                invalid_reason = None
                
                self.logger.debug(f"RESORT: Validating {fighter_name} (ID: {fighter.get('ID', '?')})")
                
                # Check paid status
                paid_status = fighter.get('Paid', False)
                self.logger.debug(f"RESORT:   Paid: {paid_status}")
                if not paid_status:
                    is_valid = False
                    invalid_reason = "unpaid"
                    self.logger.debug(f"RESORT:   → INVALID: {invalid_reason}")
                else:
                    # Check manual valid flag
                    is_manually_valid = fighter.get('Valid', True)
                    self.logger.debug(f"RESORT:   Manual Valid Flag: {is_manually_valid}")
                    if not is_manually_valid:
                        is_valid = False
                        invalid_reason = "marked_invalid"
                        self.logger.debug(f"RESORT:   → INVALID: {invalid_reason}")
                    else:
                        # Check age validity using unified validation function (SINGLE SOURCE OF TRUTH)
                        birthyear = fighter.get('Birthyear') or fighter.get('Age')
                        age_group, calculated_age, age_is_valid, age_rejection_reason = validate_age_from_birthyear(birthyear)
                        
                        self.logger.debug(f"RESORT:   Age validation: birthyear={birthyear}, calculated_age={calculated_age}, valid={age_is_valid}, reason={age_rejection_reason}")
                        
                        if not age_is_valid:
                            is_valid = False
                            invalid_reason = age_rejection_reason
                            self.logger.debug(f"RESORT:   → INVALID: {invalid_reason}")
                        else:
                            self.logger.debug(f"RESORT:   Age bounds OK, age group {age_group} - VALID")
                
                if is_valid:
                    valid_from_quarantine.append(fighter)
                    self.logger.info(f"RESORT: ✓ {fighter_name} now valid (fixed)")
                else:
                    still_invalid.append(fighter)
                    self.logger.info(f"RESORT: ✗ {fighter_name} remains invalid ({invalid_reason})")
            
            # Update quarantine bracket with only still-invalid fighters
            if still_invalid:
                brackets[quarantine_key]['fighters'] = still_invalid
                self.logger.info(f"Re-sorted from {quarantine_key}: {len(quarantine_fighters) - len(still_invalid)} now valid, {len(still_invalid)} remain invalid")
            else:
                # Remove quarantine bracket if empty
                brackets_to_remove.append(quarantine_key)
                self.logger.info(f"Re-sorted all {len(quarantine_fighters)} from {quarantine_key} - now valid")
        
        # Remove empty quarantine brackets
        for quarantine_key in brackets_to_remove:
            del brackets[quarantine_key]
        
        # Clear preserved quarantine brackets if all empty
        if not any(k.startswith('QUARANTINE_') for k in brackets.keys()):
            self.quarantine_brackets = {}
        
        # Re-generate brackets with valid participants
        if valid_from_quarantine:
            # Save current brackets (excluding QUARANTINE_*)
            temp_brackets = {k: v for k, v in brackets.items() if not k.startswith('QUARANTINE_')}
            
            # Generate brackets for the newly valid fighters
            new_brackets = export_all_brackets(valid_from_quarantine)
            
            # Start brackets with the existing ones
            brackets.clear()
            brackets.update(temp_brackets)
            
            # Merge the newly valid fighters into the brackets
            for key, new_bracket_data in new_brackets.items():
                if key in brackets:
                    # Bracket already exists, append the new fighters
                    brackets[key]['fighters'].extend(new_bracket_data.get('fighters', []))
                    # Reset the fight tree (bracket) so it gets regenerated later if needed
                    brackets[key]['bracket'] = []
                    self.logger.debug(f"RESORT: Merged {len(new_bracket_data.get('fighters', []))} fighter(s) into existing bracket {key}")
                else:
                    # New bracket, add it entirely
                    brackets[key] = new_bracket_data
                    self.logger.debug(f"RESORT: Created new bracket {key} with {len(new_bracket_data.get('fighters', []))} fighter(s)")
            
            # Log where each fighter was placed
            for fighter in valid_from_quarantine:
                fighter_id = fighter.get('ID')
                fighter_name = fighter.get('Name', f"Unknown ({fighter_id})")
                
                # Find which bracket contains this fighter
                new_bracket_key = None
                for bracket_key, bracket_data in brackets.items():
                    if bracket_key.startswith('QUARANTINE_'):
                        continue
                    fighters = bracket_data.get('fighters', [])
                    for f in fighters:
                        if f.get('ID') == fighter_id:
                            new_bracket_key = bracket_key
                            break
                    if new_bracket_key:
                        break
                
                if new_bracket_key:
                    self.logger.debug(f"RESORT: {fighter_name} → new bracket: {new_bracket_key}")
                else:
                    self.logger.warning(f"RESORT: {fighter_name} could not find assigned bracket after re-sort")
        
        # Refresh the group preview display with updated data
        if group_preview_screen and group_preview_screen.winfo_exists():
            # Preserve the currently selected bracket before reloading data
            current_selection = None
            if hasattr(group_preview_screen, 'current_bracket_key'):
                current_selection = group_preview_screen.current_bracket_key
            
            # Force reload of the entire display with current brackets data
            # This ensures updated participant counts are shown
            group_preview_screen.load_data(brackets)
            
            # Restore the selection if it still exists
            if current_selection and current_selection in brackets:
                group_preview_screen._display_participants(current_selection)
                self.logger.info(f"Group preview refreshed with updated data, selection restored to {current_selection}")
            else:
                self.logger.info("Group preview refreshed with updated data after resort")
        else:
            self.logger.debug("RESORT: No group_preview_screen to refresh")
