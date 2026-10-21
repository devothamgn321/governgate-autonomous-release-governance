import copy
from pathlib import Path

import pytest
import yaml

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
        "runs": {
            name: {"baseline": {"status": "PASS"}, "candidate": {"status": "PASS"}}
            for name in manual_review.EXPECTED_CONSUMERS
        },
        "verdict": "REQUIRES_MANUAL_REVIEW",
    }


def test_manual_review_accepts_complete_all_pass_evidence():
    sealed = evidence_ledger.seal(evidence())
    assert manual_review.validate_evidence(sealed)["mr_iid"] == 2


@pytest.mark.parametrize(
    "mutation",
    [
        lambda record: record.update(verdict="BLOCKED"),
        lambda record: record["runs"]["billing-service"]["candidate"].update(status="FAIL"),
        lambda record: record["runs"].pop("notification-service"),
        lambda record: record["consumers"]["billing-service"].update(commit="unknown"),
    ],
)
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


@pytest.mark.parametrize("mutation", [
    None,
    lambda record: record["runs"]["billing-service"]["baseline"].update(status="FAIL"),
    lambda record: record["runs"]["billing-service"]["candidate"].update(status="FAIL"),
    lambda record: record["runs"].pop("notification-service"),
    lambda record: record["baseline"].update(commit="unknown"),
])
def test_controller_requires_complete_passing_evidence(monkeypatch, tmp_path, mutation):
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
    record = evidence()
    if mutation is not None:
        mutation(record)
    monkeypatch.setattr(controller, "execute", lambda *args: record)
    expected = 0 if mutation is None else 1
    assert controller.main(["--image", "sha256:" + "b" * 64]) == expected


def test_manual_ci_job_is_blocking_and_has_no_controller_secret():
    config_path = Path(__file__).parents[1] / ".gitlab-ci.yml"
    documents = list(yaml.safe_load_all(config_path.read_text(encoding="utf-8")))
    config = documents[-1]
    job = config["manual-evidence-review"]
    assert job["needs"] == [{"job": "trusted-controller", "artifacts": True}]
    assert job["rules"][0]["when"] == "manual"
    assert job["rules"][0]["allow_failure"] is False
    assert "environment" not in job
    assert "GOVERNGATE_API_TOKEN" not in str(job)
    assert "GOVERNGATE_SIGNING_KEY" not in str(job)

class FreshRefs:
    def get_merge_request(self, project, iid):
        return {"state": "opened", "source_project_id": controller.SDK,
                "target_project_id": controller.SDK, "target_branch": "main",
                "diff_refs": {"head_sha": "c" * 40}}

    def get_branch_sha(self, project, branch):
        return "a" * 40


def test_post_review_freshness_accepts_matching_refs():
    manual_review.validate_freshness(FreshRefs(), evidence(), 2, "c" * 40)


@pytest.mark.parametrize("project", [controller.SDK, *controller.CONSUMERS])
def test_post_review_freshness_rejects_moved_refs(project):
    client = FreshRefs()
    client.get_branch_sha = lambda current, branch: ("d" if current == project else "a") * 40
    with pytest.raises(ValueError, match="changed"):
        manual_review.validate_freshness(client, evidence(), 2, "c" * 40)


def test_post_review_freshness_rejects_changed_mr():
    client = FreshRefs()
    client.get_merge_request = lambda *args: {"state": "closed"}
    with pytest.raises(ValueError, match="changed"):
        manual_review.validate_freshness(client, evidence(), 2, "c" * 40)


def test_post_review_freshness_rejects_unrelated_evidence():
    with pytest.raises(ValueError, match="upstream"):
        manual_review.validate_freshness(FreshRefs(), evidence(), 3, "c" * 40)


def test_freshness_cli_fails_closed_on_api_error(monkeypatch, tmp_path):
    import json
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence_ledger.seal(evidence())))
    def unavailable(record):
        raise RuntimeError("secret API detail")
    monkeypatch.setattr(manual_review, "check_trusted_freshness", unavailable)
    assert manual_review.main(["--check-freshness", "--evidence", str(path)]) == 1


def test_freshness_checks_context_before_authentication(monkeypatch):
    monkeypatch.delenv("CI_PROJECT_ID", raising=False)
    monkeypatch.setattr(controller, "GitLabClient", lambda **kw: pytest.fail("must not authenticate"))
    with pytest.raises(ValueError, match="Protected"):
        manual_review.check_trusted_freshness(evidence())


def test_final_ci_step_requires_manual_review_and_scoped_environment():
    config = yaml.safe_load((Path(__file__).parents[1] / ".gitlab-ci.yml").read_text())
    job = config["trusted-freshness-check"]
    assert job["stage"] == "finalize"
    assert {"job": "manual-evidence-review", "artifacts": False} in job["needs"]
    assert job["environment"]["name"] == "governgate-controller"
    assert job["allow_failure"] is False
    assert "--check-freshness" in " ".join(job["script"])
