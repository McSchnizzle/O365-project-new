import msal
import json
import os
import requests
import sqlite3

# --- Configuration ---
CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"
SCOPE = ["Calendars.Read"]
TOKEN_CACHE_FILE = "token_cache.bin"
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0/me/events"
SQLITE_DB_FILE = "calendar.db"

# --- Step 1: Authenticate with persistent token cache ---
# Create a token cache and load it from file if available.
cache = msal.SerializableTokenCache()
if os.path.exists(TOKEN_CACHE_FILE):
    with open(TOKEN_CACHE_FILE, "r") as f:
        cache.deserialize(f.read())

# Create the PublicClientApplication with the token cache
app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

# Attempt to acquire token silently
accounts = app.get_accounts()
result = None
if accounts:
    result = app.acquire_token_silent(SCOPE, account=accounts[0])

# If no valid token was found, perform the device code flow
if not result:
    flow = app.initiate_device_flow(scopes=SCOPE)
    if "user_code" not in flow:
        raise Exception("Failed to create device flow. Error details: " + json.dumps(flow, indent=4))
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)

# Save token cache if it has changed
if cache.has_state_changed:
    with open(TOKEN_CACHE_FILE, "w") as f:
        f.write(cache.serialize())

if "access_token" not in result:
    print("Authentication failed.")
    print(json.dumps(result, indent=4))
    exit(1)

access_token = result["access_token"]
print("Authentication successful!")

# --- Step 2: Retrieve Calendar Events from Microsoft Graph ---
headers = {
    "Authorization": "Bearer " + access_token
}
response = requests.get(GRAPH_ENDPOINT, headers=headers)
if response.status_code != 200:
    print("Error retrieving calendar events:", response.status_code, response.text)
    exit(1)

events_data = response.json()
events = events_data.get("value", [])
print(f"Retrieved {len(events)} events.")

# --- Step 3: Store Events in SQLite ---
# Connect to (or create) the SQLite database
conn = sqlite3.connect(SQLITE_DB_FILE)
cursor = conn.cursor()

# Create the events table if it doesn't exist
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

# Insert or update events in the database
for event in events:
    event_id = event.get("id")
    subject = event.get("subject", "")
    
    # Extract start and end times; these are objects with 'dateTime' and 'timeZone'
    start_obj = event.get("start", {})
    end_obj = event.get("end", {})
    start_time = start_obj.get("dateTime", "")
    end_time = end_obj.get("dateTime", "")
    
    # Get location display name if available
    location_obj = event.get("location", {})
    location = location_obj.get("displayName", "")
    
    # Attendees, if available, will be a list of attendee objects. We'll store it as JSON.
    attendees = json.dumps(event.get("attendees", []))
    
    # Store the entire event JSON as a string (for future reference if needed)
    raw_json = json.dumps(event)
    
    # Use INSERT OR REPLACE to update the record if it already exists.
    cursor.execute("""
        INSERT OR REPLACE INTO events (id, subject, start_time, end_time, location, attendees, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_id, subject, start_time, end_time, location, attendees, raw_json))

conn.commit()
conn.close()

print(f"Successfully stored {len(events)} events into the SQLite database '{SQLITE_DB_FILE}'.")
