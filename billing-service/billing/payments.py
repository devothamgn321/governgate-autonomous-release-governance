"""Payment authorization.

Every charge must come from a caller with a valid login token. Token
checking is delegated to the shared core-auth-sdk; billing never parses
tokens itself.
"""

import os

from core_auth_sdk import InvalidTokenError, verify_token


class PaymentRejected(Exception):
    """Raised when a payment cannot be authorized."""


def _auth_secret():
    # Fail closed: refuse to run without a configured secret.
    secret = os.environ.get("AUTH_SECRET")
    if not secret:
        raise RuntimeError("AUTH_SECRET is not set")
    return secret


def authorize_payment(token, amount_cents):
    """Authorize a charge of `amount_cents` for the user who owns `token`.

    Returns a receipt dict. Raises PaymentRejected for a bad token or amount.
    """
    if amount_cents <= 0:
        raise PaymentRejected("amount must be positive")

    try:
        # The call GovernGate will watch: billing depends on this exact signature.
        claims = verify_token(token, _auth_secret())
    except InvalidTokenError as error:
        raise PaymentRejected("invalid token: " + str(error)) from error

    return {
        "status": "authorized",
        "customer": claims["sub"],
        "amount_cents": amount_cents,
    }
