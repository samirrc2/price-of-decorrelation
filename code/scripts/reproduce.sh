#!/usr/bin/env bash
# Reproduce Phase-3 outputs from frozen data, OR collect a new dated dataset.
#
# Offline (default):
#   bash reproduce.sh
#   bash reproduce.sh --analyze-only
#   bash reproduce.sh --data data/confirmatory/20260704
#
# Live collection (API keys required):
#   bash reproduce.sh --scratch-run 48k     # fresh collect + analyze + results/latest
#   bash reproduce.sh --scratch-run full
set -euo pipefail

usage() {
  cat <<'EOF'
Usage (from repository root):

  Offline analysis / replication
    bash reproduce.sh
    bash reproduce.sh --analyze-only
    bash reproduce.sh --data data/confirmatory/latest
    bash reproduce.sh --data data/confirmatory/20260704

  New collection (scratch run — always live: collect + analyze + link latest)
    bash reproduce.sh --scratch-run 48k
    bash reproduce.sh --scratch-run full

  Size for --scratch-run: 48k | 54k | 48000 | full (default: full)
  Results: results/data-<dataDate>_run-<runStamp>/
  Note: --dry-run cannot be combined with --scratch-run
        (use: python code/src/orchestrator.py --dry-run … for validation only)
EOF
}

# Parse "48k" / "54k" / "48000" / "full" → integer or empty (full grid)
parse_call_budget() {
  local s
  s="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  case "$s" in
    full|all|"")
      echo ""
      ;;
    *k)
      local n="${s%k}"
      if [[ ! "$n" =~ ^[0-9]+$ ]]; then
        echo "ERROR: bad size '$1' (use e.g. 48k, 54000, full)" >&2
        return 1
      fi
      echo $((n * 1000))
      ;;
    *)
      if [[ ! "$s" =~ ^[0-9]+$ ]]; then
        echo "ERROR: bad size '$1' (use e.g. 48k, 54000, full)" >&2
        return 1
      fi
      echo "$s"
      ;;
  esac
}

MODE="replication"
DATA_DIR="data/confirmatory/latest"
SCRATCH_SIZE="full"
DATASET_KIND="confirmatory"
DRY_RUN_FLAG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --replication|--full-check)
      MODE="replication"
      shift
      ;;
    --analyze-only|--analyze|--quick)
      MODE="analyze"
      shift
      ;;
    --scratch-run|--scratch_run)
      MODE="scratch"
      if [[ $# -ge 2 && "$2" != -* ]]; then
        SCRATCH_SIZE="$2"
        shift 2
      else
        SCRATCH_SIZE="full"
        shift
      fi
      ;;
    --dry-run)
      DRY_RUN_FLAG=1
      shift
      ;;
    --dataset-kind)
      DATASET_KIND="${2:-}"
      if [[ -z "$DATASET_KIND" ]]; then
        echo "ERROR: --dataset-kind requires a name" >&2
        exit 1
      fi
      shift 2
      ;;
    --data)
      DATA_DIR="${2:-}"
      if [[ -z "$DATA_DIR" ]]; then
        echo "ERROR: --data requires a directory" >&2
        exit 1
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$MODE" == "scratch" && "$DRY_RUN_FLAG" -eq 1 ]]; then
  echo "ERROR: --dry-run cannot be used with --scratch-run." >&2
  echo "--scratch-run is a full live collect + analyze." >&2
  echo "For validation only:" >&2
  echo "  python code/src/orchestrator.py --phase full --max-calls 48000 --dry-run --fresh" >&2
  exit 1
fi

CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$CODE_ROOT/.." && pwd)"
if [[ -d /code/src && -d /data ]]; then
  CODE_ROOT="/code"
  REPO_ROOT="/"
  DATA_ROOT="/data"
  RESULTS_ROOT="/results"
else
  DATA_ROOT="$REPO_ROOT/data"
  RESULTS_ROOT="$REPO_ROOT/results"
fi

cd "$REPO_ROOT" 2>/dev/null || cd "$CODE_ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

_VENV="$REPO_ROOT/.venv"
_ensure_env() {
  if [[ -d /code/src && -d /data ]]; then
    export PYTHONPATH="/code/src:${PYTHONPATH:-}"
    if command -v python >/dev/null 2>&1; then
      echo "Code Ocean env: $(python --version 2>&1)"
      return 0
    fi
  fi
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    _active="$(cd "$VIRTUAL_ENV" 2>/dev/null && pwd)" || _active=""
    _want="$(cd "$_VENV" 2>/dev/null && pwd)" || _want=""
    if [[ -n "$_active" && -n "$_want" && "$_active" == "$_want" ]]; then
      echo "Environment already active: $VIRTUAL_ENV"
      export PYTHONPATH="$CODE_ROOT/src:${PYTHONPATH:-}"
      return 0
    fi
  fi
  # shellcheck disable=SC1091
  source "$CODE_ROOT/scripts/activate_env.sh"
}

_ensure_env
export PYTHONPATH="$CODE_ROOT/src:${PYTHONPATH:-}"

