# auth.py
import msal
from config import GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_AUTHORITY, GRAPH_SCOPE

def get_access_token():
    """
    Acquires an access token from Microsoft Graph using the client credentials flow.
    Ensure that the credentials in config.py are set correctly.
    """
    app = msal.ConfidentialClientApplication(
        client_id=GRAPH_CLIENT_ID,
        client_credential=GRAPH_CLIENT_SECRET,
        authority=GRAPH_AUTHORITY
    )
    # Try to get token from cache first
    result = app.acquire_token_silent(GRAPH_SCOPE, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    if "access_token" in result:
        return result['access_token']
    else:
        raise Exception("Could not obtain access token: " + str(result))
