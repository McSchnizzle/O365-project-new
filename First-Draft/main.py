import os
import sys
from config import SQLITE_DB_FILE, ATTENDEE_DB_FILE, DELTA_LINK_FILE
from sync_email import main as sync_main

def initialize():
    files_to_delete = [SQLITE_DB_FILE, ATTENDEE_DB_FILE, DELTA_LINK_FILE]
    for f in files_to_delete:
        if os.path.exists(f):
            os.remove(f)
            print(f"Deleted {f}")
        else:
            print(f"{f} not found.")
    print("Initialization complete. Databases and delta_link will be recreated on next sync.")

if __name__ == "__main__":
    # Check command-line parameters.
    if len(sys.argv) > 1 and sys.argv[1].lower() == "initialize":
        initialize()
    # Run the sync/email process.
    sync_main()
