import msal
import json
import os

CLIENT_ID = "db1311b5-c7de-4db6-a4ba-07bb8103fb77"
AUTHORITY = "https://login.microsoftonline.com/f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf"
SCOPE = ["Calendars.Read"]

# File to persist the token cache
TOKEN_CACHE_FILE = "token_cache.bin"

# Create a SerializableTokenCache instance
cache = msal.SerializableTokenCache()

# Load cache from file if it exists
if os.path.exists(TOKEN_CACHE_FILE):
    with open(TOKEN_CACHE_FILE, "r") as f:
        cache.deserialize(f.read())

# Create a PublicClientApplication with the token cache
app = msal.PublicClientApplication(
    CLIENT_ID, authority=AUTHORITY, token_cache=cache
)

# Try to acquire token silently from the cache
accounts = app.get_accounts()
result = None
if accounts:
    # Using the first account found in the cache
    result = app.acquire_token_silent(SCOPE, account=accounts[0])

if not result:
    # If no token is available in cache, initiate device code flow
    flow = app.initiate_device_flow(scopes=SCOPE)
    if "user_code" not in flow:
        raise Exception("Failed to create device flow. Error details: " + json.dumps(flow, indent=4))
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)

# Save the token cache if it has changed
if cache.has_state_changed:
    with open(TOKEN_CACHE_FILE, "w") as f:
        f.write(cache.serialize())

# Check if we obtained an access token successfully
if "access_token" in result:
    print("Authentication successful!")
    print("Access token:", result["access_token"])
else:
    print("Authentication failed.")
    print(json.dumps(result, indent=4))
