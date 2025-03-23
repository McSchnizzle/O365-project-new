import unittest
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os
from importlib import reload
from app.attendees_db import update_attendees_with_event, get_attendee_summary, init_attendee_db
from app.config import Config

def iso_dt(dt: datetime) -> str:
    # Force replacement so that we use 'Z' for UTC.
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

class TestAttendeesDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db = Config.ATTENDEE_DB_FILE + ".test"
        cls.original_attendees_db = Config.ATTENDEE_DB_FILE
        Config.ATTENDEE_DB_FILE = cls.temp_db
        conn = sqlite3.connect(cls.temp_db)
        try:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS attendees")
            cursor.execute("""
                CREATE TABLE attendees (
                    email TEXT PRIMARY KEY,
                    name TEXT,
                    first_meeting TEXT,
                    last_meeting TEXT,
                    next_meeting TEXT,
                    last_meeting_subject TEXT,
                    times_met INTEGER DEFAULT 0,
                    ok_to_ignore TEXT DEFAULT 'no',
                    source TEXT DEFAULT 'paul@teamcinder.com'
                )
            """)
            conn.commit()
        finally:
            conn.close()
        from importlib import reload
        import app.attendees_db as adb
        reload(adb)
        adb.init_attendee_db()

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(cls.temp_db)
        except Exception:
            pass
        Config.ATTENDEE_DB_FILE = cls.original_attendees_db

    def setUp(self):
        with sqlite3.connect(Config.ATTENDEE_DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendees")
            conn.commit()

    def parse_iso(self, s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    
    def test_update_attendees_with_event(self):
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        event_past = {
            "id": "event-past",
            "subject": "Past Meeting",
            "start": {"dateTime": iso_dt(yesterday)},
            "end": {"dateTime": iso_dt(yesterday + timedelta(hours=1))},
            "attendees": [{"emailAddress": {"address": "alice@example.com", "name": "Alice"}}],
            "organizer": {"emailAddress": {"address": "paul@teamcinder.com", "name": "Paul Brown"}}
        }
        event_future = {
            "id": "event-future",
            "subject": "Future Meeting",
            "start": {"dateTime": iso_dt(tomorrow)},
            "end": {"dateTime": iso_dt(tomorrow + timedelta(hours=1))},
            "attendees": [{"emailAddress": {"address": "alice@example.com", "name": "Alice"}}],
            "organizer": {"emailAddress": {"address": "paul@teamcinder.com", "name": "Paul Brown"}}
        }
        update_attendees_with_event(event_past)
        update_attendees_with_event(event_future)

        summary = get_attendee_summary()
        alice = next((r for r in summary if r[0] == "alice@example.com"), None)
        self.assertIsNotNone(alice)
        email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore, source = alice
        
        # Compare datetimes parsed from the strings.
        self.assertEqual(self.parse_iso(first_meeting), yesterday)
        self.assertEqual(self.parse_iso(last_meeting), yesterday)
        self.assertEqual(self.parse_iso(next_meeting), tomorrow)
        self.assertEqual(last_meeting_subject, "Past Meeting")
        self.assertEqual(times_met, 1)
        self.assertEqual(ok_to_ignore, "no")
        self.assertEqual(source, "paul@teamcinder.com")

    def test_multiple_updates(self):
        now = datetime.now(timezone.utc)
        event1 = {
            "id": "event1",
            "subject": "Morning Meeting",
            "start": {"dateTime": iso_dt(now - timedelta(days=3))},
            "end": {"dateTime": iso_dt(now - timedelta(days=3) + timedelta(hours=1))},
            "attendees": [{"emailAddress": {"address": "bob@example.com", "name": "Bob"}}],
            "organizer": {"emailAddress": {"address": "paul@teamcinder.com", "name": "Paul Brown"}}
        }
        event2 = {
            "id": "event2",
            "subject": "Afternoon Meeting",
            "start": {"dateTime": iso_dt(now - timedelta(days=1))},
            "end": {"dateTime": iso_dt(now - timedelta(days=1) + timedelta(hours=1))},
            "attendees": [{"emailAddress": {"address": "bob@example.com", "name": "Bob"}}],
            "organizer": {"emailAddress": {"address": "paul@teamcinder.com", "name": "Paul Brown"}}
        }
        event3 = {
            "id": "event3",
            "subject": "Upcoming Meeting",
            "start": {"dateTime": iso_dt(now + timedelta(days=2))},
            "end": {"dateTime": iso_dt(now + timedelta(days=2) + timedelta(hours=1))},
            "attendees": [{"emailAddress": {"address": "bob@example.com", "name": "Bob"}}],
            "organizer": {"emailAddress": {"address": "paul@teamcinder.com", "name": "Paul Brown"}}
        }
        update_attendees_with_event(event1)
        update_attendees_with_event(event2)
        update_attendees_with_event(event3)

        summary = get_attendee_summary()
        bob = next((r for r in summary if r[0] == "bob@example.com"), None)
        self.assertIsNotNone(bob)
        email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore, source = bob
        
        self.assertEqual(self.parse_iso(first_meeting), now - timedelta(days=3))
        self.assertEqual(self.parse_iso(last_meeting), now - timedelta(days=1))
        self.assertEqual(self.parse_iso(next_meeting), now + timedelta(days=2))
        self.assertEqual(last_meeting_subject, "Afternoon Meeting")
        self.assertEqual(times_met, 2)
        self.assertEqual(ok_to_ignore, "no")
        self.assertEqual(source, "paul@teamcinder.com")

if __name__ == "__main__":
    unittest.main()
