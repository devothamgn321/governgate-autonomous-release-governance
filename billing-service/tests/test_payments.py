"""Integration tests: billing + the real core-auth-sdk it has installed.

These are the tests GovernGate runs against each SDK candidate.
"""

import secrets

import pytest

from core_auth_sdk import issue_token
from billing.payments import PaymentRejected, authorize_payment


@pytest.fixture
def secret(monkeypatch):
    value = secrets.token_hex(32)
    monkeypatch.setenv("AUTH_SECRET", value)
    return value


def test_valid_token_authorizes_payment(secret):
    token = issue_token("customer-7", secret)
    receipt = authorize_payment(token, 2500)
    assert receipt["status"] == "authorized"
    assert receipt["customer"] == "customer-7"
    assert receipt["amount_cents"] == 2500


def test_forged_token_is_rejected(secret):
    token = issue_token("customer-7", secrets.token_hex(32))
    with pytest.raises(PaymentRejected):
        authorize_payment(token, 2500)


def test_expired_token_is_rejected(secret):
    token = issue_token("customer-7", secret, ttl_seconds=-10)
    with pytest.raises(PaymentRejected):
        authorize_payment(token, 2500)


def test_non_positive_amount_is_rejected(secret):
    token = issue_token("customer-7", secret)
    with pytest.raises(PaymentRejected):
        authorize_payment(token, 0)


def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        authorize_payment("anything", 100)
