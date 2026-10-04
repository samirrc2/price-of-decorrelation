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
  echo "  $PY code/src/orchestrator.py --phase full --max-calls 48000 --dry-run --fresh" >&2
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

# APPEND these, do not prepend: prepending forced /usr/local/bin/python3 ahead of whatever
# interpreter the operator had selected, and that one lacks pyyaml -- so a machine with a
# perfectly good python failed with "missing Python packages".
export PATH="${PATH:-}:/opt/homebrew/bin:/usr/local/bin"

# PY is the ONE interpreter every step uses. Overridable, because the environment that can
# import the dependencies is not always the first `python` on PATH:
#   PY=./.venv/bin/python bash reproduce.sh
# Resolution order: an explicit PY, then a repo-local .venv, then python3, then python. The
# first one that can import the dependencies wins -- selecting by name alone is what made a
# machine with a working interpreter report "missing Python packages".
_pick_python() {
  local cands=()
  [[ -n "${PY:-}" ]] && cands+=("$PY")
  [[ -x "$REPO_ROOT/.venv/bin/python" ]] && cands+=("$REPO_ROOT/.venv/bin/python")
  cands+=(python3 python)
  for c in "${cands[@]}"; do
    command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]] || continue
    if "$c" -c "import yaml, numpy, matplotlib" >/dev/null 2>&1; then
      PY="$c"; return 0
    fi
  done
  return 1
}

_ensure_env() {
  if [[ -d /code/src && -d /data ]]; then
    export PYTHONPATH="/code/src:${PYTHONPATH:-}"
    if _pick_python; then
      echo "Code Ocean env: $("$PY" --version 2>&1)  [$PY]"
      return 0
    fi
  fi
  export PYTHONPATH="$CODE_ROOT/src:${PYTHONPATH:-}"
  if ! _pick_python; then
    echo "ERROR: no python on PATH can import yaml, numpy and matplotlib." >&2
    echo "Tried: ${PY:-} ${REPO_ROOT}/.venv/bin/python python3 python" >&2
    echo "Install with: pip install -r code/requirements.txt" >&2
    echo "Or point at a working interpreter: PY=/path/to/python bash reproduce.sh" >&2
    exit 1
  fi
  echo "Python: $("$PY" --version 2>&1)  [$PY]"
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

  (cd "$CODE_ROOT" && "$PY" src/orchestrator.py "${ORCH_ARGS[@]}")
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
  (cd "$CODE_ROOT" && "$PY" src/analyze.py)
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

# --------------------------------------------------------------------------- #
# Gates. Every one prints its own coverage count, and exit 2 means "this copy
# cannot run this gate" (the /code + /data capsule has no paper/ or submission/),
# which must not read as a pass. Modelled on Paper 2's code/reproduce.sh.
# --------------------------------------------------------------------------- #
GATES_INCOMPLETE=0

_gate() {   # name, then the command
  local name="$1"; shift
  local rc=0
  "$@" || rc=$?
  case "$rc" in
    0) ;;
    2) echo "     [$name] NOT CHECKABLE in this copy (exit 2)"; GATES_INCOMPLETE=1 ;;
    *) echo "     [$name] FAILED (exit $rc)"; return "$rc" ;;
  esac
  return 0
}

