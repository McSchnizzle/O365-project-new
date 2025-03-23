# tests/test_sync_email.py
import os
import unittest
from sync_email import build_html_email
from database import create_calendar_db, insert_or_update_event
from attendees_db import create_attendees_db, insert_or_update_attendee

class TestSyncEmail(unittest.TestCase):
    def setUp(self):
        # Remove the database files if they exist.
        for db_file in ["calendar.db", "attendees.db"]:
            try:
                os.remove(db_file)
            except Exception:
                pass
        create_calendar_db()
        create_attendees_db()
        
        # Insert a sample event.
        event = {
            'event_id': '1',
            'subject': 'Test Meeting',
            'start_time': '2022-01-01T12:00:00Z',
            'end_time': '2022-01-01T13:00:00Z',
            'location': 'Test Room',
            'attendees': 'test@example.com',
            'is_recurring': 0
        }
        insert_or_update_event(event)
        
        # Insert a sample attendee record.
        attendee = {
            'email': 'test@example.com',
            'name': 'Test User',
            'first_meeting': '2022-01-01T12:00:00Z',
            'last_meeting': '2022-01-01T12:00:00Z',
            'next_meeting': '2022-01-01T12:00:00Z',
            'last_meeting_subject': 'Test Meeting',
            'times_met': 1,
            'ok_to_ignore': 0
        }
        insert_or_update_attendee(attendee)
        
    def test_build_html_email(self):
        html = build_html_email()
        self.assertIn("Total Events:", html)
        self.assertIn("Today's Meetings", html)
        self.assertIn("Attendee Summary", html)
        self.assertIn("Stale Contacts List", html)

if __name__ == '__main__':
    unittest.main()
