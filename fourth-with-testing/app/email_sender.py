"""Email sender module.
Sends emails using the Microsoft Graph API.
"""

import logging
import requests
from .auth import get_token
from .config import Config

logger = logging.getLogger(__name__)
MAIL_SCOPES = Config.MAIL_SCOPES

def send_email_via_graph(html_content: str) -> None:
    """
    Send an email with the provided HTML content via the Graph API.
    
    Args:
        html_content (str): The HTML content for the email.
    """
    token = get_token(MAIL_SCOPES)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    message = {
        "message": {
            "subject": "Daily Calendar Summary",
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {"emailAddress": {"address": "paul@teamcinder.com"}}
            ]
        },
        "saveToSentItems": "true"
    }
    response = requests.post("https://graph.microsoft.com/v1.0/me/sendMail", headers=headers, json=message)
    if response.status_code in (200, 202):
        logger.info("Email sent successfully via Graph API.")
    else:
        logger.error("Failed to send email: %s - %s", response.status_code, response.text)
