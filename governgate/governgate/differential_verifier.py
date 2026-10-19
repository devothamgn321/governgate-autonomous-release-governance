"""Step 3 - Does it actually break?

Runs the SAME consumer commit twice:
    baseline : consumer + SDK at the MR's base commit
    candidate: consumer + SDK at the MR's head commit

Each run is a real GitLab pipeline in the consumer project, started with
SDK_REF=<sha>. The consumer job prints which SDK commit it really installed;
GovernGate checks that against what it asked for. A run whose identity does
not match is thrown out (INVALID_EVIDENCE), never trusted.
"""

import re

REGRESSION = "REGRESSION"                 # baseline passed, candidate failed
COMPATIBLE = "COMPATIBLE"                 # both passed
PRE_EXISTING_FAILURE = "PRE_EXISTING_FAILURE"  # baseline already failed
INCONCLUSIVE = "INCONCLUSIVE"             # timeout, cancel, missing data
INVALID_EVIDENCE = "INVALID_EVIDENCE"     # wrong SDK installed or consumer commit moved

SDK_COMMIT_PATTERN = re.compile(r"SDK commit: ([0-9a-f]{40})")
SUMMARY_PATTERN = re.compile(r"^(?:=+ )?(\d+ (?:passed|failed|errors?)[^=\n]*?) in [0-9.]+s", re.MULTILINE)
FAILED_TEST_PATTERN = re.compile(r"^FAILED (\S+)(?: - (.*))?$", re.MULTILINE)
ERROR_LINE_PATTERN = re.compile(r"^E\s+(\w+(?:Error|Exception)\b.*)$", re.MULTILINE)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TEST_JOB = "integration-tests"


def parse_test_log(log):
    """Extract installed SDK commit, pytest summary, failed tests and first error lines."""
    clean = ANSI.sub("", log)
    commit = SDK_COMMIT_PATTERN.search(clean)
    summary = SUMMARY_PATTERN.findall(clean)
    return {
        "installed_sdk_commit": commit.group(1) if commit else None,
        "summary": summary[-1] if summary else None,
        "failed_tests": [m[0] for m in FAILED_TEST_PATTERN.findall(clean)][:20],
        "errors": list(dict.fromkeys(ERROR_LINE_PATTERN.findall(clean)))[:5],
    }


def run_consumer(client, consumer, sdk_sha, timeout_seconds=900):
    """Start one consumer pipeline against `sdk_sha` and collect its evidence."""
    pipeline = client.create_pipeline(consumer["project_id"], consumer["ref"],
                                      {"SDK_REF": sdk_sha, "GOVERNGATE_RUN": "true"})
    finished = client.wait_for_pipeline(consumer["project_id"], pipeline["id"], timeout_seconds)
    run = {
        "pipeline_id": pipeline["id"],
        "pipeline_url": pipeline.get("web_url"),
        "consumer_sha": pipeline.get("sha"),
        "requested_sdk_sha": sdk_sha,
        "status": finished["status"] if finished else "timeout",
    }
    if not finished:
        return run
    jobs = client.list_pipeline_jobs(consumer["project_id"], pipeline["id"])
    test_job = next((j for j in jobs if j["name"] == TEST_JOB), None)
    if test_job is None:
        run["status"] = "missing_test_job"
        return run
    run["job_id"] = test_job["id"]
    run["job_status"] = test_job["status"]
    run.update(parse_test_log(client.get_job_log(consumer["project_id"], test_job["id"])))
    return run


def classify(baseline, candidate):
    """Turn two runs into one verdict for this consumer."""
    for run in (baseline, candidate):
        if run["status"] in ("timeout", "canceled", "skipped", "missing_test_job"):
            return INCONCLUSIVE, run["status"] + " in pipeline " + str(run["pipeline_id"])
        if run.get("installed_sdk_commit") != run["requested_sdk_sha"]:
            return INVALID_EVIDENCE, ("pipeline " + str(run["pipeline_id"]) + " installed "
                                      + str(run.get("installed_sdk_commit")) + ", expected " + run["requested_sdk_sha"])
    if baseline["consumer_sha"] != candidate["consumer_sha"]:
        return INVALID_EVIDENCE, "consumer commit changed between runs"
    for run in (baseline, candidate):
        if run.get("job_status") != "success" and not run.get("summary"):
            # Failed before any test ran (install error, runner problem): not evidence about the SDK.
            return INCONCLUSIVE, "pipeline " + str(run["pipeline_id"]) + " failed before tests ran"
    base_ok = baseline.get("job_status") == "success"
    cand_ok = candidate.get("job_status") == "success"
    if not base_ok:
        return PRE_EXISTING_FAILURE, "consumer already fails on the baseline SDK"
    if cand_ok:
        return COMPATIBLE, "consumer passes on both SDK versions"
    return REGRESSION, "consumer passes on the baseline SDK and fails on the candidate"


def verify_consumer(client, consumer, base_sha, head_sha, timeout_seconds=900):
    baseline = run_consumer(client, consumer, base_sha, timeout_seconds)
    candidate = run_consumer(client, consumer, head_sha, timeout_seconds)
    outcome, reason = classify(baseline, candidate)
    return {"project": consumer["project"], "outcome": outcome, "reason": reason,
            "baseline": baseline, "candidate": candidate}
