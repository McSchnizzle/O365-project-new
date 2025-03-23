import os
import unittest
import tempfile
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Import functions from your project modules.
# Adjust these imports as needed for your file structure.
from utils import convert_to_pacific, parse_iso_time, get_event_start_dt, should_ignore_event
from sync_email import get_conflict_groups, build_html_email
from attendees_db import init_attendee_db, update_attendees_with_event, get_attendee_summary, get_series_master_attendees
from database import init_db, upsert_event

# Dummy event used for testing.
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


class TestProjectFunctions(unittest.TestCase):

    def test_parse_iso_time_utc(self):
        iso_str = "2025-03-19T15:00:00Z"
        dt = parse_iso_time(iso_str)
        self.assertIsNotNone(dt.tzinfo, "Returned datetime should be timezone-aware")
        # Check that tzinfo offset equals UTC offset.
        self.assertEqual(dt.tzinfo.utcoffset(dt), timezone.utc.utcoffset(dt))

    def test_convert_to_pacific(self):
        # For a known UTC time, convert_to_pacific should produce the correct Pacific time.
        # March 19, 2025 is in PDT (UTC-7), so 15:00 UTC should be 8:00 AM PDT.
        iso_str = "2025-03-19T15:00:00Z"
        pacific_time = convert_to_pacific(iso_str)
        # Check that the result contains "8:00" (format may vary slightly between OS)
        self.assertIn("8:00", pacific_time)

    def test_get_event_start_dt(self):
        dt = get_event_start_dt(dummy_event)
        self.assertIsInstance(dt, datetime)
        self.assertIsNotNone(dt.tzinfo, "Event start datetime must be timezone-aware")

    def test_should_ignore_event(self):
        # Create an event that should be ignored.
        ignore_event = {
            "subject": "Reservation Confirmed: Meeting",
            "organizer": {"emailAddress": {"address": "sjb@silvix.org"}}
        }
        self.assertTrue(should_ignore_event(ignore_event))
        # And one that should not be ignored.
        valid_event = {
            "subject": "Regular Meeting",
            "organizer": {"emailAddress": {"address": "other@example.com"}}
        }
        self.assertFalse(should_ignore_event(valid_event))

    def test_conflict_groups(self):
        # Create two events that overlap.
        event1 = dummy_event.copy()
        event1["id"] = "event1"
        event1["start"]["dateTime"] = "2025-03-19T15:00:00Z"
        event1["end"]["dateTime"] = "2025-03-19T16:00:00Z"
        event2 = dummy_event.copy()
        event2["id"] = "event2"
        event2["start"]["dateTime"] = "2025-03-19T15:30:00Z"
        event2["end"]["dateTime"] = "2025-03-19T16:30:00Z"
        events = [event1, event2]
        # Add _start_pacific for each event.
        for ev in events:
            dt = get_event_start_dt(ev)
            ev["_start_pacific"] = dt.astimezone(ZoneInfo("America/Los_Angeles"))
        groups = get_conflict_groups(events)
        self.assertTrue(len(groups) >= 1)
        self.assertTrue(all(len(group) > 1 for group in groups))

    def test_build_html_email(self):
        # Test that build_html_email produces HTML that includes expected content.
        events = [dummy_event]
        for ev in events:
            dt = get_event_start_dt(ev)
            ev["_start_pacific"] = dt.astimezone(ZoneInfo("America/Los_Angeles"))
        html = build_html_email(events)
        self.assertIn("Today's Meetings", html)
        self.assertIn("Zoom", html)
        self.assertIn("Test Meeting", html)

    def test_update_attendees(self):
        # Create a temporary attendees database file.
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(delete=False)
        temp_db.close()
        # Override the ATTENDEE_DB_FILE in config for testing.
        import config
        original_db = config.ATTENDEE_DB_FILE
        config.ATTENDEE_DB_FILE = temp_db.name
        try:
            init_attendee_db()
            update_attendees_with_event(dummy_event)
            summary = get_attendee_summary()
            self.assertTrue(len(summary) > 0, "Attendee summary should have at least one record after update.")
        finally:
            config.ATTENDEE_DB_FILE = original_db
            os.unlink(temp_db.name)

if __name__ == "__main__":
    unittest.main()