_run_gates() {
  echo "[gate] input integrity (SHA-256 of every frozen input)"
  _gate manifest "$PY" "$CODE_ROOT/src/make_manifest.py" --verify || return 1

  # Hashes verifying is not the same as the inputs being COMPLETE. The capsule passed its
  # hash check while data/datacache/forward_returns.json was missing, which silently turned
  # an offline run into a network-dependent one and then crashed the reviewer analyses.
  echo "[gate] capsule completeness (inputs a /code + /data mount must carry)"
  _gate capsule "$PY" "$CODE_ROOT/src/make_manifest.py" --capsule || return 1

  # The revision arms are keys-free: both read only frozen captures. Regenerating them here
  # is what LOCKS them -- previously reproduce.sh rebuilt the primary endpoint and left
  # results/revision_metrics.json and results/mmlu_replication.json as whatever was last
  # committed, so a stale revision number could not be detected by any run.
  echo "[gate] revision arms (reviewer analyses + cross-domain replication)"
  if [[ -f "$DATA_ROOT/confirmatory/latest/runs.csv" || -d "$DATA_ROOT/confirmatory" ]]; then
    _gate revision "$PY" "$CODE_ROOT/src/reviewer_revision.py" || return 1
  else
    echo "     [revision] NOT CHECKABLE: confirmatory capture absent"; GATES_INCOMPLETE=1
  fi
  if compgen -G "$DATA_ROOT/mmlu/*/runs.csv" >/dev/null; then
    _gate mmlu "$PY" "$CODE_ROOT/src/analyze_mmlu.py" || return 1
  else
    echo "     [mmlu] NOT CHECKABLE: cross-domain capture absent"; GATES_INCOMPLETE=1
  fi

  # Three further analyses feed the manuscript and were NEVER run by reproduce.sh, so the
  # HET-SameTier control, the temperature sweep and the reviewer-hardening tables were
  # whatever a past run happened to leave behind. All three are keys-free functions of
  # frozen inputs; regenerating them is what locks those manuscript values.
  echo "[gate] supporting analyses (control arm, temperature sweep, reviewer hardening)"
  for _s in analyze_pilot control_kappa temp_analyze reviewer_analysis; do
    if [[ -f "$CODE_ROOT/src/$_s.py" ]]; then
      _gate "$_s" "$PY" "$CODE_ROOT/src/$_s.py" || return 1
    fi
  done

  echo "[gate] claims extraction"
  _gate claims "$PY" "$CODE_ROOT/src/make_claims.py" || return 1
  echo "[gate] manuscript numbers vs frozen analysis"
  _gate check-claims "$PY" "$CODE_ROOT/src/check_claims.py" || return 1
  # The reverse direction: check_claims verifies that OUR claims appear in the manuscript,
  # which cannot notice a manuscript number no analysis produces. This walks every literal in
  # main.tex and demands provenance. It is the gate that found five figures -- the whole
  # capability-matched passage -- existing only in the manuscript, with no generating code.
  echo "[gate] manuscript provenance (every number traced to a claim or declared non-result)"
  _gate coverage "$PY" "$CODE_ROOT/src/check_coverage.py" || return 1
  # Both gates above are set-membership tests: they ask whether a number appears on the other
  # side, not whether it appears in the right PLACE. Swapping kappa_HOM and kappa_HET in the
  # text -- which inverts the paper's finding -- passes both. This one binds each number to the
  # single claim it must equal, and to the phrase it must follow.
  echo "[gate] manuscript binding (every number equals the one claim it is bound to)"
  _gate binding "$PY" "$CODE_ROOT/src/check_binding.py" || return 1
  # Binding is total over the manuscript, so no printed number lacks a tie -- but 219 of the 376
  # claims are named by no rule, and fault injection showed one of those could be bent to 0.4242
  # with no gate noticing. claims.lock.json pins every value as reviewed, so a code change that
  # moves a number nobody is watching shows up here and in the commit diff.
  # A figure is a reported result, and no text gate can see it. build_submission.sh compiles
  # paper/ directly without syncing, so a stale PNG there ships in every deliverable -- which it
  # did, for two months, with a superseded Fig. 2.
  # Two IEEE ordering requirements no other gate can see: Index Terms must be alphabetical,
  # and references must be numbered by order of first mention. The manuscript was SUBMITTED
  # with unordered Index Terms, which nothing noticed.
  echo "[gate] IEEE ordering rules (Index Terms, reference numbering)"
  _gate ieee-style "$PY" "$CODE_ROOT/src/check_ieee_style.py" || return 1
  echo "[gate] manuscript figures vs the analysis output"
  _gate figures "$PY" "$CODE_ROOT/src/check_figures.py" || return 1
  echo "[gate] claim values vs the reviewed lock"
  _gate claims-lock "$PY" "$CODE_ROOT/src/check_claims_bound.py" || return 1
  # The response letter quotes most of the paper's numbers back to the reviewers, and for this
  # whole revision nothing bound them: substituting 0.455 for the error-correlation contrast
  # 0.454 passed every gate, because 0.455 is the true value of a different claim. These four
  # gates bind the letter the way check_binding binds the manuscript, and check its factual
  # claims about the paper: numbers, section and table pointers, what was added or revised
  # against the as-submitted tag, and the reference numbers it quotes.
  echo "[gate] response-letter numbers bound to claims"
  _gate letter-binding "$PY" "$CODE_ROOT/src/check_letter_binding.py" || return 1
  echo "[gate] response-letter section, table and figure pointers"
  _gate letter-sections "$PY" "$CODE_ROOT/src/check_letter_sections.py" || return 1
  echo "[gate] response-letter claims about what changed"
  _gate letter-actions "$PY" "$CODE_ROOT/src/check_letter_actions.py" || return 1
  echo "[gate] letter and manuscript tell the reviewers the same story"
  _gate response-consistency "$PY" "$CODE_ROOT/src/check_response_consistency.py" || return 1
  echo "[gate] freeze receipts vs the commits and artifacts they attest"
  _gate freeze-receipt "$PY" "$CODE_ROOT/src/check_freeze_receipt.py" || return 1
  # Does the yellow on the page match what actually changed? Nothing else asks this: the other
  # highlighting checks verify that the two PDFs share a layout and that the build located every
  # change it was told about, which is not the same question. Four defects reached the author
  # before this gate existed.
  echo "[gate] highlighting vs the real diff against as-submitted"
  _gate highlight-coverage "$PY" "$CODE_ROOT/src/check_highlight_coverage.py" || return 1
  echo "[gate] freeze timestamps quoted in prose vs the receipts"
  _gate freeze-timestamps "$PY" "$CODE_ROOT/src/check_freeze_timestamps.py" || return 1
  echo "[gate] unit tests"
  if [[ -d "$CODE_ROOT/tests" ]]; then
    if "$PY" -c "import pytest" >/dev/null 2>&1; then
      _gate tests "$PY" -m pytest -q "$CODE_ROOT/tests" || return 1
    else
      echo "     [tests] NOT CHECKABLE: pytest not installed in $PY"
      GATES_INCOMPLETE=1
    fi
  fi
  return 0
}

