# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
CALENDAR_DB_PATH = os.path.join(BASE_DIR, 'calendar.db')
ATTENDEES_DB_PATH = os.path.join(BASE_DIR, 'attendees.db')

PACIFIC_TIMEZONE = 'America/Los_Angeles'

# Add your recipient email address here.
RECIPIENT_EMAIL = "paul@teamcinder.com"


GRAPH_CLIENT_ID = 'db1311b5-c7de-4db6-a4ba-07bb8103fb77'
GRAPH_CLIENT_SECRET = '_5x8Q~TstpFm6FHoTkhX7q5moeQ0ZsiNg4m0Xc6~'
GRAPH_TENANT_ID = 'f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf'
GRAPH_AUTHORITY = f'https://login.microsoftonline.com/{GRAPH_TENANT_ID}'
# Using a specific set of scopes
GRAPH_SCOPE = ["Calendars.Read", "Mail.Send"]
SYNC_SCOPES = ["Calendars.Read"]
MAIL_SCOPES = ["Mail.Send"]

import os

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

# Delta sync constants
TOKEN_CACHE_FILE = os.path.join(BASE_DIR, "token_cache.bin")
DELTA_LINK_FILE = os.path.join(BASE_DIR, "delta_link.txt")
GRAPH_DELTA_ENDPOINT = "https://graph.microsoft.com/v1.0/me/calendarView/delta"
FUTURE_WINDOW_DAYS = 30

# Specify a fixed redirect URI (this must be registered in Azure)
REDIRECT_URI = "https://login.microsoftonline.com/common/oauth2/nativeclient"
# In config.py (add this near the other Graph-related constants)
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

#================


AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"

#TOKEN_CACHE_FILE = os.path.join(BASE_DIR, "token_cache.bin")
#DELTA_LINK_FILE = os.path.join(BASE_DIR, "delta_link.txt")
SQLITE_DB_FILE = os.path.join(BASE_DIR, "calendar.db")
ATTENDEE_DB_FILE = os.path.join(BASE_DIR, "attendees.db")
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

