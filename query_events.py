import sqlite3
import json

SQLITE_DB_FILE = "calendar.db"

conn = sqlite3.connect(SQLITE_DB_FILE)
cursor = conn.cursor()

cursor.execute("SELECT id, subject, start_time, end_time, location, attendees FROM events")
rows = cursor.fetchall()

# Print a header row
print(f"{'ID':<36} | {'Subject':<30} | {'Start Time':<20} | {'End Time':<20} | {'Location':<20}")
print("-" * 130)

# Loop through each row and print event details
for row in rows:
    event_id, subject, start_time, end_time, location, attendees = row
    print(f"{event_id:<36} | {subject[:30]:<30} | {start_time:<20} | {end_time:<20} | {location[:20]:<20}")
    
conn.close()
