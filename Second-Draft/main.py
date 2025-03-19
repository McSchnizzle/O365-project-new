# main.py
import sys
import os
from database import create_calendar_db
from attendees_db import create_attendees_db
from sync_email import fetch_calendar_events, process_events, build_html_email, send_email_via_graph

def initialize():
    """
    Deletes existing databases (if any) and reinitializes them.
    Run with: python main.py initialize
    """
    for db_file in ['calendar.db', 'attendees.db']:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"Deleted {db_file}")
    create_calendar_db()
    create_attendees_db()
    print("Databases initialized.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "initialize":
        initialize()
    else:
        # Fetch events from Microsoft Graph and process them
        events = fetch_calendar_events()
        process_events(events)
        # Build the HTML email content
        html_content = build_html_email()
        print("HTML email content built.")
        # Send the email via Microsoft Graph (adjust recipient email in sync_email.py)
        send_email_via_graph(html_content)
        print("Sync process complete.")

if __name__ == '__main__':
    main()
