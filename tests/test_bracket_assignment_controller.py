# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for BracketAssignmentController."""

import pytest
from unittest.mock import Mock, MagicMock

from frontend.state import TournamentState
from frontend.services.bracket_assignment_controller import BracketAssignmentController


@pytest.fixture
def mock_db_service():
    """Create a mock database service."""
    service = Mock()
    service.assign_and_create_fights = Mock(return_value=True)
    service.unassign_bracket_from_table = Mock(return_value=True)
    return service


@pytest.fixture
def state():
    """Create a tournament state with sample data."""
    state = TournamentState()
    state.brackets = {
        'M | U13 | -50kg': {
            'bracket': [('Alice', 'Bob')],
            'fighters': [
                {'Name': 'Alice', 'Verein': 'ClubA'},
                {'Name': 'Bob', 'Verein': 'ClubB'}
            ],
        },
        'W | U15 | -60kg': {
            'bracket': [('Carol', 'Diana')],
            'fighters': [
                {'Name': 'Carol', 'Verein': 'ClubC'},
                {'Name': 'Diana', 'Verein': 'ClubD'}
            ],
        }
    }
    state.bracket_generation_methods = {
        'M | U13 | -50kg': 'ko',
        'W | U15 | -60kg': 'pools',
    }
    return state


@pytest.fixture
def controller(mock_db_service, state):
    """Create a bracket assignment controller with mocked dependencies."""
    return BracketAssignmentController(state, mock_db_service)


class TestAssignBracketToTable:
    """Tests for assign_bracket_to_table method."""
    
    def test_assign_success(self, controller, mock_db_service, state):
        """Test successful bracket assignment."""
        success, error = controller.assign_bracket_to_table('M | U13 | -50kg', 1)
        
        assert success is True
        assert error is None
        assert state.bracket_table_assignment['M | U13 | -50kg'] == 1
        mock_db_service.assign_and_create_fights.assert_called_once()
    
    def test_assign_invalid_bracket_key(self, controller):
        """Test assignment with non-existent bracket."""
        success, error = controller.assign_bracket_to_table('Nonexistent', 1)
        
        assert success is False
        assert 'not found' in error
    
    def test_assign_invalid_table_number_too_low(self, controller):
        """Test assignment with table number too low."""
        success, error = controller.assign_bracket_to_table('M | U13 | -50kg', 0)
        
        assert success is False
        assert 'Invalid table number' in error
    
    def test_assign_invalid_table_number_too_high(self, controller):
        """Test assignment with table number too high."""
        success, error = controller.assign_bracket_to_table('M | U13 | -50kg', 99)
        
        assert success is False
        assert 'Invalid table number' in error
    
    def test_assign_database_failure(self, controller, mock_db_service, state):
        """Test rollback when database operation fails."""
        # Make database operation fail
        mock_db_service.assign_and_create_fights.return_value = False
        
        success, error = controller.assign_bracket_to_table('M | U13 | -50kg', 1)
        
        assert success is False
        assert error is not None
        # State should be rolled back (remain None)
        assert state.bracket_table_assignment.get('M | U13 | -50kg') is None
    
    def test_assign_database_exception(self, controller, mock_db_service, state):
        """Test rollback when database operation raises exception."""
        # Make database operation raise exception
        mock_db_service.assign_and_create_fights.side_effect = Exception('Database error')
        
        success, error = controller.assign_bracket_to_table('M | U13 | -50kg', 1)
        
        assert success is False
        assert 'Unexpected error' in error
        # State should be rolled back
        assert state.bracket_table_assignment.get('M | U13 | -50kg') is None
    
    def test_assign_passes_correct_parameters(self, controller, mock_db_service, state):
        """Test that correct parameters are passed to database service."""
        controller.assign_bracket_to_table('M | U13 | -50kg', 2)
        
        call_args = mock_db_service.assign_and_create_fights.call_args
        assert call_args[0][0] == 'M | U13 | -50kg'  # bracket_key
        assert call_args[1]['table_num'] == 2
        assert call_args[1]['bracket_type'] == 'ko'
        assert len(call_args[1]['fight_pairs']) == 1
        assert len(call_args[1]['fighters']) == 2
    
    def test_assign_preserves_previous_assignment_on_failure(self, controller, mock_db_service, state):
        """Test that previous assignment is restored on failure."""
        # First assign successfully
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        
        # Make next assignment fail
        mock_db_service.assign_and_create_fights.return_value = False
        
        # Try to reassign
        success, error = controller.assign_bracket_to_table('M | U13 | -50kg', 2)
        
        assert success is False
        # Should restore previous assignment
        assert state.bracket_table_assignment['M | U13 | -50kg'] == 1


