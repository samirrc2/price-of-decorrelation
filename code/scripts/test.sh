#!/usr/bin/env bash
# Run unit tests for metrics and stats (no API, no runs.csv needed).
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$CODE_ROOT/.." && pwd)"
cd "$CODE_ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"
export PYTHONPATH="$CODE_ROOT/src:${PYTHONPATH:-}"

if [[ -x "$REPO_ROOT/.venv/bin/pytest" ]]; then
  PYTEST="$REPO_ROOT/.venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
  PYTEST="pytest"
else
  echo "ERROR: pytest not found. Activate the env and install deps:"
  echo "  source code/scripts/activate_env.sh"
  echo "  pip install -r code/requirements.txt"
  exit 1
fi

exec "$PYTEST" "$@"
