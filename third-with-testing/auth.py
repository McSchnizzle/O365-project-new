import os
import json
import msal
import certifi
from config import CLIENT_ID, AUTHORITY, TOKEN_CACHE_FILE, SYNC_SCOPES

# Ensure that requests uses certifi's certificate bundle.
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

def get_token(scopes=SYNC_SCOPES, interactive=False):
    """
    Device flow authentication as in the first draft.
    The 'interactive' parameter is accepted for compatibility but is ignored.
    """
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=scopes, verify=False)
        if "user_code" not in flow:
            raise Exception("Failed to create device flow: " + json.dumps(flow, indent=4))
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow, verify=False)
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())
    if "access_token" not in result:
        raise Exception("Failed to obtain token: " + json.dumps(result, indent=4))
    return result["access_token"]

# For compatibility, alias get_access_token to get_token.
get_access_token = get_token
