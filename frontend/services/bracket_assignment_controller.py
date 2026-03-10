# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Bracket Assignment Controller — coordinates state and database operations.

Provides a clean interface between UI layer and backend services,
ensuring state and database stay in sync.
"""

from typing import Optional, Tuple
import os
import sys

_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402


class BracketAssignmentController:
    """
    Coordinates bracket-to-table assignment operations.
    
    Manages both in-memory state (TournamentState) and persistence (DatabaseService)
    to ensure they stay synchronized.
    """
    
    def __init__(self, state, db_service):
        """Initialize controller with state and database service.
        
        Args:
            state: TournamentState instance (in-memory tournament data)
            db_service: DatabaseService instance (persistence layer)
        """
        self.state = state
        self.db_service = db_service
        self.logger = get_logger('bracket_assignment_controller')
    
    def assign_bracket_to_table(
        self,
        bracket_key: str,
        table_num: int
    ) -> Tuple[bool, Optional[str]]:
        """Assign a bracket to a table.
        
        Coordinates both state update and database persistence.
        Rolls back state if database operation fails.
        
        Args:
            bracket_key: Bracket identifier (e.g., "M | U13 | -50kg")
            table_num: Table number (1-8)
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        # Validation
        if bracket_key not in self.state.brackets:
            error = f"Bracket '{bracket_key}' not found in current brackets"
            self.logger.warning(f"[ASSIGN] {error}")
            return False, error
        
        if table_num < 1 or table_num > 8:
            error = f"Invalid table number: {table_num} (must be 1-8)"
            self.logger.warning(f"[ASSIGN] {error}")
            return False, error
        
        # Get bracket data needed for fight creation
        bracket_data = self.state.brackets[bracket_key]
        bracket_type = self.state.bracket_generation_methods.get(bracket_key, 'ko')
        fight_pairs = bracket_data.get('bracket', [])
        fighters = bracket_data.get('fighters', [])
        pool_size = bracket_data.get('pool_size')
        
        # Store previous state for rollback
        previous_assignment = self.state.bracket_table_assignment.get(bracket_key)
        
        try:
            # Update in-memory state first
            self.state.bracket_table_assignment[bracket_key] = table_num
            
            # Persist to database (this also creates fight rows)
            success = self.db_service.assign_and_create_fights(
                bracket_key,
                table_num=table_num,
                fight_pairs=fight_pairs,
                bracket_type=bracket_type,
                fighters=fighters,
                pool_size=pool_size,
            )
            
            if not success:
                # Database operation failed - rollback state
                self.state.bracket_table_assignment[bracket_key] = previous_assignment
                error = "Database operation failed"
                self.logger.error(f"[ASSIGN] '{bracket_key}' → Table {table_num}: {error}")
                return False, error
            
            self.logger.info(f"[ASSIGN] '{bracket_key}' → Table {table_num}: SUCCESS")
            return True, None
            
        except Exception as e:
            # Unexpected error - rollback state
            self.state.bracket_table_assignment[bracket_key] = previous_assignment
            error = f"Unexpected error: {str(e)}"
            self.logger.error(f"[ASSIGN] '{bracket_key}' → Table {table_num}: {error}")
            return False, error
    
    def unassign_bracket(self, bracket_key: str) -> Tuple[bool, Optional[str]]:
        """Unassign a bracket from its table.
        
        Removes table assignment from both state and database.
        Rolls back state if database operation fails.
        
        Args:
            bracket_key: Bracket identifier
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        # Validation
        if bracket_key not in self.state.brackets:
            error = f"Bracket '{bracket_key}' not found"
            self.logger.warning(f"[UNASSIGN] {error}")
            return False, error
        
        current_assignment = self.state.bracket_table_assignment.get(bracket_key)
        if not current_assignment:
            error = "Bracket is not currently assigned to any table"
            self.logger.warning(f"[UNASSIGN] '{bracket_key}': {error}")
            return False, error
        
        try:
            # Update in-memory state first
            self.state.bracket_table_assignment[bracket_key] = None
            
            # Persist to database
            success = self.db_service.unassign_bracket_from_table(bracket_key)
            
            if not success:
                # Database operation failed - rollback state
                self.state.bracket_table_assignment[bracket_key] = current_assignment
                error = "Database operation failed"
                self.logger.error(f"[UNASSIGN] '{bracket_key}': {error}")
                return False, error
            
            self.logger.info(f"[UNASSIGN] '{bracket_key}' from Table {current_assignment}: SUCCESS")
            return True, None
            
        except Exception as e:
            # Unexpected error - rollback state
            self.state.bracket_table_assignment[bracket_key] = current_assignment
            error = f"Unexpected error: {str(e)}"
            self.logger.error(f"[UNASSIGN] '{bracket_key}': {error}")
            return False, error
    
    def get_assigned_table(self, bracket_key: str) -> Optional[int]:
        """Get the table number a bracket is assigned to.
        
        Args:
            bracket_key: Bracket identifier
        
        Returns:
            Table number if assigned, None otherwise
        """
        return self.state.bracket_table_assignment.get(bracket_key)
    
    def get_unassigned_brackets(self) -> list[str]:
        """Get list of brackets not assigned to any table.
        
        Returns:
            List of bracket keys without table assignments
        """
        return [
            key for key in self.state.brackets.keys()
            if not self.state.bracket_table_assignment.get(key)
        ]
    
    def get_brackets_for_table(self, table_num: int) -> list[str]:
        """Get list of brackets assigned to a specific table.
        
        Args:
            table_num: Table number
        
        Returns:
            List of bracket keys assigned to the table
        """
        return [
            key for key, assigned_table in self.state.bracket_table_assignment.items()
            if assigned_table == table_num
        ]
