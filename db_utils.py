"""
SQLite Database Manager for Job Queue and Encoding Heuristics.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Tuple
from threading import Lock
from models import JobStatus

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = Lock()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite tables for jobs and encoding profiles."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Job Queue Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Heuristics Profiles Table
            # UNIQUE constraint on (width, height, codec, pix_fmt) 
            # so we only have one "best" profile for a given set of parameters.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS encoding_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    codec TEXT NOT NULL,
                    pix_fmt TEXT NOT NULL,
                    best_bf INTEGER NOT NULL,
                    best_lad INTEGER NOT NULL,
                    best_async_depth INTEGER NOT NULL,
                    success_count INTEGER DEFAULT 1,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(width, height, codec, pix_fmt)
                )
            """)
            
            conn.commit()

    def _get_connection(self):
        """Get a thread-safe connection to the SQLite DB."""
        # Using timeout and isolation_level for concurrency safety
        return sqlite3.connect(
            str(self.db_path), 
            timeout=10.0, 
            isolation_level='IMMEDIATE'
        )

    # --- Job Queue Methods ---

    def add_job(self, path: str) -> bool:
        """Add a job to the queue if it doesn't already exist."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO jobs (path, status) VALUES (?, ?)",
                    (path, JobStatus.PENDING.value)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Job path already exists
                return False

    def dequeue_pending_job(self) -> Optional[Tuple[int, str]]:
        """
        Atomically find a PENDING job, mark it as PROCESSING, and return it.
        Returns: (job_id, path) or None if queue is empty.
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # SQLite doesn't have UPDATE ... RETURNING in older versions, 
            # so we SELECT then UPDATE carefully in a transaction.
            cursor.execute("""
                SELECT id, path FROM jobs 
                WHERE status = ? 
                ORDER BY created_at ASC 
                LIMIT 1
            """, (JobStatus.PENDING.value,))
            row = cursor.fetchone()
            
            if row:
                job_id, path = row
                cursor.execute(
                    "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (JobStatus.PROCESSING.value, job_id)
                )
                conn.commit()
                return job_id, path
            return None

    def update_job_status(self, job_id: int, status: str):
        """Update a job's status (e.g., COMPLETED, FAILED)."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, job_id)
            )
            conn.commit()

    # --- Heuristics Methods ---

    def get_best_profile(self, width: int, height: int, codec: str, pix_fmt: str) -> Optional[Tuple[int, int, int]]:
        """
        Get the most aggressive known-safe parameters for the given media type.
        Returns: (bf, lad, async_depth) or None if no heuristic is known.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT best_bf, best_lad, best_async_depth 
                FROM encoding_profiles
                WHERE width = ? AND height = ? AND codec = ? AND pix_fmt = ?
            """, (width, height, codec, pix_fmt))
            row = cursor.fetchone()
            
            if row:
                # Update last_used timestamp
                cursor.execute("""
                    UPDATE encoding_profiles 
                    SET last_used = CURRENT_TIMESTAMP 
                    WHERE width = ? AND height = ? AND codec = ? AND pix_fmt = ?
                """, (width, height, codec, pix_fmt))
                conn.commit()
                return row
            return None

    def save_successful_profile(self, width: int, height: int, codec: str, pix_fmt: str, 
                                bf: int, lad: int, async_depth: int):
        """
        Save the successful parameters for these media characteristics.
        If a profile exists, it overwrites it (assuming recent success = safe fallback state).
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO encoding_profiles 
                (width, height, codec, pix_fmt, best_bf, best_lad, best_async_depth) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(width, height, codec, pix_fmt) 
                DO UPDATE SET 
                    best_bf = excluded.best_bf,
                    best_lad = excluded.best_lad,
                    best_async_depth = excluded.best_async_depth,
                    success_count = success_count + 1,
                    last_used = CURRENT_TIMESTAMP
            """, (width, height, codec, pix_fmt, bf, lad, async_depth))
            conn.commit()
