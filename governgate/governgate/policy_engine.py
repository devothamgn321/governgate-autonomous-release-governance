"""Step 6 - The verdict.

Pure function of the evidence. No AI input is read here.
Only READY_FOR_APPROVAL lets the GitLab job pass; every other verdict fails
the job, and "Pipelines must succeed" then blocks the merge. A human still
approves the merge request either way.
"""

from governgate import differential_verifier as dv

READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
BLOCKED = "BLOCKED"
INCOMPLETE_EVIDENCE = "INCOMPLETE_EVIDENCE"
REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"
SUPERSEDED = "SUPERSEDED"

PASSING = {READY_FOR_APPROVAL}


def decide(analysis, discovery, verifications, head_sha_now):
    """Return (verdict, reasons)."""
    reasons = []

    if head_sha_now != analysis["head_sha"]:
        return SUPERSEDED, ["merge request moved from " + analysis["head_sha"][:8] + " to " + head_sha_now[:8] + " during the check"]

    expected = {c["project"] for c in discovery["consumers"] if c.get("needs_verification")}
    observed = [v["project"] for v in verifications]
    known = {dv.REGRESSION, dv.COMPATIBLE, dv.PRE_EXISTING_FAILURE, dv.INCONCLUSIVE, dv.INVALID_EVIDENCE}
    if expected - set(observed) or len(observed) != len(set(observed)) or any(v["outcome"] not in known for v in verifications):
        return INCOMPLETE_EVIDENCE, ["Missing, duplicate, or unknown verification outcome"]

    regressions = [v for v in verifications if v["outcome"] == dv.REGRESSION]
    if regressions:
        return BLOCKED, [v["project"] + ": " + v["reason"] for v in regressions]

    bad_evidence = [v for v in verifications if v["outcome"] in (dv.INVALID_EVIDENCE, dv.INCONCLUSIVE)]
    if bad_evidence or discovery["unreadable"]:
        reasons += [v["project"] + ": " + v["reason"] for v in bad_evidence]
        reasons += [u["project"] + ": could not be scanned" for u in discovery["unreadable"]]
        return INCOMPLETE_EVIDENCE, reasons

    pre_existing = [v for v in verifications if v["outcome"] == dv.PRE_EXISTING_FAILURE]
    if pre_existing:
        return REQUIRES_MANUAL_REVIEW, [v["project"] + ": " + v["reason"] for v in pre_existing]

    # A static break that tests did not catch means the tests are too weak to trust.
    tested = {v["project"] for v in verifications}
    for consumer in discovery["consumers"]:
        if consumer["static_breaks"] and consumer["project"] in tested:
            outcome = next(v["outcome"] for v in verifications if v["project"] == consumer["project"])
            if outcome == dv.COMPATIBLE:
                return REQUIRES_MANUAL_REVIEW, [consumer["project"] + ": code analysis finds a broken call but its tests pass"]

    if not verifications:
        reasons.append("no consumer calls a changed public function")
    else:
        reasons += [v["project"] + ": compatible on both SDK versions" for v in verifications]
    return READY_FOR_APPROVAL, reasons
