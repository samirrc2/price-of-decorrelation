#!/usr/bin/env bash
# Remove disposable bulk not needed for Phase-3 analysis from frozen CSVs.
# Does NOT delete data/*/runs*.csv or data/configs/.
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$CODE_ROOT/.." && pwd)"
cd "$REPO_ROOT"

echo "Will remove (if present):"
echo "  - data/raw/     (per-call JSON dumps)"
echo "  - cache/        (API response cache)"
echo "  - __pycache__ / .pytest_cache"
echo ""
read -r -p "Continue? [y/N] " ans
case "$ans" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 0 ;;
esac

rm -rf data/raw cache
find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache

echo "Done. Frozen call logs under data/*/ are untouched."
echo "Re-running orchestrator will recreate data/raw/YYYYMMDD/ locally (gitignored)."
