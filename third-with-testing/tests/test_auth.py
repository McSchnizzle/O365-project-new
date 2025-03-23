import os
import unittest
import msal
from auth import get_access_token  # This is our alias for get_token
from config import SYNC_SCOPES, TOKEN_CACHE_FILE

class DummyApp:
    def __init__(self, client_id, authority, token_cache):
        self.client_id = client_id
        self.authority = authority
        self.token_cache = token_cache

    def get_accounts(self):
        # Simulate no cached accounts.
        return []

    def initiate_device_flow(self, scopes, verify):
        # Return a dummy device flow response.
        return {"user_code": "ABC123", "message": "Use code ABC123 to sign in."}

    def acquire_token_by_device_flow(self, flow, verify):
        # Return a dummy token.
        return {"access_token": "dummy_token_basic"}

class TestAuth(unittest.TestCase):
    def setUp(self):
        # Remove token cache file if it exists.
        if os.path.exists(TOKEN_CACHE_FILE):
            os.remove(TOKEN_CACHE_FILE)

    def test_get_access_token(self):
        # Patch MSAL's PublicClientApplication with our DummyApp.
        original_app = msal.PublicClientApplication
        msal.PublicClientApplication = DummyApp

        # Call get_access_token with our SYNC_SCOPES.
        token = get_access_token(SYNC_SCOPES)
        self.assertEqual(token, "dummy_token_basic")

        # Restore the original PublicClientApplication.
        msal.PublicClientApplication = original_app

if __name__ == '__main__':
    unittest.main()
