# database.py
import sqlite3
from config import CALENDAR_DB_PATH

def create_calendar_db():
    """Initializes the calendar database and creates the events table."""
    conn = sqlite3.connect(CALENDAR_DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            subject TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            attendees TEXT,
            is_recurring INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insert_or_update_event(event):
    """
    Inserts a new event or updates an existing one.
    The event parameter is expected to be a dictionary with keys:
    event_id, subject, start_time, end_time, location, attendees, is_recurring.
    """
    conn = sqlite3.connect(CALENDAR_DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO events (event_id, subject, start_time, end_time, location, attendees, is_recurring)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            subject=excluded.subject,
            start_time=excluded.start_time,
            end_time=excluded.end_time,
            location=excluded.location,
            attendees=excluded.attendees,
            is_recurring=excluded.is_recurring
    ''', (
        event.get('event_id'),
        event.get('subject'),
        event.get('start_time'),
        event.get('end_time'),
        event.get('location'),
        event.get('attendees'),
        event.get('is_recurring')
    ))
    conn.commit()
    conn.close()

def get_all_events():
    """Retrieves all events from the calendar database."""
    conn = sqlite3.connect(CALENDAR_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM events')
    events = c.fetchall()
    conn.close()
    return events
