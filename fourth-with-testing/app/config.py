import os

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    os.chdir(BASE_DIR)

    SYNC_SCOPES = ["Calendars.Read"]
    MAIL_SCOPES = ["Mail.Send"]

    CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
    AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"

    TOKEN_CACHE_FILE = os.path.join(BASE_DIR, "token_cache.bin")
    DELTA_LINK_FILE = os.path.join(BASE_DIR, "delta_link.txt")

    SQLITE_DB_FILE = os.path.join(BASE_DIR, "calendar.db")
    ATTENDEE_DB_FILE = os.path.join(BASE_DIR, "attendees.db")

    GRAPH_DELTA_ENDPOINT = "https://graph.microsoft.com/v1.0/me/calendarView/delta"
    FUTURE_WINDOW_DAYS = 30

    DEFAULT_SOURCE = "paul@teamcinder.com"
