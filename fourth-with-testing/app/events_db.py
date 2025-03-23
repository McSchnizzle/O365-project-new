# app/events_db.py
"""
Event database module.
Handles initialization and upsert operations for event data.
"""

import sqlite3
import json
import logging
from .config import Config
SQLITE_DB_FILE = Config.SQLITE_DB_FILE


logger = logging.getLogger(__name__)

def init_events_db() -> None:
    """
    Initialize the events database with the required schema.
    """
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
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
    logger.info("Events database initialized.")

def upsert_event(event: dict) -> None:
    """
    Insert or update an event in the events database.
    
    Args:
        event (dict): The event object.
    """
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
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
    logger.debug("Upserted event %s", event_id)
