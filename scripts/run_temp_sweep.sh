#!/usr/bin/env bash
# Temperature-sensitivity sweep (reviewer point #3). Runs the small stratified
# subgrid at T in {0.0, 0.7, 1.0}, each into its OWN file under temp_sweep/, then
# analyzes. Never touches the frozen study runs.csv. Resumable: re-running skips
# completed cells. Total ~2,160 calls, ~$2-4.
#
# Run from the repository root:  bash scripts/run_temp_sweep.sh
set -euo pipefail
cd "$(dirname "$0")/.."          # repo root
mkdir -p temp_sweep

for TV in "0.0:T00" "0.7:T07" "1.0:T10"; do
  T="${TV%%:*}"; TAG="${TV##*:}"
  echo "=== Temperature ${T}  ->  temp_sweep/runs_${TAG}.csv ==="
  python src/orchestrator.py --config configs/config_temp.yaml --phase full \
      --temperature "${T}" --runs-csv "temp_sweep/runs_${TAG}.csv"
done

echo "=== Analyzing sweep ==="
python src/temp_analyze.py
echo "Done. See temp_sweep_result.md and temp_sweep_table.tex"
