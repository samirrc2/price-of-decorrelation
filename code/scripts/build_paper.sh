#!/usr/bin/env bash
# Build paper/main.pdf from analysis figures under a results/ directory.
#
# Default: sync figures from results/latest, then pdflatex + bibtex.
# Does NOT re-run analyze or call APIs. Table numbers in main.tex remain
# as authored; regenerating analysis does not rewrite κ/Δκ in the .tex.
#
# Usage (from repository root):
#   bash code/scripts/build_paper.sh
#   bash code/scripts/build_paper.sh --results results/<timestamp>
#   bash code/scripts/build_paper.sh --skip-sync
#   bash code/scripts/build_paper.sh --help
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PAPER_DIR="$REPO_ROOT/paper"
FIG_DST="$PAPER_DIR/figures"
RESULTS_DIR="$REPO_ROOT/results/latest"
SKIP_SYNC=0
OPEN_PDF=0

usage() {
  cat <<'EOF'
Build paper/main.pdf from analysis figures under results/.

  bash code/scripts/build_paper.sh
  bash code/scripts/build_paper.sh --results results/<timestamp>
  bash code/scripts/build_paper.sh --skip-sync
  bash code/scripts/build_paper.sh --open
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --results|-r)
      RESULTS_DIR="${2:-}"
      if [[ -z "$RESULTS_DIR" ]]; then
        echo "ERROR: --results requires a directory" >&2
        exit 1
      fi
      shift 2
      ;;
    --skip-sync)
      SKIP_SYNC=1
      shift
      ;;
    --open)
      OPEN_PDF=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Resolve relative --results against repo root
if [[ "$RESULTS_DIR" != /* ]]; then
  RESULTS_DIR="$REPO_ROOT/$RESULTS_DIR"
fi

find_pdflatex() {
  if command -v pdflatex >/dev/null 2>&1; then
    command -v pdflatex
    return 0
  fi
  for cand in \
    /Library/TeX/texbin/pdflatex \
    /usr/local/texlive/2025/bin/universal-darwin/pdflatex \
    /usr/local/texlive/2024/bin/universal-darwin/pdflatex \
    /usr/local/texlive/2023/bin/universal-darwin/pdflatex; do
    if [[ -x "$cand" ]]; then
      echo "$cand"
      return 0
    fi
  done
  return 1
}

sync_figures() {
  local src="$RESULTS_DIR/figures"
  if [[ ! -d "$RESULTS_DIR" ]]; then
    echo "ERROR: results dir not found: $RESULTS_DIR" >&2
    echo "Run: bash reproduce.sh --analyze-only" >&2
    exit 1
  fi
  if [[ ! -d "$src" ]]; then
    echo "ERROR: no figures/ under $RESULTS_DIR" >&2
    exit 1
  fi

  mkdir -p "$FIG_DST"
  local required=(fig1_frontier.png fig2_protocol.png fig3_provider_heatmap.png)
  local f
  for f in "${required[@]}"; do
    if [[ ! -f "$src/$f" ]]; then
      echo "ERROR: missing $src/$f" >&2
      exit 1
    fi
    cp -f "$src/$f" "$FIG_DST/$f"
    echo "  synced $f  ←  $src/$f"
  done

  # fig5: from results/latest/figures (reviewer_analysis), else keep paper copy
  if [[ -f "$src/fig5_calibration.png" ]]; then
    cp -f "$src/fig5_calibration.png" "$FIG_DST/fig5_calibration.png"
    echo "  synced fig5_calibration.png  ←  $src/fig5_calibration.png"
  elif [[ -f "$FIG_DST/fig5_calibration.png" ]]; then
    echo "  keeping existing paper/figures/fig5_calibration.png"
  else
    echo "WARNING: fig5_calibration.png not found; PDF may miss Fig. 5" >&2
  fi

  # Optional: copy generated table snippets for reference (main.tex does not \\input them)
  if [[ -d "$RESULTS_DIR/tables" ]]; then
    mkdir -p "$PAPER_DIR/generated_tables"
    cp -f "$RESULTS_DIR/tables/"*.tex "$PAPER_DIR/generated_tables/" 2>/dev/null || true
    cp -f "$RESULTS_DIR/tables/"*.csv "$PAPER_DIR/generated_tables/" 2>/dev/null || true
    echo "  copied tables → paper/generated_tables/ (reference only; not auto-injected)"
  fi
}

compile_pdf() {
  local pdflatex_bin bibtex_bin texbin
  if ! pdflatex_bin="$(find_pdflatex)"; then
    echo "ERROR: pdflatex not found. Install MacTeX / TeX Live (needs IEEEtran.cls)." >&2
    exit 1
  fi
  texbin="$(dirname "$pdflatex_bin")"
  bibtex_bin="$texbin/bibtex"
  if [[ ! -x "$bibtex_bin" ]]; then
    if command -v bibtex >/dev/null 2>&1; then
      bibtex_bin="$(command -v bibtex)"
    else
      echo "ERROR: bibtex not found next to pdflatex ($texbin)" >&2
      exit 1
    fi
  fi

  if ! "$pdflatex_bin" -version >/dev/null 2>&1; then
    echo "ERROR: cannot run $pdflatex_bin" >&2
    exit 1
  fi

  # IEEEtran check (non-fatal warning if kpsewhich missing)
  if command -v kpsewhich >/dev/null 2>&1 || [[ -x "$texbin/kpsewhich" ]]; then
    local kpse="$texbin/kpsewhich"
    command -v kpsewhich >/dev/null 2>&1 && kpse="$(command -v kpsewhich)"
    if ! "$kpse" IEEEtran.cls >/dev/null 2>&1; then
      echo "WARNING: IEEEtran.cls not found on TeX path; compile may fail." >&2
    fi
  fi

  echo "Using: $pdflatex_bin"
  cd "$PAPER_DIR"
  # -interaction=nonstopmode so CI/agents don't hang on errors
  "$pdflatex_bin" -interaction=nonstopmode -halt-on-error main.tex
  "$bibtex_bin" main
  "$pdflatex_bin" -interaction=nonstopmode -halt-on-error main.tex
  "$pdflatex_bin" -interaction=nonstopmode -halt-on-error main.tex

  if [[ ! -f "$PAPER_DIR/main.pdf" ]]; then
    echo "ERROR: paper/main.pdf was not produced" >&2
    exit 1
  fi
  echo "Wrote $PAPER_DIR/main.pdf"
}

echo "Paper build"
echo "  results: $RESULTS_DIR"
echo "  paper:   $PAPER_DIR"

if [[ "$SKIP_SYNC" -eq 0 ]]; then
  echo "Syncing figures..."
  sync_figures
else
  echo "Skipping figure sync (--skip-sync)"
fi

echo "Compiling LaTeX..."
compile_pdf

if [[ "$OPEN_PDF" -eq 1 ]] && [[ "$(uname -s)" == "Darwin" ]]; then
  open "$PAPER_DIR/main.pdf"
fi
