import os
import json
import sqlite3
import requests
import msal
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Change working directory to the folder containing this script.
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
    If it ends with 'Z', replace it with '+00:00' so that fromisoformat() treats it as UTC.
    """
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception as e:
        raise ValueError(f"Could not parse datetime '{iso_str}': {e}")
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

def get_event_start_dt(event):
    """
    Return the event’s start datetime as a timezone-aware datetime.
    If the event's start object contains a timeZone that is 'Pacific Standard Time' or 'Pacific Daylight Time',
    assume the provided dateTime is already in Pacific time.
    """
    start_obj = event.get("start", {})
    dt_str = start_obj.get("dateTime")
    tz_str = start_obj.get("timeZone")
    if dt_str:
        if tz_str in ["Pacific Standard Time", "Pacific Daylight Time"]:
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                dt = parse_iso_time(dt_str)
            return dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        else:
            return parse_iso_time(dt_str)
    elif "date" in start_obj:
        dt_str = start_obj["date"] + "T00:00:00+00:00"
        return datetime.fromisoformat(dt_str)
    return None

# -------------------- Event Filtering Helper --------------------
def should_ignore_event(event):
    """Return True if the event should be ignored (organizer is sjb@silvix.org and subject includes 'reservation confirmed')."""
    if not event:
        return True
    subject = event.get("subject")
    if subject is None:
        subject = ""
    organizer = event.get("organizer", {}).get("emailAddress", {}).get("address", "").lower()
    return organizer == "sjb@silvix.org" and "reservation confirmed" in subject.lower()

# -------------------- Attendee Frequency --------------------
def compute_attendee_frequency(events):
    """Compute frequency counts for attendees across the given events."""
    freq = {}
    for event in events:
        if should_ignore_event(event):
            continue
        for att in event.get("attendees", []):
            email = att.get("emailAddress", {}).get("address", "").lower()
            if email:
                freq[email] = freq.get(email, 0) + 1
    return freq

# -------------------- Conflict Detection --------------------
def get_conflict_groups(events):
    """
    Return a list of conflict groups.
    Each group is a list of events that overlap in time.
    Assumes events are sorted by their _start_pacific attribute.
    """
    groups = []
    current_group = []
    current_end = None
    for event in events:
        end_str = event.get("end", {}).get("dateTime")
        if not end_str:
            continue
        try:
            end_dt = parse_iso_time(end_str).astimezone(ZoneInfo("America/Los_Angeles"))
        except Exception:
            end_dt = event["_start_pacific"]
        if not current_group:
            current_group = [event]
            current_end = end_dt
        else:
            if event["_start_pacific"] < current_end:
                current_group.append(event)
                if end_dt > current_end:
                    current_end = end_dt
            else:
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = [event]
                current_end = end_dt
    if current_group and len(current_group) > 1:
        groups.append(current_group)
    return groups

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

# -------------------- Series Master Query --------------------
def get_series_master_subject(series_master_id):
    global series_master_cache
    if series_master_id in series_master_cache:
        return series_master_cache[series_master_id]
    token = get_token(SYNC_SCOPES)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/me/events/{series_master_id}?$select=subject"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        subject = data.get("subject", "").strip()
        series_master_cache[series_master_id] = subject
        return subject
    else:
        print("Failed to fetch series master event", series_master_id, response.status_code, response.text)
        series_master_cache[series_master_id] = ""
        return ""

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
        url = f"{GRAPH_DELTA_ENDPOINT}?$select=subject,start,end,location,attendees,isAllDay,organizer,seriesMasterId&startDateTime={start_str}&endDateTime={end_str}"
    
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
            if should_ignore_event(event):
                continue
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
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM events WHERE raw_json IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    events = [json.loads(row[0]) for row in rows]
    
    # Filter out events that should be ignored.
    events = [e for e in events if not should_ignore_event(e)]
    
    now_pacific = datetime.now(ZoneInfo("America/Los_Angeles"))
    today_midnight = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_midnight = today_midnight + timedelta(days=1)
    
    filtered = []
    for event in events:
        start_dt = get_event_start_dt(event)
        if not start_dt:
            continue
        start_pacific = start_dt.astimezone(ZoneInfo("America/Los_Angeles"))
        if today_midnight <= start_pacific < tomorrow_midnight:
            event["_start_pacific"] = start_pacific
            filtered.append(event)
        elif now_pacific.weekday() == 4:  # Friday: include events until Monday 8AM.
            next_monday = today_midnight + timedelta(days=(7 - today_midnight.weekday()))
            monday_8am = next_monday.replace(hour=8)
            if tomorrow_midnight <= start_pacific < monday_8am:
                event["_start_pacific"] = start_pacific
                filtered.append(event)
    filtered.sort(key=lambda e: e["_start_pacific"])
    return filtered

def build_html_email(events):
    # Compute attendee frequency across today's events.
    freq_dict = {}
    for event in events:
        for att in event.get("attendees", []):
            email = att.get("emailAddress", {}).get("address", "").lower()
            if email:
                freq_dict[email] = freq_dict.get(email, 0) + 1

    html = "<html><body>"
    html += "<h2>Today's Meetings</h2>"
    html += "<table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Time</th><th>Location</th><th>Subject</th><th>Status</th><th>Attendees</th></tr>"
    for event in events:
        start = event.get("start", {}).get("dateTime", "TBD")
        end = event.get("end", {}).get("dateTime", "TBD")
        
        subject = event.get("subject", "").strip()
        if not subject:
            if event.get("seriesMasterId"):
                series_master_id = event.get("seriesMasterId")
                series_subject = get_series_master_subject(series_master_id)
                if series_subject:
                    subject = f"(Recurring) {series_subject}"
                else:
                    subject = "(Recurring, no subject)"
            else:
                subject = "(No Subject)"
        
        location = event.get("location", {}).get("displayName", "")
        loc_lower = location.lower()
        if "zoom" in loc_lower:
            location = "Zoom"
        elif "teams" in loc_lower:
            location = "Teams"
        elif "google meet" in loc_lower:
            location = "Google Meet"
        elif "webex" in loc_lower:
            location = "Webex"
        
        formatted_start = convert_to_pacific(start) if start != "TBD" else "TBD"
        formatted_end = convert_to_pacific(end) if end != "TBD" else "TBD"
        time_range = f"{formatted_start} - {formatted_end}" if formatted_start != "TBD" and formatted_end != "TBD" else "TBD"
        
        response_status = event.get("responseStatus", {}).get("response", "").strip()
        if response_status == "tentativelyAccepted":
            status_label = "Tentative"
        elif response_status in ["notResponded", "none", ""]:
            status_label = "Pending"
        elif response_status == "accepted":
            status_label = "Accepted"
        elif response_status == "declined":
            status_label = "Declined"
        else:
            status_label = response_status
        
        # Process attendees with frequency filtering.
        attendees_list = event.get("attendees", [])
        att_tuples = []
        for att in attendees_list:
            email = att.get("emailAddress", {}).get("address", "").lower()
            name = att.get("emailAddress", {}).get("name", "").strip()
            if email:
                count = freq_dict.get(email, 0)
                att_tuples.append((count, name, email))
        if len(att_tuples) > 4:
            att_tuples.sort(key=lambda t: (-t[0], t[1].lower()))
            top_attendees = [t[1] for t in att_tuples[:4]]
            attendees_names = ", ".join(top_attendees) + ", and others"
        else:
            names = sorted([t[1] for t in att_tuples], key=lambda n: n.lower())
            attendees_names = ", ".join(names)
        
        html += f"<tr><td>{time_range}</td><td>{location}</td><td>{subject}</td><td>{status_label}</td><td>{attendees_names}</td></tr>"
    html += "</table>"
    
    # Build conflict table.
    conflict_groups = get_conflict_groups(events)
    if conflict_groups:
        html += "<h2>Meeting Conflicts</h2>"
        html += "<table border='1' cellspacing='0' cellpadding='5'>"
        html += "<tr><th>Time Slot</th><th>Meetings</th></tr>"
        for group in conflict_groups:
            group_starts = [e["_start_pacific"] for e in group]
            group_ends = []
            for e in group:
                end_str = e.get("end", {}).get("dateTime")
                try:
                    end_dt = parse_iso_time(end_str).astimezone(ZoneInfo("America/Los_Angeles"))
                except Exception:
                    end_dt = e["_start_pacific"]
                group_ends.append(end_dt)
            slot_start = min(group_starts)
            slot_end = max(group_ends)
            time_slot = f"{slot_start.strftime('%-I:%M %p')} - {slot_end.strftime('%-I:%M %p')}"
            meetings_details = "<br>".join([
                f"{e.get('subject','(No Subject)').strip()} (Organizer: {e.get('organizer', {}).get('emailAddress', {}).get('name','Unknown')})"
                for e in group
            ])
            html += f"<tr><td>{time_slot}</td><td>{meetings_details}</td></tr>"
        html += "</table>"
    html += "</body></html>"
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
