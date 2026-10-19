"""Step 7 - Evidence ledger.

One JSON record per run: commits, pipelines, installed SDK identity, test
results, AI calls, verdict. It is stored as a CI artifact.

Integrity: a SHA-256 digest of the canonical JSON, plus an HMAC-SHA256
signature when GOVERNGATE_SIGNING_KEY is set. There is NO default key.
If GOVERNGATE_REQUIRE_SIGNATURE=true and the key is missing, writing fails
(fail closed) instead of silently producing an unsigned record.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone


class LedgerError(Exception):
    pass


def _canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode()


def _signing_key():
    key = os.environ.get("GOVERNGATE_SIGNING_KEY")
    required = os.environ.get("GOVERNGATE_REQUIRE_SIGNATURE", "false").lower() == "true"
    if required and not key:
        raise LedgerError("GOVERNGATE_REQUIRE_SIGNATURE is true but GOVERNGATE_SIGNING_KEY is not set")
    if key and len(key) < 32:
        raise LedgerError("GOVERNGATE_SIGNING_KEY must be at least 32 characters")
    return key


def seal(record):
    """Return a sealed copy: record + digest (+ signature)."""
    body = dict(record)
    body["recorded_at"] = datetime.now(timezone.utc).isoformat()
    payload = _canonical(body)
    sealed = {"record": body, "sha256": hashlib.sha256(payload).hexdigest()}
    key = _signing_key()
    if key:
        sealed["hmac_sha256"] = hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()
    return sealed


def verify(sealed, key=None):
    """Verify integrity; a configured key requires a valid signature."""
    if not isinstance(sealed, dict) or not isinstance(sealed.get("record"), dict):
        return False
    try:
        configured_key = key or _signing_key()
    except LedgerError:
        return False
    payload = _canonical(sealed["record"])
    if hashlib.sha256(payload).hexdigest() != sealed.get("sha256"):
        return False
    signature = sealed.get("hmac_sha256")
    if configured_key:
        if not isinstance(signature, str):
            return False
        expected = hmac.new(configured_key.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    if signature is not None:
        return False
    return True


def write(sealed, path):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sealed, handle, indent=2, default=str)
