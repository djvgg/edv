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
from .bracket_reconstruction_service import BracketReconstructionService  # noqa: E402

logger = get_logger('database_service')


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
        self.logger = logger
        self._initialized = False
        self._db_available = True

        try:
            self.logger.info("Initializing database schema...")
            _init_db()
            self._initialized = True
            self.logger.info("Database schema initialized successfully")
        except Exception as e:
            error_msg = str(e).lower()
            if 'connection refused' in error_msg or 'could not connect' in error_msg:
                self._db_available = False
                self.logger.warning(f"Database unavailable at startup: {e}")
            else:
                self.logger.error(f"Failed to initialize database: {e}")
                self._db_available = False
        
        # Initialize bracket reconstruction service
        self.bracket_reconstruction = BracketReconstructionService(self)

    def is_available(self) -> bool:
        """Check if database is available."""
        return self._db_available

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
        if not self._db_available:
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
                self._db_available = False
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
        Add participants to database, skipping duplicates.

        Args:
            participants: List of participant dicts

        Returns:
            True if successful, False if DB unavailable or error
        """
        def _save(svc: TournamentService):
            new_count = svc.add_participants(participants)
            self.logger.info(
                f"Added {new_count} new participants "
                f"({len(participants) - new_count} duplicates skipped)"
            )
            return True

        result = self._execute_with_session(_save)
        return result is True

    def update_participants(self, participants: list) -> bool:
        """
        Update existing participants or insert if not found (UPSERT).
        Matches by natural key and updates fields like paid, valid, doublestart.

        Args:
            participants: List of participant dicts

        Returns:
            True if successful, False if DB unavailable or error
        """
        def _update(svc: TournamentService):
            count = svc.update_participants(participants)
            self.logger.info(f"Upserted {count} participant(s) (updated or inserted)")
            return True

        result = self._execute_with_session(_update)
        return result is True

    def update_participants_respecting_locks(self, participants: list, locked_age_classes=None) -> bool:
        """
        Upsert participants after the caller filtered age-class locks.

        The lock set is logged here so JSON import code can use one persistence
        entry point while keeping the backend boundary explicit.
        """
        locked_age_classes = set(locked_age_classes or [])
        if locked_age_classes:
            self.logger.info(
                f"Upserting {len(participants)} participant(s) with age locks active: "
                f"{sorted(locked_age_classes)}"
            )
        return self.update_participants(participants)

    def flush_database(self) -> bool:
        """Wipe all tournament data (explicit user action via Flush button)."""
        self.logger.warning("[FLUSH] User requested full database flush")

        def _flush(svc: TournamentService):
            svc.flush_database()
            return True
        result = self._execute_with_session(_flush)
        self.logger.info(f"[FLUSH] {'OK' if result else 'FAILED'}")
        return result is True

    def clear_all_data(self) -> bool:
        """Wipe all tournament data (used before importing new data to ensure a clean slate)."""
        return self.flush_database()

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

    # ===== AGE-CLASS LOCK CRUD =====

    def lock_age_class(self, age_group: str, gender: str = None, reason: str = 'manual') -> bool:
        """Persist a lock that protects an age class from editing/import updates."""
        def _lock(svc: TournamentService):
            svc.lock_age_class(age_group, gender=gender, reason=reason)
            return True

        return self._execute_with_session(_lock) is True

    def unlock_age_class(self, age_group: str, gender: str = None) -> bool:
        """Remove a persisted age-class lock."""
        def _unlock(svc: TournamentService):
            svc.unlock_age_class(age_group, gender=gender)
            return True

        return self._execute_with_session(_unlock) is True

    def get_locked_age_classes(self) -> set:
        """Return all persisted age-class lock scope keys."""
        def _fetch(svc: TournamentService):
            return svc.get_locked_age_classes()

        return self._execute_with_session(_fetch) or set()

    def get_age_class_activity(self, age_group: str, gender: str = None) -> dict:
        """Return bracket/fight counts for unlock warnings."""
        def _fetch(svc: TournamentService):
            return svc.get_age_class_activity(age_group, gender=gender)

        return self._execute_with_session(_fetch) or {
            'bracket_count': 0,
            'fight_count': 0,
            'completed_fight_count': 0,
        }

    def reconstruct_bracket_from_db(
        self,
        bracket_id: int,
        bracket_key: str,
        bracket_type: str = 'ko',
        pool_size: int = None,
    ) -> dict:
        """
        Reconstruct a bracket data structure from database Fight records.
        
        Uses the reverse mapping algorithm to recover original participant ordering
        for pool brackets by analyzing the deterministic fight generation algorithm.
        
        Args:
            bracket_id: Database bracket ID
            bracket_key: Human-readable bracket key (for logging)
            bracket_type: 'ko', 'pools', or 'double'
            pool_size: Max fighters per pool (if applicable)
        
        Returns:
            Dict matching self.brackets[bracket_key] format:
            {
                'fighters': [participant dicts with 'Name', 'Verein' keys],
                'bracket': [(fighter1, fighter2), ...],  # KO pairs only
                'bracket_phase': 'pool' or 'wb',
                'pool_size': pool_size,
                'is_quarantine': False
            }
        """
        return self.bracket_reconstruction.reconstruct_bracket_from_db(
            bracket_id=bracket_id,
            bracket_key=bracket_key,
            bracket_type=bracket_type,
            pool_size=pool_size,
        )

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
        self.logger.info(f"[MAT ASSIGN] '{bracket_key}' → Mat {table_num}")

        def _assign(svc: TournamentService):
            svc.assign_mat(bracket_key, table_num)
            return True

        result = self._execute_with_session(_assign)
        self.logger.info(f"[MAT ASSIGN] '{bracket_key}' → Mat {table_num}: {'OK' if result else 'FAILED'}")
        return result is True

    def unassign_bracket_from_table(self, bracket_key: str) -> bool:
        """Set mat_id back to NULL when a bracket is removed from its mat."""
        self.logger.info(f"[MAT UNASSIGN] '{bracket_key}'")

        def _unassign(svc: TournamentService):
            svc.unassign_mat(bracket_key)
            return True
        return self._execute_with_session(_unassign) is True

    # ===== FIGHT MONITORING CRUD =====
    
    def create_fights_for_bracket(
        self,
        bracket_key: str,
        fight_pairs: list,
        bracket_type: str = 'ko',
        fighters: list = None,
        pool_size: int = None,
    ) -> bool:
        """
        Create fight rows for a bracket (for fight monitoring).

        Args:
            bracket_key:   Bracket identifier
            fight_pairs:   WB round-0 name pairs for KO/special brackets
            bracket_type:  'pools' | 'double' | 'ko' | 'special'
            fighters:      Full fighters list — required for pool/double brackets
            pool_size:     Max fighters per pool (for U9/U11 multi-pool splits)
        """
        self.logger.info(f"[CREATE FIGHTS] '{bracket_key}' type={bracket_type}, "
                         f"{len(fight_pairs)} pairs, {len(fighters or [])} fighters")

        def _create(svc: TournamentService):
            try:
                fights = svc.open_bracket_for_monitoring(
                    bracket_key, fight_pairs,
                    bracket_type=bracket_type,
                    fighters=fighters,
                    pool_size=pool_size,
                )
                self.logger.info(f"[CREATE FIGHTS] '{bracket_key}': {len(fights)} fight rows in DB")
                return True
            except ValueError as e:
                self.logger.debug(f"Bracket '{bracket_key}' not yet in DB: {e}")
                return False

        result = self._execute_with_session(_create)
        return result is True

    def assign_and_create_fights(
        self,
        bracket_key: str,
        table_num: int,
        fight_pairs: list,
        bracket_type: str = 'ko',
        fighters: list = None,
        pool_size: int = None,
    ) -> bool:
        """
        Combined operation: Assign bracket to table AND create fights in one session.
        
        This is the preferred method when a bracket is being assigned to a mat
        (consolidates repetitive assign + create pattern from GUI callers).

        Args:
            bracket_key:   Bracket identifier
            table_num:     Table/mat number (1-4)
            fight_pairs:   WB round-0 name pairs for KO/special brackets
            bracket_type:  'pools' | 'double' | 'ko' | 'special'
            fighters:      Full fighters list — required for pool/double brackets
            pool_size:     Max fighters per pool (for U9/U11 multi-pool splits)

        Returns:
            True if both assign and create succeeded, False otherwise
        """
        self.logger.info(f"[ASSIGN+CREATE] '{bracket_key}' → Mat {table_num}, "
                         f"type={bracket_type}, {len(fight_pairs)} pairs")

        def _assign_and_create(svc: TournamentService):
            try:
                # 1. Assign bracket to table
                svc.assign_mat(bracket_key, table_num)
                self.logger.info(f"[ASSIGN+CREATE] Step 1/2: Assigned '{bracket_key}' → Mat {table_num}")

                # 2. Create fight rows
                fights = svc.open_bracket_for_monitoring(
                    bracket_key, fight_pairs,
                    bracket_type=bracket_type,
                    fighters=fighters,
                    pool_size=pool_size,
                )
                self.logger.info(f"[ASSIGN+CREATE] Step 2/2: Created {len(fights)} fight rows for '{bracket_key}'")
                return True
            except ValueError as e:
                self.logger.debug(f"[ASSIGN+CREATE] Failed: Bracket '{bracket_key}' not yet in DB: {e}")
                return False

        result = self._execute_with_session(_assign_and_create)
        return result is True

    # ===== FIGHT RESULT PERSISTENCE =====

    def record_fight_result(
        self,
        bracket_key: str,
        phase: str,
        round_num: int,
        pos: int,
        winner_name: str,
        p1_name: str = None,
        p2_name: str = None,
    ) -> bool:
        """Persist a KO or LB fight result after a winner is clicked.

        p1_name / p2_name are required for rounds 1+ that were not pre-inserted —
        the service will lazily create the fight row when they are provided.
        """
        self.logger.info(
            f"[RECORD RESULT] '{bracket_key}' {phase} R{round_num} pos{pos}: "
            f"winner='{winner_name}' (p1='{p1_name}', p2='{p2_name}')"
        )

        def _record(svc: TournamentService):
            return svc.record_ko_result(
                bracket_key, phase, round_num, pos, winner_name,
                p1_name=p1_name, p2_name=p2_name,
            )
        ok = self._execute_with_session(_record) is True
        self.logger.info(f"[RECORD RESULT] '{bracket_key}' {phase} R{round_num} pos{pos}: {'OK' if ok else 'FAILED'}")
        return ok

    def reset_fight_result(
        self,
        bracket_key: str,
        phase: str,
        round_num: int,
        pos: int,
    ) -> bool:
        """Clear a KO or LB fight result (user de-selected the winner)."""
        self.logger.info(f"[RESET RESULT] '{bracket_key}' {phase} R{round_num} pos{pos}")

        def _reset(svc: TournamentService):
            return svc.reset_ko_result(bracket_key, phase, round_num, pos)
        return self._execute_with_session(_reset) is True

    def delete_fight_position(
        self,
        bracket_key: str,
        phase: str,
        round_num: int,
        pos: int,
    ) -> bool:
        """Delete a lazily-created fight row (used when undoing upstream results)."""
        self.logger.info(f"[DELETE FIGHT] '{bracket_key}' {phase} R{round_num} pos{pos}")

        def _delete(svc: TournamentService):
            svc.delete_ko_fight(bracket_key, phase, round_num, pos)
            return True
        return self._execute_with_session(_delete) is True

    def compute_placements(self, bracket_key: str) -> dict:
        """Compute and store placements for a completed KO bracket.
        Returns dict with first/second/third_1/third_2 group_participant IDs."""
        self.logger.info(f"[PLACEMENTS] Computing placements for '{bracket_key}'")

        def _compute(svc: TournamentService):
            return svc.compute_and_store_placements(bracket_key)
        return self._execute_with_session(_compute) or {}

    def record_pool_score(
        self,
        bracket_key: str,
        fighter1_name: str,
        fighter2_name: str,
        score1: str,
        score2: str,
        winner_name: str = None,
    ) -> bool:
        """Persist a pool fight score after a cell is committed."""
        def _record(svc: TournamentService):
            return svc.record_pool_score(
                bracket_key, fighter1_name, fighter2_name,
                score1, score2, winner_name,
            )
        return self._execute_with_session(_record) is True

    def get_bracket_placements(self, bracket_key: str) -> list:
        """Return placement rows for a completed bracket.

        Each row: {'platz': int, 'vorname': str, 'nachname': str, 'verein': str}
        Returns [] if bracket not found or has no placements.
        """
        from sqlalchemy import text  # noqa: PLC0415

        sql = text("""
            SELECT
                1                                        AS platz,
                b.bracket_type                           AS bracket_type,
                p1.first_name                            AS vorname,
                p1.last_name                             AS nachname,
                COALESCE(p1.club, '')                    AS verein
            FROM brackets b
            JOIN groups g       ON g.id = b.group_id
            LEFT JOIN group_participants gp1 ON gp1.id = b.first_place
            LEFT JOIN participants        p1  ON p1.id  = gp1.participant_id
            WHERE g.name = :key AND p1.id IS NOT NULL

            UNION ALL

            SELECT 2, b.bracket_type, p2.first_name, p2.last_name, COALESCE(p2.club, '')
            FROM brackets b
            JOIN groups g       ON g.id = b.group_id
            LEFT JOIN group_participants gp2 ON gp2.id = b.second_place
            LEFT JOIN participants        p2  ON p2.id  = gp2.participant_id
            WHERE g.name = :key AND p2.id IS NOT NULL

            UNION ALL

            SELECT 3, b.bracket_type, p3a.first_name, p3a.last_name, COALESCE(p3a.club, '')
            FROM brackets b
            JOIN groups g        ON g.id = b.group_id
            LEFT JOIN group_participants gp3a ON gp3a.id = b.third_place_1
            LEFT JOIN participants        p3a  ON p3a.id  = gp3a.participant_id
            WHERE g.name = :key AND p3a.id IS NOT NULL

            UNION ALL

            SELECT 3, b.bracket_type, p3b.first_name, p3b.last_name, COALESCE(p3b.club, '')
            FROM brackets b
            JOIN groups g        ON g.id = b.group_id
            LEFT JOIN group_participants gp3b ON gp3b.id = b.third_place_2
            LEFT JOIN participants        p3b  ON p3b.id  = gp3b.participant_id
            WHERE g.name = :key AND p3b.id IS NOT NULL
              AND b.bracket_type NOT IN ('pools', 'double')

            ORDER BY platz
        """)

        def _fetch(svc: TournamentService):
            rows = svc.db.execute(sql, {'key': bracket_key}).fetchall()
            return [
                {'platz': r.platz, 'bracket_type': r.bracket_type,
                 'vorname': r.vorname, 'nachname': r.nachname, 'verein': r.verein}
                for r in rows
            ]
        return self._execute_with_session(_fetch) or []

    def get_completed_bracket_keys(self) -> set:
        """Return bracket keys (group names) whose DB status is 'completed'."""
        from ..data.models import Bracket, Group  # noqa: PLC0415

        def _fetch(svc: TournamentService):
            rows = (
                svc.db.query(Group.name)
                .join(Bracket, Bracket.group_id == Group.id)
                .filter(Bracket.status == 'completed')
                .all()
            )
            return {row.name for row in rows}

        return self._execute_with_session(_fetch) or set()

    # ===== UTILITY =====

    def reinitialize_schema(self) -> bool:
        """
        Reinitialize database schema (drops and recreates all tables).
        
        WARNING: This will delete all data!
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.warning("Reinitializing database schema (all data will be lost)")
            Base.metadata.drop_all(engine)
            _init_db()
            self._db_available = True
            self.logger.info("Database schema reinitialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reinitialize schema: {e}")
            self._db_available = False
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
