"""Validate evidence before the credential-free manual approval CI job."""

import argparse
import json
import re
from pathlib import Path

from governgate import evidence_ledger

SDK_PROJECT_ID = 87600355
EXPECTED_CONSUMERS = {"billing-service", "notification-service"}
SHA = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def validate_evidence(sealed):
    """Accept only complete, pinned all-pass evidence explicitly awaiting review."""
    if not evidence_ledger.verify(sealed):
        raise ValueError("Evidence ledger integrity check failed")
    record = sealed["record"]
    if record.get("project_id") != SDK_PROJECT_ID or not isinstance(record.get("mr_iid"), int):
        raise ValueError("Evidence does not identify an SDK merge request")
    if record.get("verdict") != "REQUIRES_MANUAL_REVIEW":
        raise ValueError("Only a complete result awaiting manual review can be approved")

    baseline = record.get("baseline")
    candidate = record.get("candidate")
    worker = record.get("worker_image", "")
    for identity in (baseline, candidate):
        if (not isinstance(identity, dict)
                or identity.get("project_id") != SDK_PROJECT_ID
                or not SHA.fullmatch(str(identity.get("commit", "")))
                or not SHA256.fullmatch(str(identity.get("archive_sha256", "")))):
            raise ValueError("SDK baseline or candidate identity is incomplete")
    if not SHA256.fullmatch(str(worker).removeprefix("sha256:")):
        raise ValueError("Worker image identity is incomplete")

    consumers = record.get("consumers", {})
    runs = record.get("runs", {})
    if (not isinstance(consumers, dict) or not isinstance(runs, dict)
            or set(consumers) != EXPECTED_CONSUMERS or set(runs) != EXPECTED_CONSUMERS):
        raise ValueError("Consumer evidence is incomplete")
    for name in EXPECTED_CONSUMERS:
        if (not isinstance(consumers[name], dict)
                or not SHA.fullmatch(str(consumers[name].get("commit", "")))):
            raise ValueError(f"{name} commit identity is incomplete")
        pair = runs[name]
        if not isinstance(pair, dict) or set(pair) != {"baseline", "candidate"}:
            raise ValueError(f"{name} baseline/candidate pair is incomplete")
        if any(not isinstance(result, dict) or result.get("status") != "PASS"
               for result in pair.values()):
            raise ValueError(f"{name} has a non-passing or missing test result")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="governgate-evidence.json")
    args = parser.parse_args(argv)
    try:
        sealed = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        record = validate_evidence(sealed)
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as error:
        print(f"Manual approval refused: {type(error).__name__}")
        return 1
    print(f"Manual approval recorded for SDK MR !{record['mr_iid']}; all pinned consumer runs passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
