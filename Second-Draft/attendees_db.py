# attendees_db.py
import sqlite3
from config import ATTENDEES_DB_PATH

def create_attendees_db():
    """Initializes the attendees database and creates the attendees table."""
    conn = sqlite3.connect(ATTENDEES_DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendees (
            email TEXT PRIMARY KEY,
            name TEXT,
            first_meeting TEXT,
            last_meeting TEXT,
            next_meeting TEXT,
            last_meeting_subject TEXT,
            times_met INTEGER,
            ok_to_ignore INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insert_or_update_attendee(attendee):
    """
    Inserts a new attendee or updates an existing record.
    The attendee parameter is expected to be a dictionary with keys:
    email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore.
    """
    conn = sqlite3.connect(ATTENDEES_DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO attendees (email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            name=excluded.name,
            first_meeting=excluded.first_meeting,
            last_meeting=excluded.last_meeting,
            next_meeting=excluded.next_meeting,
            last_meeting_subject=excluded.last_meeting_subject,
            times_met=excluded.times_met,
            ok_to_ignore=excluded.ok_to_ignore
    ''', (
        attendee.get('email'),
        attendee.get('name'),
        attendee.get('first_meeting'),
        attendee.get('last_meeting'),
        attendee.get('next_meeting'),
        attendee.get('last_meeting_subject'),
        attendee.get('times_met'),
        attendee.get('ok_to_ignore')
    ))
    conn.commit()
    conn.close()

def get_all_attendees():
    """Retrieves all attendee records from the database."""
    conn = sqlite3.connect(ATTENDEES_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM attendees')
    attendees = c.fetchall()
    conn.close()
    return attendees

def get_stale_contacts(limit=5):
    """
    Retrieves the 'limit' number of contacts that haven't been met in the longest time,
    based on the last_meeting date.
    """
    conn = sqlite3.connect(ATTENDEES_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM attendees ORDER BY last_meeting ASC LIMIT ?', (limit,))
    stale = c.fetchall()
    conn.close()
    return stale
