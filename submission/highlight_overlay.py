#!/usr/bin/env python3
"""Paint the revision's changes onto the manuscript PDF itself.

Two decisions define this script, and both were arrived at the hard way.

1. Nothing is compiled twice for the highlighting. main_manuscript.pdf is built once and the
   marks are drawn onto that exact file, so the two deliverables agree line for line and page for
   page -- which is the point of a highlighted copy, since a reviewer reads them side by side.
   Compiling a second document with soul's \\texthl cannot do that (soul will not hyphenate inside
   a highlight, so four of fourteen pages started a line out), and neither can compiling with
   zero-width \\pdfsavepos markers (a whatsit suppresses hyphenation of the word after it).

2. What changed is decided by diffing the two RENDERED documents, not by parsing latexdiff's
   markup. The earlier version reduced \\DIFadd runs to tokens and searched for them in the page,
   and every defect found in review came from that reduction: inline maths became a wildcard and
   so was never painted, leaving "giving" yellow and "DeltaKappa = 0.072 (95% CI" plain; a run
   boundary inside "54{,}000" needed prefix matching; \\begin{tabular} leaked the word "tabular"
   into a table's context; float contents could not be placed at all, because a float is printed
   where the page has room and not where it sits in the source. Diffing the printed words has
   none of those problems: maths, numbers and table cells are just words on both sides.

The baseline is the manuscript as submitted, compiled from the `as-submitted` tag. Words that are
inserted or replaced relative to it are the changes, with one refinement: a block of four or more
words that appears verbatim in the baseline has MOVED rather than changed -- a float printed on a
different page -- and is not marked.

Exit 1 if the baseline cannot be built, because a highlighted PDF that silently marks nothing, or
everything, is worse than none.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
from pathlib import Path

YELLOW = (1.0, 0.94, 0.30)

# The running header and the VOLUME footer are page furniture, not text. A change that spans a
# page boundary would otherwise swallow them, and "Chincholikar et al.: The Price of
# De-correlation ..." was once highlighted on three pages that way.
FURNITURE = re.compile(r"(Chincholikar\s+et\s+al\.|VOLUME\s+\d+,\s+\d{4})")
MOVED_BLOCK = 4


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9%]", "", w.lower())


def word_stream(doc):
    """Every word in reading order, hyphenation repaired, with the rects that drew it."""
    stream = []
    for pno, page in enumerate(doc):
        skip = set()
        for blk in page.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for ln in blk["lines"]:
                if FURNITURE.search("".join(sp["text"] for sp in ln["spans"])):
                    skip.add(round(ln["bbox"][1], 1))
        sizes = {}
        for blk in page.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for ln in blk["lines"]:
                for sp in ln["spans"]:
                    # key on the integer top edge: a word's y0 and its line's bbox top differ by
                    # a fraction, and a 0.1 key missed, leaving every size 0 and the guard inert
                    sizes[int(round(ln["bbox"][1]))] = round(sp["size"])
        ws = sorted((w for w in page.get_text("words") if round(w[1], 1) not in skip),
                    key=lambda w: (w[5], w[6], w[7]))
        i = 0
        while i < len(ws):
            w = ws[i]
            txt, rects = w[4], [(pno, w[:4])]
            # a line-final hyphen continues into the next word, which pdflatex may place in
            # another block: a caption and its paragraph are separate blocks
            if txt.endswith("-") and i + 1 < len(ws) and ws[i + 1][1] > w[1] + 2:
                txt = txt[:-1] + ws[i + 1][4]
                rects.append((pno, ws[i + 1][:4]))
                i += 1
            n = norm(txt)
            if n:
                stream.append((n, rects, sizes.get(int(round(w[1])), 0)))
            i += 1
    return stream


def build_baseline(root: Path, ref: str, work: Path) -> Path | None:
    """Compile the manuscript as submitted, from the tag, in a scratch directory."""
    work.mkdir(parents=True, exist_ok=True)
    pdf = work / "paper" / "main.pdf"
    if pdf.exists():
        return pdf
    tar = subprocess.run(["git", "-C", str(root), "archive", ref, "paper"],
                         capture_output=True)
    if tar.returncode != 0:
        return None
    subprocess.run(["tar", "-x", "-C", str(work)], input=tar.stdout, capture_output=True)
    env = {"PATH": f"{Path.home()}/Library/TinyTeX/bin/universal-darwin:"
                   f"{subprocess.os.environ.get('PATH', '')}"}
    for cmd in (["pdflatex", "-interaction=nonstopmode", "main.tex"],
                ["bibtex", "main"],
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                ["pdflatex", "-interaction=nonstopmode", "main.tex"]):
        subprocess.run(cmd, cwd=work / "paper", capture_output=True,
                       env={**subprocess.os.environ, **env})
    return pdf if pdf.exists() else None


def changed_words(old_words, new_words):
    """Indices into new_words that are inserted or replaced relative to the baseline."""
    sm = difflib.SequenceMatcher(a=old_words, b=new_words, autojunk=False)
    changed = set()
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            changed.update(range(j1, j2))
    # A stretch that appears verbatim in the baseline has moved, not changed. Floats are printed
    # where the page has room, so a table or caption can land in a different place in the two
    # documents and look inserted to a monotonic diff.
    joined = " ".join(old_words)
    runs, cur = [], []
    for i in sorted(changed):
        if cur and i == cur[-1] + 1:
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = [i]
    if cur:
        runs.append(cur)
    moved = 0
    for r in runs:
        if len(r) >= MOVED_BLOCK and " ".join(new_words[r[0]:r[-1] + 1]) in joined:
            changed.difference_update(r)
            moved += len(r)
    return changed, moved


def paint(doc, stream, indices, pymupdf):
    """One rectangle per CONTIGUOUS run of marked words on a line.

    Merging every marked word on a line into a single box was wrong: the title block puts the
    author names and the e-mail address on the same text line, so marking the ORCIDs added to the
    address drew one box from the ORCID back across "ROBIN CHAWLA". Boxes now follow runs of
    consecutive words, so an unmarked word breaks the box.
    """
    boxes = []
    run = []
    for idx in indices:
        if run and idx == run[-1] + 1:
            run.append(idx)
        else:
            if run:
                boxes.extend(_boxes_for(stream, run))
            run = [idx]
    if run:
        boxes.extend(_boxes_for(stream, run))
    for pno, (x0, y0, x1, y1) in boxes:
        doc[pno].draw_rect(pymupdf.Rect(x0 - 0.6, y0 - 0.5, x1 + 0.6, y1 + 0.5),
                           color=None, fill=YELLOW, overlay=False)
    return len(boxes)


def _boxes_for(stream, run):
    by_line = {}
    order = []
    for idx in run:
        for pno, (x0, y0, x1, y1) in stream[idx][1]:
            key = (pno, round(y0, 1))
            if key not in by_line:
                by_line[key] = [x0, y0, x1, y1]
                order.append(key)
            else:
                b = by_line[key]
                b[0], b[1] = min(b[0], x0), min(b[1], y0)
                b[2], b[3] = max(b[2], x1), max(b[3], y1)
    return [(k[0], tuple(by_line[k])) for k in order]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    try:
        import pymupdf
    except ImportError:
        print("highlight_overlay: pymupdf is required", file=sys.stderr)
        return 2
    clean, out_pdf = Path(sys.argv[1]), Path(sys.argv[2])
    ref = sys.argv[3] if len(sys.argv) > 3 else "as-submitted"
    root = Path(__file__).resolve().parents[1]
    work = Path(sys.argv[4]) if len(sys.argv) > 4 else root / ".baseline_build"

    base = build_baseline(root, ref, work)
    if base is None:
        print(f"highlight_overlay: could not build the {ref} baseline, so there is nothing to "
              f"diff against", file=sys.stderr)
        return 1

    old = word_stream(pymupdf.open(base))
    doc = pymupdf.open(clean)
    new = word_stream(doc)
    ow = [t[0] for t in old]
    nw = [t[0] for t in new]
    changed, moved = changed_words(ow, nw)

    # Close short holes inside a marked passage. A word-level diff keeps whatever words a
    # rewritten sentence happens to reuse, so "a three-class BUY/HOLD/SELL output space" becoming
    # "a three-class BUY, HOLD, and SELL label set" leaves "three-class" unmarked in the middle
    # of the change -- speckled, and it reads as a mistake rather than as information. A gap of
    # up to GAP words bounded by marked words on both sides, on the same page, is closed. The
    # bound on both sides is what keeps this from reaching into text that genuinely did not
    # change: an unchanged paragraph has no marked word to anchor against.
    GAP = 10
    filled = 0
    marks = sorted(changed)
    for a, b in zip(marks, marks[1:]):
        if not (1 < b - a <= GAP + 1):
            continue
        if new[a][1][0][0] != new[b][1][0][0]:
            continue                      # different pages
        # and never across a change of type size. The author names are set far larger than the
        # address line beneath them; without this the ORCIDs added to that address reached up and
        # highlighted the authors' own names in the title block.
        size = new[a][2]
        # An unknown size (0) blocks the gap too. The author names in the title block come back
        # with no size, and treating unknown as "same" let the ORCIDs added to the address line
        # below reach up and highlight the authors' own names.
        if size == 0 or new[b][2] != size or any(new[i][2] != size for i in range(a + 1, b)):
            continue
        for i in range(a + 1, b):
            if i not in changed:
                changed.add(i)
                filled += 1

    boxes = paint(doc, new, sorted(changed), pymupdf)
    doc.save(out_pdf, garbage=3, deflate=True)
    pct = 100.0 * len(changed) / max(1, len(nw))
    print(f"   {len(changed)} of {len(nw)} words changed against {ref} ({pct:.1f}%) highlighted "
          f"in {boxes} runs; {moved} word(s) moved rather than changed, {filled} interior gap(s) "
          f"filled; {len(doc)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
