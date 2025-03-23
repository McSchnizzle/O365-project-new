import os
import unittest
import msal
from auth import get_access_token  # Our alias for get_token
from config import SYNC_SCOPES, TOKEN_CACHE_FILE

class DummyAppInteractive:
    def __init__(self, client_id, authority, token_cache):
        self.client_id = client_id
        self.authority = authority
        self.token_cache = token_cache

    def get_accounts(self):
        # Simulate no cached accounts.
        return []

    def initiate_device_flow(self, scopes, verify):
        # Simulate an interactive device flow.
        return {"user_code": "XYZ789", "message": "Use code XYZ789 to sign in interactively."}

    def acquire_token_by_device_flow(self, flow, verify):
        # Return a different dummy token for interactive flows.
        return {"access_token": "dummy_token_interactive"}

class TestAuthInteractive(unittest.TestCase):
    def setUp(self):
        # Remove the token cache if it exists.
        if os.path.exists(TOKEN_CACHE_FILE):
            os.remove(TOKEN_CACHE_FILE)

    def test_get_access_token_interactive(self):
        original_app = msal.PublicClientApplication
        msal.PublicClientApplication = DummyAppInteractive

        # Call get_access_token with interactive=True.
        token = get_access_token(SYNC_SCOPES, interactive=True)
        self.assertEqual(token, "dummy_token_interactive")

        msal.PublicClientApplication = original_app

if __name__ == '__main__':
    unittest.main()
