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
        self.quarantine_bracket = None  # Preserved quarantine bracket for group preview
    
    def extract_quarantine(self, brackets):
        """Extract and preserve QUARANTINE bracket from workflow.
        
        Call this when transitioning from group preview to generation method.
        Removes QUARANTINE from brackets dict and preserves it for later restoration.
        
        Args:
            brackets (dict): The brackets dictionary
            
        Returns:
            dict: The preserved QUARANTINE bracket (or None if not present)
        """
        if 'QUARANTINE' in brackets:
            self.quarantine_bracket = brackets.pop('QUARANTINE')
            self.logger.info(f"QUARANTINE bracket extracted and preserved ({len(self.quarantine_bracket.get('fighters', []))} participants)")
            return self.quarantine_bracket
        return None
    
    def restore_quarantine(self, brackets):
        """Restore preserved QUARANTINE bracket to brackets dict.
        
        Call this when showing group preview screen.
        Adds the preserved QUARANTINE back to brackets.
        
        Args:
            brackets (dict): The brackets dictionary to update
            
        Returns:
            bool: True if quarantine was restored, False if none to restore
        """
        if self.quarantine_bracket:
            brackets['QUARANTINE'] = self.quarantine_bracket
            self.logger.debug(f"QUARANTINE bracket restored ({len(self.quarantine_bracket.get('fighters', []))} participants)")
            return True
        return False
    
    def create_quarantine_bracket(self, brackets, invalid_participants):
        """Create a QUARANTINE bracket with all rejected participants for manual review.
        
        Args:
            brackets (dict): The brackets dictionary to update with quarantine bracket
            invalid_participants (list): List of full participant dicts with 'rejection_reason' 
                                        and 'calculated_age' added
        
        Returns:
            list: List of fighter dicts (participant format)
        """
        if not invalid_participants:
            return []
        
        # Convert invalid participant dicts to fighter format
        fighters = []
        for i, invalid_p in enumerate(invalid_participants, 1):
            # Copy all original fields from the participant
            fighter = dict(invalid_p)
            
            # Add rejection tracking fields
            fighter['ID'] = invalid_p.get('ID', f"QUARANTINE_{i}")
            fighter['RejectionReason'] = invalid_p.get('rejection_reason', 'Unknown reason')
            
            # Ensure Age field contains the original age/birthyear value
            # (calculated_age is the computed age, Age is the original field)
            if 'Age' not in fighter or fighter.get('Age') is None:
                # If Age is missing, try Birthyear
                if 'Birthyear' in invalid_p:
                    fighter['Age'] = invalid_p['Birthyear']
            
            fighters.append(fighter)
        
        # Create quarantine bracket entry
        if 'QUARANTINE' not in brackets:
            brackets['QUARANTINE'] = {
                'fighters': fighters,
                'bracket': [],  # No bracket structure; people manually reviewed here
                'pool_size': None,
                'is_quarantine': True,  # Flag to identify as quarantine
            }
        else:
            # Append to existing quarantine if it exists
            brackets['QUARANTINE']['fighters'].extend(fighters)
        
        self.logger.info(f"Created QUARANTINE bracket with {len(fighters)} rejected participant(s)")
        return fighters

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
                
        return issues

    def resort_brackets(self, brackets, edited_fighter=None, group_preview_screen=None):
        """Re-sort brackets after changes in QUARANTINE.
        
        Args:
            brackets (dict): The brackets dictionary to update
            edited_fighter (dict, optional): The fighter that was just edited.
                                           If provided, only that fighter is checked for re-sorting.
                                           If None, all QUARANTINE fighters are checked.
            group_preview_screen (object, optional): Reference to group preview screen to refresh
        
        This method:
        1. Extracts valid participants from QUARANTINE
        2. Removes them from QUARANTINE
        3. Re-generates brackets with all valid participants
        4. Updates the group preview display
        """
        self.logger.debug("RESORT: resort_brackets() called")
        
        if 'QUARANTINE' not in brackets:
            self.logger.debug("RESORT: QUARANTINE bracket not found in brackets, returning early")
            return
        
        quarantine_fighters = brackets['QUARANTINE'].get('fighters', [])
        self.logger.debug(f"RESORT: Found {len(quarantine_fighters)} fighters in QUARANTINE")
        
        if not quarantine_fighters:
            self.logger.debug("RESORT: QUARANTINE bracket is empty, returning early")
            return
        
        # Determine which fighters to check
        if edited_fighter is not None:
            self.logger.debug(f"RESORT: Checking only the explicitly edited fighter object (ID: {edited_fighter.get('ID')})")
        else:
            self.logger.debug(f"RESORT: Checking all {len(quarantine_fighters)} fighters in QUARANTINE")
        
        # Separate valid and still-invalid participants while PRESERVING original list order
        valid_from_quarantine = []
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
        
        # Update QUARANTINE with only still-invalid fighters
        if still_invalid:
            brackets['QUARANTINE']['fighters'] = still_invalid
            self.logger.info(f"Re-sorted from QUARANTINE: {len(valid_from_quarantine)} now valid, {len(still_invalid)} remain invalid")
        else:
            # Remove QUARANTINE if empty
            del brackets['QUARANTINE']
            # Clear the preserved quarantine since all fighters are now valid
            self.quarantine_bracket = None
            self.logger.info(f"Re-sorted all {len(valid_from_quarantine)} from QUARANTINE - now valid")
        
        # Re-generate brackets with valid participants
        if valid_from_quarantine:
            # Save current brackets (excluding QUARANTINE)
            temp_brackets = {k: v for k, v in brackets.items() if k != 'QUARANTINE'}
            
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
                    if bracket_key == 'QUARANTINE':
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
        
        # Re-add QUARANTINE if there are still-invalid (update in place to keep references in sync)
        if still_invalid:
            # Update the preserved quarantine bracket in place so references stay synced
            if self.quarantine_bracket is not None:
                self.quarantine_bracket['fighters'] = still_invalid
                brackets['QUARANTINE'] = self.quarantine_bracket  # Use the reference
                self.logger.debug(f"Updated quarantine bracket with {len(still_invalid)} remaining invalid fighters")
            else:
                # Fallback: create new if preserved doesn't exist (shouldn't happen)
                brackets['QUARANTINE'] = {
                    'fighters': still_invalid,
                    'bracket': [],
                    'pool_size': None,
                    'is_quarantine': True,
                }
                self.logger.warning("QUARANTINE bracket was not preserved; creating new one")
        
        # Refresh the group preview display with updated data
        if group_preview_screen and group_preview_screen.winfo_exists():
            # Preserve the currently selected bracket before reloading data
            current_selection = None
            if hasattr(group_preview_screen, 'current_bracket_key'):
                current_selection = group_preview_screen.current_bracket_key
            
            # Force reload of the entire display with current brackets data
            # This ensures updated participant counts are shown (e.g., fewer people in QUARANTINE)
            group_preview_screen.load_data(brackets)
            
            # Restore the selection if it still exists
            if current_selection and current_selection in brackets:
                group_preview_screen._display_participants(current_selection)
                self.logger.info(f"Group preview refreshed with updated data, selection restored to {current_selection}")
            else:
                self.logger.info("Group preview refreshed with updated data after resort")
        else:
            self.logger.debug("RESORT: No group_preview_screen to refresh")
