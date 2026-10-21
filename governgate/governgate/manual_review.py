"""Validate evidence before the credential-free manual approval CI job."""

import argparse
import json
import os
import re
from pathlib import Path

from governgate import evidence_ledger

SDK_PROJECT_ID = 87600355
EXPECTED_CONSUMERS = {"billing-service", "notification-service"}
SHA = re.compile(r"[0-9a-f]{40}$")
SHA256 = re.compile(r"[0-9a-f]{64}$")


def validate_evidence(sealed):
    """Accept only complete, pinned all-pass evidence awaiting human review."""
    if not isinstance(sealed, dict) or not evidence_ledger.verify(sealed):
        raise ValueError("Evidence ledger integrity check failed")
    record = sealed.get("record")
    if not isinstance(record, dict):
        raise ValueError("Evidence record is missing")
    mr_iid = record.get("mr_iid")
    if (record.get("project_id") != SDK_PROJECT_ID or isinstance(mr_iid, bool)
            or not isinstance(mr_iid, int) or mr_iid < 1):
        raise ValueError("Evidence does not identify an SDK merge request")
    if record.get("verdict") != "REQUIRES_MANUAL_REVIEW":
        raise ValueError("Only a complete result awaiting manual review can be approved")

    for label in ("baseline", "candidate"):
        identity = record.get(label)
        if (not isinstance(identity, dict)
                or identity.get("project_id") != SDK_PROJECT_ID
                or not SHA.fullmatch(str(identity.get("commit", "")))
                or not SHA256.fullmatch(str(identity.get("archive_sha256", "")))):
            raise ValueError("SDK baseline or candidate identity is incomplete")
    worker = str(record.get("worker_image", "")).removeprefix("sha256:")
    if not SHA256.fullmatch(worker):
        raise ValueError("Worker image identity is incomplete")

    consumers = record.get("consumers")
    runs = record.get("runs")
    if (not isinstance(consumers, dict) or not isinstance(runs, dict)
            or set(consumers) != EXPECTED_CONSUMERS or set(runs) != EXPECTED_CONSUMERS):
        raise ValueError("Consumer evidence is incomplete")
    for name in EXPECTED_CONSUMERS:
        consumer = consumers[name]
        if (not isinstance(consumer, dict)
                or not SHA.fullmatch(str(consumer.get("commit", "")))):
            raise ValueError(f"{name} commit identity is incomplete")
        pair = runs[name]
        if not isinstance(pair, dict) or set(pair) != {"baseline", "candidate"}:
            raise ValueError(f"{name} baseline/candidate pair is incomplete")
        if any(not isinstance(result, dict) or result.get("status") != "PASS"
               for result in pair.values()):
            raise ValueError(f"{name} has a non-passing or missing test result")
    return record


def validate_freshness(client, record, iid, head):
    """Recheck mutable refs after human review using only the trusted API client."""
    from governgate.controller import SDK, CONSUMERS
    if record["mr_iid"] != iid or record["candidate"]["commit"] != head:
        raise ValueError("Evidence does not match this upstream request")
    mr = client.get_merge_request(SDK, iid)
    if (mr.get("state") != "opened" or mr.get("source_project_id") != SDK
            or mr.get("target_project_id") != SDK or mr.get("target_branch") != "main"
            or mr.get("diff_refs", {}).get("head_sha") != head):
        raise ValueError("SDK merge request changed after verification")
    if client.get_branch_sha(SDK, "main") != record["baseline"]["commit"]:
        raise ValueError("SDK target changed; rerun verification and review")
    for project, name in CONSUMERS.items():
        if client.get_branch_sha(project, "main") != record["consumers"][name]["commit"]:
            raise ValueError("Consumer changed; rerun verification and review")


def check_trusted_freshness(record):
    from governgate.controller import API, CONTROLLER, GitLabClient, resolve_upstream_request
    if (os.environ.get("CI_PROJECT_ID") != str(CONTROLLER)
            or os.environ.get("CI_COMMIT_BRANCH") != "main"
            or os.environ.get("CI_COMMIT_REF_PROTECTED") != "true"
            or os.environ.get("CI_PIPELINE_SOURCE") != "pipeline"):
        raise ValueError("Protected controller execution is required")
    client = GitLabClient(base_url=API)
    iid, head = resolve_upstream_request(
        client, os.environ.get("CI_UPSTREAM_PROJECT_ID"),
        os.environ.get("CI_UPSTREAM_PIPELINE_ID"), os.environ.get("CI_UPSTREAM_JOB_ID"),
        os.environ.get("CI_PIPELINE_ID"), os.environ.get("CI_PROJECT_ID"))
    validate_freshness(client, record, iid, head)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="governgate-evidence.json")
    parser.add_argument("--check-freshness", action="store_true")
    args = parser.parse_args(argv)
    try:
        sealed = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        record = validate_evidence(sealed)
        if args.check_freshness:
            check_trusted_freshness(record)
    except Exception as error:
        print(f"Manual approval refused: {type(error).__name__}")
        return 1
    print(f"Evidence accepted for SDK MR !{record['mr_iid']}; all pinned consumer runs passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
