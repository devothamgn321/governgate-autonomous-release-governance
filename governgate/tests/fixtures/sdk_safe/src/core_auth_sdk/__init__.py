"""core-auth-sdk: shared token handling for internal services."""

from core_auth_sdk.tokens import (
    ALLOWED_ALGORITHM,
    InvalidTokenError,
    issue_token,
    verify_token,
)

__version__ = "1.0.0"

__all__ = [
    "ALLOWED_ALGORITHM",
    "InvalidTokenError",
    "issue_token",
    "verify_token",
    "__version__",
]
