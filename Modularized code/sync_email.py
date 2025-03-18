import os, json, sqlite3, requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from config import TOKEN_CACHE_FILE, DELTA_LINK_FILE, GRAPH_DELTA_ENDPOINT, FUTURE_WINDOW_DAYS, SYNC_SCOPES, MAIL_SCOPES, SQLITE_DB_FILE
from auth import get_token
from database import init_db, upsert_event
from utils import parse_iso_time, convert_to_pacific, get_event_start_dt, should_ignore_event

# Global cache for series master subjects.
series_master_cache = {}

# -------------------- Series Master Queries --------------------
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

def get_series_master_attendees(series_master_id):
    """
    Query the Graph API for the master event's attendees.
    """
    token = get_token(SYNC_SCOPES)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/me/events/{series_master_id}?$select=attendees"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("attendees", [])
    else:
        print("Failed to fetch series master attendees", series_master_id, response.status_code, response.text)
        return []

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
            # Update attendee database as needed (if using a parallel attendees database, call that function here)
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
        elif now_pacific.weekday() == 4:
            next_monday = today_midnight + timedelta(days=(7 - today_midnight.weekday()))
            monday_8am = next_monday.replace(hour=8)
            if tomorrow_midnight <= start_pacific < monday_8am:
                event["_start_pacific"] = start_pacific
                filtered.append(event)
    filtered.sort(key=lambda e: e["_start_pacific"])
    return filtered

def get_conflict_groups(events):
    groups = []
    current_group = []
    current_end = None
    for event in events:
        # Exclude all-day events from conflict detection.
        if event.get("isAllDay", False):
            continue
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

def build_html_email(events):
    # First, compute overall attendee frequency for today's events.
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
        # Get start and end times.
        start = event.get("start", {}).get("dateTime", "TBD")
        end = event.get("end", {}).get("dateTime", "TBD")
        
        # Determine subject.
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
        
        # Process location.
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
        
        # Format time range.
        formatted_start = convert_to_pacific(start) if start != "TBD" else "TBD"
        formatted_end = convert_to_pacific(end) if end != "TBD" else "TBD"
        time_range = f"{formatted_start} - {formatted_end}" if formatted_start != "TBD" and formatted_end != "TBD" else "TBD"
        
        # Determine status.
        response_status = event.get("responseStatus", {}).get("response", "").strip()
        # Check if Paul's individual attendee record exists.
        for att in event.get("attendees", []):
            if att.get("emailAddress", {}).get("address", "").lower() == "paul@teamcinder.com":
                # If there is a status field for Paul's attendee record, use it.
                paul_status = att.get("status", {}).get("response", "").strip()
                if paul_status:
                    response_status = paul_status
                break
        # Map the status.
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
        
        # Process attendees: remove Paul from the list.
        attendees_list = event.get("attendees", [])
        # If the attendee list is empty and it's a recurring event, try the series master attendees.
        if not attendees_list and event.get("seriesMasterId"):
            attendees_list = get_series_master_attendees(event.get("seriesMasterId"))
        
        att_tuples = []
        for att in attendees_list:
            email = att.get("emailAddress", {}).get("address", "").lower()
            # Skip Paul.
            if email == "paul@teamcinder.com":
                continue
            name = att.get("emailAddress", {}).get("name", "").strip()
            if email:
                count = freq_dict.get(email, 0)
                att_tuples.append((count, name, email))
        if len(att_tuples) > 4:
            # Sort by frequency descending, then name ascending.
            att_tuples.sort(key=lambda t: (-t[0], t[1].lower()))
            top_attendees = [t[1] for t in att_tuples[:4]]
            attendees_names = ", ".join(top_attendees) + ", and others"
        else:
            names = sorted([t[1] for t in att_tuples], key=lambda n: n.lower())
            attendees_names = ", ".join(names)
        
        html += f"<tr><td>{time_range}</td><td>{location}</td><td>{subject}</td>" \
                f"<td>{status_label}</td><td>{attendees_names}</td></tr>"
    html += "</table>"
    
    # Build the conflict table.
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
            meetings_details_list = []
            for e in group:
                subj = e.get("subject", "").strip()
                if not subj and e.get("seriesMasterId"):
                    subj = get_series_master_subject(e.get("seriesMasterId"))
                if not subj:
                    subj = "(No Subject)"
                organizer = e.get("organizer", {}).get("emailAddress", {}).get("name", "Unknown")
                meetings_details_list.append(f"{subj} (Organizer: {organizer})")
            meetings_details = "<br>".join(meetings_details_list)
            html += f"<tr><td>{time_slot}</td><td>{meetings_details}</td></tr>"
        html += "</table>"
    
    # Build the attendee summary table.
    from attendees import get_attendee_summary
    attendee_summary = get_attendee_summary()
    if attendee_summary:
        html += "<h2>Attendee Summary</h2>"
        html += "<table border='1' cellspacing='0' cellpadding='5'>"
        html += "<tr><th>Name</th><th>Email</th><th>Last Meeting</th><th>Next Meeting</th><th>Last Meeting Subject</th></tr>"
        for row in attendee_summary:
            email, name, last_meeting, next_meeting, last_meeting_subject = row
            try:
                last_meeting_fmt = datetime.fromisoformat(last_meeting).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%-m/%-d/%Y %-I:%M %p") if last_meeting else ""
            except Exception:
                last_meeting_fmt = last_meeting if last_meeting else ""
            try:
                next_meeting_fmt = datetime.fromisoformat(next_meeting).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%-m/%-d/%Y %-I:%M %p") if next_meeting else ""
            except Exception:
                next_meeting_fmt = next_meeting if next_meeting else ""
            html += f"<tr><td>{name}</td><td>{email}</td><td>{last_meeting_fmt}</td><td>{next_meeting_fmt}</td><td>{last_meeting_subject}</td></tr>"
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

def main():
    print("Starting daily sync and email process...")
    sync_calendar()
    today_events = get_today_events()
    print(f"Found {len(today_events)} event(s) for today.")
    html_content = build_html_email(today_events)
    send_email_via_graph(html_content)

if __name__ == "__main__":
    main()
