import os
import json
import sqlite3
import requests
import msal
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import Counter

# Set working directory to the folder containing this script.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# -------------------- Global Variables --------------------
series_master_cache = {}  # Cache for series master subjects

# -------------------- Configuration --------------------
SYNC_SCOPES = ["Calendars.Read"]
MAIL_SCOPES = ["Mail.Send"]

CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"

TOKEN_CACHE_FILE = os.path.join(BASE_DIR, "token_cache.bin")
DELTA_LINK_FILE = os.path.join(BASE_DIR, "delta_link.txt")
SQLITE_DB_FILE = os.path.join(BASE_DIR, "calendar.db")

GRAPH_DELTA_ENDPOINT = "https://graph.microsoft.com/v1.0/me/calendarView/delta"
FUTURE_WINDOW_DAYS = 30

# -------------------- Date Parsing Helpers --------------------
def parse_iso_time(iso_str):
    """
    Parse an ISO datetime string.
    If it ends with 'Z', treat it as UTC.
    If it's naive (no offset), assume it's already in Pacific.
    """
    s = iso_str.strip()
    if s.endswith("Z"):
        # Replace trailing 'Z' with '+00:00' so fromisoformat can parse it as UTC.
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception as e:
        raise ValueError(f"Could not parse datetime '{iso_str}': {e}")
    # If no tzinfo is present, assume the time is already in America/Los_Angeles.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    return dt

def convert_to_pacific(iso_time_str):
    """
    Convert an ISO datetime string to America/Los_Angeles time in 12‑hour format.
    """
    dt = parse_iso_time(iso_time_str)
    dt_pacific = dt.astimezone(ZoneInfo("America/Los_Angeles"))
    if os.name != 'nt':
        return dt_pacific.strftime("%-I:%M %p")
    else:
        return dt_pacific.strftime("%#I:%M %p")

def get_series_master_subject(series_master_id):
    global series_master_cache
    if not series_master_id:
        return "", []  # Return empty string and empty list if series_master_id is None or empty
    
    if series_master_id in series_master_cache:
        return series_master_cache[series_master_id]
    
    token = get_token(SYNC_SCOPES)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/me/events/{series_master_id}?$select=subject,attendees"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        subject = data.get("subject", "").strip()
        attendees = data.get("attendees", [])
        series_master_cache[series_master_id] = (subject, attendees)
        return subject, attendees
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch series master event {series_master_id}: {str(e)}")
        series_master_cache[series_master_id] = ("", [])
        return "", []

    
def get_top_attendees(all_events):
    attendee_counter = Counter()
    for event in all_events:
        attendees = event.get("attendees", [])
        for attendee in attendees:
            email = attendee.get("emailAddress", {}).get("address", "")
            if email:
                attendee_counter[email] += 1
    return [email for email, _ in attendee_counter.most_common()]

def format_attendees(attendees, top_attendees):
    if len(attendees) <= 4:
        return ", ".join(a.get("emailAddress", {}).get("name", "") for a in attendees)
    
    selected_attendees = []
    for email in top_attendees:
        for attendee in attendees:
            if attendee.get("emailAddress", {}).get("address", "") == email:
                selected_attendees.append(attendee)
                if len(selected_attendees) == 4:
                    break
        if len(selected_attendees) == 4:
            break
    
    # If we don't have 4 attendees yet, add alphabetically
    if len(selected_attendees) < 4:
        remaining = sorted([a for a in attendees if a not in selected_attendees], 
                           key=lambda x: x.get("emailAddress", {}).get("name", ""))
        selected_attendees.extend(remaining[:4-len(selected_attendees)])
    
    names = [a.get("emailAddress", {}).get("name", "") for a in selected_attendees]
    return ", ".join(names) + " and others"

def get_event_start_dt(event):
    """Return the event’s start datetime as a timezone-aware datetime."""
    start_obj = event.get("start", {})
    dt_str = start_obj.get("dateTime")
    tz_str = start_obj.get("timeZone")
    if dt_str:
        # If a timeZone is provided and it indicates Pacific, assume dt_str is already Pacific.
        if tz_str in ["Pacific Standard Time", "Pacific Daylight Time"]:
            try:
                # Try to parse it as a naive datetime
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                # Fall back to our robust parser
                dt = parse_iso_time(dt_str)
            # Explicitly mark it as Pacific
            return dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        else:
            # Otherwise, parse normally (our parse_iso_time handles strings with trailing Z)
            return parse_iso_time(dt_str)
    elif "date" in start_obj:
        # For all-day events that only have a date, assume midnight UTC,
        # but you might choose to interpret them differently.
        dt_str = start_obj["date"] + "T00:00:00+00:00"
        return datetime.fromisoformat(dt_str)
    return None


# -------------------- Database Functions --------------------
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

# -------------------- Authentication --------------------
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
            raise Exception("Failed to create device flow: " + json.dumps(flow, indent=4))
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())
    if "access_token" not in result:
        raise Exception("Failed to obtain token: " + json.dumps(result, indent=4))
    return result["access_token"]

