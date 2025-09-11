#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  uv run python -m src.manic.main
else
  python -m src.manic.main
fi

