import unittest
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import sqlite3
import json
import os
from importlib import reload
from app.config import Config
from app.schedule import get_events_for_date, get_open_happy_hours, build_schedule_html
from app.utils import get_event_start_dt

class TestSchedule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Save original database file paths.
        cls.original_events_db = Config.SQLITE_DB_FILE
        cls.original_attendees_db = Config.ATTENDEE_DB_FILE
        
        # Set temporary test database file paths.
        cls.temp_events_db = Config.SQLITE_DB_FILE + ".test"
        cls.temp_attendees_db = Config.ATTENDEE_DB_FILE + ".test"
        Config.SQLITE_DB_FILE = cls.temp_events_db
        Config.ATTENDEE_DB_FILE = cls.temp_attendees_db

        # Create events table.
        conn = sqlite3.connect(cls.temp_events_db)
        try:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS events")
            cursor.execute("""
                CREATE TABLE events (
                    id TEXT PRIMARY KEY,
                    subject TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    attendees TEXT,
                    raw_json TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

        # Create attendees table.
        conn = sqlite3.connect(cls.temp_attendees_db)
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

        # Force reinitialization of app.attendees_db so that it picks up the new Config values.
        import app.attendees_db as adb
        reload(adb)
        adb.init_attendee_db()

        # Use a fixed date for testing.
        fixed_date = date(2025, 3, 21)
        cls.fixed_date = fixed_date

        # Insert a test event into the events table using the fixed date.
        conn = sqlite3.connect(cls.temp_events_db)
        try:
            cursor = conn.cursor()
            event = {
                "id": "test-event-1",
                "subject": "Test Event 5PM",
                "start": {"dateTime": f"{fixed_date.isoformat()}T17:00:00-07:00", "timeZone": "Pacific Daylight Time"},
                "end": {"dateTime": f"{fixed_date.isoformat()}T18:00:00-07:00", "timeZone": "Pacific Daylight Time"},
                "location": {"displayName": "Test Location"},
                "attendees": [],
                "organizer": {"emailAddress": {"name": "Tester", "address": "tester@example.com"}}
            }
            raw_json = json.dumps(event)
            cursor.execute("""
                INSERT OR REPLACE INTO events (id, subject, start_time, end_time, location, attendees, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event["id"], event["subject"], event["start"]["dateTime"], event["end"]["dateTime"],
                  event["location"]["displayName"], json.dumps(event.get("attendees", [])), raw_json))
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(cls.temp_events_db)
        except Exception:
            pass
        try:
            os.remove(cls.temp_attendees_db)
        except Exception:
            pass
        Config.SQLITE_DB_FILE = cls.original_events_db
        Config.ATTENDEE_DB_FILE = cls.original_attendees_db

    def test_get_events_for_date(self):
        events = get_events_for_date(self.fixed_date)
        self.assertGreaterEqual(len(events), 1, "Expected at least one event for the fixed date")
        for event in events:
            start_dt = get_event_start_dt(event)
            local_date = start_dt.astimezone(ZoneInfo("America/Los_Angeles")).date()
            self.assertEqual(local_date, self.fixed_date)

    def test_get_open_happy_hours(self):
        open_dates = get_open_happy_hours()
        today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        if today.weekday() < 5:
            self.assertNotIn(today, open_dates)
        self.assertIsInstance(open_dates, list)

    def test_build_schedule_html(self):
        html = build_schedule_html(self.fixed_date)
        self.assertIsNotNone(html)
        self.assertIn("Calendar for", html)
        self.assertIn("Select Date", html)
        self.assertIn("Test Event 5PM", html)
        self.assertIn("Open Happy Hours", html)

    def test_free_day_message(self):
        # Delete all events to simulate a free day.
        conn = sqlite3.connect(Config.SQLITE_DB_FILE)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events")
            conn.commit()
        finally:
            conn.close()
        free_date = self.fixed_date + timedelta(days=1)
        html = build_schedule_html(free_date)
        day_name = free_date.strftime("%A")
        self.assertIn(f"Congratulations, you have a free {day_name}!", html)

if __name__ == "__main__":
    unittest.main()
