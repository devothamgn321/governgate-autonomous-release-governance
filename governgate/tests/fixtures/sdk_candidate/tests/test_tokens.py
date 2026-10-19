"""Functional and security tests for core-auth-sdk.

The security tests here are what later reject an unsafe "fix" (CP10):
any change that weakens verification makes at least one of them fail.
"""

import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from core_auth_sdk import InvalidTokenError, issue_token, verify_token


@pytest.fixture
def secret():
    # A fresh random secret per test. Nothing is hardcoded.
    return secrets.token_hex(32)


# ---------- Functional ----------

def test_valid_token_round_trip(secret):
    token = issue_token("user-42", secret)
    claims = verify_token(token, secret, "HS256")
    assert claims["sub"] == "user-42"


def test_claims_include_expiry(secret):
    claims = verify_token(issue_token("user-42", secret), secret, "HS256")
    assert "exp" in claims


# ---------- Security: must reject ----------

def test_rejects_wrong_secret(secret):
    token = issue_token("user-42", secret)
    with pytest.raises(InvalidTokenError):
        verify_token(token, secrets.token_hex(32), "HS256")


def test_rejects_tampered_token(secret):
    token = issue_token("user-42", secret)
    header, payload, signature = token.split(".")
    forged = header + "." + payload + "." + signature[::-1]
    with pytest.raises(InvalidTokenError):
        verify_token(forged, secret, "HS256")


def test_rejects_expired_token(secret):
    token = issue_token("user-42", secret, ttl_seconds=-10)
    with pytest.raises(InvalidTokenError):
        verify_token(token, secret, "HS256")


def test_rejects_alg_none(secret):
    # Classic attack: an unsigned token claiming "alg": "none".
    unsigned = jwt.encode({"sub": "admin", "exp": 9999999999}, None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        verify_token(unsigned, secret, "HS256")


def test_rejects_other_algorithm(secret):
    # Signed correctly, but with an algorithm we do not allow.
    other = jwt.encode(
        {"sub": "user-42", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        secret,
        algorithm="HS512",
    )
    with pytest.raises(InvalidTokenError):
        verify_token(other, secret, "HS256")


def test_rejects_missing_subject(secret):
    no_sub = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        verify_token(no_sub, secret, "HS256")


def test_rejects_missing_expiry(secret):
    no_exp = jwt.encode({"sub": "user-42"}, secret, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        verify_token(no_exp, secret, "HS256")


def test_rejects_empty_token(secret):
    with pytest.raises(InvalidTokenError):
        verify_token("", secret, "HS256")


def test_rejects_weak_secret():
    with pytest.raises(ValueError):
        issue_token("user-42", "short")
    with pytest.raises(ValueError):
        verify_token("anything", "", "HS256")
