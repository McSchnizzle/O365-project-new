# tests/test_main.py
import sys
import os
import unittest
from unittest.mock import patch
from main import main

class TestMainCLI(unittest.TestCase):
    def test_authenticate_option(self):
        test_args = ["main.py", "authenticate"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)

    def test_initialize_option(self):
        # Create dummy database files.
        with open("calendar.db", "w") as f:
            f.write("dummy")
        with open("attendees.db", "w") as f:
            f.write("dummy")
        test_args = ["main.py", "initialize"]
        with patch.object(sys, 'argv', test_args):
            main()
        # Check that new database files exist.
        self.assertTrue(os.path.exists("calendar.db"))
        self.assertTrue(os.path.exists("attendees.db"))
        # Clean up.
        os.remove("calendar.db")
        os.remove("attendees.db")

    def test_normal_flow(self):
        test_args = ["main.py"]
        with patch.object(sys, 'argv', test_args):
            with patch("main.get_access_token", return_value="dummy_token"), \
                 patch("main.fetch_calendar_events", return_value=[]), \
                 patch("main.process_events") as mock_process, \
                 patch("main.build_html_email", return_value="dummy_html"), \
                 patch("main.send_email_via_graph") as mock_send:
                main()
                mock_process.assert_called_once()
                mock_send.assert_called_once_with("dummy_html")

if __name__ == '__main__':
    unittest.main()
