#!/usr/bin/env bash
# Assemble the four-file IEEE Access resubmission set from source, in dependency order.
#
#   bash submission/build_submission.sh           # rebuild everything
#   bash submission/build_submission.sh --check   # verify only, exit 1 if stale
#
# Deliverables:
#   submission/main_manuscript.pdf              clean manuscript
#   submission/main_manuscript.docx             Word version of the same
#   submission/highlighted_pdf.pdf              every change marked in yellow
#   submission/IEEE-Access-Response-to-Reviewers.{pdf,docx}
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"

if [ "${1:-}" = "--check" ]; then
    rc=0
    for f in submission/main_manuscript.pdf submission/main_manuscript.docx \
             submission/highlighted_pdf.pdf submission/IEEE-Access-Response-to-Reviewers.pdf; do
        [ -f "$f" ] || { echo "MISSING: $f"; rc=1; continue; }
        [ "$f" -ot paper/main.tex ] && { echo "STALE: $f is older than paper/main.tex"; rc=1; }
    done
    [ submission/IEEE-Access-Response-to-Reviewers.pdf -ot submission/response_to_reviewers.txt ] \
        && { echo "STALE: response PDF older than its source .txt"; rc=1; }
    python3 submission/check_highlighting.py || rc=1
    [ "$rc" = 0 ] && echo "submission package is current"
    exit "$rc"
fi

# Sync the figures first. This script compiles paper/ directly, so without this it uses
# whatever PNGs happen to be sitting there -- and it shipped a two-month-old Fig. 2 showing
# three bars while the text, the caption and the analysis all described two.
echo "== 0/4 figures =="
for f in results/latest/figures/*.png; do
    [ -f "$f" ] || continue
    b=$(basename "$f")
    if [ -f "paper/figures/$b" ] && ! cmp -s "$f" "paper/figures/$b"; then
        cp -f "$f" "paper/figures/$b"; echo "   refreshed paper/figures/$b"
    fi
done
python3 code/src/check_figures.py | sed 's/^/   /'

echo "== 1/4 manuscript PDF =="
( cd paper && pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true
             bibtex main >/dev/null 2>&1 || true
             for i in 2 3; do pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true; done )
grep -o "Output written.*" paper/main.log | head -1 || true
cp paper/main.pdf submission/main_manuscript.pdf

# The reference-numbering half of the IEEE check needs paper/main.bbl, which exists only after
# the manuscript is built. reproduce.sh checks the keys from source; this checks the realised
# numbering, so between them nothing is left unchecked.
python3 code/src/check_ieee_style.py | sed 's/^/   /'
# Same reason: the letter quotes reference numbers, which exist only in main.bbl.
python3 code/src/check_letter_refs.py | sed 's/^/   /'
python3 code/src/check_letter_binding.py | sed 's/^/   /'
python3 code/src/check_letter_sections.py | sed 's/^/   /'
python3 code/src/check_letter_actions.py | sed 's/^/   /'
python3 code/src/check_freeze_timestamps.py | sed 's/^/   /'

echo "== 2/4 Word version =="
# --citeproc is required: this manuscript builds its reference list from references.bib, and
# without it pandoc emits a DOCX with no REFERENCES section at all.
( cd paper && pandoc main.tex --citeproc --bibliography=references.bib \
      --resource-path=.:figures -o "$OLDPWD/submission/main_manuscript.docx" 2>/dev/null ) \
  && echo "   -> submission/main_manuscript.docx" \
  || echo "   WARNING: pandoc conversion failed; DOCX not refreshed"

echo "== 3/4 highlighted PDF =="
bash submission/build_highlighted.sh

echo "== 4/4 response to reviewers =="
( cd submission && python3 build_response.py )

echo
bash submission/build_submission.sh --check
