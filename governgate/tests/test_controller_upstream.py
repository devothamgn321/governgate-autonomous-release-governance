import pytest

from governgate.controller import SDK, resolve_upstream_request


class FakeGitLab:
    def __init__(self, *, project_id=SDK, source="merge_request_event",
                 ref="refs/merge-requests/42/head", sha="a" * 40,
                 job_name="governgate-impact", mr_sha="a" * 40,
                 downstream_id=789, downstream_project=87601227):
        self.pipeline = {"project_id": project_id, "source": source, "ref": ref, "sha": sha}
        self.job = {"id": 456, "name": job_name, "pipeline": {"id": 123},
                    "downstream_pipeline": {"id": downstream_id, "project_id": downstream_project}}
        self.mr = {"diff_refs": {"head_sha": mr_sha}}

    def get_pipeline(self, project_id, pipeline_id):
        assert project_id == SDK
        assert pipeline_id == 123
        return self.pipeline

    def list_pipeline_trigger_jobs(self, project_id, pipeline_id):
        assert project_id == SDK
        assert pipeline_id == 123
        return [self.job]

    def get_merge_request(self, project_id, iid):
        assert project_id == SDK
        assert iid == 42
        return self.mr


def test_resolves_mr_from_verified_upstream_pipeline_and_bridge():
    assert resolve_upstream_request(FakeGitLab(), SDK, "123", "456", "789") == (42, "a" * 40)


@pytest.mark.parametrize("kwargs", [
    {"project_id": SDK + 1},
    {"source": "push"},
    {"ref": "refs/merge-requests/42/merge"},
    {"job_name": "untrusted-job"},
    {"mr_sha": "b" * 40},
    {"downstream_id": 790},
    {"downstream_project": 12345},
])
def test_rejects_untrusted_or_mismatched_upstream_identity(kwargs):
    with pytest.raises(ValueError):
        resolve_upstream_request(FakeGitLab(**kwargs), SDK, "123", "456", "789")


def test_rejects_invalid_upstream_identifiers():
    with pytest.raises(ValueError):
        resolve_upstream_request(FakeGitLab(), SDK + 1, "123", "456", "789")
    with pytest.raises(ValueError):
        resolve_upstream_request(FakeGitLab(), SDK, "0", "456", "789")
    with pytest.raises(ValueError):
        resolve_upstream_request(FakeGitLab(), SDK, "123", "456", "789", current_project_id=SDK)
