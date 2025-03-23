# main.py
import sys
import os
from database import create_calendar_db
from attendees_db import create_attendees_db
from sync_email import fetch_calendar_events, process_events, build_html_email, send_email_via_graph
from auth import get_access_token

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

def authenticate():
    """
    Prompts for interactive authentication and then exits.
    Run with: python main.py authenticate
    """
    try:
        token = get_access_token(interactive=True)
        print("Authentication successful. Token cache updated (saved to token_cache.bin).")
    except Exception as e:
        print("Authentication failed:", e)
    # Stop execution after authentication.
    sys.exit(0)

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "initialize":
            initialize()
            return
        elif sys.argv[1] == "authenticate":
            authenticate()
            return

    # Normal flow: fetch events, process them, build HTML email, and send email.
    events = fetch_calendar_events()
    process_events(events)
    html_content = build_html_email()
    print("HTML email content built.")
    send_email_via_graph(html_content)
    print("Sync process complete.")

if __name__ == '__main__':
    main()
