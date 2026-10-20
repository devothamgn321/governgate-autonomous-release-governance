import copy

import pytest

from governgate import controller, evidence_ledger, manual_review


def evidence():
    sha = "a" * 40
    digest = "b" * 64
    return {
        "project_id": manual_review.SDK_PROJECT_ID,
        "mr_iid": 2,
        "baseline": {"project_id": manual_review.SDK_PROJECT_ID, "commit": sha, "archive_sha256": digest},
        "candidate": {"project_id": manual_review.SDK_PROJECT_ID, "commit": "c" * 40, "archive_sha256": digest},
        "worker_image": "sha256:" + digest,
        "consumers": {name: {"commit": sha} for name in manual_review.EXPECTED_CONSUMERS},
        "runs": {name: {"baseline": {"status": "PASS"}, "candidate": {"status": "PASS"}}
                 for name in manual_review.EXPECTED_CONSUMERS},
        "verdict": "REQUIRES_MANUAL_REVIEW",
    }


def test_manual_review_accepts_only_sealed_complete_all_pass_matrix():
    sealed = evidence_ledger.seal(evidence())
    assert manual_review.validate_evidence(sealed)["mr_iid"] == 2


@pytest.mark.parametrize("mutation", [
    lambda record: record.update(verdict="BLOCKED"),
    lambda record: record["runs"]["billing-service"]["candidate"].update(status="FAIL"),
    lambda record: record["runs"].pop("notification-service"),
    lambda record: record["consumers"]["billing-service"].update(commit="unknown"),
])
def test_manual_review_rejects_nonpassing_or_incomplete_evidence(mutation):
    record = evidence()
    mutation(record)
    with pytest.raises(ValueError):
        manual_review.validate_evidence(evidence_ledger.seal(record))


def test_manual_review_rejects_tampered_ledger():
    sealed = evidence_ledger.seal(evidence())
    tampered = copy.deepcopy(sealed)
    tampered["record"]["mr_iid"] = 999
    with pytest.raises(ValueError, match="integrity"):
        manual_review.validate_evidence(tampered)


def test_review_ready_controller_run_reaches_required_manual_job(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key, value in {
        "CI_PROJECT_ID": str(controller.CONTROLLER),
        "CI_COMMIT_BRANCH": "main",
        "CI_COMMIT_REF_PROTECTED": "true",
        "CI_PIPELINE_SOURCE": "pipeline",
    }.items():
        monkeypatch.setenv(key, value)
    client = object()
    monkeypatch.setattr(controller, "GitLabClient", lambda **_: client)
    monkeypatch.setattr(controller, "resolve_upstream_request", lambda *args: (2, "a" * 40))
    monkeypatch.setattr(controller, "execute", lambda *args: {"verdict": "REQUIRES_MANUAL_REVIEW"})
    assert controller.main(["--image", "sha256:" + "b" * 64]) == 0
