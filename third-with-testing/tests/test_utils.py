# tests/test_utils.py
import unittest
from datetime import datetime
import pytz
from utils import parse_datetime, to_pacific, format_datetime, is_all_day

class TestUtils(unittest.TestCase):
    def test_parse_datetime(self):
        dt_str = "2022-01-01T12:00:00Z"
        dt = parse_datetime(dt_str)
        self.assertIsNotNone(dt)
        self.assertTrue(isinstance(dt, datetime))

    def test_to_pacific(self):
        # Use a UTC datetime.
        dt = datetime(2022, 1, 1, 12, 0, 0, tzinfo=pytz.utc)
        dt_pacific = to_pacific(dt)
        # Check that the UTC offset is -8 hours (i.e. -8*3600 seconds) for PST.
        self.assertEqual(dt_pacific.utcoffset().total_seconds(), -8 * 3600)

    def test_format_datetime(self):
        dt = datetime(2022, 1, 1, 12, 0, 0, tzinfo=pytz.utc)
        formatted = format_datetime(dt)
        self.assertTrue(isinstance(formatted, str))
        self.assertIn("2022", formatted)

    def test_is_all_day(self):
        self.assertTrue(is_all_day("2022-01-01"))
        self.assertFalse(is_all_day("2022-01-01T12:00:00"))

if __name__ == '__main__':
    unittest.main()
