"""Trusted controller. Repository contents are data here, never imported or installed.

This demo deliberately supports only the fixed SDK and two known consumers. It
runs BOTH consumers against both revisions, independent of static predictions.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import subprocess
import tarfile
import tempfile
import uuid
import zipfile

import requests

from governgate.gitlab_client import GitLabClient, GitLabError
from governgate import evidence_ledger

API = "https://gitlab.com/api/v4"
CONTROLLER = 87601227
SDK = 87600355
CONSUMERS = {87601313: "billing-service", 87601329: "notification-service"}
SHA = re.compile(r"[0-9a-f]{40}\Z")
MR_REF = re.compile(r"refs/merge-requests/([1-9][0-9]*)/head\Z")
MAX_BYTES = 20 * 1024 * 1024
MAX_WORKER_LOG_BYTES = 1024 * 1024


def require_sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("A full immutable commit SHA is required")
    return value


def snapshot(client, project, sha):
    """Bind every archive byte to GitLab's SHA-256 metadata at an immutable commit."""
    require_sha(sha)
    commit = client._request("GET", f"/projects/{project}/repository/commits/{sha}")
    if commit.get("id") != sha:
        raise ValueError("Commit identity mismatch")
    tree = client.list_tree(project, sha)
    blobs = {x["path"]: x for x in tree if x["type"] == "blob"}
    if not blobs or len(blobs) > 1000 or any(x["type"] not in ("blob", "tree") for x in tree):
        raise ValueError("Unsupported or excessive repository tree")
    if any(x.get("mode") not in ("100644", "100755") for x in blobs.values()):
        raise ValueError("Symlinks and special files are unsupported")
    with requests.get(f"{API}/projects/{project}/repository/archive.zip", params={"sha": sha},
                      headers={"PRIVATE-TOKEN": client.token}, timeout=30,
                      allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise GitLabError("Archive download failed")
        chunks, total = [], 0
        for chunk in response.iter_content(65536):
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError("Archive size limit exceeded")
            chunks.append(chunk)
    archive = b"".join(chunks)
    # GitLab exposes SHA-256 for file content at a pinned ref. Use that stronger
    # digest rather than relying on SHA-1 Git object IDs for evidence integrity.
    for path, item in blobs.items():
        metadata = client._request("GET", f"/projects/{project}/repository/files/{client._enc(path)}",
                                   params={"ref": sha})
        digest = metadata.get("content_sha256", "")
        if metadata.get("commit_id") != sha or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Missing or mismatched source content identity")
        item["content_sha256"] = digest
    files = verify_archive(archive, blobs)
    return files, {"project_id": project, "commit": sha,
                   "archive_sha256": hashlib.sha256(archive).hexdigest(), "files": len(files)}


def verify_archive(archive, blobs):
    files, total = {}, 0
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            parts = PurePosixPath(item.filename).parts
            if len(parts) < 2 or ".." in parts or parts[0] == "/":
                raise ValueError("Unsafe archive path")
            path = "/".join(parts[1:])
            total += item.file_size
            if total > MAX_BYTES or path in files or path not in blobs:
                raise ValueError("Unexpected, duplicate or excessive archive content")
            data = z.read(item)
            content_hash = hashlib.sha256(data).hexdigest()
            if content_hash != blobs[path]["content_sha256"]:
                raise ValueError("Archive does not match the requested Git tree")
            files[path] = data
    if files.keys() != blobs.keys():
        raise ValueError("Incomplete archive")
    return files


def pack_inputs(sdk, consumer):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as tar:
        for prefix, files in (("sdk", sdk), ("consumer", consumer)):
            for path, data in files.items():
                info = tarfile.TarInfo(prefix + "/" + path)
                info.size, info.mode = len(data), 0o444
                tar.addfile(info, io.BytesIO(data))
    return output.getvalue()


def sandbox(image, sdk, consumer, timeout=180):
    """No credentials, network, host mounts or Docker socket enter this container."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Worker image must be resolved to an immutable local image ID")
    name = "governgate-" + uuid.uuid4().hex
    command = ["docker", "run", "--rm", "--name", name, "-i", "--network=none",
               "--read-only", "--cap-drop=ALL", "--cap-add=SETUID", "--cap-add=SETGID",
               "--security-opt=no-new-privileges", "--pids-limit=128", "--memory=512m", "--cpus=1",
               "--tmpfs=/tmp:rw,exec,nosuid,size=256m", "--log-driver=none", image]
    # Pass only Docker transport settings to the Docker client, never to the worker.
    env = {k: os.environ[k] for k in ("PATH", "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH") if k in os.environ}
    def cap_worker_log():
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_WORKER_LOG_BYTES, MAX_WORKER_LOG_BYTES))

    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run(command, input=pack_inputs(sdk, consumer), stdout=log,
                                    stderr=subprocess.STDOUT, timeout=timeout, env=env, check=False,
                                    preexec_fn=cap_worker_log)
            code = result.returncode
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], env=env, capture_output=True, timeout=20, check=False)
            return {"status": "INCONCLUSIVE", "reason": "Worker timed out"}
        log.seek(0, 2)
        size = log.tell()
        log.seek(max(0, size - 32000))
        text = log.read().decode("utf-8", errors="replace")
    if size >= MAX_WORKER_LOG_BYTES or code < 0:
        subprocess.run(["docker", "rm", "-f", name], env=env, capture_output=True,
                       timeout=20, check=False)
        return {"status": "INCONCLUSIVE", "reason": "Worker output limit exceeded or runner terminated",
                "exit_code": code, "log_tail": text}
    # Only the trusted worker's post-pytest structured summary can produce a
    # verdict. A candidate's early os._exit(0) leaves no valid summary.
    summary = None
    for line in reversed(text.splitlines()):
        if line.startswith("GOVERNGATE_RESULT "):
            try:
                parsed = json.loads(line[len("GOVERNGATE_RESULT "):])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                summary = parsed
                break
    status = "INCONCLUSIVE"
    if summary and summary.get("tests", 0) > 0 and summary.get("expected_tests", 0) > 0:
        if code == 0 and summary.get("status") == "PASS" and not summary.get("missing_tests"):
            status = "PASS"
        elif code == 1 and summary.get("status") == "FAIL" and not summary.get("missing_tests"):
            status = "FAIL"
    return {"status": status, "exit_code": code,
            "test_summary": summary, "log_tail": text}


def verdict(runs):
    if set(runs) != set(CONSUMERS.values()):
        return "INCOMPLETE_EVIDENCE"
    for pair in runs.values():
        if set(pair) != {"baseline", "candidate"} or any(r.get("status") not in {"PASS", "FAIL"} for r in pair.values()):
            return "INCOMPLETE_EVIDENCE"
    if any(p["baseline"]["status"] != "PASS" for p in runs.values()):
        return "REQUIRES_MANUAL_REVIEW"
    if any(p["candidate"]["status"] == "FAIL" for p in runs.values()):
        return "BLOCKED"
    # Candidate code shares the pytest process that writes JUnit and can forge
    # that report. Passing test output is advisory until results come from an
    # independent trusted reporter; never let it produce a passing gate.
    return "REQUIRES_MANUAL_REVIEW"


def execute(client, iid, expected_head, image):
    mr = client.get_merge_request(SDK, iid)
    if (mr.get("state") != "opened" or mr.get("target_project_id") != SDK
            or mr.get("source_project_id") != SDK or mr.get("target_branch") != "main"):
        raise ValueError("Only open same-project SDK merge requests targeting main are supported")
    head = require_sha(mr["diff_refs"]["head_sha"])
    if head != require_sha(expected_head):
        raise ValueError("Requested MR head is stale")
    # Compare with current target branch, not an old merge base.
    base = require_sha(client.get_branch_sha(SDK, "main"))
    baseline, base_identity = snapshot(client, SDK, base)
    candidate, candidate_identity = snapshot(client, SDK, head)
    record = {"mr_iid": iid, "project_id": SDK, "baseline": base_identity,
              "candidate": candidate_identity, "worker_image": image, "consumers": {}, "runs": {}}
    for project, name in CONSUMERS.items():
        sha = require_sha(client.get_branch_sha(project, "main"))
        consumer, identity = snapshot(client, project, sha)
        record["consumers"][name] = identity
        record["runs"][name] = {"baseline": sandbox(image, baseline, consumer),
                               "candidate": sandbox(image, candidate, consumer)}
    record["verdict"] = verdict(record["runs"])
    record["evidence_limitations"] = [
        "Untrusted candidate code can forge the pytest JUnit report; passing candidate tests require manual review."
    ]
    if (client.get_merge_request(SDK, iid)["diff_refs"]["head_sha"] != head
            or client.get_branch_sha(SDK, "main") != base
            or any(client.get_branch_sha(project, "main") != record["consumers"][name]["commit"]
                   for project, name in CONSUMERS.items())):
        record["verdict"] = "SUPERSEDED"
    return record


def resolve_upstream_request(client, upstream_project, pipeline_id, job_id,
                             current_pipeline_id, current_project_id=CONTROLLER):
    """Resolve the SDK MR from GitLab's immutable downstream relationship."""
    if str(upstream_project) != str(SDK):
        raise ValueError("Unexpected upstream project")
    if not str(pipeline_id).isdigit() or int(pipeline_id) < 1:
        raise ValueError("Missing upstream pipeline identity")
    if not str(job_id).isdigit() or int(job_id) < 1:
        raise ValueError("Missing upstream bridge identity")
    if not str(current_pipeline_id).isdigit() or int(current_pipeline_id) < 1:
        raise ValueError("Missing current controller pipeline identity")
    if str(current_project_id) != str(CONTROLLER):
        raise ValueError("Unexpected controller project")
    pipeline = client.get_pipeline(SDK, int(pipeline_id))
    if (int(pipeline.get("project_id", 0)) != SDK
            or pipeline.get("source") != "merge_request_event"):
        raise ValueError("Upstream pipeline is not an SDK merge-request pipeline")
    match = MR_REF.fullmatch(pipeline.get("ref", ""))
    if not match:
        raise ValueError("Upstream pipeline is not a detached merge-request pipeline")
    head = require_sha(pipeline.get("sha"))
    # Bridge jobs are not reliably returned by the regular Jobs API. Use the
    # pipeline-scoped trigger_jobs endpoint and bind the downstream relation.
    jobs = client.list_pipeline_trigger_jobs(SDK, int(pipeline_id))
    job = next((item for item in jobs if int(item.get("id", 0)) == int(job_id)), None)
    downstream = (job or {}).get("downstream_pipeline") or {}
    if (not job or job.get("name") != "governgate-impact"
            or int(job.get("pipeline", {}).get("id", 0)) != int(pipeline_id)
            or int(downstream.get("id", 0)) != int(current_pipeline_id)
            or int(downstream.get("project_id", 0)) != CONTROLLER):
        raise ValueError("Upstream job is not the GovernGate bridge for this pipeline")
    iid = int(match.group(1))
    mr = client.get_merge_request(SDK, iid)
    if mr.get("diff_refs", {}).get("head_sha") != head:
        raise ValueError("Upstream pipeline SHA does not match the current MR head")
    return iid, head


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    args = parser.parse_args(argv)
    record = {"verdict": "INCOMPLETE_EVIDENCE", "project_id": SDK}
    try:
        if (os.environ.get("CI_PROJECT_ID") != str(CONTROLLER)
                or os.environ.get("CI_COMMIT_BRANCH") != "main"
                or os.environ.get("CI_COMMIT_REF_PROTECTED") != "true"
                or os.environ.get("CI_PIPELINE_SOURCE") != "pipeline"):
            raise ValueError("Protected trusted-controller execution is required")
        client = GitLabClient(base_url=API)
        iid, head = resolve_upstream_request(
            client, os.environ.get("CI_UPSTREAM_PROJECT_ID"),
            os.environ.get("CI_UPSTREAM_PIPELINE_ID"), os.environ.get("CI_UPSTREAM_JOB_ID"),
            os.environ.get("CI_PIPELINE_ID"), os.environ.get("CI_PROJECT_ID"))
        record["mr_iid"] = iid
        record = execute(client, iid, head, args.image)
    except Exception as error:
        # Do not print API bodies, credential-bearing URLs or arbitrary exception text.
        record = {**record, "verdict": "INCOMPLETE_EVIDENCE", "error_type": type(error).__name__}
    Path("governgate-evidence.json").write_text(json.dumps(evidence_ledger.seal(record), indent=2))
    lines = ["# GovernGate: " + record["verdict"], "", f"SDK MR !{record.get('mr_iid') or 'unknown'}"]
    for name, pair in record.get("runs", {}).items():
        lines.append(f"- {name}: baseline {pair['baseline']['status']}; candidate {pair['candidate']['status']}")
    for limitation in record.get("evidence_limitations", []):
        lines.append("Evidence limitation: " + limitation)
    if "error_type" in record:
        lines.append("Verification unavailable: " + record["error_type"])
    Path("governgate-report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if record["verdict"] == "READY_FOR_APPROVAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
