import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta

import msal

# --- Configuration ---
CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"
# Use both scopes if needed; here, we need Mail.Send to send emails
MAIL_SCOPE = ["Mail.Send"]

# File for persisting the token cache (used for both authentication flows)
TOKEN_CACHE_FILE = "token_cache.bin"

SQLITE_DB_FILE = "calendar.db"

# Email details (sending to/from your own O365 account)
EMAIL_FROM = "paul@teamcinder.com"  # Replace with your email address
EMAIL_TO = "paul@teamcinder.com"    # Replace with your email address
EMAIL_SUBJECT = "Daily Calendar Summary"

GRAPH_SENDMAIL_ENDPOINT = "https://graph.microsoft.com/v1.0/me/sendMail"


# --- Helper: Get Access Token for Given Scopes ---
def get_token(scopes):
    """Obtain an access token for the specified scopes using a persistent token cache."""
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


# --- Database Functions ---
def get_events():
    """Retrieve all events from the database (as full JSON objects)."""
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM events")
    rows = cursor.fetchall()
    conn.close()
    events = []
    for row in rows:
        event = json.loads(row[0])
        events.append(event)
    return events


# --- HTML Building Functions ---
def build_html_table(events):
    """Build an HTML table for the list of events."""
    html = "<h2>Today's Meetings</h2>"
    html += "<table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Time</th><th>Location</th><th>Subject</th><th>Attendees</th></tr>"
    for event in events:
        # Extract event details
        start = event.get("start", {}).get("dateTime", "TBD")
        end = event.get("end", {}).get("dateTime", "TBD")
        subject = event.get("subject", "TBD")
        location = event.get("location", {}).get("displayName", "TBD")
        # Simplify location if it's a meeting URL for common services.
        location_lower = location.lower()
        if any(service in location_lower for service in ["zoom", "teams", "google meet", "webex"]):
            if "zoom" in location_lower:
                location = "Zoom"
            elif "teams" in location_lower:
                location = "Teams"
            elif "google meet" in location_lower:
                location = "Google Meet"
            elif "webex" in location_lower:
                location = "Webex"
        # Attendees: extract names from emailAddress objects
        attendees_list = event.get("attendees", [])
        attendees_names = ", ".join(
            [att.get("emailAddress", {}).get("name", "Unknown") for att in attendees_list]
        )
        # Highlight the row if any key detail is "TBD"
        highlight = ""
        if "tbd" in subject.lower() or "tbd" in location.lower() or start == "TBD" or end == "TBD":
            highlight = " style='background-color: yellow;'"
        # Convert times to Pacific Time and format them (assuming input is ISO 8601 in UTC)
        formatted_start = format_to_pacific(start) if start != "TBD" else "TBD"
        formatted_end = format_to_pacific(end) if end != "TBD" else "TBD"
        time_range = f"{formatted_start} - {formatted_end}" if formatted_start != "TBD" and formatted_end != "TBD" else "TBD"
        html += f"<tr{highlight}><td>{time_range}</td><td>{location}</td><td>{subject}</td><td>{attendees_names}</td></tr>"
    html += "</table>"
    return html


def build_conflict_section(events):
    """Detect overlapping meetings and build an HTML section listing the conflicts."""
    conflicts = []
    n = len(events)
    for i in range(n):
        event_i = events[i]
        start_i_str = event_i.get("start", {}).get("dateTime")
        end_i_str = event_i.get("end", {}).get("dateTime")
        if not start_i_str or not end_i_str:
            continue
        try:
            start_i = datetime.fromisoformat(start_i_str)
            end_i = datetime.fromisoformat(end_i_str)
        except Exception:
            continue
        for j in range(i + 1, n):
            event_j = events[j]
            start_j_str = event_j.get("start", {}).get("dateTime")
            end_j_str = event_j.get("end", {}).get("dateTime")
            if not start_j_str or not end_j_str:
                continue
            try:
                start_j = datetime.fromisoformat(start_j_str)
                end_j = datetime.fromisoformat(end_j_str)
            except Exception:
                continue
            # Check for overlap
            if start_i < end_j and start_j < end_i:
                conflicts.append((event_i, event_j))
    if not conflicts:
        return "<p>No meeting conflicts detected.</p>"
    html = "<h2>Meeting Conflicts</h2>"
    for (event1, event2) in conflicts:
        html += "<p>"
        html += f"Conflict between <strong>{event1.get('subject', 'TBD')}</strong> and <strong>{event2.get('subject', 'TBD')}</strong>."
        html += "</p>"
    return html


