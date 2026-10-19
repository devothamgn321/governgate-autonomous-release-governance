"""Tests for notification-service against the installed core-auth-sdk."""

import secrets

import jwt
import pytest

from notifications.sender import SERVICE_NAME, build_alert


@pytest.fixture
def secret(monkeypatch):
    value = secrets.token_hex(32)
    monkeypatch.setenv("AUTH_SECRET", value)
    return value


def test_alert_carries_signed_service_token(secret):
    alert = build_alert("ops-team", "disk almost full")
    token = alert["headers"]["Authorization"].removeprefix("Bearer ")
    # Check the token independently with PyJWT, not through the SDK.
    claims = jwt.decode(token, secret, algorithms=["HS256"])
    assert claims["sub"] == SERVICE_NAME


def test_alert_requires_recipient_and_message(secret):
    with pytest.raises(ValueError):
        build_alert("", "hello")
    with pytest.raises(ValueError):
        build_alert("ops-team", "")


def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        build_alert("ops-team", "hello")
