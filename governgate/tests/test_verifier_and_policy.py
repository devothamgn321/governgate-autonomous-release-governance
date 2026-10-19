from governgate import differential_verifier as dv
from governgate import policy_engine as pe

SHA_A, SHA_B = "a" * 40, "b" * 40


def run(status="success", sdk=SHA_A, requested=SHA_A, consumer="f" * 40, summary="5 passed"):
    return {"pipeline_id": 1, "status": status, "job_status": status, "installed_sdk_commit": sdk,
            "requested_sdk_sha": requested, "consumer_sha": consumer, "summary": summary}


def test_failure_before_tests_ran_is_inconclusive_not_regression():
    assert dv.classify(run(), run("failed", SHA_B, SHA_B, summary=None))[0] == dv.INCONCLUSIVE


def test_parse_test_log():
    log = ("\x1b[32mSDK commit: " + SHA_B + "\x1b[0m\nFAILED tests/test_payments.py::test_x - TypeError: boom\n"
           "E       TypeError: verify_token() missing 1 required positional argument: 'algorithm'\n"
           "===== 3 failed, 2 passed in 0.05s =====\n")
    parsed = dv.parse_test_log(log)
    assert parsed["installed_sdk_commit"] == SHA_B
    assert parsed["summary"] == "3 failed, 2 passed"
    assert parsed["failed_tests"] == ["tests/test_payments.py::test_x"]
    assert "missing 1 required positional argument" in parsed["errors"][0]


def test_parse_quiet_pytest_summary():
    assert dv.parse_test_log("SDK commit: " + SHA_A + "\n...\n5 passed in 0.04s\n")["summary"] == "5 passed"


def test_classify_regression():
    assert dv.classify(run(), run("failed", SHA_B, SHA_B))[0] == dv.REGRESSION


def test_classify_compatible():
    assert dv.classify(run(), run("success", SHA_B, SHA_B))[0] == dv.COMPATIBLE


def test_classify_pre_existing_failure():
    assert dv.classify(run("failed"), run("failed", SHA_B, SHA_B))[0] == dv.PRE_EXISTING_FAILURE


def test_wrong_sdk_installed_is_invalid_evidence():
    assert dv.classify(run(), run("success", SHA_A, SHA_B))[0] == dv.INVALID_EVIDENCE


def test_consumer_commit_moved_is_invalid_evidence():
    assert dv.classify(run(), run("failed", SHA_B, SHA_B, consumer="9" * 40))[0] == dv.INVALID_EVIDENCE


def test_timeout_is_inconclusive():
    assert dv.classify(run(), run("timeout", None, SHA_B))[0] == dv.INCONCLUSIVE


ANALYSIS = {"head_sha": SHA_B}
EMPTY = {"consumers": [], "unreadable": []}


def v(outcome, project="billing"):
    return {"project": project, "outcome": outcome, "reason": outcome}


def test_policy_blocks_regression():
    assert pe.decide(ANALYSIS, EMPTY, [v(dv.REGRESSION)], SHA_B)[0] == pe.BLOCKED


def test_policy_superseded_when_head_moves():
    assert pe.decide(ANALYSIS, EMPTY, [v(dv.COMPATIBLE)], "c" * 40)[0] == pe.SUPERSEDED


def test_policy_incomplete_on_bad_evidence_or_unreadable_project():
    assert pe.decide(ANALYSIS, EMPTY, [v(dv.INCONCLUSIVE)], SHA_B)[0] == pe.INCOMPLETE_EVIDENCE
    unreadable = {"consumers": [], "unreadable": [{"project": "x", "reason": "403"}]}
    assert pe.decide(ANALYSIS, unreadable, [], SHA_B)[0] == pe.INCOMPLETE_EVIDENCE


def test_policy_manual_review_on_pre_existing_failure():
    assert pe.decide(ANALYSIS, EMPTY, [v(dv.PRE_EXISTING_FAILURE)], SHA_B)[0] == pe.REQUIRES_MANUAL_REVIEW


def test_policy_manual_review_when_tests_miss_a_static_break():
    discovery = {"unreadable": [], "consumers": [{"project": "billing", "static_breaks": [{"x": 1}]}]}
    assert pe.decide(ANALYSIS, discovery, [v(dv.COMPATIBLE)], SHA_B)[0] == pe.REQUIRES_MANUAL_REVIEW


def test_policy_ready_when_compatible_or_nothing_affected():
    assert pe.decide(ANALYSIS, EMPTY, [v(dv.COMPATIBLE)], SHA_B)[0] == pe.READY_FOR_APPROVAL
    assert pe.decide(ANALYSIS, EMPTY, [], SHA_B)[0] == pe.READY_FOR_APPROVAL
