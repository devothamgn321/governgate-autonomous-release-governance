"""The whole GovernGate run on the demo scenario.

Consumer tests really execute against each SDK version (see fake_gitlab.py).
"""

from governgate import cli, evidence_ledger, impact_reporter, policy_engine
from fake_gitlab import UPSTREAM_ID, FakeGitLab, FakeNemotron
from test_ledger_and_remediation import SAFE_FIX, UNSAFE_FIX


def check(gitlab, nemotron, autofix=False):
    return cli.run_check(gitlab, nemotron, UPSTREAM_ID, 1, "governgate2", autofix=autofix)


def test_breaking_change_is_blocked_with_evidence():
    gitlab, nemotron = FakeGitLab(), FakeNemotron()
    record = check(gitlab, nemotron)

    assert record["verdict"] == policy_engine.BLOCKED
    change_types = {(c["symbol"], c["change_type"]) for c in record["analysis"]["changes"]}
    assert ("verify_token", "REQUIRED_PARAMETER_ADDED") in change_types

    consumers = {c["project"]: c for c in record["discovery"]["consumers"]}
    billing = consumers["governgate2/billing-service"]
    notification = consumers["governgate2/notification-service"]
    assert billing["needs_verification"] and billing["static_breaks"]
    assert billing["call_sites"][0]["file"] == "billing/payments.py"
    assert not notification["needs_verification"]          # only calls issue_token
    assert "governgate2/governgate" not in consumers         # does not depend on the SDK

    [verification] = record["verifications"]                 # only billing was run
    assert verification["outcome"] == "REGRESSION"
    assert verification["baseline"]["job_status"] == "success"
    assert verification["candidate"]["job_status"] == "failed"
    assert verification["candidate"]["installed_sdk_commit"] == "b" * 40
    assert any("algorithm" in e for e in verification["candidate"]["errors"])

    assert record["root_causes"][0]["explanation"]["source"] == "nemotron+deterministic"
    report = impact_reporter.render(dict(record, ledger_sha256="0" * 64))
    assert "BLOCKED" in report and "billing/payments.py" in report


def test_works_without_nemotron():
    from governgate.nemotron_client import NemotronClient
    record = check(FakeGitLab(), NemotronClient(api_key=""))
    assert record["verdict"] == policy_engine.BLOCKED
    assert record["root_causes"][0]["explanation"]["source"] == "deterministic"
    assert record["model_calls"][0]["status"] == "skipped"


def test_safe_fix_version_is_ready_for_approval():
    record = check(FakeGitLab(head_sha="c" * 40), FakeNemotron())
    assert record["verdict"] == policy_engine.READY_FOR_APPROVAL
    assert record["verifications"][0]["outcome"] == "COMPATIBLE"


def test_autofix_opens_remediation_mr_for_safe_proposal():
    gitlab = FakeGitLab()
    record = check(gitlab, FakeNemotron(fix_source=SAFE_FIX), autofix=True)
    assert record["remediation"]["status"] == "validated"
    assert gitlab.commits[0]["branch"] == "governgate/fix-mr-1"
    assert "algorithm=ALLOWED_ALGORITHM" in gitlab.commits[0]["files"]["src/core_auth_sdk/tokens.py"]
    assert gitlab.merge_requests[0]["target"] == "main"


def test_autofix_never_commits_unsafe_proposal():
    gitlab = FakeGitLab()
    record = check(gitlab, FakeNemotron(fix_source=UNSAFE_FIX), autofix=True)
    assert record["remediation"]["status"] == "rejected_by_checks"
    assert gitlab.commits == [] and gitlab.merge_requests == []
    assert record["verdict"] == policy_engine.BLOCKED


def test_wrong_sdk_installed_never_passes():
    record = check(FakeGitLab(head_sha="c" * 40, wrong_install=True), FakeNemotron())
    assert record["verdict"] == policy_engine.INCOMPLETE_EVIDENCE


def test_legacy_cli_cannot_execute_privileged_mr_work(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "1")
    monkeypatch.setattr(cli, "GitLabClient", lambda: (_ for _ in ()).throw(AssertionError("must not authenticate")))
    assert cli.main(["check"]) == 1
    assert not (tmp_path / "governgate-evidence.json").exists()
