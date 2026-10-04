#!/usr/bin/env bash
# Temperature-robustness check (small subgrid; not a full temperature study).
# Writes into data/temperature_robustness_small/<YYYYMMDD>/ and points latest.
#
# Run from the repository root:  bash code/scripts/run_temp_sweep.sh
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$CODE_ROOT/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$CODE_ROOT/src:${PYTHONPATH:-}"

DAY="$(date -u +%Y%m%d)"
OUT_DIR="data/temperature_robustness_small/${DAY}"
mkdir -p "$OUT_DIR"
ln -sfn "$DAY" data/temperature_robustness_small/latest

for TV in "0.0:T00" "0.7:T07" "1.0:T10"; do
  T="${TV%%:*}"; TAG="${TV##*:}"
  echo "=== Temperature ${T}  ->  ${OUT_DIR}/runs_${TAG}.csv ==="
  python "$CODE_ROOT/src/orchestrator.py" --config configs/config_temp.yaml --phase full \
      --dataset-kind temperature_robustness_small --data-date "$DAY" \
      --temperature "${T}" --runs-csv "${OUT_DIR}/runs_${TAG}.csv"
done

echo "=== Analyzing ==="
python "$CODE_ROOT/src/temp_analyze.py"
echo "Done. See results/latest/temp_sweep_result.md and temp_sweep_table.tex"
