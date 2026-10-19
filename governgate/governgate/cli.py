"""Command line entry point, run as a CI job in the upstream library's MR pipeline.

    governgate check          full run; exit 0 only for READY_FOR_APPROVAL
    governgate verify-ledger  check a sealed evidence file

Everything it needs comes from GitLab's predefined CI variables plus:
    GOVERNGATE_API_TOKEN   group access token (api scope)       - required
    NEBIUS_API_KEY         Nemotron via Token Factory            - optional
    GOVERNGATE_AUTOFIX     "true" to open a remediation MR       - optional
    GOVERNGATE_SIGNING_KEY HMAC key for the evidence ledger      - optional
"""

import argparse
import json
import os
import re
import sys

from governgate import __version__
from governgate import consumer_discovery, differential_verifier, evidence_ledger
from governgate import impact_reporter, policy_engine, remediation, root_cause, semantic_analyzer
from governgate.gitlab_client import GitLabClient
from governgate.nemotron_client import NemotronClient

EVIDENCE_FILE = "governgate-evidence.json"
REPORT_FILE = "governgate-report.md"


def _library_names(client, project_id, ref):
    name = os.environ.get("GOVERNGATE_LIBRARY")
    if not name:
        pyproject = client.get_file(project_id, "pyproject.toml", ref) or ""
        match = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
        if not match:
            raise SystemExit("GovernGate: cannot find the library name; set GOVERNGATE_LIBRARY")
        name = match.group(1)
    import_name = os.environ.get("GOVERNGATE_IMPORT_NAME") or name.replace("-", "_")
    return name, import_name


def run_check(client, nemotron, project_id, mr_iid, group_id, autofix=False, timeout_seconds=900):
    mr = client.get_merge_request(project_id, mr_iid)
    library, import_name = _library_names(client, project_id, mr["diff_refs"]["head_sha"])

    analysis = semantic_analyzer.analyze_merge_request(client, project_id, mr)
    new_required = {c["symbol"]: c["new_required"] for c in analysis["changes"]}
    discovery = consumer_discovery.discover_consumers(client, group_id, project_id, library, import_name,
                                                      analysis["changes"], new_required)

    verifications = []
    for consumer in discovery["consumers"]:
        if consumer["needs_verification"]:
            verifications.append(differential_verifier.verify_consumer(
                client, consumer, analysis["base_sha"], analysis["head_sha"], timeout_seconds))

    root_causes = []
    for v in verifications:
        if v["outcome"] == differential_verifier.REGRESSION:
            consumer = next(c for c in discovery["consumers"] if c["project"] == v["project"])
            change = next((c for c in analysis["changes"] if c["breaking"]
                           and any(s["symbol"] == c["symbol"] for s in consumer["call_sites"])), None)
            if change:
                explanation, _ = root_cause.explain(nemotron, change, v, consumer)
                root_causes.append({"project": v["project"], "change": change, "explanation": explanation})

    head_now = client.get_merge_request(project_id, mr_iid)["diff_refs"]["head_sha"]
    verdict, reasons = policy_engine.decide(analysis, discovery, verifications, head_now)

    remediation_result = None
    if autofix and verdict == policy_engine.BLOCKED and root_causes:
        remediation_result = _remediate(client, nemotron, project_id, mr, analysis, root_causes[0]["change"])

    record = {
        "governgate_version": __version__,
        "project_id": project_id,
        "mr_iid": mr_iid,
        "pipeline_id": os.environ.get("CI_PIPELINE_ID"),
        "library": library,
        "analysis": analysis,
        "discovery": discovery,
        "verifications": verifications,
        "root_causes": root_causes,
        "remediation": {k: v for k, v in (remediation_result or {}).items() if k != "patched_module"} or None,
        "model_calls": nemotron.calls,
        "verdict": verdict,
        "verdict_reasons": reasons,
    }
    return record


def _remediate(client, nemotron, project_id, mr, analysis, change):
    original = client.get_file(project_id, change["module"], analysis["base_sha"])
    candidate = client.get_file(project_id, change["module"], analysis["head_sha"])
    proposal = remediation.propose_fix(nemotron, original, candidate, change)
    if proposal["status"] != "validated":
        return proposal
    branch = "governgate/fix-mr-" + str(mr["iid"])
    client.commit_files(project_id, branch, analysis["head_sha"],
                        "GovernGate: restore backward compatibility of " + change["symbol"] + "\n\n" + (proposal.get("strategy") or ""),
                        {change["module"]: proposal["patched_module"]})
    fix_mr = client.create_merge_request(
        project_id, branch, mr["target_branch"],
        "GovernGate fix for !" + str(mr["iid"]) + ": keep " + change["symbol"] + " backward compatible",
        "Proposed by GovernGate (Nemotron) after !" + str(mr["iid"]) + " broke a downstream consumer.\n\n"
        "**Strategy:** " + str(proposal.get("strategy")) + "\n\n**Risks:** " + str(proposal.get("risks"))
        + "\n\nThis MR must pass the SDK security tests and a fresh GovernGate check before anyone can merge it.")
    proposal["merge_request_url"] = fix_mr.get("web_url")
    proposal["branch"] = branch
    return proposal


def main(argv=None):
    parser = argparse.ArgumentParser(prog="governgate")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    verify = sub.add_parser("verify-ledger")
    verify.add_argument("path")
    args = parser.parse_args(argv)

    if args.command == "verify-ledger":
        try:
            with open(args.path, encoding="utf-8") as handle:
                ok = evidence_ledger.verify(json.load(handle))
        except (OSError, ValueError, KeyError, TypeError):
            ok = False
        print("ledger " + ("VALID" if ok else "INVALID"))
        return 0 if ok else 1

    print("Legacy MR execution is disabled. Use python -m governgate.controller on the protected controller.")
    return 1



if __name__ == "__main__":
    sys.exit(main())
