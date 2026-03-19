import sqlite3
import json
from schema import CompetitorEvent

DB_PATH = "intel.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            competitor TEXT,
            event_type TEXT,
            title TEXT,
            description TEXT,
            strategic_implication TEXT,
            confidence_score REAL,
            source_url TEXT,
            date_detected TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_event(event: CompetitorEvent):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO events (
            event_id, competitor, event_type, title, description,
            strategic_implication, confidence_score, source_url, date_detected
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event.event_id, event.competitor, event.event_type, event.title,
        event.description, event.strategic_implication, event.confidence_score,
        event.source_url, event.date_detected
    ))
    conn.commit()
    conn.close()

def get_all_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events ORDER BY date_detected DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
    
if __name__ == "__main__":
    init_db()
    print("Database initialized.")
