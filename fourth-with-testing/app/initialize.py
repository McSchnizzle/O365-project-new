#!/usr/bin/env python
"""
Initialize script to delete existing databases and related files.
This ensures that the next run will recreate the databases with the updated schema,
including the 'source' column in the attendees table.
"""

import os
from app.config import Config

def initialize():
    files_to_delete = [
        Config.SQLITE_DB_FILE,    # The events database
        Config.ATTENDEE_DB_FILE,  # The attendees database
        Config.DELTA_LINK_FILE    # (if applicable)
    ]
    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"Deleted {file}")
            except Exception as e:
                print(f"Could not delete {file}: {e}")
        else:
            print(f"{file} not found.")
    print("Initialization complete. Databases and delta_link will be recreated on next run.")

if __name__ == "__main__":
    initialize()
