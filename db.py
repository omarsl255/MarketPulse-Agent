"""
db.py — SQLite database for V3.
Tables: events, snapshots, failed_extractions, runs, alerts, reviews,
        correlations, budget_usage.
Includes migration helpers from V1/V2 schemas.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from schema import (
    CompetitorEvent, FailedExtraction, RunMetadata,
    AlertRecord, AnalystReview, CorrelationCluster, BudgetUsage,
)

logger = logging.getLogger(__name__)

DB_PATH = "intel.db"


def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    """Add missing columns to an existing table."""
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in c.fetchall()}
    for col_name, col_def in columns.items():
        if col_name not in existing:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            logger.info(f"Migrated: added column '{col_name}' to {table}")


# ───────────────────────────────────────────────────────────────
# Initialisation & migration
# ───────────────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH):
    """Create all V3 tables (idempotent)."""
    conn = _get_conn(db_path)
    c = conn.cursor()

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
            is_new              INTEGER DEFAULT 1,
            review_status       TEXT DEFAULT 'unreviewed',
            alert_status        TEXT DEFAULT 'pending',
            correlation_id      TEXT DEFAULT '',
            provenance          TEXT DEFAULT 'pipeline',
            extraction_model    TEXT DEFAULT '',
            extraction_tokens   INTEGER DEFAULT 0,
            calibration_tokens  INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            url             TEXT PRIMARY KEY,
            content_hash    TEXT,
            raw_text        TEXT,
            last_updated    TEXT
        )
    ''')

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

    c.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id          TEXT PRIMARY KEY,
            started_at      TEXT,
            finished_at     TEXT DEFAULT '',
            status          TEXT DEFAULT 'running',
            total_urls      INTEGER DEFAULT 0,
            urls_changed    INTEGER DEFAULT 0,
            urls_unchanged  INTEGER DEFAULT 0,
            urls_failed     INTEGER DEFAULT 0,
            events_extracted INTEGER DEFAULT 0,
            extractions_failed INTEGER DEFAULT 0,
            alerts_sent     INTEGER DEFAULT 0,
            total_tokens    INTEGER DEFAULT 0,
            correlations_found INTEGER DEFAULT 0,
            trigger         TEXT DEFAULT 'manual'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id        TEXT PRIMARY KEY,
            event_id        TEXT,
            channel         TEXT,
            status          TEXT DEFAULT 'pending',
            created_at      TEXT,
            sent_at         TEXT DEFAULT '',
            error_detail    TEXT DEFAULT '',
            run_id          TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            review_id       TEXT PRIMARY KEY,
            event_id        TEXT,
            verdict         TEXT DEFAULT 'unreviewed',
            reviewer        TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            reviewed_at     TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS correlations (
            cluster_id      TEXT PRIMARY KEY,
            label           TEXT,
            description     TEXT DEFAULT '',
            event_ids       TEXT DEFAULT '[]',
            competitors     TEXT DEFAULT '[]',
            signal_types    TEXT DEFAULT '[]',
            strength        REAL DEFAULT 0.0,
            created_at      TEXT DEFAULT '',
            run_id          TEXT DEFAULT ''
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS budget_usage (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT,
            competitor      TEXT DEFAULT '',
            stage           TEXT DEFAULT '',
            tokens_used     INTEGER DEFAULT 0,
            llm_calls       INTEGER DEFAULT 0,
            timestamp       TEXT DEFAULT ''
        )
    ''')

    _ensure_columns(conn, "failed_extractions", {
        "failure_category": "TEXT DEFAULT ''",
        "http_status_code": "INTEGER",
        "detail": "TEXT DEFAULT ''",
    })

    _ensure_columns(conn, "events", {
        "run_id": "TEXT DEFAULT ''",
        "signal_type": "TEXT DEFAULT 'unknown'",
        "content_hash": "TEXT DEFAULT ''",
        "is_new": "INTEGER DEFAULT 1",
        "review_status": "TEXT DEFAULT 'unreviewed'",
        "alert_status": "TEXT DEFAULT 'pending'",
        "correlation_id": "TEXT DEFAULT ''",
        "provenance": "TEXT DEFAULT 'pipeline'",
        "extraction_model": "TEXT DEFAULT ''",
        "extraction_tokens": "INTEGER DEFAULT 0",
        "calibration_tokens": "INTEGER DEFAULT 0",
    })

    conn.commit()
    conn.close()
    logger.info("Database initialised (V3 schema)")


def migrate_db(db_path: str = DB_PATH):
    """Add V3 columns to an existing V2 database if they are missing."""
    conn = _get_conn(db_path)
    _ensure_columns(conn, "events", {
        "run_id": "TEXT DEFAULT ''",
        "signal_type": "TEXT DEFAULT 'unknown'",
        "content_hash": "TEXT DEFAULT ''",
        "is_new": "INTEGER DEFAULT 1",
        "review_status": "TEXT DEFAULT 'unreviewed'",
        "alert_status": "TEXT DEFAULT 'pending'",
        "correlation_id": "TEXT DEFAULT ''",
        "provenance": "TEXT DEFAULT 'pipeline'",
        "extraction_model": "TEXT DEFAULT ''",
        "extraction_tokens": "INTEGER DEFAULT 0",
        "calibration_tokens": "INTEGER DEFAULT 0",
    })
    conn.commit()
    conn.close()


# ───────────────────────────────────────────────────────────────
# Events CRUD
# ───────────────────────────────────────────────────────────────

def save_event(event: CompetitorEvent, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO events (
            event_id, competitor, event_type, title, description,
            strategic_implication, confidence_score, source_url, date_detected,
            run_id, signal_type, content_hash, is_new,
            review_status, alert_status, correlation_id, provenance,
            extraction_model, extraction_tokens, calibration_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event.event_id, event.competitor, event.event_type, event.title,
        event.description, event.strategic_implication, event.confidence_score,
        event.source_url, event.date_detected,
        event.run_id, event.signal_type, event.content_hash,
        1 if event.is_new else 0,
        event.review_status, event.alert_status, event.correlation_id,
        event.provenance, event.extraction_model,
        event.extraction_tokens, event.calibration_tokens,
    ))
    conn.commit()
    conn.close()


def get_all_events(db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM events ORDER BY date_detected DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_events_by_event_type(event_type: str, db_path: str = DB_PATH) -> int:
    conn = _get_conn(db_path)
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
    conn = _get_conn(db_path)
    n = int(
        conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = ?", (event_type,)
        ).fetchone()[0]
    )
    conn.close()
    return n


def get_events_by_run(run_id: str, db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM events WHERE run_id = ? ORDER BY date_detected DESC', (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_events_by_competitor(competitor: str, db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM events WHERE competitor = ? ORDER BY date_detected DESC', (competitor,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_event_review(event_id: str, review_status: str, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute(
        "UPDATE events SET review_status = ? WHERE event_id = ?",
        (review_status, event_id),
    )
    conn.commit()
    conn.close()


def update_event_alert_status(event_id: str, alert_status: str, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute(
        "UPDATE events SET alert_status = ? WHERE event_id = ?",
        (alert_status, event_id),
    )
    conn.commit()
    conn.close()


def update_event_correlation(event_id: str, correlation_id: str, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute(
        "UPDATE events SET correlation_id = ? WHERE event_id = ?",
        (correlation_id, event_id),
    )
    conn.commit()
    conn.close()


# ───────────────────────────────────────────────────────────────
# Snapshots (change detection)
# ───────────────────────────────────────────────────────────────

def save_snapshot(url: str, content_hash: str, raw_text: str, timestamp: str, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO snapshots (url, content_hash, raw_text, last_updated)
        VALUES (?, ?, ?, ?)
    ''', (url, content_hash, raw_text[:50000], timestamp))
    conn.commit()
    conn.close()


def get_last_snapshot(url: str, db_path: str = DB_PATH) -> Optional[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM snapshots WHERE url = ?', (url,)).fetchone()
    conn.close()
    return dict(row) if row else None


def count_snapshots(db_path: str = DB_PATH) -> int:
    conn = _get_conn(db_path)
    row = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()
    conn.close()
    return int(row[0]) if row else 0


def clear_all_snapshots(db_path: str = DB_PATH) -> int:
    conn = _get_conn(db_path)
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
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO failed_extractions (
            id, url, error_message, raw_text_snippet, timestamp, run_id,
            failure_category, http_status_code, detail
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        failure.id, failure.url, failure.error_message,
        failure.raw_text_snippet, failure.timestamp, failure.run_id,
        failure.failure_category, failure.http_status_code, failure.detail,
    ))
    conn.commit()
    conn.close()
    logger.warning(f"Saved failed extraction for {failure.url}: {failure.error_message[:80]}")


def get_failed_extractions(db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM failed_extractions ORDER BY timestamp DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ───────────────────────────────────────────────────────────────
# Runs
# ───────────────────────────────────────────────────────────────

def save_run(run: RunMetadata, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO runs (
            run_id, started_at, finished_at, status,
            total_urls, urls_changed, urls_unchanged, urls_failed,
            events_extracted, extractions_failed, alerts_sent,
            total_tokens, correlations_found, trigger
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        run.run_id, run.started_at, run.finished_at, run.status,
        run.total_urls, run.urls_changed, run.urls_unchanged, run.urls_failed,
        run.events_extracted, run.extractions_failed, run.alerts_sent,
        run.total_tokens, run.correlations_found, run.trigger,
    ))
    conn.commit()
    conn.close()


def get_all_runs(db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM runs ORDER BY started_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ───────────────────────────────────────────────────────────────
# Alerts
# ───────────────────────────────────────────────────────────────

def save_alert(alert: AlertRecord, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO alerts (
            alert_id, event_id, channel, status,
            created_at, sent_at, error_detail, run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        alert.alert_id, alert.event_id, alert.channel, alert.status,
        alert.created_at, alert.sent_at, alert.error_detail, alert.run_id,
    ))
    conn.commit()
    conn.close()


def get_alerts_by_run(run_id: str, db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM alerts WHERE run_id = ? ORDER BY created_at DESC', (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_alerts(db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM alerts ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ───────────────────────────────────────────────────────────────
# Reviews
# ───────────────────────────────────────────────────────────────

def save_review(review: AnalystReview, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO reviews (
            review_id, event_id, verdict, reviewer, notes, reviewed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        review.review_id, review.event_id, review.verdict,
        review.reviewer, review.notes, review.reviewed_at,
    ))
    conn.commit()
    conn.close()


def get_reviews_for_event(event_id: str, db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM reviews WHERE event_id = ? ORDER BY reviewed_at DESC', (event_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unreviewed_events(db_path: str = DB_PATH) -> List[Dict]:
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM events WHERE review_status = 'unreviewed' ORDER BY confidence_score DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ───────────────────────────────────────────────────────────────
# Correlations
# ───────────────────────────────────────────────────────────────

def save_correlation(cluster: CorrelationCluster, db_path: str = DB_PATH):
    import json
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT OR REPLACE INTO correlations (
            cluster_id, label, description, event_ids,
            competitors, signal_types, strength, created_at, run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        cluster.cluster_id, cluster.label, cluster.description,
        json.dumps(cluster.event_ids), json.dumps(cluster.competitors),
        json.dumps(cluster.signal_types), cluster.strength,
        cluster.created_at, cluster.run_id,
    ))
    conn.commit()
    conn.close()


def get_all_correlations(db_path: str = DB_PATH) -> List[Dict]:
    import json
    conn = _get_conn(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM correlations ORDER BY created_at DESC').fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        for field in ("event_ids", "competitors", "signal_types"):
            try:
                d[field] = json.loads(d.get(field, "[]"))
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        result.append(d)
    return result


# ───────────────────────────────────────────────────────────────
# Budget usage
# ───────────────────────────────────────────────────────────────

def save_budget_usage(usage: BudgetUsage, db_path: str = DB_PATH):
    conn = _get_conn(db_path)
    conn.execute('''
        INSERT INTO budget_usage (run_id, competitor, stage, tokens_used, llm_calls, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        usage.run_id, usage.competitor, usage.stage,
        usage.tokens_used, usage.llm_calls, usage.timestamp,
    ))
    conn.commit()
    conn.close()


def get_budget_for_run(run_id: str, db_path: str = DB_PATH) -> Dict[str, int]:
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT COALESCE(SUM(tokens_used), 0) as tokens, COALESCE(SUM(llm_calls), 0) as calls "
        "FROM budget_usage WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    conn.close()
    return {"tokens": int(row[0]), "calls": int(row[1])}


# ───────────────────────────────────────────────────────────────
# Retention cleanup
# ───────────────────────────────────────────────────────────────

def apply_retention(retention_config, db_path: str = DB_PATH) -> Dict[str, int]:
    """Delete rows older than the configured retention windows. Returns counts deleted."""
    conn = _get_conn(db_path)
    counts = {}
    now = datetime.now()

    def _prune(table: str, date_col: str, days: int) -> int:
        cutoff = (now - timedelta(days=days)).isoformat()
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {date_col} < ? AND {date_col} != ''",
            (cutoff,),
        ).fetchone()[0]
        conn.execute(
            f"DELETE FROM {table} WHERE {date_col} < ? AND {date_col} != ''",
            (cutoff,),
        )
        return int(n)

    counts["events"] = _prune("events", "date_detected", retention_config.events_days)
    counts["snapshots"] = _prune("snapshots", "last_updated", retention_config.snapshots_days)
    counts["failed_extractions"] = _prune("failed_extractions", "timestamp", retention_config.failed_extractions_days)
    counts["alerts"] = _prune("alerts", "created_at", retention_config.alerts_days)
    counts["runs"] = _prune("runs", "started_at", retention_config.runs_days)

    conn.commit()
    conn.close()

    total = sum(counts.values())
    if total > 0:
        logger.info(f"Retention cleanup: removed {counts}")
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    init_db()
    print("Database initialised (V3).")
