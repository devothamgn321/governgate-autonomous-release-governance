"""Builds outgoing alert requests.

Each alert carries a short-lived service token so the receiver knows it
came from notification-service. This service only ISSUES tokens; it never
verifies them, so a change to verify_token should not affect it.
"""

import os

from core_auth_sdk import issue_token

SERVICE_NAME = "notification-service"


def _auth_secret():
    secret = os.environ.get("AUTH_SECRET")
    if not secret:
        raise RuntimeError("AUTH_SECRET is not set")
    return secret


def build_alert(recipient, message):
    """Return the request an alert would be sent with."""
    if not recipient or not message:
        raise ValueError("recipient and message are required")

    token = issue_token(SERVICE_NAME, _auth_secret(), ttl_seconds=60)
    return {
        "to": recipient,
        "message": message,
        "headers": {"Authorization": "Bearer " + token},
    }