if [[ "$MODE" == "analyze" ]]; then
    # The protocol-collapse figure used to carry four hardcoded pilot constants. They are
    # derived from data/pilot/ now, so this must run before analyze.py reads them.
    echo "Running: $PY src/analyze_pilot.py"
    (cd "$CODE_ROOT" && "$PY" src/analyze_pilot.py)
    echo "Running: $PY src/analyze.py"
    (cd "$CODE_ROOT" && "$PY" src/analyze.py)
    _point_latest
    _run_gates || exit 1
    echo "Done. Open results/latest/ (figures/, tables/, metrics_summary.md)."
elif [[ "$MODE" == "replication" ]]; then
    echo "Running: $PY src/analyze_pilot.py"
    (cd "$CODE_ROOT" && "$PY" src/analyze_pilot.py)
    echo "Running: $PY src/replication_check.py"
    unset POD_OUT_DIR
    (cd "$CODE_ROOT" && "$PY" src/replication_check.py)
    _run_gates || exit 1
    echo "Done. See results/latest/replication_check.md"
fi

# A gate that could not run is not a pass -- but a /code + /data capsule has no paper/ and
# no submission/ BY DESIGN, so "the manuscript gate did not run" is the documented layout
# there and must exit 0. Only a FULL checkout that is missing them is incomplete. Paper 2
# draws the same distinction, and getting it wrong means every capsule run reports failure.
if [[ "$GATES_INCOMPLETE" == 1 ]]; then
  if [[ -d "$REPO_ROOT/paper" || -d "$REPO_ROOT/submission" ]]; then
    echo "[reproduce] INCOMPLETE: this is a full checkout, yet a gate could not run"
    exit 2
  fi
  echo "[reproduce] capsule layout: analysis and data gates passed; document gates are"
  echo "[reproduce] not part of a /code + /data capsule and were correctly skipped"
  exit 0
fi
echo "[reproduce] all gates passed"
exit 0