def build_priority_section(events):
    """Build a section for priority events such as 0-minute meetings or birthday notifications."""
    priority_events = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")
        subject = event.get("subject", "").lower()
        if start_str and end_str:
            try:
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                if start_dt == end_dt:  # 0-minute meeting
                    priority_events.append(event)
            except Exception:
                pass
        if "birthday" in subject:
            priority_events.append(event)
    if not priority_events:
        return ""
    html = "<h2>Priority Events</h2>"
    html += "<table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Time</th><th>Subject</th></tr>"
    for event in priority_events:
        start = event.get("start", {}).get("dateTime", "TBD")
        subject = event.get("subject", "TBD")
        formatted_start = format_to_pacific(start) if start != "TBD" else "TBD"
        html += f"<tr><td>{formatted_start}</td><td>{subject}</td></tr>"
    html += "</table>"
    return html


def format_to_pacific(iso_datetime_str):
    """Convert an ISO datetime string (assumed in UTC) to Pacific Time and return a formatted string."""
    try:
        from_zone = datetime.strptime(iso_datetime_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        try:
            from_zone = datetime.strptime(iso_datetime_str, "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return iso_datetime_str
    # UTC time
    utc_time = from_zone
    # Offset for Pacific Time (adjust for PDT/PST as needed; here we'll assume PDT, UTC-7)
    pacific_offset = timedelta(hours=-7)
    pacific_time = utc_time + pacific_offset
    return pacific_time.strftime("%I:%M %p")


# --- Graph API Email Sending ---
def send_email_graph(html_content):
    """Send an email using the Microsoft Graph API sendMail endpoint."""
    token = get_token(MAIL_SCOPE)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    message = {
        "message": {
            "subject": EMAIL_SUBJECT,
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": EMAIL_TO
                    }
                }
            ]
        },
        "saveToSentItems": "true"
    }
    response = requests.post(GRAPH_SENDMAIL_ENDPOINT, headers=headers, json=message)
    if response.status_code in (202, 200):
        print("Email sent successfully via Graph API.")
    else:
        print("Failed to send email. Status:", response.status_code, response.text)


# --- Main Routine ---
def main():
    now = datetime.now()
    is_friday = now.weekday() == 4  # Monday=0, Friday=4
    events = get_events()

    # Filter events: on a normal day, only today's events.
    # On Friday, include events from now until Monday 8am.
    filtered_events = []
    for event in events:
        start_str = event.get("start", {}).get("dateTime")
        if not start_str:
            continue
        try:
            start_dt = datetime.fromisoformat(start_str)
        except Exception:
            continue
        if is_friday:
            days_until_monday = (7 - now.weekday()) % 7 or 7
            next_monday = now + timedelta(days=days_until_monday)
            monday_8am = datetime(next_monday.year, next_monday.month, next_monday.day, 8, 0, 0)
            if now <= start_dt <= monday_8am:
                filtered_events.append(event)
        else:
            if start_dt.date() == now.date():
                filtered_events.append(event)

    # Build the email content sections
    html_body = "<html><body>"
    html_body += build_priority_section(filtered_events)
    html_body += build_html_table(filtered_events)
    html_body += build_conflict_section(filtered_events)
    html_body += "</body></html>"

    # Send the email using Graph API
    send_email_graph(html_body)

if __name__ == "__main__":
    main()
