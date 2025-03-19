import os
import json
import sqlite3
import requests
import msal
from datetime import datetime, timedelta, timezone

# --- Configuration ---
CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"
SCOPES = ["Calendars.Read"]

TOKEN_CACHE_FILE = "token_cache.bin"
LAST_SYNC_FILE = "last_sync.txt"
SQLITE_DB_FILE = "calendar.db"

# Endpoints:
# For full sync (GET events in a time window)
GRAPH_CALENDARVIEW_ENDPOINT = "https://graph.microsoft.com/v1.0/me/calendarView"
# For incremental sync using delta (only works reliably on a small time window)
GRAPH_DELTA_ENDPOINT = "https://graph.microsoft.com/v1.0/me/calendarView/delta"

# Set maximum window (in days) for each GET call—keeping it within the supported range
CHUNK_DAYS = 60

# For incremental sync, we’ll fetch events up to this many days in the future.
FUTURE_WINDOW_DAYS = 30

# --- Helper: Get Access Token ---
def get_token(scopes):
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise Exception("Failed to create device flow. Error details: " + json.dumps(flow, indent=4))
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())
    if "access_token" not in result:
        raise Exception("Failed to obtain token: " + json.dumps(result, indent=4))
    return result["access_token"]

# --- Database Setup ---
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

# --- Upsert Event into Database ---
def upsert_event(event):
    event_id = event.get("id")
    subject = event.get("subject", "")
    start_obj = event.get("start", {})
    end_obj = event.get("end", {})
    start_time = start_obj.get("dateTime", "")
    end_time = end_obj.get("dateTime", "")
    location = event.get("location", {}).get("displayName", "")
    attendees = json.dumps(event.get("attendees", []))
    raw_json = json.dumps(event)
    
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO events (id, subject, start_time, end_time, location, attendees, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_id, subject, start_time, end_time, location, attendees, raw_json))
    conn.commit()
    conn.close()

# --- Perform Full Sync in Chunks ---
def full_sync():
    print("Performing full sync (historical + future data) in chunks.")
    token = get_token(SCOPES)
    headers = {"Authorization": "Bearer " + token}
    
    # Define time range: from 12 months ago to FUTURE_WINDOW_DAYS in the future.
    start_date = datetime.now(timezone.utc) - timedelta(days=365)
    end_date_final = datetime.now(timezone.utc) + timedelta(days=FUTURE_WINDOW_DAYS)
    
    current_start = start_date
    while current_start < end_date_final:
        current_end = current_start + timedelta(days=CHUNK_DAYS)
        if current_end > end_date_final:
            current_end = end_date_final
        # Format in ISO 8601 with 'Z' suffix (UTC)
        start_str = current_start.isoformat(timespec='seconds').replace('+00:00', 'Z')
        end_str = current_end.isoformat(timespec='seconds').replace('+00:00', 'Z')
        url = f"{GRAPH_CALENDARVIEW_ENDPOINT}?startDateTime={start_str}&endDateTime={end_str}"
        print(f"Requesting events from {start_str} to {end_str}")
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("Error during full sync:", response.status_code, response.text)
            return
        data = response.json()
        events = data.get("value", [])
        print(f"  Retrieved {len(events)} events.")
        for event in events:
            upsert_event(event)
        current_start = current_end  # move to the next chunk
    
    # Update the last sync marker to now.
    now_str = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    with open(LAST_SYNC_FILE, "w") as f:
        f.write(now_str)
    print("Full sync complete.")

# --- Perform Incremental Sync using Delta Query ---
def delta_sync(last_sync):
    print("Performing incremental (delta) sync from", last_sync)
    token = get_token(SCOPES)
    headers = {"Authorization": "Bearer " + token}
    
    # For delta sync, we define the window from last_sync to FUTURE_WINDOW_DAYS in the future.
    # Convert last_sync (which is in format with "Z") to a datetime object.
    start_dt = datetime.strptime(last_sync, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc) + timedelta(days=FUTURE_WINDOW_DAYS)
    start_str = start_dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    end_str = end_dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    
    # Use the calendarView/delta endpoint with the time window.
    url = f"{GRAPH_DELTA_ENDPOINT}?startDateTime={start_str}&endDateTime={end_str}"
    while url:
        print("Requesting delta data:", url)
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("Error during delta sync:", response.status_code, response.text)
            return
        data = response.json()
        events = data.get("value", [])
        print(f"  Retrieved {len(events)} events in this batch.")
        for event in events:
            upsert_event(event)
        if "@odata.nextLink" in data:
            url = data["@odata.nextLink"]
        elif "@odata.deltaLink" in data:
            # Save new sync marker (using current time) for future runs.
            now_str = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
            with open(LAST_SYNC_FILE, "w") as f:
                f.write(now_str)
            print("Delta sync complete. New sync marker stored.")
            url = None
        else:
            url = None

# --- Main Sync Routine ---
def sync_calendar():
    init_db()
    if not os.path.exists(LAST_SYNC_FILE):
        # No previous sync marker: do a full sync.
        full_sync()
    else:
        with open(LAST_SYNC_FILE, "r") as f:
            last_sync = f.read().strip()
        # Convert last_sync into a timezone-aware datetime
        last_sync_dt = datetime.strptime(last_sync, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_sync_dt > timedelta(days=CHUNK_DAYS):
            print("Large gap since last sync detected; performing full sync.")
            full_sync()
        else:
            delta_sync(last_sync)

if __name__ == "__main__":
    sync_calendar()
