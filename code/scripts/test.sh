#!/usr/bin/env bash
# Run unit tests for metrics and stats (no API, no runs.csv needed).
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$CODE_ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"
export PYTHONPATH="$CODE_ROOT/src:${PYTHONPATH:-}"

if ! command -v pytest >/dev/null 2>&1; then
  echo "ERROR: pytest not found. Install deps:"
  echo "  pip install -r code/requirements.txt"
  exit 1
fi

exec pytest "$@"
