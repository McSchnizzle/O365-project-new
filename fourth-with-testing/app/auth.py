# app/auth.py
"""
Authentication module.
Handles token acquisition using MSAL.
"""

import os
import json
import msal
import certifi
import logging
from .config import Config

CLIENT_ID = Config.CLIENT_ID
AUTHORITY = Config.AUTHORITY
TOKEN_CACHE_FILE = Config.TOKEN_CACHE_FILE
SYNC_SCOPES = Config.SYNC_SCOPES
MAIL_SCOPES = Config.MAIL_SCOPES


logger = logging.getLogger(__name__)

# For testing, set the environment variables so that requests uses certifi’s certificate bundle.
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

def get_token(scopes: list) -> str:
    """
    Retrieve an access token for the provided scopes.
    
    Args:
        scopes (list): A list of scopes for which to request a token.
    
    Returns:
        str: The access token.
    
    Raises:
        Exception: If token acquisition fails.
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
        flow = app.initiate_device_flow(scopes=scopes, verify=False)  # Verification disabled for testing.
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
