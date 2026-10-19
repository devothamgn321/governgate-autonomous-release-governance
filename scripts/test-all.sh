#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
python_bin="$(command -v "${PYTHON:-python}")"
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
