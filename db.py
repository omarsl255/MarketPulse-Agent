"""
db.py — SQLite database for V2.
Tables: events, snapshots, failed_extractions.
Includes migration helper from V1 schema.
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from schema import CompetitorEvent, FailedExtraction

logger = logging.getLogger(__name__)

DB_PATH = "intel.db"


def _ensure_failed_extractions_columns(conn: sqlite3.Connection) -> None:
    """Add observability columns to failed_extractions on existing DBs."""
    c = conn.cursor()
    c.execute("PRAGMA table_info(failed_extractions)")
    cols = {row[1] for row in c.fetchall()}
    if "failure_category" not in cols:
        c.execute(
            "ALTER TABLE failed_extractions ADD COLUMN failure_category TEXT DEFAULT ''"
        )
        logger.info("Migrated: added column 'failure_category' to failed_extractions")
    if "http_status_code" not in cols:
        c.execute(
            "ALTER TABLE failed_extractions ADD COLUMN http_status_code INTEGER"
        )
        logger.info("Migrated: added column 'http_status_code' to failed_extractions")
    if "detail" not in cols:
        c.execute("ALTER TABLE failed_extractions ADD COLUMN detail TEXT DEFAULT ''")
        logger.info("Migrated: added column 'detail' to failed_extractions")


# ───────────────────────────────────────────────────────────────
# Initialisation & migration
# ───────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH):
    """Create all V2 tables (idempotent)."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Events table (V2 schema)
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id            TEXT PRIMARY KEY,
            competitor          TEXT,
            event_type          TEXT,
            title               TEXT,
            description         TEXT,
            strategic_implication TEXT,
            confidence_score    REAL,
            source_url          TEXT,
            date_detected       TEXT,
            run_id              TEXT DEFAULT '',
            signal_type         TEXT DEFAULT 'unknown',
            content_hash        TEXT DEFAULT '',
            is_new              INTEGER DEFAULT 1
        )
    ''')

    # Snapshots table (change detection)
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            url             TEXT PRIMARY KEY,
            content_hash    TEXT,
            raw_text        TEXT,
            last_updated    TEXT
        )
    ''')

    # Dead-letter queue for failed extractions
    c.execute('''
        CREATE TABLE IF NOT EXISTS failed_extractions (
            id              TEXT PRIMARY KEY,
            url             TEXT,
            error_message   TEXT,
            raw_text_snippet TEXT DEFAULT '',
            timestamp       TEXT,
            run_id          TEXT DEFAULT '',
            failure_category TEXT DEFAULT '',
            http_status_code INTEGER,
            detail          TEXT DEFAULT ''
        )
    ''')

    _ensure_failed_extractions_columns(conn)

    conn.commit()
    conn.close()
    logger.info("Database initialised (V2 schema)")


def migrate_db(db_path: str = DB_PATH):
    """Add V2 columns to an existing V1 database if they are missing."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check existing columns
    c.execute("PRAGMA table_info(events)")
    existing_cols = {row[1] for row in c.fetchall()}

    new_cols = {
        "run_id":       "TEXT DEFAULT ''",
        "signal_type":  "TEXT DEFAULT 'unknown'",
        "content_hash": "TEXT DEFAULT ''",
        "is_new":       "INTEGER DEFAULT 1",
    }

    for col_name, col_def in new_cols.items():
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_def}")
            logger.info(f"Migrated: added column '{col_name}' to events table")

    conn.commit()
    conn.close()

# ───────────────────────────────────────────────────────────────
# Events CRUD
# ───────────────────────────────────────────────────────────────

def save_event(event: CompetitorEvent, db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO events (
            event_id, competitor, event_type, title, description,
            strategic_implication, confidence_score, source_url, date_detected,
            run_id, signal_type, content_hash, is_new
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event.event_id, event.competitor, event.event_type, event.title,
        event.description, event.strategic_implication, event.confidence_score,
        event.source_url, event.date_detected,
        event.run_id, event.signal_type, event.content_hash,
        1 if event.is_new else 0,
    ))
    conn.commit()
    conn.close()


def get_all_events(db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM events ORDER BY date_detected DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_events_by_event_type(event_type: str, db_path: str = DB_PATH) -> int:
    """Delete all events with the given event_type (e.g. MOCK_SIGNAL). Returns rows removed."""
    conn = sqlite3.connect(db_path)
    n = int(
        conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = ?", (event_type,)
        ).fetchone()[0]
    )
    conn.execute("DELETE FROM events WHERE event_type = ?", (event_type,))
    conn.commit()
    conn.close()
    logger.info("Deleted %s event(s) with event_type=%s", n, event_type)
    return n


def count_events_by_event_type(event_type: str, db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    n = int(
        conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = ?", (event_type,)
        ).fetchone()[0]
    )
    conn.close()
    return n


def get_events_by_run(run_id: str, db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM events WHERE run_id = ? ORDER BY date_detected DESC', (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_events_by_competitor(competitor: str, db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM events WHERE competitor = ? ORDER BY date_detected DESC', (competitor,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ───────────────────────────────────────────────────────────────
# Snapshots (change detection)
# ───────────────────────────────────────────────────────────────

def save_snapshot(url: str, content_hash: str, raw_text: str, timestamp: str, db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO snapshots (url, content_hash, raw_text, last_updated)
        VALUES (?, ?, ?, ?)
    ''', (url, content_hash, raw_text[:50000], timestamp))  # cap raw text at 50k chars
    conn.commit()
    conn.close()


def get_last_snapshot(url: str, db_path: str = DB_PATH) -> Optional[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM snapshots WHERE url = ?', (url,)).fetchone()
    conn.close()
    return dict(row) if row else None


def count_snapshots(db_path: str = DB_PATH) -> int:
    """Return number of stored URL snapshots (used for change detection)."""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()
    conn.close()
    return int(row[0]) if row else 0


def clear_all_snapshots(db_path: str = DB_PATH) -> int:
    """
    Remove all snapshots so the next pipeline run treats each URL as changed
    and re-runs extraction (e.g. after configuring GOOGLE_API_KEY).
    """
    conn = sqlite3.connect(db_path)
    n = int(conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0])
    conn.execute("DELETE FROM snapshots")
    conn.commit()
    conn.close()
    logger.info("Cleared %s snapshot row(s)", n)
    return n

# ───────────────────────────────────────────────────────────────
# Dead-letter queue
# ───────────────────────────────────────────────────────────────

def save_failed_extraction(failure: FailedExtraction, db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    _ensure_failed_extractions_columns(conn)
    conn.execute('''
        INSERT OR REPLACE INTO failed_extractions (
            id, url, error_message, raw_text_snippet, timestamp, run_id,
            failure_category, http_status_code, detail
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        failure.id,
        failure.url,
        failure.error_message,
        failure.raw_text_snippet,
        failure.timestamp,
        failure.run_id,
        failure.failure_category,
        failure.http_status_code,
        failure.detail,
    ))
    conn.commit()
    conn.close()
    logger.warning(f"Saved failed extraction for {failure.url}: {failure.error_message[:80]}")


def get_failed_extractions(db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM failed_extractions ORDER BY timestamp DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    init_db()
    print("Database initialised (V2).")
