# tests/test_database.py
import os
import unittest
from database import create_calendar_db, insert_or_update_event, get_all_events
from config import CALENDAR_DB_PATH

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Ensure a fresh calendar database for each test.
        if os.path.exists(CALENDAR_DB_PATH):
            os.remove(CALENDAR_DB_PATH)
        create_calendar_db()

    def test_insert_and_get_event(self):
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
        events = get_all_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], '1')  # Check that event_id matches

if __name__ == '__main__':
    unittest.main()
