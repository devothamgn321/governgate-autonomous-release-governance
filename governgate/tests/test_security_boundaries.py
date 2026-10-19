import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml
import sys

from governgate import controller, cli, policy_engine
from governgate.gitlab_client import GitLabClient, GitLabError
from governgate.nemotron_client import NemotronClient

sys.path.insert(0, str(Path(__file__).parents[1] / 'ci'))
from worker_results import summarize_junit


def test_tree_pagination_reaches_second_page(monkeypatch):
    client = GitLabClient(token='test')
    calls = []
    def request(method, path, params):
        calls.append(params['page'])
        return [{'path': str(i)} for i in range(100)] if params['page'] == 1 else [{'path': 'late.py'}]
    monkeypatch.setattr(client, '_request', request)
    assert client.list_tree(1, 'a' * 40)[-1]['path'] == 'late.py'
    assert calls == [1, 2]


def test_repeated_pagination_fails_closed(monkeypatch):
    client = GitLabClient(token='test')
    monkeypatch.setattr(client, '_request', lambda *a, **k: [{}] * 100)
    with pytest.raises(GitLabError):
        client.list_tree(1, 'a' * 40)


def archive(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, data in files.items():
            z.writestr('root/' + name, data)
    return out.getvalue()


def blob(data):
    return {'content_sha256': hashlib.sha256(data).hexdigest()}


def test_archive_identity_is_verified_not_taken_from_test_log():
    assert controller.verify_archive(archive({'x.py': b'abc'}), {'x.py': blob(b'abc')}) == {'x.py': b'abc'}
    with pytest.raises(ValueError):
        controller.verify_archive(archive({'x.py': b'different'}), {'x.py': blob(b'abc')})


@pytest.mark.parametrize('files', [{'../escape': b'x'}, {'other.py': b'x'}, {}])
def test_missing_or_unsafe_archive_fails(files):
    with pytest.raises(ValueError):
        controller.verify_archive(archive(files), {'x.py': blob(b'x')})


def test_nebius_explicitly_disabled_even_if_key_exists(monkeypatch):
    monkeypatch.setenv('NEBIUS_API_KEY', 'not-a-real-key')
    assert not NemotronClient(api_key='').enabled


def pairs(billing='PASS', notification='PASS'):
    return {name: {'baseline': {'status': 'PASS'}, 'candidate': {'status': candidate}}
            for name, candidate in [('billing-service', billing), ('notification-service', notification)]}


def test_controller_requires_complete_test_matrix():
    assert controller.verdict(pairs()) == 'REQUIRES_MANUAL_REVIEW'
    assert controller.verdict(pairs('FAIL')) == 'BLOCKED'
    assert controller.verdict(pairs('INCONCLUSIVE')) == 'INCOMPLETE_EVIDENCE'
    assert controller.verdict({}) == 'INCOMPLETE_EVIDENCE'
    runs = pairs(); runs['notification-service']['baseline']['status'] = 'FAIL'
    assert controller.verdict(runs) == 'REQUIRES_MANUAL_REVIEW'


def test_untrusted_context_never_constructs_api_client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CI_PROJECT_ID', str(controller.SDK))
    monkeypatch.setattr(controller, 'GitLabClient', lambda **k: pytest.fail('must not access token'))
    assert controller.main(['--mr', '1', '--head', 'a' * 40, '--image', 'sha256:' + 'b' * 64]) == 1
    evidence = json.loads(Path('governgate-evidence.json').read_text())
    assert 'INCOMPLETE_EVIDENCE' in json.dumps(evidence)
    assert Path('governgate-report.md').exists()


def test_controller_does_not_leak_exception_message(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key, val in {'CI_PROJECT_ID': str(controller.CONTROLLER), 'CI_COMMIT_BRANCH': 'main',
                     'CI_COMMIT_REF_PROTECTED': 'true', 'CI_PIPELINE_SOURCE': 'pipeline'}.items():
        monkeypatch.setenv(key, val)
    def fail(**kwargs):
        raise RuntimeError('secret-test-value')
    monkeypatch.setattr(controller, 'GitLabClient', fail)
    assert controller.main(['--mr', '1', '--head', 'a' * 40, '--image', 'sha256:' + 'b' * 64]) == 1
    assert 'secret-test-value' not in Path('governgate-evidence.json').read_text()


def test_missing_required_verification_never_passes():
    discovery = {'unreadable': [], 'consumers': [{'project': 'billing', 'needs_verification': True}]}
    assert policy_engine.decide({'head_sha': 'a'}, discovery, [], 'a')[0] == 'INCOMPLETE_EVIDENCE'


def test_bridge_forwards_no_variables_or_credentials():
    root = Path(__file__).parents[1]
    bridge = yaml.safe_load((root / 'templates/governgate-check.gitlab-ci.yml').read_text())['governgate-impact']
    assert bridge['stage'] == '.post'
    assert bridge['trigger']['strategy'] == 'mirror'
    assert bridge['trigger']['forward'] == {'yaml_variables': False, 'pipeline_variables': False}
    assert bridge['inherit']['variables'] is False
    assert 'script' not in bridge and 'variables' not in bridge
    docs = list(yaml.safe_load_all((root / '.gitlab-ci.yml').read_text()))
    assert docs[1]['trusted-controller']['environment']['name'] == 'governgate-controller'


def test_worker_receives_no_host_credentials(monkeypatch):
    monkeypatch.setenv('GOVERNGATE_API_TOKEN', 'secret-test-value')
    monkeypatch.setenv('NEBIUS_API_KEY', 'nebius-test-value')
    def run(command, **kwargs):
        assert '--network=none' in command and '--read-only' in command
        assert '--log-driver=none' in command
        assert '--cap-drop=ALL' in command and '--cap-add=SETUID' in command and '--cap-add=SETGID' in command
        assert kwargs['preexec_fn'] is not None
        assert not any(x in command for x in ['--privileged', '-v', '--mount', '-e', '--env-file'])
        assert 'GOVERNGATE_API_TOKEN' not in kwargs['env']
        assert 'NEBIUS_API_KEY' not in kwargs['env']
        assert b'secret-test-value' not in kwargs['input']
        kwargs['stdout'].write(b'GOVERNGATE_RESULT {"status":"PASS","tests":1,"expected_tests":1,"failures":0,"errors":0,"missing_tests":[]}\n')
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(controller.subprocess, 'run', run)
    assert controller.sandbox('sha256:' + 'b' * 64, {}, {})['status'] == 'PASS'


@pytest.mark.parametrize(('xml', 'expected_status'), [
    ('<testsuite tests="0"/>', 'INCONCLUSIVE'),
    ('<testsuite tests="1"><testcase classname="test_api" name="test_login"/></testsuite>', 'PASS'),
    ('<testsuite tests="1"><testcase classname="test_api" name="test_login"><failure/></testcase></testsuite>', 'FAIL'),
    ('<testsuite tests="1"><testcase classname="test_api" name="test_other"/></testsuite>', 'INCONCLUSIVE'),
    ('<!DOCTYPE testsuite [<!ENTITY x "boom">]><testsuite tests="1"><testcase classname="test_api" name="test_login"><failure>&x;</failure></testcase></testsuite>', 'INCONCLUSIVE'),
])
def test_junit_summary_requires_expected_executed_tests(tmp_path, xml, expected_status):
    report = tmp_path / 'junit.xml'
    report.write_text(xml)
    assert summarize_junit(report, {('test_api', 'test_login')})['status'] == expected_status


def test_sandbox_does_not_trust_exit_code_without_worker_summary(monkeypatch):
    def run(command, **kwargs):
        kwargs['stdout'].write(b'candidate says all tests passed\n')
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(controller.subprocess, 'run', run)
    assert controller.sandbox('sha256:' + 'b' * 64, {}, {})['status'] == 'INCONCLUSIVE'


def test_worker_log_limit_fails_closed_and_removes_container(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            kwargs['stdout'].write(b'x' * controller.MAX_WORKER_LOG_BYTES)
            return type('Result', (), {'returncode': -25})()
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(controller.subprocess, 'run', run)
    result = controller.sandbox('sha256:' + 'b' * 64, {}, {})
    assert result['status'] == 'INCONCLUSIVE'
    assert 'output limit' in result['reason']
    assert calls[1][:3] == ['docker', 'rm', '-f']

@pytest.mark.parametrize('mismatch', [None, 'commit', 'digest'])
def test_snapshot_binds_api_metadata_to_requested_commit(monkeypatch, mismatch):
    sha = 'a' * 40
    class Client:
        token = 'test'
        _enc = staticmethod(GitLabClient._enc)
        def list_tree(self, project, ref):
            assert ref == sha
            return [{'path': 'x.py', 'type': 'blob', 'mode': '100644', 'id': 'b' * 40}]
        def _request(self, method, path, **kwargs):
            if '/commits/' in path:
                return {'id': sha}
            assert kwargs['params']['ref'] == sha
            return {'commit_id': 'c' * 40 if mismatch == 'commit' else sha,
                    'content_sha256': '0' * 64 if mismatch == 'digest' else hashlib.sha256(b'abc').hexdigest()}
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield archive({'x.py': b'abc'})
    def get(url, **kwargs):
        assert kwargs['params']['sha'] == sha
        assert kwargs['allow_redirects'] is False
        return Response()
    monkeypatch.setattr(controller.requests, 'get', get)
    if mismatch:
        with pytest.raises(ValueError):
            controller.snapshot(Client(), 1, sha)
    else:
        files, identity = controller.snapshot(Client(), 1, sha)
        assert files == {'x.py': b'abc'} and identity['commit'] == sha
