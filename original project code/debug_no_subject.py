import sqlite3
import json

DB_FILE = "calendar.db"  # Ensure this is the correct path.

def main():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM events")
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        raw = row[0]
        if not raw:
            continue  # Skip if raw JSON is empty.
        try:
            event = json.loads(raw)
        except Exception as e:
            print("Error parsing row:", raw, e)
            continue
        
        # Safely get the subject
        subject = event.get("subject")
        if subject is None:
            subject = ""
        
        if subject.strip() == "":
            print("Event with no subject:")
            print(json.dumps(event, indent=4))
            print("----------")

if __name__ == "__main__":
    main()
