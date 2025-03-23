#!/usr/bin/env python
"""
Debug Contacts Module

This script connects to the attendees database and writes out all attendee records
to a file named 'debug_contacts_output.txt'. Use this file to verify that the attendee
summary and stale contacts data are being stored correctly.
"""

import sqlite3
from app.config import Config

def debug_contacts():
    db_file = Config.ATTENDEE_DB_FILE
    output_file = "debug_contacts_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Connecting to attendee database: {db_file}\n")
        try:
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM attendees")
                rows = cursor.fetchall()
                f.write(f"Total attendee records: {len(rows)}\n\n")
                f.write("Attendee Records:\n")
                for row in rows:
                    # Each row is a tuple: (email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore)
                    f.write(f"Email: {row[0]}, Name: {row[1]}, First: {row[2]}, Last: {row[3]}, Next: {row[4]}, Subject: {row[5]}, Times: {row[6]}, Ignore: {row[7]}\n")
        except Exception as e:
            f.write(f"Error accessing attendees database: {e}\n")
    print(f"Debug contacts output written to {output_file}")

if __name__ == "__main__":
    debug_contacts()
