# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Background Task Runner - Thread pool for long-running operations.

Enables:
- Running multiple tasks in parallel (DB operations + file loading simultaneously)
- Fine-grained progress reporting
- Task cancellation
- Centralized error handling
- Graceful shutdown

Works for both frontend (UI) and backend (database/file operations) use cases.

Frontend Example (with UI feedback):
    runner = TaskRunner(num_workers=2)
    runner.submit_task(
        'load_xlsx',
        fn=lambda on_progress: load_xlsx_with_updates(filepath, on_progress),
        on_progress=ui.update_progress,
        on_complete=ui.show_results,
        on_error=ui.show_error,
    )

Backend Example (without UI):
    runner = TaskRunner(num_workers=4)
    runner.submit_task(
        'bulk_import',
        fn=lambda on_progress: bulk_import_participants(data, on_progress),
        on_error=lambda e: logger.error(f"Import failed: {e}"),
    )
"""

import queue
import threading
from typing import Callable, Optional

from .logging import get_logger

logger = get_logger('task_runner')


class Task:
    """Represents a background task."""
    
    def __init__(
        self,
        task_id: str,
        fn: Callable,
        on_progress: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
    ):
        self.task_id = task_id
        self.fn = fn
        self.on_progress = on_progress
        self.on_error = on_error
        self.on_complete = on_complete
        self.cancelled = False
        self.result = None
        self.error = None


class TaskRunner:
    """
    Thread pool for running background tasks without blocking the main thread.
    
    Can be used for:
    - Frontend: Long-running UI operations (file loading, bracket generation)
    - Backend: Database operations (bulk imports, data processing)
    
    Features:
    - Multiple worker threads process tasks from a queue
    - Optional progress reporting via callbacks
    - Task cancellation
    - Error handling and logging
    - Graceful shutdown
    """
    
    def __init__(self, num_workers: int = 2):
        """
        Initialize the task runner.
        
        Args:
            num_workers: Number of worker threads (default 2 for parallelism)
        """
        self.logger = logger
        self.num_workers = num_workers
        self.queue: queue.Queue = queue.Queue()
        self.tasks: dict = {}  # task_id → Task
        self.lock = threading.Lock()
        self.running = True
        
        # Start worker threads (daemon mode so they don't block shutdown)
        self.workers = []
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        self.logger.debug(f"TaskRunner initialized with {num_workers} workers")
    
    def submit_task(
        self,
        task_id: str,
        fn: Callable,
        on_progress: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
    ) -> str:
        """
        Submit a task to the queue.
        
        Args:
            task_id: Unique identifier for the task
            fn: Function to execute. Should accept on_progress keyword arg:
                def fn(on_progress=None):
                    if on_progress:
                        on_progress(50)  # Update progress
                    return result
            on_progress: Optional callback called with progress value (0-100)
            on_error: Optional callback called with Exception if task fails
            on_complete: Optional callback called with result when task succeeds
        
        Returns:
            task_id (for cancellation)
        
        Note:
            All callbacks are optional. Use:
            - on_progress for UI progress updates
            - on_error for error logging
            - on_complete for result handling
        """
        task = Task(task_id, fn, on_progress, on_error, on_complete)
        
        with self.lock:
            # Prevent duplicate task IDs
            if task_id in self.tasks:
                self.logger.warning(f"Task '{task_id}' already exists, cancelling previous")
                self.cancel_task(task_id)
            
            self.tasks[task_id] = task
        
        self.queue.put(task)
        self.logger.info(f"Task '{task_id}' submitted (queue size: {self.queue.qsize()})")
        
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: ID of task to cancel
        
        Returns:
            True if cancelled, False if task not found or already completed
        """
        with self.lock:
            if task_id not in self.tasks:
                self.logger.debug(f"Cannot cancel '{task_id}': not found")
                return False
            
            task = self.tasks[task_id]
            task.cancelled = True
            self.logger.info(f"Task '{task_id}' marked for cancellation")
            return True
    
    def get_task_status(self, task_id: str) -> dict:
        """
        Get current status of a task.
        
        Returns:
            {
                'state': 'queued'|'running'|'complete'|'error'|'cancelled',
                'result': result (if complete),
                'error': error message (if error),
            }
        """
        with self.lock:
            if task_id not in self.tasks:
                return {'state': 'unknown'}
            
            task = self.tasks[task_id]
            
            if task.cancelled:
                state = 'cancelled'
            elif task.error:
                state = 'error'
            elif task.result is not None:
                state = 'complete'
            else:
                state = 'running'
            
            return {
                'state': state,
                'result': task.result,
                'error': task.error,
            }
    
    def _worker_loop(self):
        """Worker thread main loop."""
        worker_name = threading.current_thread().name
        self.logger.debug(f"{worker_name} started")
        
        while self.running:
            try:
                # Get task from queue (timeout prevents hanging on shutdown)
                task: Task = self.queue.get(timeout=1)
            except queue.Empty:
                continue
            
            try:
                # Check if task was cancelled before we could run it
                if task.cancelled:
                    self.logger.info(f"Task '{task.task_id}' was cancelled, skipping")
                    continue
                
                self.logger.debug(f"{worker_name} executing task '{task.task_id}'")
                
                # Execute the task function, passing progress callback
                task.result = task.fn(on_progress=self._make_progress_callback(task))
                
                # Notify completion (if not cancelled in the meantime)
                if not task.cancelled and task.on_complete:
                    self.logger.debug(f"Task '{task.task_id}' complete, calling on_complete")
                    try:
                        task.on_complete(task.result)
                    except Exception as e:
                        self.logger.error(f"on_complete callback for '{task.task_id}' failed: {e}")
                
            except Exception as e:
                # Log and notify error
                task.error = str(e)
                self.logger.error(f"Task '{task.task_id}' failed: {e}", exc_info=True)
                
                if task.on_error:
                    try:
                        task.on_error(e)
                    except Exception as cb_err:
                        self.logger.error(f"on_error callback for '{task.task_id}' failed: {cb_err}")
            
            finally:
                # Clean up task from registry
                with self.lock:
                    if task.task_id in self.tasks:
                        del self.tasks[task.task_id]
                
                self.queue.task_done()
        
        self.logger.debug(f"{worker_name} shutting down")
    
    def _make_progress_callback(self, task: Task) -> Callable:
        """Create a progress callback for a specific task."""
        def on_progress(value: int):
            # Only report if task hasn't been cancelled
            if not task.cancelled and task.on_progress:
                try:
                    task.on_progress(value)
                except Exception as e:
                    self.logger.error(f"Progress callback for '{task.task_id}' failed: {e}")
        
        return on_progress
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the task runner.
        
        Args:
            wait: If True, wait for all tasks to complete before returning
        """
        self.logger.info(f"Shutting down TaskRunner (wait={wait})")
        
        if wait:
            self.queue.join()
            self.logger.debug("All tasks completed")
        
        self.running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=2)
        
        self.logger.info("TaskRunner shutdown complete")
    
    def __repr__(self) -> str:
        queue_size = self.queue.qsize()
        active_tasks = len(self.tasks)
        return f"TaskRunner(workers={self.num_workers}, queue={queue_size}, active={active_tasks})"
