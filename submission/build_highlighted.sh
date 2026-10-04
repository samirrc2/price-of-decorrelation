#!/usr/bin/env bash
# Build the "Highlighted PDF" required by the IEEE Access resubmission checklist: the
# revised manuscript with every individual change marked in yellow. The markup rewrite
# lives in highlight_markup.py; see its docstring for why latexdiff's own preamble is
# discarded rather than restyled.
#
#   bash submission/build_highlighted.sh            # against the as-submitted tag
#   bash submission/build_highlighted.sh <ref>      # against another ref
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
# The baseline is the version the reviewers read, which is a fixed point in history -- not
# "whatever was committed last". This defaulted to HEAD, which worked only while the revision
# was uncommitted; committing it moved the baseline onto the revision itself and the next build
# failed outright. A tag keeps it pinned.
BASE_REF="${1:-as-submitted}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if ! git rev-parse --verify --quiet "$BASE_REF^{commit}" >/dev/null; then
  echo "ERROR: baseline ref '$BASE_REF' does not exist. The highlighted PDF must be diffed" >&2
  echo "       against the manuscript as submitted; create the tag with:" >&2
  echo "         git tag -a as-submitted <commit> -m 'Manuscript as submitted'" >&2
  exit 3
fi
git show "$BASE_REF:paper/main.tex" > "$WORK/old.tex"
cp paper/main.tex "$WORK/new.tex"

# Paper 2 held its reordered bibliography and its rounding-only corrections constant
# across the diff. Neither applies here: this revision does not reorder the reference
# list and introduces no digit-level corrections, so nothing is withheld from the
# markup and every change in the manuscript is highlighted.

# --append-textcmd=tfootnote: latexdiff will not descend into \tfootnote, so a change
# inside the IEEE Access title-block footnote would be replaced wholesale and render
# unhighlighted. Without
# this latexdiff replaces the whole \tfootnote command -- \DIFaddbegin \tfootnote{...}
# \DIFaddend rather than \DIFadd{...} around the changed words -- and since only \DIFadd is
# mapped to \texthl, the new date rendered plain. A reviewer comparing the two PDFs saw the
# date change with no mark on it.
latexdiff --type=CFONT --math-markup=0 --append-textcmd="tfootnote" \
          "$WORK/old.tex" "$WORK/new.tex" > "$WORK/diff.tex" 2>/dev/null || true
python3 submission/highlight_markup.py "$WORK/diff.tex"

# Compile inside paper/ rather than a temp directory. The IEEE Access template needs its
# font maps (t1-*.map) and font descriptors (t1*.fd) alongside the source; copying only the
# class, style, .pfb and .tfm files leaves pdflatex unable to resolve formata at title size,
# and even the unmodified manuscript fails to build. Nothing of the author's is overwritten:
# the working file is a uniquely named temporary that is removed on exit.
STEM="_highlighted_build"
cp "$WORK/diff.tex" "paper/$STEM.tex"
trap 'rm -rf "$WORK" paper/'"$STEM"'.*' EXIT
# BibTeX must run between passes: this manuscript builds its reference list from
# references.bib rather than an inline thebibliography, so a pdflatex-only loop produces a
# highlighted PDF with every citation unresolved and no REFERENCES section at all.
( cd paper && pdflatex -interaction=nonstopmode "$STEM.tex" >/dev/null 2>&1 || true
             bibtex "$STEM" >/dev/null 2>&1 || true
             for i in 2 3; do pdflatex -interaction=nonstopmode "$STEM.tex" >/dev/null 2>&1 || true; done )

if [ -f "paper/$STEM.pdf" ]; then
    cp "paper/$STEM.pdf" submission/highlighted_pdf.pdf
    grep -o "Output written on $STEM.pdf ([0-9]* pages" "paper/$STEM.log" | head -1 | sed 's/^/   /'
    echo "   -> submission/highlighted_pdf.pdf"
else
    echo "   FAILED: no PDF produced" >&2
    grep -E "^! |pdfTeX error" "paper/$STEM.log" | head -6 >&2 || true
    exit 1
fi
