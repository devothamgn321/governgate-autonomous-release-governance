"""Exercise actual container isolation and the demo matrix without GitLab tokens."""
import sys
from pathlib import Path
from governgate.controller import sandbox

fixtures = Path('tests/fixtures')
def files(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}

for consumer in ['billing', 'notification']:
    for sdk in ['sdk_v1', 'sdk_candidate']:
        result = sandbox(sys.argv[1], files(fixtures / sdk), files(fixtures / consumer))
        expected = 'FAIL' if (consumer, sdk) == ('billing', 'sdk_candidate') else 'PASS'
        print(consumer, sdk, result['status'], flush=True)
        if result['status'] != expected:
            print(result)
            raise SystemExit(1)
# Check isolation from inside the worker. This payload is deliberately adversarial.
probe = b'''import os, socket
from pathlib import Path
def test_isolation():
    assert os.getuid() == 65534
    assert not any(k in os.environ for k in ['GOVERNGATE_API_TOKEN', 'NEBIUS_API_KEY', 'CI_JOB_TOKEN'])
    assert not Path('/var/run/docker.sock').exists()
    assert not Path('/builds').exists()
    try:
        Path('/forbidden').write_text('bad')
    except OSError:
        pass
    else:
        assert False, 'root filesystem writable'
    with socket.socket() as s:
        s.settimeout(1)
        assert s.connect_ex(('1.1.1.1', 443)) != 0
'''
result = sandbox(sys.argv[1], files(fixtures / 'sdk_v1'), {'tests/test_isolation.py': probe})
print('isolation', result['status'])
if result['status'] != 'PASS':
    print(result)
    raise SystemExit(1)

# A candidate that exits pytest during import cannot produce a passing report.
early_exit = files(fixtures / 'sdk_candidate')
early_exit['src/core_auth_sdk/__init__.py'] = b'import os\nos._exit(0)\n'
result = sandbox(sys.argv[1], early_exit, files(fixtures / 'billing'))
print('candidate early exit', result['status'])
if result['status'] != 'INCONCLUSIVE':
    print(result)
    raise SystemExit(1)

# A hostile candidate can forge pytest's JUnit file because pytest and the SDK
# share a UID. Demonstrate the limitation and verify passing evidence fails
# closed to manual review instead of making the gate pass.
report_forgery = files(fixtures / 'sdk_candidate')
report_forgery['src/core_auth_sdk/__init__.py'] = b'''import os, sys
from pathlib import Path
report = Path(sys.argv[sys.argv.index("--junitxml") + 1])
tests = ["test_valid_token_authorizes_payment", "test_forged_token_is_rejected",
         "test_expired_token_is_rejected", "test_non_positive_amount_is_rejected",
         "test_missing_secret_fails_closed"]
cases = "".join(f'<testcase classname="test_payments" name="{name}" />' for name in tests)
report.write_text(f'<testsuite tests="{len(tests)}">{cases}</testsuite>')
os._exit(0)
'''
forged = sandbox(sys.argv[1], report_forgery, files(fixtures / 'billing'))
print('candidate JUnit forgery', forged['status'], flush=True)
matrix = {'billing-service': {'baseline': {'status': 'PASS'}, 'candidate': forged},
          'notification-service': {'baseline': {'status': 'PASS'}, 'candidate': forged}}
from governgate.controller import verdict
if forged['status'] != 'PASS' or verdict(matrix) != 'REQUIRES_MANUAL_REVIEW':
    print(forged)
    raise SystemExit(1)

# Flooding stdout must hit the controller cap and terminate the container.
log_flood = files(fixtures / 'sdk_candidate')
log_flood['src/core_auth_sdk/__init__.py'] = b'import sys\nsys.stdout.write("x" * 2000000)\nsys.stdout.flush()\n'
result = sandbox(sys.argv[1], log_flood, files(fixtures / 'billing'))
print('candidate log flood', result['status'])
if result['status'] != 'INCONCLUSIVE' or 'output limit' not in result.get('reason', ''):
    print(result)
    raise SystemExit(1)
