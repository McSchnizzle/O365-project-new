#!/usr/bin/env python
"""
Debug Events Module

This script connects to the events database and writes key details to a file named
'debug_events_output.txt'. It will check for all-day events (or events with a 'date' key
in the 'start' object) and events with unusual date/time formats. Use this file to help
debug why certain events (e.g. all-day events) may not be appearing as expected.
"""

import sqlite3
import json
from app.config import Config

def debug_events():
    db_file = Config.SQLITE_DB_FILE
    output_file = "debug_events_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Connecting to events database: {db_file}\n")
        try:
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT raw_json FROM events")
                rows = cursor.fetchall()
                f.write(f"Total event records: {len(rows)}\n\n")
                f.write("Event Details:\n")
                for row in rows:
                    try:
                        event = json.loads(row[0])
                    except Exception as e:
                        f.write(f"Error parsing event JSON: {e}\n")
                        continue
                    start_info = event.get("start", {})
                    if "date" in start_info:
                        # All-day or date-only event.
                        f.write("All-day or date-only event found:\n")
                        f.write(f"  ID: {event.get('id')}\n")
                        f.write(f"  Subject: {event.get('subject')}\n")
                        f.write(f"  Start (date): {start_info.get('date')}\n")
                        f.write(f"  End (if available): {event.get('end', {}).get('date')}\n\n")
                    else:
                        dt = start_info.get("dateTime", "N/A")
                        f.write(f"Event ID: {event.get('id')}, Subject: {event.get('subject')}, Start (dateTime): {dt}\n")
        except Exception as e:
            f.write(f"Error accessing events database: {e}\n")
    print(f"Debug events output written to {output_file}")

if __name__ == "__main__":
    debug_events()
