import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.utils import convert_to_pacific, parse_iso_time, get_event_start_dt, should_ignore_event

# Dummy event for testing get_event_start_dt.
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

class TestUtils(unittest.TestCase):
    def test_parse_iso_time_utc(self):
        iso_str = "2025-03-19T15:00:00Z"
        dt = parse_iso_time(iso_str)
        self.assertIsNotNone(dt.tzinfo, "Returned datetime should be timezone-aware")
        # Check that tzinfo offset equals UTC offset.
        self.assertEqual(dt.tzinfo.utcoffset(dt), timezone.utc.utcoffset(dt))

    def test_convert_to_pacific(self):
        # March 19, 2025 15:00 UTC should be 8:00 AM in Pacific Daylight Time (UTC-7)
        iso_str = "2025-03-19T15:00:00Z"
        pacific_time = convert_to_pacific(iso_str)
        self.assertIn("8:00", pacific_time)

    def test_get_event_start_dt(self):
        dt = get_event_start_dt(dummy_event)
        self.assertIsInstance(dt, datetime)
        self.assertIsNotNone(dt.tzinfo, "Event start datetime must be timezone-aware")

    def test_should_ignore_event(self):
        # Test an event that should be ignored.
        ignore_event = {
            "subject": "Reservation Confirmed: Meeting",
            "organizer": {"emailAddress": {"address": "sjb@silvix.org"}}
        }
        self.assertTrue(should_ignore_event(ignore_event))
        # And an event that should not be ignored.
        valid_event = {
            "subject": "Regular Meeting",
            "organizer": {"emailAddress": {"address": "other@example.com"}}
        }
        self.assertFalse(should_ignore_event(valid_event))

if __name__ == "__main__":
    unittest.main()
