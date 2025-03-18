import msal
import json
import requests

# Your registered application's details
CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"
SCOPE = ["Calendars.Read"]

# Create a PublicClientApplication instance
app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

# Initiate the device code flow for authentication
flow = app.initiate_device_flow(scopes=SCOPE)
if "user_code" not in flow:
    raise Exception("Failed to create device flow. Error details: " + json.dumps(flow, indent=4))

# Print the instructions to complete the device code flow
print(flow["message"])

# Acquire token using the device code
result = app.acquire_token_by_device_flow(flow)
if "access_token" in result:
    access_token = result["access_token"]
    print("Authentication successful!")
else:
    print("Authentication failed.")
    print(json.dumps(result, indent=4))
    exit(1)

# Define the Microsoft Graph API endpoint to get calendar events
endpoint = "https://graph.microsoft.com/v1.0/me/events"
headers = {
    "Authorization": "Bearer " + access_token
}

# Make the GET request to retrieve calendar events
response = requests.get(endpoint, headers=headers)
if response.status_code == 200:
    events = response.json()
    print("Retrieved calendar events:")
    print(json.dumps(events, indent=4))
else:
    print("Error retrieving calendar events:", response.status_code, response.text)
