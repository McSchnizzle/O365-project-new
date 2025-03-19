# config.py
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database file paths
CALENDAR_DB_PATH = os.path.join(BASE_DIR, 'calendar.db')
ATTENDEES_DB_PATH = os.path.join(BASE_DIR, 'attendees.db')

# Time zone configuration
PACIFIC_TIMEZONE = 'America/Los_Angeles'

# Microsoft Graph API configuration (fill these in with your credentials)
GRAPH_CLIENT_ID = 'db1311b5-c7de-4db6-a4ba-07bb8103fb77'
GRAPH_CLIENT_SECRET = 'your_client_secret_here'
GRAPH_TENANT_ID = 'your_tenant_id_here'
GRAPH_AUTHORITY = f'https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf'
GRAPH_SCOPE = ['https://graph.microsoft.com/.default']

# Graph API endpoints
GRAPH_API_ENDPOINT = 'https://graph.microsoft.com/v1.0'
