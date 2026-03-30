# database.py — SQLite persistence for CompetitorIQ
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "competitoriq.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS search_results (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id         TEXT    UNIQUE NOT NULL,
            email             TEXT,
            competitor_domain TEXT    NOT NULL,
            icp_filters       TEXT    NOT NULL DEFAULT '{}',
            preview_companies TEXT    NOT NULL DEFAULT '[]',
            full_companies    TEXT    NOT NULL DEFAULT '[]',
            total_found       INTEGER NOT NULL DEFAULT 0,
            payment_status    TEXT    NOT NULL DEFAULT 'pending',
            payment_reference TEXT,
            unlock_token      TEXT    UNIQUE,
            email_sent_at     TEXT,
            created_at        TEXT    NOT NULL,
            updated_at        TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _now():
    return datetime.utcnow().isoformat()


def create_result(result_id: str, competitor_domain: str, icp_filters: dict):
    conn = get_db()
    now = _now()
    conn.execute("""
        INSERT INTO search_results
            (result_id, competitor_domain, icp_filters, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (result_id, competitor_domain, json.dumps(icp_filters), now, now))
    conn.commit()
    conn.close()


def save_companies(result_id: str, preview: list, full: list):
    conn = get_db()
    conn.execute("""
        UPDATE search_results
        SET preview_companies = ?, full_companies = ?, total_found = ?, updated_at = ?
        WHERE result_id = ?
    """, (json.dumps(preview), json.dumps(full), len(full), _now(), result_id))
    conn.commit()
    conn.close()


def get_result(result_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM search_results WHERE result_id = ?", (result_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_cached_companies(competitor_domain: str):
    """Return the most recent saved company list for a domain (any previous search)."""
    conn = get_db()
    row = conn.execute(
        """SELECT full_companies FROM search_results
           WHERE competitor_domain = ?
             AND full_companies IS NOT NULL
             AND full_companies != '[]'
             AND full_companies != ''
           ORDER BY created_at DESC LIMIT 1""",
        (competitor_domain,)
    ).fetchone()
    conn.close()
    if row and row["full_companies"]:
        try:
            return json.loads(row["full_companies"])
        except Exception:
            return None
    return None


def get_result_by_token(token: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM search_results WHERE unlock_token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_email(result_id: str, email: str):
    conn = get_db()
    conn.execute(
        "UPDATE search_results SET email = ?, updated_at = ? WHERE result_id = ?",
        (email, _now(), result_id)
    )
    conn.commit()
    conn.close()


def mark_paid(result_id: str, payment_reference: str, unlock_token: str):
    conn = get_db()
    conn.execute("""
        UPDATE search_results
        SET payment_status = 'paid', payment_reference = ?, unlock_token = ?, updated_at = ?
        WHERE result_id = ?
    """, (payment_reference, unlock_token, _now(), result_id))
    conn.commit()
    conn.close()


def mark_email_sent(result_id: str):
    conn = get_db()
    conn.execute(
        "UPDATE search_results SET email_sent_at = ?, updated_at = ? WHERE result_id = ?",
        (_now(), _now(), result_id)
    )
    conn.commit()
    conn.close()
