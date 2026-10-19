"""A fake GitLab for tests.

It serves files from local fixture folders, and when GovernGate "starts a
consumer pipeline" it really runs that consumer's pytest suite against the
requested SDK version (via PYTHONPATH), then returns the log in the same
format the real CI job prints. So the end-to-end test exercises real test
outcomes, not canned answers.
"""

import os
import pathlib
import subprocess
import sys

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

UPSTREAM_ID = 1
BILLING_ID = 2
NOTIFICATION_ID = 3
GOVERNGATE_ID = 4

# Commit SHA -> SDK fixture folder.
SDK_BY_SHA = {
    "a" * 40: "sdk_v1",          # MR base (main)
    "b" * 40: "sdk_candidate",   # MR head: breaking change
    "c" * 40: "sdk_safe",        # remediation branch
}


class FakeGitLab:
    def __init__(self, head_sha="b" * 40, base_sha="a" * 40, wrong_install=False, consumer_baseline_broken=False):
        self.head_sha = head_sha
        self.base_sha = base_sha
        self.wrong_install = wrong_install
        self.consumer_baseline_broken = consumer_baseline_broken
        self.pipelines = {}
        self.notes = []
        self.commits = []
        self.merge_requests = []
        self._next_pipeline = 1000
        self.projects = {
            UPSTREAM_ID: ("governgate2/core-auth-sdk", None),
            BILLING_ID: ("governgate2/billing-service", "billing"),
            NOTIFICATION_ID: ("governgate2/notification-service", "notification"),
            GOVERNGATE_ID: ("governgate2/governgate", None),
        }

    # ---- projects / files ----
    def list_group_projects(self, group_id):
        return [{"id": pid, "path_with_namespace": name, "default_branch": "main"} for pid, (name, _) in self.projects.items()]

    def _root(self, project_id, ref):
        if project_id == UPSTREAM_ID:
            return FIXTURES / SDK_BY_SHA[ref]
        folder = self.projects[project_id][1]
        return FIXTURES / folder if folder else None

    def get_file(self, project_id, path, ref):
        root = self._root(project_id, ref)
        if root is None or not (root / path).is_file():
            return None
        return (root / path).read_text()

    def list_tree(self, project_id, ref):
        root = self._root(project_id, ref)
        return [{"type": "blob", "path": p.relative_to(root).as_posix()} for p in root.rglob("*.py")]

    # ---- merge requests ----
    def get_merge_request(self, project_id, mr_iid):
        return {"iid": mr_iid, "target_branch": "main", "source_branch": "feature/explicit-algorithm",
                "diff_refs": {"base_sha": self.base_sha, "head_sha": self.head_sha}}

    def list_mr_diffs(self, project_id, mr_iid):
        return [{"old_path": "src/core_auth_sdk/tokens.py", "new_path": "src/core_auth_sdk/tokens.py",
                 "new_file": False, "deleted_file": False},
                {"old_path": "tests/test_tokens.py", "new_path": "tests/test_tokens.py",
                 "new_file": False, "deleted_file": False}]

    def post_mr_note(self, project_id, mr_iid, body):
        self.notes.append(body)
        return {"id": len(self.notes)}

    def commit_files(self, project_id, branch, start_sha, message, files):
        self.commits.append({"branch": branch, "start_sha": start_sha, "files": files})
        return {"id": "d" * 40}

    def create_merge_request(self, project_id, source_branch, target_branch, title, description):
        self.merge_requests.append({"source": source_branch, "target": target_branch, "title": title})
        return {"iid": 2, "web_url": "https://gitlab.example/mr/2"}

    # ---- pipelines: really run the consumer tests ----
    def create_pipeline(self, project_id, ref, variables):
        sdk_sha = variables["SDK_REF"]
        sdk_dir = FIXTURES / SDK_BY_SHA[sdk_sha]
        consumer_dir = FIXTURES / self.projects[project_id][1]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(sdk_dir / "src") + os.pathsep + str(consumer_dir)
        if self.consumer_baseline_broken and sdk_sha == self.base_sha:
            env["AUTH_SECRET"] = ""  # not used by tests, but we force a failure below
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                                cwd=consumer_dir, env=env, capture_output=True, text=True)
        passed = result.returncode == 0
        if self.consumer_baseline_broken and sdk_sha == self.base_sha:
            passed = False
        installed = ("e" * 40) if self.wrong_install else sdk_sha
        log = "SDK version: x\nSDK commit: " + installed + "\n" + result.stdout + result.stderr
        self._next_pipeline += 1
        pid = self._next_pipeline
        self.pipelines[pid] = {"project_id": project_id, "status": "success" if passed else "failed", "log": log}
        return {"id": pid, "sha": "f" * 40, "web_url": "https://gitlab.example/pipelines/" + str(pid)}

    def wait_for_pipeline(self, project_id, pipeline_id, timeout_seconds=900, poll_seconds=10):
        return {"id": pipeline_id, "status": self.pipelines[pipeline_id]["status"]}

    def list_pipeline_jobs(self, project_id, pipeline_id):
        return [{"id": pipeline_id * 10, "name": "integration-tests", "status": self.pipelines[pipeline_id]["status"]}]

    def get_job_log(self, project_id, job_id):
        return self.pipelines[job_id // 10]["log"]


class FakeNemotron:
    """Stands in for Nemotron: returns a fixed answer and records the call."""

    def __init__(self, fix_source=None):
        self.calls = []
        self.fix_source = fix_source

    @property
    def enabled(self):
        return True

    def complete_json(self, system, user, reasoning=False, max_tokens=1500):
        record = {"model": "fake-nemotron", "status": "ok", "latency_seconds": 0.0}
        self.calls.append(record)
        if "fix backward-compatibility" in system:
            if self.fix_source is None:
                return None, record
            return {"strategy": "make algorithm optional, default to the pinned constant",
                    "function_source": self.fix_source, "risks": "none"}, record
        return {"root_cause": "billing calls verify_token with two arguments; the SDK now needs three.",
                "mechanism": "TypeError at call time.", "confidence": "high",
                "recommended_action": "Make algorithm optional with the SDK's pinned HS256 default."}, record
