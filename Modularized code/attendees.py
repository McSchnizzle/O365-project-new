import requests
import sqlite3
from config import ATTENDEE_DB_FILE

def init_attendee_db():
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendees (
            email TEXT PRIMARY KEY,
            name TEXT,
            last_meeting TEXT,
            next_meeting TEXT,
            last_meeting_subject TEXT
        )
    """)
    conn.commit()
    conn.close()

def update_attendee_db(event):
    # Your existing logic to update the attendee database.
    pass

def get_attendee_summary():
    conn = sqlite3.connect(ATTENDEE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, last_meeting, next_meeting, last_meeting_subject FROM attendees")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_series_master_attendees(series_master_id):
    from auth import get_token
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
