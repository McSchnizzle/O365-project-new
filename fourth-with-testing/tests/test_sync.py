import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.sync import get_conflict_groups, build_html_email
from app.utils import get_event_start_dt
from app.attendees_db import init_attendee_db

# Dummy event for testing conflict groups and HTML email.
dummy_event = {
    "id": "test-event-1",
    "subject": "Test Meeting",
    "start": {
        "dateTime": "2025-03-19T15:00:00Z",
        "timeZone": "UTC"
    },
    "end": {
        "dateTime": "2025-03-19T16:00:00Z",
        "timeZone": "UTC"
    },
    "location": {
        "displayName": "Zoom Meeting"
    },
    "attendees": [
        {
            "emailAddress": {"name": "Alice", "address": "alice@example.com"},
            "status": {"response": "accepted"}
        },
        {
            "emailAddress": {"name": "Bob", "address": "bob@example.com"},
            "status": {"response": "accepted"}
        }
    ],
    "organizer": {
        "emailAddress": {"name": "Paul Brown", "address": "paul@teamcinder.com"}
    },
    "isAllDay": False
}

class TestSync(unittest.TestCase):
    def test_conflict_groups(self):
        # Create two events that overlap in time.
        event1 = dummy_event.copy()
        event1["id"] = "event1"
        event1["start"]["dateTime"] = "2025-03-19T15:00:00Z"
        event1["end"]["dateTime"] = "2025-03-19T16:00:00Z"
        event2 = dummy_event.copy()
        event2["id"] = "event2"
        event2["start"]["dateTime"] = "2025-03-19T15:30:00Z"
        event2["end"]["dateTime"] = "2025-03-19T16:30:00Z"
        events = [event1, event2]
        # Add _start_pacific property required by get_conflict_groups.
        for ev in events:
            dt = get_event_start_dt(ev)
            ev["_start_pacific"] = dt.astimezone(ZoneInfo("America/Los_Angeles"))
        groups = get_conflict_groups(events)
        self.assertTrue(len(groups) >= 1)
        self.assertTrue(all(len(group) > 1 for group in groups))

    def test_build_html_email(self):
        # Ensure the attendees table exists.
        init_attendee_db()
        events = [dummy_event]
        for ev in events:
            dt = get_event_start_dt(ev)
            ev["_start_pacific"] = dt.astimezone(ZoneInfo("America/Los_Angeles"))
        html = build_html_email(events)
        self.assertIn("Today's Meetings", html)
        self.assertIn("Zoom", html)
        self.assertIn("Test Meeting", html)

if __name__ == "__main__":
    unittest.main()
