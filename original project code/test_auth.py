import msal
import json

CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"
SCOPE = ["Calendars.Read"]

app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

# Initiate the device flow
flow = app.initiate_device_flow(scopes=SCOPE)
if "user_code" not in flow:
    raise Exception("Failed to create device flow. Error details: " + json.dumps(flow, indent=4))

print(flow["message"])

# Acquire token using the device flow
result = app.acquire_token_by_device_flow(flow)
if "access_token" in result:
    print("Authentication successful!")
    print("Access token:", result["access_token"])
else:
    print("Authentication failed.")
    print(json.dumps(result, indent=4))
