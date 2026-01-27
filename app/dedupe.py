"""Deduplication using SQLite database."""

import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from .models import JobApplication

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "processed.sqlite"


def get_connection() -> sqlite3.Connection:
    """Get SQLite database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database schema."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                date_applied TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT,
                processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_position_date
            ON processed_emails (company, position, date_applied)
        """)
        conn.commit()
        logger.debug("Database initialized")
    finally:
        conn.close()


def is_processed(email_id: str) -> bool:
    """Check if an email has already been processed."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM processed_emails WHERE email_id = ?", (email_id,)
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def is_duplicate(company: str, position: str, date_applied: date) -> bool:
    """Check if a similar application already exists (within +/- 1 day)."""
    conn = get_connection()
    try:
        date_before = (date_applied - timedelta(days=1)).isoformat()
        date_after = (date_applied + timedelta(days=1)).isoformat()

        cursor = conn.execute(
            """
            SELECT 1 FROM processed_emails
            WHERE LOWER(company) = LOWER(?)
            AND LOWER(position) = LOWER(?)
            AND date_applied BETWEEN ? AND ?
            """,
            (company, position, date_before, date_after),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def mark_processed(email_id: str, job: JobApplication) -> None:
    """Record a processed email in the database."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO processed_emails
            (email_id, company, position, date_applied, confidence, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                email_id,
                job.company,
                job.position,
                job.date_applied.isoformat(),
                job.confidence,
                job.source,
            ),
        )
        conn.commit()
        logger.debug(f"Marked email {email_id} as processed")
    finally:
        conn.close()


def get_processed_count() -> int:
    """Get the total number of processed emails."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM processed_emails")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_recent_applications(limit: int = 10) -> list[dict]:
    """Get recent processed applications."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT company, position, date_applied, confidence, processed_at
            FROM processed_emails
            ORDER BY processed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
