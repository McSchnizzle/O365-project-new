import os
import requests
from datetime import datetime, timedelta, timezone
from auth import get_access_token  # This is our device flow alias from auth.py
from config import GRAPH_DELTA_ENDPOINT, DELTA_LINK_FILE, FUTURE_WINDOW_DAYS, SYNC_SCOPES, MAIL_SCOPES
from database import insert_or_update_event, get_all_events
from attendees_db import insert_or_update_attendee, get_all_attendees, get_stale_contacts
from utils import parse_datetime, format_datetime
from config import RECIPIENT_EMAIL

# For testing; in production, enable SSL verification.
VERIFY_SSL = False

def fetch_calendar_events():
    """
    Fetch events from Microsoft Graph using delta queries.
    If a delta link is saved, use it; otherwise, initiate a new delta query.
    """
    access_token = get_access_token(SYNC_SCOPES)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Check for an existing delta link.
    if os.path.exists(DELTA_LINK_FILE):
        with open(DELTA_LINK_FILE, "r") as f:
            url = f.read().strip()
        if not url:
            url = None
    else:
        url = None

    if not url:
        # Construct a new delta query URL with a time window.
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = (datetime.now(timezone.utc) + timedelta(days=FUTURE_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{GRAPH_DELTA_ENDPOINT}?startDateTime={start_date}&endDateTime={end_date}"

    response = requests.get(url, headers=headers, verify=VERIFY_SSL)
    if response.status_code == 200:
        data = response.json()
        events = data.get("value", [])
        new_delta_link = data.get("@odata.deltaLink")
        if new_delta_link:
            with open(DELTA_LINK_FILE, "w") as f:
                f.write(new_delta_link)
        return events
    else:
        print(f"Error fetching events: {response.status_code} {response.text}")
        return []

def process_events(events):
    """
    Process and store events in the calendar database,
    and update attendee records for each event.
    """
    for event in events:
        event_id = event.get("id")
        subject = event.get("subject", "No Subject")
        start_time = event.get("start", {}).get("dateTime")
        end_time = event.get("end", {}).get("dateTime")
        location = event.get("location", {}).get("displayName", "")
        attendees = event.get("attendees", [])
        is_recurring = 1 if event.get("recurrence") else 0
        attendees_emails = ",".join([att.get("emailAddress", {}).get("address", "") for att in attendees])
        
        event_data = {
            "event_id": event_id,
            "subject": subject,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "attendees": attendees_emails,
            "is_recurring": is_recurring
        }
        insert_or_update_event(event_data)
        
        for att in attendees:
            email = att.get("emailAddress", {}).get("address")
            name = att.get("emailAddress", {}).get("name", "")
            attendee_record = {
                "email": email,
                "name": name,
                "first_meeting": start_time,
                "last_meeting": start_time,
                "next_meeting": start_time,
                "last_meeting_subject": subject,
                "times_met": 1,
                "ok_to_ignore": 0
            }
            insert_or_update_attendee(attendee_record)

def build_html_email():
    """
    Build the HTML email containing:
      - A header with event and attendee counts.
      - A table for today's meetings.
      - A placeholder table for meeting conflicts.
      - A summary table for attendees.
      - A stale contacts list.
    """
    events = get_all_events()
    attendees = get_all_attendees()
    stale_contacts = get_stale_contacts()
    
    html = "<html><body>"
    html += f"<h2>Total Events: {len(events)} | Total Attendees: {len(attendees)}</h2>"
    
    # Today's Meetings Table.
    html += "<h3>Today's Meetings</h3>"
    html += "<table border='1'><tr><th>Time</th><th>Location</th><th>Subject</th><th>Status</th><th>Attendees</th></tr>"
    today_str = datetime.now().strftime("%Y-%m-%d")
    for ev in events:
        # Here we assume events are stored as tuples with index positions matching our insert order.
        if today_str in ev[2]:
            html += f"<tr><td>{ev[2]}</td><td>{ev[4]}</td><td>{ev[1]}</td><td>Scheduled</td><td>{ev[5]}</td></tr>"
    html += "</table>"
    
    # Meeting Conflicts Table (placeholder).
    html += "<h3>Meeting Conflicts</h3>"
    html += "<table border='1'><tr><th>Time Slot</th><th>Meetings</th><th>Organizer</th></tr>"
    html += "<tr><td>N/A</td><td>No conflicts detected</td><td>N/A</td></tr>"
    html += "</table>"
    
    # Attendee Summary Table.
    html += "<h3>Attendee Summary</h3>"
    html += "<table border='1'><tr><th>Email</th><th>Name</th><th>First Meeting</th><th>Last Meeting</th><th>Next Meeting</th><th>Last Meeting Subject</th><th>Times Met</th><th>OK to Ignore</th></tr>"
    for att in attendees:
        html += f"<tr><td>{att[0]}</td><td>{att[1]}</td><td>{att[2]}</td><td>{att[3]}</td><td>{att[4]}</td><td>{att[5]}</td><td>{att[6]}</td><td>{att[7]}</td></tr>"
    html += "</table>"
    
    # Stale Contacts List Table.
    html += "<h3>Stale Contacts List</h3>"
    html += "<table border='1'><tr><th>Email</th><th>Name</th><th>Last Meeting</th></tr>"
    for stale in stale_contacts:
        html += f"<tr><td>{stale[0]}</td><td>{stale[1]}</td><td>{stale[3]}</td></tr>"
    html += "</table>"
    
    html += "</body></html>"
    return html

def send_email_via_graph(html_content):
    """
    Send the HTML email via Microsoft Graph using device flow authentication for MAIL_SCOPES.
    """
    access_token = get_access_token(MAIL_SCOPES)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = "https://graph.microsoft.com/v1.0/me/sendMail"
    email_payload = {
        "message": {
            "subject": "Daily Calendar Summary",
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {"emailAddress": {"address": RECIPIENT_EMAIL}}
            ]
        },
        "saveToSentItems": "true"
    }
    response = requests.post(url, headers=headers, json=email_payload, verify=VERIFY_SSL)
    if response.status_code in (200, 202):
        print("Email sent successfully.")
    else:
        print(f"Failed to send email: {response.status_code} {response.text}")

if __name__ == "__main__":
    events = fetch_calendar_events()
    process_events(events)
    html = build_html_email()
    print(html)
    send_email_via_graph(html)
