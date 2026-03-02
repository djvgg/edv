# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Database Service - Centralized database operations for the application.

Keeps DB logic in the backend layer. Frontend should never:
- Import SessionLocal
- Call create_engine
- Manage database sessions
- Access models directly
"""

import os
import sys
import traceback
from typing import Callable, Any, Optional

# Add edv_backend directory to path for utils access
# We're in backend/services/, so go up 2 levels to edv_backend/
_edv_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _edv_backend_path not in sys.path:
    sys.path.insert(0, _edv_backend_path)

from utils.logging import get_logger  # noqa: E402
from ..data.database import SessionLocal, init_db as _init_db, Base, engine  # noqa: E402
from .tournament_service import TournamentService  # noqa: E402

logger = get_logger('database_service')

# Track database availability (set to False if connection fails)
DB_AVAILABLE = True


class DatabaseService:
    """
    Central service for all database operations.
    
    Features:
    - Manages SQLAlchemy sessions internally (frontend never touches SessionLocal)
    - Initializes database schema on startup
    - Handles connection errors gracefully
    - Provides clean CRUD interface to frontend
    - Thread-safe session management
    """

    def __init__(self):
        """Initialize database service and schema."""
        global DB_AVAILABLE
        self.logger = logger
        self._initialized = False
        
        try:
            self.logger.info("Initializing database schema...")
            _init_db()
            self._initialized = True
            self.logger.info("Database schema initialized successfully")
        except Exception as e:
            error_msg = str(e).lower()
            if 'connection refused' in error_msg or 'could not connect' in error_msg:
                DB_AVAILABLE = False
                self.logger.warning(f"Database unavailable at startup: {e}")
            else:
                self.logger.error(f"Failed to initialize database: {e}")
                DB_AVAILABLE = False

    def is_available(self) -> bool:
        """Check if database is available."""
        global DB_AVAILABLE
        return DB_AVAILABLE

    def _execute_with_session(self, fn: Callable[[TournamentService], Any]) -> Optional[Any]:
        """
        Execute a function within a database session context.
        
        Args:
            fn: Function that takes TournamentService and returns a result
        
        Returns:
            Result from fn, or None if DB unavailable
            
        Handles:
        - Session creation and cleanup
        - Connection errors
        - Transaction rollback on failure
        """
        global DB_AVAILABLE
        
        if not DB_AVAILABLE:
            self.logger.debug("Database unavailable, skipping operation")
            return None
        
        db = None
        try:
            db = SessionLocal()
            service = TournamentService(db)
            result = fn(service)
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if 'connection refused' in error_msg or 'could not connect' in error_msg:
                DB_AVAILABLE = False
                self.logger.error(f"Database connection lost, disabling DB operations: {e}")
            else:
                # Other errors - log but don't disable DB
                if db:
                    db.rollback()
                self.logger.error(f"Database operation failed: {e}\n{traceback.format_exc()}")
            return None
        finally:
            if db:
                db.close()

    # ===== PARTICIPANT CRUD =====
    
    def save_participants(self, participants: list) -> bool:
        """
        Save participant list to database.
        
        Args:
            participants: List of participant dicts
            
        Returns:
            True if successful, False if DB unavailable or error
        """
        def _save(svc: TournamentService):
            svc.save_participants(participants)
            return True
        
        result = self._execute_with_session(_save)
        return result is True

    def fetch_participants(self) -> Optional[list]:
        """
        Fetch all participants from database.
        
        Returns:
            List of participant dicts, or None if DB unavailable
        """
        from ..data.repositories.participant_repository import fetch_participants_from_db
        
        def _fetch(svc: TournamentService):
            return fetch_participants_from_db()
        
        return self._execute_with_session(_fetch)

    # ===== BRACKET & GROUP CRUD =====

    def update_participant(self, fighter: dict, new_bracket_key: str) -> bool:
        """
        Persist edits from edit_participant_dialog to DB.
        Updates the participants row and moves the group_participants entry.
        """
        def _update(svc: TournamentService):
            svc.update_participant(fighter, new_bracket_key)
            return True
        return self._execute_with_session(_update) is True

    def initialize_all_groups(self) -> bool:
        """Create all possible groups from config + QUARANTINE. Called once after save_participants."""
        def _init(svc: TournamentService):
            svc.initialize_all_groups()
            return True
        return self._execute_with_session(_init) is True

    def save_groups(self, brackets: dict) -> bool:
        """Re-sync group_participants after load or group preview edits."""
        def _save(svc: TournamentService):
            svc.save_groups(brackets)
            return True
        return self._execute_with_session(_save) is True

    def save_brackets(self, brackets: dict, generation_methods: dict) -> bool:
        """Write brackets table after generation methods are confirmed."""
        def _save(svc: TournamentService):
            svc.save_brackets(brackets, generation_methods)
            return True
        return self._execute_with_session(_save) is True

    def save_groups_and_brackets(self, brackets: dict, generation_methods: dict) -> bool:
        """
        Save bracket groups and their assignments.
        
        Args:
            brackets: Dict of {bracket_key: bracket_data}
            generation_methods: Dict of {bracket_key: method_name}
            
        Returns:
            True if successful, False if DB unavailable or error
        """
        def _save(svc: TournamentService):
            svc.save_groups_and_brackets(brackets, generation_methods)
            return True
        
        result = self._execute_with_session(_save)
        return result is True

    # ===== TABLE ASSIGNMENT CRUD =====
    
    def assign_bracket_to_table(self, bracket_key: str, table_num: int) -> bool:
        """
        Assign a bracket to a specific table (mat).
        
        Args:
            bracket_key: Bracket identifier (e.g. 'U13')
            table_num: Table/mat number (1-4)
            
        Returns:
            True if successful, False if DB unavailable or error
        """
        def _assign(svc: TournamentService):
            svc.assign_mat(bracket_key, table_num)
            return True
        
        result = self._execute_with_session(_assign)
        return result is True

    # ===== FIGHT MONITORING CRUD =====
    
    def create_fights_for_bracket(self, bracket_key: str, fight_pairs: list) -> bool:
        """
        Create fight rows for a bracket (for fight monitoring).
        
        Args:
            bracket_key: Bracket identifier
            fight_pairs: List of (fighter1, fighter2) tuples
            
        Returns:
            True if successful, False if DB unavailable or error
        """
        def _create(svc: TournamentService):
            try:
                svc.open_bracket_for_monitoring(bracket_key, fight_pairs)
                return True
            except ValueError:
                # Bracket not yet saved to DB (expected if loaded from file)
                self.logger.debug(f"Bracket '{bracket_key}' not yet in DB (skipping fight creation)")
                return False
        
        result = self._execute_with_session(_create)
        return result is True

    # ===== UTILITY =====
    
    def reinitialize_schema(self) -> bool:
        """
        Reinitialize database schema (drops and recreates all tables).
        
        WARNING: This will delete all data!
        
        Returns:
            True if successful, False otherwise
        """
        global DB_AVAILABLE
        
        try:
            self.logger.warning("Reinitializing database schema (all data will be lost)")
            Base.metadata.drop_all(engine)
            _init_db()
            DB_AVAILABLE = True
            self.logger.info("Database schema reinitialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reinitialize schema: {e}")
            DB_AVAILABLE = False
            return False


# Singleton instance
_instance: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """
    Get the database service instance (creates it if needed).
    
    This is the main entry point for frontend to access database operations.
    """
    global _instance
    if _instance is None:
        _instance = DatabaseService()
    return _instance


def reset_database_service():
    """Reset the singleton instance (for testing)."""
    global _instance
    _instance = None
