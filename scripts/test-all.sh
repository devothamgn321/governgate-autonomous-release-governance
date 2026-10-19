#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
if [[ -n "${PYTHON:-}" ]]; then
  python_cmd="$PYTHON"
elif [[ -x "$root_dir/.venv/bin/python" ]]; then
  python_cmd="$root_dir/.venv/bin/python"
else
  python_cmd=python3
fi
python_bin="$(command -v "$python_cmd" || printf '%s' "$python_cmd")"
if [[ "$python_bin" != /* ]]; then
  python_bin="$(cd "$(dirname "$python_bin")" && pwd)/$(basename "$python_bin")"
fi

"$python_bin" -m pytest -q core-auth-sdk/tests
(
  cd billing-service
  PYTHONPATH="../core-auth-sdk/src${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" -m pytest -q
)
(
  cd notification-service
  PYTHONPATH="../core-auth-sdk/src${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" -m pytest -q
)
"$python_bin" -m pytest -q governgate/tests