# -------------------- Calendar Sync --------------------
def sync_calendar():
    init_db()
    token = get_token(SYNC_SCOPES)
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.timezone="Pacific Standard Time"'
    }
    
    if os.path.exists(DELTA_LINK_FILE):
        with open(DELTA_LINK_FILE, "r") as f:
            url = f.read().strip()
        print("Using stored deltaLink for incremental sync.")
    else:
        print("No deltaLink found; performing full sync.")
        start_date = datetime.now(timezone.utc) - timedelta(days=365)
        end_date = datetime.now(timezone.utc) + timedelta(days=FUTURE_WINDOW_DAYS)
        start_str = start_date.isoformat(timespec='seconds').replace('+00:00', 'Z')
        end_str = end_date.isoformat(timespec='seconds').replace('+00:00', 'Z')
        url = f"{GRAPH_DELTA_ENDPOINT}?$select=subject,start,end,location,attendees,isAllDay&startDateTime={start_str}&endDateTime={end_str}"
    
    while url:
        print("Requesting:", url)
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("Error during sync:", response.status_code, response.text)
            return
        data = response.json()
        events = data.get("value", [])
        print(f"Retrieved {len(events)} events in this batch.")
        for event in events:
            upsert_event(event)
        if "@odata.nextLink" in data:
            url = data["@odata.nextLink"]
        elif "@odata.deltaLink" in data:
            delta_link = data["@odata.deltaLink"]
            with open(DELTA_LINK_FILE, "w") as f:
                f.write(delta_link)
            print("Delta sync complete. DeltaLink updated.")
            url = None
        else:
            url = None

# -------------------- Email Building --------------------
def get_today_events():
    import sqlite3, json
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM events")
    rows = cursor.fetchall()
    conn.close()
    events = [json.loads(row[0]) for row in rows]
    
    # Get current time in Pacific using zoneinfo.
    now_pacific = datetime.now(ZoneInfo("America/Los_Angeles"))
    today_midnight = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_midnight = today_midnight + timedelta(days=1)
    
    filtered = []
    for event in events:
        start_dt = get_event_start_dt(event)
        if not start_dt:
            continue
        # Ensure the event's start time is in Pacific
        start_pacific = start_dt.astimezone(ZoneInfo("America/Los_Angeles"))
        if today_midnight <= start_pacific < tomorrow_midnight:
            event["_start_pacific"] = start_pacific
            filtered.append(event)
        elif now_pacific.weekday() == 4:  # If today is Friday, include events before next Monday 8AM.
            next_monday = today_midnight + timedelta(days=(7 - today_midnight.weekday()))
            monday_8am = next_monday.replace(hour=8)
            if tomorrow_midnight <= start_pacific < monday_8am:
                event["_start_pacific"] = start_pacific
                filtered.append(event)
    # Sort events by the computed Pacific start time.
    filtered.sort(key=lambda e: e["_start_pacific"])
    return filtered


def build_html_email(events):
    html = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
      <tr>
        <td align="center" bgcolor="#f4f4f4" style="padding: 20px 0;">
          <h1 style="color: #333333;">Daily Calendar Summary</h1>
        </td>
      </tr>
      <tr>
        <td style="padding: 20px;">
          <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr style="background-color: #333333; color: #ffffff;">
              <th style="padding: 10px; text-align: left;">Time</th>
              <th style="padding: 10px; text-align: left;">Location</th>
              <th style="padding: 10px; text-align: left;">Subject</th>
              <th style="padding: 10px; text-align: left;">Status</th>
              <th style="padding: 10px; text-align: left;">Attendees</th>
            </tr>
    """
    
    for event in events:
        start_time = convert_to_pacific(event["start"]["dateTime"])
        end_time = convert_to_pacific(event["end"]["dateTime"])
        time_range = f"{start_time} - {end_time}"
        
        location = event.get("location", {}).get("displayName", "")
        subject = event.get("subject", "")
        
        if "seriesMasterId" in event:
            master_subject, master_attendees = get_series_master_subject(event["seriesMasterId"])
            subject = master_subject or subject
            attendees = master_attendees or event.get("attendees", [])
        else:
            attendees = event.get("attendees", [])
        
        attendees_names = format_attendees(attendees, top_attendees)
        
        status_label = "Accepted"  # You might want to adjust this based on actual status
        
        html += f"""
            <tr>
              <td style="padding: 10px; border-bottom: 1px solid #dddddd;">{time_range}</td>
              <td style="padding: 10px; border-bottom: 1px solid #dddddd;">{location}</td>
              <td style="padding: 10px; border-bottom: 1px solid #dddddd;">{subject}</td>
              <td style="padding: 10px; border-bottom: 1px solid #dddddd;">{status_label}</td>
              <td style="padding: 10px; border-bottom: 1px solid #dddddd;">{attendees_names}</td>
            </tr>
        """
    
    html += """
          </table>
        </td>
      </tr>
    </table>
    """
    
    return html



def send_email_via_graph(html_content):
    token = get_token(MAIL_SCOPES)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    message = {
        "message": {
            "subject": "Daily Calendar Summary",
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {"emailAddress": {"address": "paul@teamcinder.com"}}
            ]
        },
        "saveToSentItems": "true"
    }
    response = requests.post("https://graph.microsoft.com/v1.0/me/sendMail", headers=headers, json=message)
    if response.status_code in (200, 202):
        print("Email sent successfully via Graph API.")
    else:
        print("Failed to send email:", response.status_code, response.text)

# -------------------- Main Routine --------------------
def main():
    print("Starting daily sync and email process...")
    sync_calendar()
    today_events = get_today_events()
    print(f"Found {len(today_events)} event(s) for today.")
    html_content = build_html_email(today_events)
    send_email_via_graph(html_content)

if __name__ == "__main__":
    main()
