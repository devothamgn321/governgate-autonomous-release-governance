"""Runs only inside the networkless, unprivileged worker container."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worker_results import summarize_junit

workspace = tempfile.TemporaryDirectory(prefix='governgate-worker-')
root = Path(workspace.name)
root.chmod(0o755)  # root-owned input tree is readable, not writable, by test code.
with tarfile.open(fileobj=sys.stdin.buffer, mode='r|') as archive:
    archive.extractall(root, filter='data')
# Ignore SDK build scripts and consumer requirements: this demo uses pure Python
# src/core_auth_sdk and a fixed, reviewed dependency set baked into the worker.
# Exact source bytes/commit are verified by the controller before packaging.
source = root / 'sdk/src'
consumer = root / 'consumer'
if not (source / 'core_auth_sdk/__init__.py').is_file() or not (consumer / 'tests').is_dir():
    raise SystemExit(2)
os.environ['PYTHONPATH'] = str(source) + os.pathsep + str(consumer)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
report_workspace = tempfile.TemporaryDirectory(prefix='governgate-junit-')
report_directory = Path(report_workspace.name)
report_directory.chmod(0o711)
report = report_directory / 'report.xml'
report.touch(mode=0o666)
report.chmod(0o666)

def drop_privileges():
    # Candidate SDK code and consumer tests run without privileges. The JUnit
    # report is written by this same untrusted pytest process and is not trusted.
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)

result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                         '--junitxml', str(report), 'tests'], cwd=consumer,
                        env={'PATH': os.defpath, 'PYTHONPATH': os.environ['PYTHONPATH'],
                             'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                             'PYTHONDONTWRITEBYTECODE': '1'}, check=False,
                        preexec_fn=drop_privileges)

# The SDK is untrusted code and can terminate pytest during import. A zero exit
# status alone is not evidence that any fixed consumer tests actually ran.
expected = set()
for test_file in (consumer / 'tests').rglob('test_*.py'):
    module = test_file.relative_to(consumer / 'tests').with_suffix('').as_posix().replace('/', '.')
    try:
        tree = ast.parse(test_file.read_bytes(), filename=str(test_file))
    except (SyntaxError, UnicodeDecodeError):
        continue
    expected.update((module, node.name) for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith('test_'))

try:
    summary = summarize_junit(report, expected)
except (OSError, ET.ParseError, ValueError):
    summary = {'status': 'INCONCLUSIVE', 'tests': 0, 'expected_tests': len(expected),
               'failures': 0, 'errors': 0, 'missing_tests': sorted(name for _, name in expected)}
report_workspace.cleanup()
print('GOVERNGATE_RESULT ' + json.dumps(summary, sort_keys=True), flush=True)
if result.returncode == 0 and summary['status'] == 'PASS':
    raise SystemExit(0)
if result.returncode == 1 and summary['status'] == 'FAIL':
    raise SystemExit(1)
raise SystemExit(2)
