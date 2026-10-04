#!/usr/bin/env bash
# Reproduce Phase-3 paper outputs from the frozen confirmatory dataset.
#
# Default (offline, $0 API): replication check - analyze twice and compare hashes.
# Optional: --analyze-only runs analyze once (no hash compare).
#
# Usage (from anywhere):
#   bash scripts/reproduce.sh                 # default: byte-identical check
#   bash scripts/reproduce.sh --analyze-only  # analyze once only
#
# Requires: Python >= 3.10, frozen runs.csv at repo root.
# Does NOT call LLM APIs and does NOT regenerate runs.csv.
set -euo pipefail

usage() {
  cat <<'EOF'
Reproduce Phase-3 paper outputs from the frozen confirmatory dataset.

Usage (from repository root):
  bash reproduce.sh                 # default: analyze x2 + hash compare
  bash reproduce.sh --replication   # same as default
  bash reproduce.sh --analyze-only  # analyze once only (no compare)
  bash reproduce.sh --help

Equivalent: bash scripts/reproduce.sh ...

Offline only - no API calls. Requires runs.csv at the repository root.
EOF
}

MODE="replication"
for arg in "$@"; do
  case "$arg" in
    --replication|--full-check)
      MODE="replication"
      ;;
    --analyze-only|--analyze|--quick)
      MODE="analyze"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      usage
      exit 1
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# On macOS, Homebrew may not be on PATH in non-interactive shells. Harmless elsewhere.
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

_VENV="$REPO_ROOT/.venv"
_ensure_env() {
  # Already using this project's venv? Skip activate.
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    _active="$(cd "$VIRTUAL_ENV" 2>/dev/null && pwd)" || _active=""
    _want="$(cd "$_VENV" 2>/dev/null && pwd)" || _want=""
    if [[ -n "$_active" && -n "$_want" && "$_active" == "$_want" ]]; then
      echo "Environment already active: $VIRTUAL_ENV"
      export PYTHONPATH="$REPO_ROOT/src:${PYTHONPATH:-}"
      return 0
    fi
  fi
  # Not active (or wrong venv): create/reuse and activate via activate_env.sh
  # shellcheck disable=SC1091
  source "$REPO_ROOT/scripts/activate_env.sh"
}

_ensure_env

if [[ ! -f "$REPO_ROOT/runs.csv" ]]; then
  echo "ERROR: runs.csv not found at repo root."
  echo "Place the frozen confirmatory dataset at: $REPO_ROOT/runs.csv"
  exit 1
fi

echo "============================================================"
echo " Phase-3 reproduction (offline - no API calls)"
echo " Repo: $REPO_ROOT"
echo " Mode: $MODE"
echo "============================================================"

case "$MODE" in
  analyze)
    echo "Running: python src/analyze.py"
    echo "(Regenerates figures/, tables/, metrics_summary.md, ...)"
    python src/analyze.py
    echo ""
    echo "Done. Open figures/ and tables/ for paper outputs."
    echo "For byte-identical check (default):  bash reproduce.sh"
    ;;
  replication)
    echo "Running: python src/replication_check.py"
    echo "(Two analyze passes + hash compare; several minutes)"
    python src/replication_check.py
    echo ""
    echo "Done. See replication_check.md"
    ;;
esac
