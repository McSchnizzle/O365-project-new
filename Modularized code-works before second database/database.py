import sqlite3
from config import SQLITE_DB_FILE

def init_db():
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            subject TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            attendees TEXT,
            raw_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def upsert_event(event):
    import json
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    event_id = event.get("id")
    subject = event.get("subject", "")
    start_time = event.get("start", {}).get("dateTime", "")
    end_time = event.get("end", {}).get("dateTime", "")
    location = event.get("location", {}).get("displayName", "")
    attendees = json.dumps(event.get("attendees", []))
    raw_json = json.dumps(event)
    cursor.execute("""
        INSERT OR REPLACE INTO events (id, subject, start_time, end_time, location, attendees, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_id, subject, start_time, end_time, location, attendees, raw_json))
    conn.commit()
    conn.close()
