"""Token issuing and verification for internal services.

This SDK is a thin, opinionated wrapper around PyJWT. All cryptography is
done by PyJWT; this module only fixes the policy every service must follow:

- Tokens are signed with HS256.
- Every token must carry an expiry ("exp") and a subject ("sub").
- The signing secret must be supplied by the caller. There is no default.
"""

from datetime import datetime, timedelta, timezone

import jwt

# The only algorithm this SDK accepts. Pinning it here is what stops the
# classic "alg: none" and algorithm-confusion attacks.
ALLOWED_ALGORITHM = "HS256"

# Shortest secret we accept, in characters. Short HMAC keys can be guessed.
MIN_SECRET_LENGTH = 32


class InvalidTokenError(Exception):
    """Raised when a token is missing, malformed, expired, or not trusted."""


def _check_secret(secret):
    # Fail closed: no secret, or a weak one, is a configuration error.
    if not secret or len(secret) < MIN_SECRET_LENGTH:
        raise ValueError(
            "secret must be at least " + str(MIN_SECRET_LENGTH) + " characters"
        )


def issue_token(subject, secret, ttl_seconds=300):
    """Create a signed token for `subject` that expires after `ttl_seconds`."""
    _check_secret(secret)
    now = datetime.now(timezone.utc)
    claims = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(claims, secret, algorithm=ALLOWED_ALGORITHM)


def verify_token(token, secret, algorithm=ALLOWED_ALGORITHM):
    """Check a token and return its claims, or raise InvalidTokenError.

    Rejects: bad signature, wrong algorithm, "none" algorithm, expired
    tokens, and tokens missing "exp" or "sub".
    """
    _check_secret(secret)
    if algorithm != ALLOWED_ALGORITHM:
        raise InvalidTokenError("algorithm not allowed: " + str(algorithm))
    if not token:
        raise InvalidTokenError("token is empty")
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error
