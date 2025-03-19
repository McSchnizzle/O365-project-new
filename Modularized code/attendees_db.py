import sqlite3
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from config import ATTENDEE_DB_FILE
from auth import get_token
from utils import parse_iso_time

def init_attendee_db():
    """
    Initialize the attendee database with the new schema.
    Columns:
      - email (primary key)
      - name
      - first_meeting (date/time string of the first meeting)
      - last_meeting (most recent meeting)
      - next_meeting (upcoming meeting)
      - last_meeting_subject (subject of the most recent meeting)
      - times_met (number of times met)
      - ok_to_ignore (flag, 0 or 1; default 0)
    """
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
            ok_to_ignore INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def update_attendees_with_event(event):
    """
    For each attendee in the event, update (or insert) their record in the attendee database.
    Uses the event start time to update:
      - first_meeting (if this event is earlier than the current record)
      - last_meeting (if this event is later than the current record)
      - next_meeting (if this event is in the future and earlier than any recorded next meeting)
      - times_met (increment by 1)
    """
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

    now = datetime.now(timezone.utc)
    event_subject = event.get("subject", "")
    if event_subject:
        event_subject = event_subject.strip()
    
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
            if not last_meeting or event_start.isoformat() > last_meeting:
                last_meeting = event_start.isoformat()
            if event_start > now:
                if not next_meeting or event_start.isoformat() < next_meeting:
                    next_meeting = event_start.isoformat()
            times_met += 1
            cursor.execute("""
                UPDATE attendees
                SET name = ?, first_meeting = ?, last_meeting = ?, next_meeting = ?, times_met = ?
                WHERE email = ?
            """, (name, first_meeting, last_meeting, next_meeting, times_met, email))
        else:
            first_meeting_val = event_start.isoformat() if event_start < now else None
            last_meeting_val = event_start.isoformat() if event_start < now else None
            next_meeting_val = event_start.isoformat() if event_start > now else None
            cursor.execute("""
                INSERT INTO attendees (email, name, first_meeting, last_meeting, next_meeting, times_met)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (email, name, first_meeting_val, last_meeting_val, next_meeting_val, 1))
    conn.commit()
    conn.close()


def get_attendee_summary():
    """
    Returns a list of attendee records.
    Each record is a tuple: 
    (email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore)
    """
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore FROM attendees")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_series_master_attendees(series_master_id):
    """
    Query the master event (using its seriesMasterId) for its attendees.
    Returns a list of attendee objects.
    """
    token = get_token(["Calendars.Read"])
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/me/events/{series_master_id}?$select=attendees"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("attendees", [])
    else:
        print("Failed to fetch series master attendees", series_master_id, response.status_code, response.text)
        return []
