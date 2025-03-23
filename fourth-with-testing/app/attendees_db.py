import sqlite3
from app.config import ATTENDEE_DB_FILE, DEFAULT_SOURCE
from app.utils import parse_iso_time

def init_attendee_db():
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendees (
            email TEXT PRIMARY KEY,
            name TEXT,
            first_meeting TEXT,
            last_meeting TEXT,
            next_meeting TEXT,
            last_meeting_subject TEXT,
            times_met INTEGER DEFAULT 0,
            ok_to_ignore TEXT DEFAULT 'no',
            source TEXT DEFAULT 'paul@teamcinder.com'
        )
    """)
    conn.commit()
    conn.close()

def update_attendees_with_event(event):
    if event is None:
        return
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    
    start_str = event.get("start", {}).get("dateTime")
    if not start_str and "date" in event.get("start", {}):
        start_str = event["start"]["date"] + "T00:00:00+00:00"
    if not start_str:
        return
    try:
        event_start = parse_iso_time(start_str)
    except Exception as e:
        print(f"Error parsing event start time: {e}")
        return

    now = event_start  # Simplification; in production, use current time if needed.
    event_subject = event.get("subject", "").strip() or ""
    
    for att in event.get("attendees", []):
        email = att.get("emailAddress", {}).get("address", "").lower()
        name = att.get("emailAddress", {}).get("name", "").strip()
        if not email:
            continue
        cursor.execute("SELECT first_meeting, last_meeting, next_meeting, times_met FROM attendees WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row:
            first_meeting, last_meeting, next_meeting, times_met = row
            times_met = times_met if times_met is not None else 0
            if not first_meeting or event_start.isoformat() < first_meeting:
                first_meeting = event_start.isoformat()
            if not last_meeting or (event_start.isoformat() > last_meeting and event_start <= now):
                last_meeting = event_start.isoformat()
                last_meeting_subject = event_subject
            if event_start > now:
                if not next_meeting or event_start.isoformat() < next_meeting:
                    next_meeting = event_start.isoformat()
            times_met += 1
            cursor.execute("""
                UPDATE attendees
                SET name = ?, first_meeting = ?, last_meeting = ?, next_meeting = ?, last_meeting_subject = ?, times_met = ?
                WHERE email = ?
            """, (name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, email))
        else:
            first_meeting_val = event_start.isoformat() if event_start <= now else None
            last_meeting_val = event_start.isoformat() if event_start <= now else None
            next_meeting_val = event_start.isoformat() if event_start > now else None
            cursor.execute("""
                INSERT INTO attendees (email, name, first_meeting, last_meeting, next_meeting, times_met)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (email, name, first_meeting_val, last_meeting_val, next_meeting_val, 1))
    conn.commit()
    conn.close()

def get_attendee_summary():
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore, source
        FROM attendees
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_attendee_ok_to_ignore(email: str):
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE attendees SET ok_to_ignore = 'yes' WHERE email = ?", (email,))
    conn.commit()
    conn.close()

from app.utils import parse_iso_time
