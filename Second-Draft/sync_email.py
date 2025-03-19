# sync_email.py
import requests
from datetime import datetime
from config import GRAPH_API_ENDPOINT
from auth import get_access_token
from database import insert_or_update_event, get_all_events
from attendees_db import insert_or_update_attendee, get_all_attendees, get_stale_contacts
from utils import parse_datetime, format_datetime

# For development, you can disable SSL verification (not recommended for production)
VERIFY_SSL = False

def fetch_calendar_events():
    """
    Fetches events from Microsoft Graph API.
    Returns a list of event objects.
    """
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    url = f"{GRAPH_API_ENDPOINT}/me/events"
    response = requests.get(url, headers=headers, verify=VERIFY_SSL)
    if response.status_code == 200:
        events = response.json().get('value', [])
        return events
    else:
        print(f"Error fetching events: {response.status_code} {response.text}")
        return []

def process_events(events):
    """
    Processes and stores events in the calendar database,
    and updates the attendee database for each event.
    """
    for event in events:
        # Extract event details; adjust keys as needed based on Microsoft Graph response
        event_id = event.get('id')
        subject = event.get('subject', 'No Subject')
        start_time = event.get('start', {}).get('dateTime')
        end_time = event.get('end', {}).get('dateTime')
        location = event.get('location', {}).get('displayName', '')
        attendees = event.get('attendees', [])
        
        # Determine if this is a recurring event
        is_recurring = 1 if event.get('recurrence') else 0
        
        # Convert attendees to a comma-separated list of emails
        attendees_emails = ','.join([att.get('emailAddress', {}).get('address', '') for att in attendees])
        
        event_data = {
            'event_id': event_id,
            'subject': subject,
            'start_time': start_time,
            'end_time': end_time,
            'location': location,
            'attendees': attendees_emails,
            'is_recurring': is_recurring
        }
        insert_or_update_event(event_data)
        
        # Update each attendee's record
        for att in attendees:
            email = att.get('emailAddress', {}).get('address')
            name = att.get('emailAddress', {}).get('name', '')
            # For simplicity, we use the event's start time as a placeholder for all meeting dates.
            # In a full implementation, you'd compare dates to update first, last, and next meeting fields.
            attendee_record = {
                'email': email,
                'name': name,
                'first_meeting': start_time,
                'last_meeting': start_time,
                'next_meeting': start_time,
                'last_meeting_subject': subject,
                'times_met': 1,
                'ok_to_ignore': 0
            }
            insert_or_update_attendee(attendee_record)

def build_html_email():
    """
    Builds the HTML content for the email, including:
      - A header with total events and attendee count.
      - A table for today's meetings.
      - A placeholder table for meeting conflicts.
      - An attendee summary table.
      - A stale contacts list.
    """
    events = get_all_events()
    attendees = get_all_attendees()
    stale_contacts = get_stale_contacts()
    
    html = "<html><body>"
    
    # Header with debug info
    html += f"<h2>Total Events: {len(events)} | Total Attendees: {len(attendees)}</h2>"
    
    # Today's Meetings Table
    html += "<h3>Today's Meetings</h3>"
    html += "<table border='1'><tr><th>Time</th><th>Location</th><th>Subject</th><th>Status</th><th>Attendees</th></tr>"
    today_str = datetime.now().strftime("%Y-%m-%d")
    for ev in events:
        # Assuming event tuple indices: 0:event_id, 1:subject, 2:start_time, 3:end_time, 4:location, 5:attendees
        if today_str in ev[2]:
            html += f"<tr><td>{ev[2]}</td><td>{ev[4]}</td><td>{ev[1]}</td><td>Scheduled</td><td>{ev[5]}</td></tr>"
    html += "</table>"
    
    # Meeting Conflicts Table (placeholder for conflict detection logic)
    html += "<h3>Meeting Conflicts</h3>"
    html += "<table border='1'><tr><th>Time Slot</th><th>Meetings</th><th>Organizer</th></tr>"
    html += "<tr><td>N/A</td><td>No conflicts detected</td><td>N/A</td></tr>"
    html += "</table>"
    
    # Attendee Summary Table
    html += "<h3>Attendee Summary</h3>"
    html += "<table border='1'><tr><th>Email</th><th>Name</th><th>First Meeting</th><th>Last Meeting</th><th>Next Meeting</th><th>Last Meeting Subject</th><th>Times Met</th><th>OK to Ignore</th></tr>"
    for att in attendees:
        html += f"<tr><td>{att[0]}</td><td>{att[1]}</td><td>{att[2]}</td><td>{att[3]}</td><td>{att[4]}</td><td>{att[5]}</td><td>{att[6]}</td><td>{att[7]}</td></tr>"
    html += "</table>"
    
    # Stale Contacts List Table
    html += "<h3>Stale Contacts List</h3>"
    html += "<table border='1'><tr><th>Email</th><th>Name</th><th>Last Meeting</th></tr>"
    for stale in stale_contacts:
        html += f"<tr><td>{stale[0]}</td><td>{stale[1]}</td><td>{stale[3]}</td></tr>"
    html += "</table>"
    
    html += "</body></html>"
    return html

def send_email_via_graph(html_content):
    """
    Sends the generated HTML email via Microsoft Graph.
    Replace 'your_email@example.com' with the recipient email address.
    """
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    url = f"{GRAPH_API_ENDPOINT}/me/sendMail"
    email_payload = {
        "message": {
            "subject": "Daily Calendar Summary",
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "your_email@example.com"
                    }
                }
            ]
        },
        "saveToSentItems": "true"
    }
    response = requests.post(url, headers=headers, json=email_payload, verify=VERIFY_SSL)
    if response.status_code in (202, 200):
        print("Email sent successfully.")
    else:
        print(f"Failed to send email: {response.status_code} {response.text}")
