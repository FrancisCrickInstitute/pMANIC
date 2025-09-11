#!/usr/bin/env bash
set -euo pipefail

echo "Running MANIC test suite..."

if command -v uv >/dev/null 2>&1; then
  echo "Detected uv; running: uv run pytest -q"
  uv run pytest -q
  exit $?
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "Using .venv; running: python -m pytest -q"
  python -m pytest -q
  exit $?
fi

echo "Running: python -m pytest -q"
python -m pytest -q
