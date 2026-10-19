"""Thin GitLab REST client.

Only the calls GovernGate needs. All of them go through `_request`, so tests
can swap in a fake client with the same public methods.

Auth: a group access token in GOVERNGATE_API_TOKEN (scopes: api).
It is read from the environment only, never logged.
"""

import os
import time
import urllib.parse

import requests


class GitLabError(Exception):
    """Raised when a GitLab API call fails."""


class GitLabClient:
    def __init__(self, base_url=None, token=None, timeout=30):
        self.base_url = (base_url or os.environ.get("CI_API_V4_URL") or "https://gitlab.com/api/v4").rstrip("/")
        self.token = token or os.environ.get("GOVERNGATE_API_TOKEN")
        if not self.token:
            # Fail closed: without a token GovernGate cannot gather evidence.
            raise GitLabError("GOVERNGATE_API_TOKEN is not set")
        self.timeout = timeout

    # ---------- plumbing ----------

    def _request(self, method, path, **kwargs):
        url = self.base_url + path
        headers = {"PRIVATE-TOKEN": self.token}
        response = requests.request(method, url, headers=headers, timeout=self.timeout, allow_redirects=False, **kwargs)
        if response.status_code >= 300:
            raise GitLabError(method + " " + path + " -> " + str(response.status_code))
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        return response.text

    def _list(self, path, params=None):
        """Read every page; fail rather than silently truncate or loop forever."""
        result = []
        previous = None
        for page in range(1, 1001):
            batch = self._request("GET", path, params={**(params or {}), "per_page": 100, "page": page})
            if not isinstance(batch, list):
                raise GitLabError("Invalid paginated response")
            if batch and batch == previous:
                raise GitLabError("Pagination repeated a page")
            result.extend(batch)
            if len(batch) < 100:
                return result
            previous = batch
        raise GitLabError("Pagination limit exceeded")

    @staticmethod
    def _enc(value):
        return urllib.parse.quote(str(value), safe="")

    # ---------- projects and files ----------

    def get_project(self, project_id):
        return self._request("GET", "/projects/" + self._enc(project_id))

    def list_group_projects(self, group_id):
        return self._list("/groups/" + self._enc(group_id) + "/projects",
                             params={"per_page": 100, "include_subgroups": "true", "archived": "false"})

    def get_file(self, project_id, path, ref):
        """Return file text, or None if the file does not exist."""
        try:
            return self._request("GET", "/projects/" + self._enc(project_id) + "/repository/files/"
                                 + self._enc(path) + "/raw", params={"ref": ref})
        except GitLabError as error:
            if " 404" in str(error):
                return None
            raise

    def list_tree(self, project_id, ref):
        return self._list("/projects/" + self._enc(project_id) + "/repository/tree",
                             params={"ref": ref, "recursive": "true", "per_page": 100})

    def get_branch_sha(self, project_id, branch):
        branch_info = self._request("GET", "/projects/" + self._enc(project_id) + "/repository/branches/" + self._enc(branch))
        return branch_info["commit"]["id"]

    # ---------- merge requests ----------

    def get_merge_request(self, project_id, mr_iid):
        return self._request("GET", "/projects/" + self._enc(project_id) + "/merge_requests/" + str(mr_iid))

    def list_mr_diffs(self, project_id, mr_iid):
        return self._list("/projects/" + self._enc(project_id) + "/merge_requests/" + str(mr_iid) + "/diffs",
                             params={"per_page": 100})

    def post_mr_note(self, project_id, mr_iid, body):
        return self._request("POST", "/projects/" + self._enc(project_id) + "/merge_requests/" + str(mr_iid) + "/notes",
                             data={"body": body})

    def commit_files(self, project_id, branch, start_sha, message, files):
        """Create `branch` from `start_sha` and commit {path: content} in one commit."""
        actions = [{"action": "update", "file_path": p, "content": c} for p, c in files.items()]
        return self._request("POST", "/projects/" + self._enc(project_id) + "/repository/commits",
                             json={"branch": branch, "start_sha": start_sha, "commit_message": message, "actions": actions})

    def create_merge_request(self, project_id, source_branch, target_branch, title, description):
        return self._request("POST", "/projects/" + self._enc(project_id) + "/merge_requests",
                             json={"source_branch": source_branch, "target_branch": target_branch,
                                   "title": title, "description": description})

    # ---------- pipelines ----------

    def create_pipeline(self, project_id, ref, variables):
        payload = {"ref": ref, "variables": [{"key": k, "value": v} for k, v in variables.items()]}
        return self._request("POST", "/projects/" + self._enc(project_id) + "/pipeline", json=payload)

    def get_pipeline(self, project_id, pipeline_id):
        return self._request("GET", "/projects/" + self._enc(project_id) + "/pipelines/" + str(pipeline_id))

    def list_pipeline_jobs(self, project_id, pipeline_id):
        return self._list("/projects/" + self._enc(project_id) + "/pipelines/" + str(pipeline_id) + "/jobs")

    def get_job_log(self, project_id, job_id):
        return self._request("GET", "/projects/" + self._enc(project_id) + "/jobs/" + str(job_id) + "/trace")

    def wait_for_pipeline(self, project_id, pipeline_id, timeout_seconds=900, poll_seconds=10):
        """Poll until the pipeline finishes. Returns the pipeline, or None on timeout."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            pipeline = self.get_pipeline(project_id, pipeline_id)
            if pipeline["status"] in ("success", "failed", "canceled", "skipped"):
                return pipeline
            time.sleep(poll_seconds)
        return None
