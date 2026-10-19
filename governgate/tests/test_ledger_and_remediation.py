import pytest

from governgate import evidence_ledger as ledger
from governgate import remediation
from fake_gitlab import FIXTURES

KEY = "k" * 40


def test_seal_and_verify_unsigned(monkeypatch):
    monkeypatch.delenv("GOVERNGATE_SIGNING_KEY", raising=False)
    sealed = ledger.seal({"verdict": "BLOCKED"})
    assert ledger.verify(sealed)
    sealed["record"]["verdict"] = "READY_FOR_APPROVAL"
    assert not ledger.verify(sealed)


def test_signed_ledger_detects_tampering(monkeypatch):
    monkeypatch.setenv("GOVERNGATE_SIGNING_KEY", KEY)
    sealed = ledger.seal({"verdict": "BLOCKED"})
    assert "hmac_sha256" in sealed and ledger.verify(sealed)
    # Attacker recomputes the plain digest but cannot recompute the HMAC.
    import hashlib
    sealed["record"]["verdict"] = "READY_FOR_APPROVAL"
    sealed["sha256"] = hashlib.sha256(ledger._canonical(sealed["record"])).hexdigest()
    assert not ledger.verify(sealed)
    assert not ledger.verify(sealed, key="wrong" * 10)


def test_signed_ledger_rejects_stripped_signature(monkeypatch):
    monkeypatch.setenv("GOVERNGATE_SIGNING_KEY", KEY)
    sealed = ledger.seal({"verdict": "BLOCKED"})
    sealed.pop("hmac_sha256")
    import hashlib
    sealed["sha256"] = hashlib.sha256(ledger._canonical(sealed["record"])).hexdigest()
    assert not ledger.verify(sealed)


def test_unsigned_ledger_rejects_unverifiable_signature(monkeypatch):
    monkeypatch.delenv("GOVERNGATE_SIGNING_KEY", raising=False)
    sealed = ledger.seal({"verdict": "BLOCKED"})
    sealed["hmac_sha256"] = "not-a-signature"
    assert not ledger.verify(sealed)


def test_required_signature_without_key_fails_closed(monkeypatch):
    monkeypatch.delenv("GOVERNGATE_SIGNING_KEY", raising=False)
    monkeypatch.setenv("GOVERNGATE_REQUIRE_SIGNATURE", "true")
    with pytest.raises(ledger.LedgerError):
        ledger.seal({"verdict": "BLOCKED"})


def test_short_signing_key_rejected(monkeypatch):
    monkeypatch.setenv("GOVERNGATE_SIGNING_KEY", "short")
    with pytest.raises(ledger.LedgerError):
        ledger.seal({"verdict": "BLOCKED"})


ORIGINAL = (FIXTURES / "sdk_v1/src/core_auth_sdk/tokens.py").read_text()
CANDIDATE = (FIXTURES / "sdk_candidate/src/core_auth_sdk/tokens.py").read_text()

SAFE_FIX = '''def verify_token(token, secret, algorithm=ALLOWED_ALGORITHM):
    """Check a token; algorithm defaults to the pinned secure constant."""
    _check_secret(secret)
    if algorithm != ALLOWED_ALGORITHM:
        raise InvalidTokenError("algorithm not allowed: " + str(algorithm))
    if not token:
        raise InvalidTokenError("token is empty")
    try:
        return jwt.decode(token, secret, algorithms=[algorithm], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error
'''

UNSAFE_FIX = '''def verify_token(token, secret, algorithm=None):
    _check_secret(secret)
    if algorithm is None:
        return jwt.decode(token, options={"verify_signature": False})
    try:
        return jwt.decode(token, secret, algorithms=[algorithm], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error
'''

STILL_BREAKING = SAFE_FIX.replace("algorithm=ALLOWED_ALGORITHM", "algorithm")


def test_safe_fix_passes_checks():
    ok, reasons, patched = remediation.validate_proposal(ORIGINAL, CANDIDATE, "verify_token", SAFE_FIX)
    assert ok, reasons
    assert "def verify_token(token, secret, algorithm=ALLOWED_ALGORITHM)" in patched
    assert "def issue_token" in patched


def test_unsafe_fix_rejected():
    ok, reasons, _ = remediation.validate_proposal(ORIGINAL, CANDIDATE, "verify_token", UNSAFE_FIX)
    assert not ok
    assert any("forbidden" in r for r in reasons)


def test_still_breaking_fix_rejected():
    ok, reasons, _ = remediation.validate_proposal(ORIGINAL, CANDIDATE, "verify_token", STILL_BREAKING)
    assert not ok and any("still breaking" in r for r in reasons)


def test_garbage_proposal_rejected():
    ok, reasons, _ = remediation.validate_proposal(ORIGINAL, CANDIDATE, "verify_token", "def (")
    assert not ok