class TestUnassignBracket:
    """Tests for unassign_bracket method."""
    
    def test_unassign_success(self, controller, mock_db_service, state):
        """Test successful bracket unassignment."""
        # First assign
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        
        # Then unassign
        success, error = controller.unassign_bracket('M | U13 | -50kg')
        
        assert success is True
        assert error is None
        assert state.bracket_table_assignment['M | U13 | -50kg'] is None
        mock_db_service.unassign_bracket_from_table.assert_called_once_with('M | U13 | -50kg')
    
    def test_unassign_bracket_not_found(self, controller):
        """Test unassignment of non-existent bracket."""
        success, error = controller.unassign_bracket('Nonexistent')
        
        assert success is False
        assert 'not found' in error
    
    def test_unassign_not_assigned(self, controller, state):
        """Test unassignment of bracket that's not assigned."""
        # Bracket exists but not assigned
        success, error = controller.unassign_bracket('M | U13 | -50kg')
        
        assert success is False
        assert 'not currently assigned' in error
    
    def test_unassign_database_failure(self, controller, mock_db_service, state):
        """Test rollback when database operation fails."""
        # First assign
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        
        # Make database operation fail
        mock_db_service.unassign_bracket_from_table.return_value = False
        
        success, error = controller.unassign_bracket('M | U13 | -50kg')
        
        assert success is False
        # State should be rolled back (restored to 1)
        assert state.bracket_table_assignment['M | U13 | -50kg'] == 1
    
    def test_unassign_database_exception(self, controller, mock_db_service, state):
        """Test rollback when database operation raises exception."""
        # First assign
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        
        # Make database operation raise exception
        mock_db_service.unassign_bracket_from_table.side_effect = Exception('Database error')
        
        success, error = controller.unassign_bracket('M | U13 | -50kg')
        
        assert success is False
        assert 'Unexpected error' in error
        # State should be rolled back
        assert state.bracket_table_assignment['M | U13 | -50kg'] == 1


class TestGetAssignedTable:
    """Tests for get_assigned_table method."""
    
    def test_get_assigned_table(self, controller, state):
        """Test getting assigned table number."""
        state.bracket_table_assignment['M | U13 | -50kg'] = 3
        
        table = controller.get_assigned_table('M | U13 | -50kg')
        
        assert table == 3
    
    def test_get_assigned_table_not_assigned(self, controller):
        """Test getting table for unassigned bracket."""
        table = controller.get_assigned_table('M | U13 | -50kg')
        
        assert table is None
    
    def test_get_assigned_table_nonexistent(self, controller):
        """Test getting table for non-existent bracket."""
        table = controller.get_assigned_table('Nonexistent')
        
        assert table is None


class TestGetUnassignedBrackets:
    """Tests for get_unassigned_brackets method."""
    
    def test_get_unassigned_brackets_all_unassigned(self, controller, state):
        """Test getting all unassigned brackets."""
        unassigned = controller.get_unassigned_brackets()
        
        assert len(unassigned) == 2
        assert 'M | U13 | -50kg' in unassigned
        assert 'W | U15 | -60kg' in unassigned
    
    def test_get_unassigned_brackets_some_assigned(self, controller, state):
        """Test getting unassigned brackets when some are assigned."""
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        
        unassigned = controller.get_unassigned_brackets()
        
        assert len(unassigned) == 1
        assert 'W | U15 | -60kg' in unassigned
    
    def test_get_unassigned_brackets_all_assigned(self, controller, state):
        """Test getting unassigned brackets when all are assigned."""
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        state.bracket_table_assignment['W | U15 | -60kg'] = 2
        
        unassigned = controller.get_unassigned_brackets()
        
        assert len(unassigned) == 0


class TestGetBracketsForTable:
    """Tests for get_brackets_for_table method."""
    
    def test_get_brackets_for_table_none(self, controller, state):
        """Test getting brackets for table with no assignments."""
        brackets = controller.get_brackets_for_table(1)
        
        assert len(brackets) == 0
    
    def test_get_brackets_for_table_one(self, controller, state):
        """Test getting brackets for table with one assignment."""
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        
        brackets = controller.get_brackets_for_table(1)
        
        assert len(brackets) == 1
        assert 'M | U13 | -50kg' in brackets
    
    def test_get_brackets_for_table_multiple(self, controller, state):
        """Test getting brackets for table with multiple assignments."""
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        state.bracket_table_assignment['W | U15 | -60kg'] = 1
        
        brackets = controller.get_brackets_for_table(1)
        
        assert len(brackets) == 2
        assert 'M | U13 | -50kg' in brackets
        assert 'W | U15 | -60kg' in brackets
    
    def test_get_brackets_for_table_different_tables(self, controller, state):
        """Test that brackets from other tables are not included."""
        state.bracket_table_assignment['M | U13 | -50kg'] = 1
        state.bracket_table_assignment['W | U15 | -60kg'] = 2
        
        brackets = controller.get_brackets_for_table(1)
        
        assert len(brackets) == 1
        assert 'M | U13 | -50kg' in brackets
        assert 'W | U15 | -60kg' not in brackets