# --------------------------------------------------------------------------- #
# Scratch collection (live API)
# --------------------------------------------------------------------------- #
if [[ "$MODE" == "scratch" ]]; then
  MAX_CALLS="$(parse_call_budget "$SCRATCH_SIZE")" || exit 1
  # Unique stamp so every scratch-run starts from an empty log (no resume).
  STAMP="$(date -u +%Y%m%d_%H%M%S)"
  echo "Scratch run: kind=$DATASET_KIND  folder=$STAMP  size=${SCRATCH_SIZE}"
  echo "Starts from the beginning (fresh empty runs.csv — will not resume old data)."
  if [[ -n "$MAX_CALLS" ]]; then
    echo "Call budget: first $MAX_CALLS slots of the study grid"
  else
    echo "Call budget: full grid (~54k for confirmatory)"
  fi
  echo "Writes: data/${DATASET_KIND}/${STAMP}/runs.csv  (latest → ${STAMP})"
  echo "Older folders (e.g. 20260704) are left untouched."
  echo "WARNING: this spends API budget, then runs analyze."
  echo "Ctrl-C safe within THIS collection folder only."

  ORCH_ARGS=(
    --config "configs/config.yaml"
    --phase full
    --dataset-kind "$DATASET_KIND"
    --data-date "$STAMP"
    --fresh
  )
  if [[ "$DATASET_KIND" == "control" ]]; then
    ORCH_ARGS=(--config "configs/config_control.yaml" --phase full
               --dataset-kind control --data-date "$STAMP" --fresh)
  fi
  if [[ -n "$MAX_CALLS" ]]; then
    ORCH_ARGS+=(--max-calls "$MAX_CALLS")
  fi

  (cd "$CODE_ROOT" && python src/orchestrator.py "${ORCH_ARGS[@]}")
  echo ""

  # Point at the folder we just collected, then analyze once into results/
  RUNS_CSV="$DATA_ROOT/${DATASET_KIND}/${STAMP}/runs.csv"
  if [[ ! -f "$RUNS_CSV" ]]; then
    echo "ERROR: expected $RUNS_CSV after collection — analyze skipped." >&2
    exit 1
  fi
  DATA_DATE="$STAMP"
  RUN_STAMP="$(date -u +%Y%m%d_%H%M%S)"
  OUT_NAME="data-${DATA_DATE}_run-${RUN_STAMP}"
  OUT_DIR="$RESULTS_ROOT/$OUT_NAME"
  mkdir -p "$OUT_DIR"
  export POD_RUNS_CSV="$RUNS_CSV"
  export POD_OUT_DIR="$OUT_DIR"
  echo "Collection done. Analyzing → results/$OUT_NAME"
  (cd "$CODE_ROOT" && python src/analyze.py)
  ln -sfn "$OUT_NAME" "$RESULTS_ROOT/latest"
  echo "results/latest -> results/$OUT_NAME"
  echo "Done. Open results/latest/ (figures/, tables/, metrics_summary.md)."
  exit 0
fi

# --------------------------------------------------------------------------- #
# Offline analyze / replication
# --------------------------------------------------------------------------- #
# Resolve runs.csv from --data (dir or file)
if [[ "$DATA_DIR" = /* ]]; then
  if [[ -d "$DATA_DIR" ]]; then
    RUNS_CSV="$DATA_DIR/runs.csv"
  else
    RUNS_CSV="$DATA_DIR"
  fi
elif [[ "$DATA_DIR" == data/* ]]; then
  _rel="${DATA_DIR#data/}"
  if [[ -d "$DATA_ROOT/$_rel" ]]; then
    RUNS_CSV="$DATA_ROOT/$_rel/runs.csv"
  elif [[ -f "$DATA_ROOT/$_rel" ]]; then
    RUNS_CSV="$DATA_ROOT/$_rel"
  else
    RUNS_CSV="$DATA_ROOT/$_rel/runs.csv"
  fi
else
  RUNS_CSV="$REPO_ROOT/$DATA_DIR/runs.csv"
fi

if [[ -L "$(dirname "$RUNS_CSV")" ]]; then
  RUNS_CSV="$(cd "$(dirname "$RUNS_CSV")" && pwd)/$(basename "$RUNS_CSV")"
fi

if [[ ! -f "$RUNS_CSV" ]]; then
  echo "ERROR: runs.csv not found at: $RUNS_CSV"
  echo "Expected e.g. data/confirmatory/latest/runs.csv"
  echo "To collect new data: bash reproduce.sh --scratch-run 48k"
  exit 1
fi

DATA_DATE="$(basename "$(dirname "$RUNS_CSV")")"
if [[ ! "$DATA_DATE" =~ ^[0-9]{8}$ ]]; then
  _parent="$(dirname "$RUNS_CSV")"
  if [[ -L "$_parent" ]]; then
    DATA_DATE="$(basename "$(readlink "$_parent")")"
  else
    DATA_DATE="unknown"
  fi
fi

RUN_STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT_NAME="data-${DATA_DATE}_run-${RUN_STAMP}"
OUT_DIR="$RESULTS_ROOT/$OUT_NAME"
mkdir -p "$OUT_DIR"

export POD_RUNS_CSV="$RUNS_CSV"
export POD_OUT_DIR="$OUT_DIR"

_point_latest() {
  ln -sfn "$OUT_NAME" "$RESULTS_ROOT/latest"
  echo "results/latest -> results/$OUT_NAME"
}

echo "POD_RUNS_CSV=$POD_RUNS_CSV"
echo "data date=$DATA_DATE"
echo "POD_OUT_DIR=$POD_OUT_DIR"

if [[ "$MODE" == "analyze" ]]; then
    echo "Running: python src/analyze.py"
    (cd "$CODE_ROOT" && python src/analyze.py)
    _point_latest
    echo "Done. Open results/latest/ (figures/, tables/, metrics_summary.md)."
elif [[ "$MODE" == "replication" ]]; then
    echo "Running: python src/replication_check.py"
    unset POD_OUT_DIR
    (cd "$CODE_ROOT" && python src/replication_check.py)
    echo "Done. See results/latest/replication_check.md"
fi
